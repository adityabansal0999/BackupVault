
import gzip
import hashlib
import logging
import mysql.connector
import os
import shutil
import subprocess
import tempfile
import threading

from datetime import datetime
from pathlib import Path

from backend.app.config import (
    ALERT_EMAIL,
    BACKUP_DIR,
    DB_HOST,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    TARGET_DB_NAME,
)
from backend.app.db import get_conn, load_sql
from backend.app.repositories import backup_repo


logger = logging.getLogger("backupvault.backup")

DUMP_TIMEOUT_SECONDS = 3600
COPY_BUFFER_SIZE = 1024 * 1024


# ============================================================
# BACKUP CONCURRENCY CONTROL
# ============================================================

def _backup_lock_name(database_name):
    digest = hashlib.sha256(
        database_name.encode("utf-8")
    ).hexdigest()[:32]

    return "backupvault_backup_" + digest


def _acquire_backup_lock(database_name):
    lock_name = _backup_lock_name(database_name)
    conn = get_conn()
    cur = None

    try:
        cur = conn.cursor()
        cur.execute("SELECT GET_LOCK(%s, 0)", (lock_name,))
        row = cur.fetchone()

        acquired = bool(row and row[0] == 1)

    except Exception:
        conn.close()
        raise

    finally:
        if cur:
            cur.close()

    if not acquired:
        conn.close()
        return None, lock_name

    return conn, lock_name


def _release_backup_lock(conn, lock_name):
    if conn is None:
        return

    cur = None

    try:
        cur = conn.cursor()
        cur.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
        cur.fetchone()

    except Exception:
        logger.exception(
            "Could not release backup lock: %s",
            lock_name,
        )

    finally:
        if cur:
            cur.close()

        conn.close()


# ============================================================
# MYSQLDUMP AND GZIP
# ============================================================

def _run_mysqldump(database_name, output_path):
    """Export a database and stream output into gzip."""

    cmd = [
        "mysqldump",
        f"-h{DB_HOST}",
        f"-P{DB_PORT}",
        f"-u{DB_USER}",
        "--single-transaction",
        "--quick",
        "--routines",
        "--triggers",
        database_name,
    ]

    env = os.environ.copy()
    env["MYSQL_PWD"] = DB_PASSWORD

    Path(BACKUP_DIR).mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp_path = output_path + ".part"

    proc = None
    timer = None
    timed_out = threading.Event()

    def kill_on_timeout():
        timed_out.set()

        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass

    try:
        with tempfile.TemporaryFile() as err_file:

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=err_file,
                    env=env,
                )

            except FileNotFoundError:
                raise RuntimeError(
                    "mysqldump not found. "
                    "Check MySQL client installation and PATH."
                ) from None

            timer = threading.Timer(
                DUMP_TIMEOUT_SECONDS,
                kill_on_timeout,
            )

            timer.daemon = True
            timer.start()

            try:
                if proc.stdout is None:
                    raise RuntimeError(
                        "Could not read mysqldump output."
                    )

                with gzip.open(tmp_path, "wb") as gz_file:
                    shutil.copyfileobj(
                        proc.stdout,
                        gz_file,
                        COPY_BUFFER_SIZE,
                    )

                proc.wait()

            finally:
                if timer:
                    timer.cancel()

                if proc.stdout and not proc.stdout.closed:
                    proc.stdout.close()

                if proc.poll() is None:
                    try:
                        proc.kill()
                    except OSError:
                        pass

                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

            if timed_out.is_set():
                raise TimeoutError(
                    f"mysqldump exceeded "
                    f"{DUMP_TIMEOUT_SECONDS} seconds."
                )

            if proc.returncode != 0:
                err_file.seek(0)

                error = err_file.read().decode(
                    errors="replace"
                ).strip()

                raise RuntimeError(
                    error[:500]
                    or f"mysqldump exited with code {proc.returncode}"
                )

        os.replace(tmp_path, output_path)

        return True, ""

    except Exception as exc:
        logger.exception(
            "mysqldump failed for database %s",
            database_name,
        )

        return False, str(exc)[:500]

    finally:
        if timer:
            timer.cancel()

        if proc is not None:
            if proc.poll() is None:
                try:
                    proc.kill()
                except OSError:
                    pass

            if proc.stdout and not proc.stdout.closed:
                proc.stdout.close()

        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                logger.exception(
                    "Could not remove temporary file: %s",
                    tmp_path,
                )


# ============================================================
# SHA-256
# ============================================================

def _sha256_of_file(path):
    """Calculate SHA-256 of the complete compressed backup."""

    hasher = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(
            lambda: file.read(COPY_BUFFER_SIZE),
            b"",
        ):
            hasher.update(chunk)

    return hasher.hexdigest()


# ============================================================
# BACKUP-TIME DATA MANIFEST
# ============================================================

def _read_database_manifest(database_name):
    """Capture table names, row counts and table checksums."""

    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=database_name,
    )

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
                """,
                (database_name,),
            )

            tables = [
                row[0] for row in cur.fetchall()
            ]

            if not tables:
                raise RuntimeError(
                    f"No tables found in database {database_name}."
                )

            manifest = []
            safe_database = database_name.replace("`", "``")

            for table_name in tables:

                safe_table = table_name.replace("`", "``")

                cur.execute(
                    f"SELECT COUNT(*) "
                    f"FROM `{safe_database}`.`{safe_table}`"
                )

                row_count = int(cur.fetchone()[0])

                cur.execute(
                    f"CHECKSUM TABLE "
                    f"`{safe_database}`.`{safe_table}` EXTENDED"
                )

                checksum = cur.fetchone()[1]

                if checksum is None:
                    raise RuntimeError(
                        f"Could not calculate checksum for {table_name}."
                    )

                manifest.append({
                    "table_name": table_name,
                    "row_count": row_count,
                    "checksum": int(checksum),
                })

            return manifest

        finally:
            cur.close()

    finally:
        conn.close()


def _save_backup_manifest(backup_id, manifest):
    """Save expected table information in metadata MySQL."""

    conn = get_conn()

    try:
        cur = conn.cursor()

        try:
            for item in manifest:
                cur.execute(
                    load_sql("insert_backup_table_manifest"),
                    (
                        backup_id,
                        item["table_name"],
                        item["row_count"],
                        item["checksum"],
                    ),
                )

            conn.commit()

        finally:
            cur.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# BACKUP CREATOR METADATA
# ============================================================

def _set_backup_creator(backup_id, created_by):
    conn = get_conn()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            load_sql("update_backup_created_by"),
            (created_by, backup_id),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        if cur:
            cur.close()

        conn.close()


# ============================================================
# BACKUP SUCCESS METADATA
# ============================================================

def _record_backup_success(
    backup_id,
    size,
    checksum,
    completed,
    duration,
):
    conn = get_conn()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            load_sql("update_backup_success"),
            (
                size,
                size,
                checksum,
                completed,
                duration,
                backup_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        if cur:
            cur.close()

        conn.close()


# ============================================================
# BACKUP FAILURE AND ALERT RECORDING
# ============================================================

def _record_backup_failure(backup_id, started, error):
    """Record failure and separately attempt alert insertion."""

    completed = datetime.now()

    duration = max(
        0,
        int((completed - started).total_seconds()),
    )

    conn = get_conn()
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            load_sql("update_backup_failed"),
            (
                completed,
                duration,
                error[:500],
                backup_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        if cur:
            cur.close()

        conn.close()

    conn = None
    cur = None

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            load_sql("insert_alert_backup_failed"),
            (
                backup_id,
                f"Backup failed at {started:%H:%M}: {error[:200]}",
                ALERT_EMAIL,
                completed,
            ),
        )

        conn.commit()

    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass

        logger.exception(
            "Backup %s was marked FAILED, but its alert "
            "could not be recorded.",
            backup_id,
        )

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()


# ============================================================
# AUTOMATIC RESTORE TEST TRIGGER
# ============================================================

def _run_automatic_restore_test(backup_id):
    """
    Test a backup immediately after successful creation.

    Restore-test failure must not change the backup's SUCCESS status.
    """

    try:
        from backend.app.services.restore_service import test_restore_auto

        result = test_restore_auto(backup_id)

        if result.get("status") == "PASS":
            logger.info(
                "Automatic restore test PASSED for backup %s.",
                backup_id,
            )

        else:
            logger.error(
                "Automatic restore test FAILED for backup %s: %s",
                backup_id,
                result,
            )

        return result

    except Exception as exc:
        logger.exception(
            "Automatic restore test could not complete for backup %s.",
            backup_id,
        )

        return {
            "status": "ERROR",
            "error": str(exc)[:500],
        }


# ============================================================
# MAIN BACKUP SERVICE
# ============================================================

def create_backup(database_name=None, created_by="scheduler"):
    """Create a full compressed backup, verify its manifest,
    and automatically test restoration after successful creation."""

    dbname = database_name or TARGET_DB_NAME

    started = datetime.now()

    file_name = (
        f"backup_{started.strftime('%Y_%m_%d_%H%M%S_%f')}.sql.gz"
    )

    file_path = os.path.join(BACKUP_DIR, file_name)

    backup_id = None
    lock_conn = None
    lock_name = None

    backup_success_recorded = False

    try:
        # 1. Acquire backup lock.
        lock_conn, lock_name = _acquire_backup_lock(dbname)

        if lock_conn is None:
            return {
                "backup_id": None,
                "file_name": None,
                "status": "FAILED",
                "error": (
                    f"Another backup for database '{dbname}' "
                    "is already running."
                ),
            }

        # 2. Insert initial metadata record.
        backup_id = backup_repo.insert_backup(
            file_name,
            file_path,
            0,
            None,
            dbname,
            "IN_PROGRESS",
            started,
        )

        _set_backup_creator(
            backup_id,
            created_by,
        )

        # 3. Capture source data before backup.
        manifest_before = _read_database_manifest(dbname)

        # 4. Execute mysqldump and gzip.
        ok, error = _run_mysqldump(
            dbname,
            file_path,
        )

        if not ok:
            raise RuntimeError(error)

        # 5. Capture source data after backup.
        manifest_after = _read_database_manifest(dbname)

        # Reject an inconsistent manifest.
        if manifest_before != manifest_after:
            raise RuntimeError(
                "Source database changed during backup. "
                "Manifest capture was rejected."
            )

        # 6. Save backup-time manifest.
        _save_backup_manifest(
            backup_id,
            manifest_before,
        )

        # 7. Calculate compressed size and SHA-256.
        size = os.path.getsize(file_path)
        checksum = _sha256_of_file(file_path)

        completed = datetime.now()

        duration = max(
            0,
            int((completed - started).total_seconds()),
        )

        # 8. Record backup SUCCESS.
        _record_backup_success(
            backup_id,
            size,
            checksum,
            completed,
            duration,
        )

        backup_success_recorded = True

        logger.info(
            "Backup %s completed successfully for %s.",
            backup_id,
            dbname,
        )

        # 9. Automatically test the successful backup.
        # A restore-test failure must not turn this backup into FAILED.
        restore_test_result = _run_automatic_restore_test(
            backup_id
        )

        return {
            "backup_id": backup_id,
            "file_name": file_name,
            "status": "SUCCESS",
            "size": size,
            "restore_test": restore_test_result,
        }

    except KeyboardInterrupt:

        # Never mark a completed backup FAILED because its
        # subsequent restore test was interrupted.
        if backup_id is not None and not backup_success_recorded:
            try:
                _record_backup_failure(
                    backup_id,
                    started,
                    "Backup interrupted by the user.",
                )

            except Exception:
                logger.exception(
                    "Could not record interrupted backup %s.",
                    backup_id,
                )

        raise

    except Exception as exc:

        # Protect a backup already marked SUCCESS.
        if backup_success_recorded:
            logger.exception(
                "An error occurred after backup %s was marked SUCCESS.",
                backup_id,
            )

            return {
                "backup_id": backup_id,
                "file_name": file_name,
                "status": "SUCCESS",
                "error": (
                    "Backup completed, but a later operation "
                    f"encountered an error: {str(exc)[:400]}"
                ),
            }

        error = str(exc)[:500] or type(exc).__name__

        logger.exception(
            "Backup failed for database %s.",
            dbname,
        )

        if backup_id is not None:
            try:
                _record_backup_failure(
                    backup_id,
                    started,
                    error,
                )

            except Exception as record_error:
                logger.exception(
                    "Could not update failed backup metadata."
                )

                error = (
                    error
                    + " | Metadata update also failed: "
                    + str(record_error)[:200]
                )

        return {
            "backup_id": backup_id,
            "file_name": file_name,
            "status": "FAILED",
            "error": error,
        }

    finally:
        # Always release the database-wide backup lock.
        if lock_conn is not None:
            _release_backup_lock(
                lock_conn,
                lock_name,
            )
