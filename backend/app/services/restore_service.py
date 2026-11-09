
import gzip
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid

from pathlib import Path

import mysql.connector

from backend.app import config
from backend.app.db import get_conn, load_sql
from backend.app.repositories.backup_repo import (
    get_backup_by_filename,
    get_backup_by_id,
)
from backend.app.services.verification_service import verify_backup


logger = logging.getLogger("backupvault.restore")

CHUNK_SIZE = 1024 * 1024
RESTORE_TIMEOUT_SECONDS = 3600


# ============================================================
# DATABASE VALIDATION
# ============================================================

def _validate_database_identifier(database_name):
    """Validate a MySQL database identifier."""

    if (
        not database_name
        or len(database_name) > 64
        or not re.fullmatch(r"[A-Za-z0-9_]+", database_name)
    ):
        raise ValueError("Invalid MySQL database name.")


def _validate_target_database(target_database):
    """Prevent restoration into protected databases."""

    _validate_database_identifier(target_database)

    protected = {
        config.TARGET_DB_NAME.lower(),
        config.DB_NAME.lower(),
        "mysql",
        "information_schema",
        "performance_schema",
        "sys",
    }

    if target_database.lower() in protected:
        raise ValueError(
            f"Restoration into protected database "
            f"'{target_database}' is not allowed."
        )


def _connect_mysql(database=None):
    """Connect using the existing project configuration."""

    options = {
        "host": config.DB_HOST,
        "port": config.DB_PORT,
        "user": config.DB_USER,
        "password": config.DB_PASSWORD,
    }

    if database:
        options["database"] = database

    return mysql.connector.connect(**options)


# ============================================================
# BACKUP FILE VALIDATION
# ============================================================

def _get_backup_file(backup):
    """Ensure the backup exists inside the configured backup folder."""

    backup_dir = Path(config.BACKUP_DIR).resolve()
    backup_path = Path(backup["file_path"]).resolve()

    try:
        backup_path.relative_to(backup_dir)

    except ValueError:
        raise ValueError(
            "Backup file is outside the configured backup directory."
        )

    if not backup_path.is_file():
        raise FileNotFoundError(
            f"Backup file does not exist: {backup_path}"
        )

    if backup_path.suffix.lower() != ".gz":
        raise ValueError(
            "Selected backup is not a gzip file."
        )

    return backup_path


# ============================================================
# EMPTY TARGET DATABASE VALIDATION
# ============================================================

def _get_empty_target_database(target_database):
    """Require an existing database with no tables or views."""

    _validate_target_database(target_database)

    conn = _connect_mysql()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT SCHEMA_NAME
                FROM INFORMATION_SCHEMA.SCHEMATA
                WHERE SCHEMA_NAME = %s
                """,
                (target_database,),
            )

            if not cur.fetchone():
                raise ValueError(
                    f"Target database '{target_database}' does not exist."
                )

            safe_database = target_database.replace("`", "``")

            cur.execute(
                f"SHOW FULL TABLES FROM `{safe_database}`"
            )

            existing_objects = cur.fetchall()

            if existing_objects:
                names = [
                    str(row[0])
                    for row in existing_objects
                ]

                raise ValueError(
                    "Target database is not empty. "
                    f"Existing objects: {', '.join(names)}"
                )

        finally:
            cur.close()

    finally:
        conn.close()


# ============================================================
# MYSQL RESTORE ENGINE
# ============================================================

def _run_mysql_restore(backup_path, target_database):
    """Stream a decompressed SQL backup into MySQL."""

    _validate_target_database(target_database)

    mysql_exe = shutil.which("mysql")

    if not mysql_exe:
        raise FileNotFoundError(
            "mysql.exe was not found. Check your MySQL PATH."
        )

    command = [
        mysql_exe,
        "--protocol=TCP",
        "--host", config.DB_HOST,
        "--port", str(config.DB_PORT),
        "--user", config.DB_USER,
        "--database", target_database,
        "--default-character-set=utf8mb4",
        "--binary-mode",
    ]

    env = os.environ.copy()
    env["MYSQL_PWD"] = config.DB_PASSWORD

    with tempfile.TemporaryFile() as error_file:

        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=error_file,
            env=env,
        )

        try:
            with gzip.open(backup_path, "rb") as compressed_file:

                while True:
                    chunk = compressed_file.read(CHUNK_SIZE)

                    if not chunk:
                        break

                    process.stdin.write(chunk)

            process.stdin.close()

            return_code = process.wait(
                timeout=RESTORE_TIMEOUT_SECONDS
            )

        except BaseException:

            if process.poll() is None:
                process.kill()

            process.wait()

            if process.stdin and not process.stdin.closed:
                process.stdin.close()

            raise

        error_file.seek(0)

        error_message = error_file.read().decode(
            "utf-8",
            errors="replace",
        ).strip()

    if return_code != 0:
        raise RuntimeError(
            error_message[-4000:]
            if error_message
            else f"MySQL restore exited with code {return_code}."
        )


# ============================================================
# RESTORE METADATA
# ============================================================

def _update_restore_success(restore_id, duration):
    conn = get_conn()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                load_sql("update_restore_success"),
                (duration, restore_id),
            )

            conn.commit()

        finally:
            cur.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def _update_restore_failed(restore_id, duration, error_message):
    conn = get_conn()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                load_sql("update_restore_failed"),
                (
                    duration,
                    str(error_message)[:4000],
                    restore_id,
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
# NORMAL RESTORE
# ============================================================

def restore_backup(
    file_name,
    target_database,
    confirm=False,
    restored_by="cli",
):
    """
    Restore a verified backup into an existing empty database.

    Protected databases cannot be targets.
    Existing target data is never automatically deleted.
    """

    if not confirm:
        raise ValueError(
            "Restoration requires explicit confirmation."
        )

    _validate_target_database(target_database)

    backup = get_backup_by_filename(file_name)

    if not backup:
        raise ValueError(
            f"Backup not found: {file_name}"
        )

    if str(backup.get("status", "")).upper() != "SUCCESS":
        raise ValueError(
            "Only successful backups can be restored."
        )

    backup_path = _get_backup_file(backup)

    _get_empty_target_database(target_database)

    # Record the restoration attempt.
    conn = get_conn()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                load_sql("insert_restore"),
                (
                    backup["backup_id"],
                    target_database,
                    restored_by,
                ),
            )

            restore_id = cur.lastrowid
            conn.commit()

        finally:
            cur.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    started = time.monotonic()

    try:
        # Verify the backup before importing.
        verification = verify_backup(
            backup["backup_id"]
        )

        if verification.get("result") != "PASS":
            raise RuntimeError(
                "Backup verification failed. Restoration cancelled."
            )

        _run_mysql_restore(
            backup_path,
            target_database,
        )

        duration = int(
            time.monotonic() - started
        )

        _update_restore_success(
            restore_id,
            duration,
        )

        return {
            "restore_id": restore_id,
            "backup_id": backup["backup_id"],
            "file_name": file_name,
            "target_database": target_database,
            "status": "SUCCESS",
            "duration_seconds": duration,
        }

    except KeyboardInterrupt as exc:
        duration = int(time.monotonic() - started)

        _update_restore_failed(
            restore_id,
            duration,
            "Restoration interrupted by the user.",
        )

        raise

    except Exception as exc:
        duration = int(time.monotonic() - started)

        try:
            _update_restore_failed(
                restore_id,
                duration,
                str(exc),
            )

        except Exception as metadata_error:
            raise RuntimeError(
                f"Restore failed: {exc}. "
                f"Metadata update also failed: {metadata_error}"
            ) from metadata_error

        logger.exception(
            "Restore failed for backup %s into %s.",
            backup["backup_id"],
            target_database,
        )

        return {
            "restore_id": restore_id,
            "backup_id": backup["backup_id"],
            "file_name": file_name,
            "target_database": target_database,
            "status": "FAILED",
            "error": str(exc),
            "duration_seconds": duration,
        }


# ============================================================
# DATABASE TABLE STATISTICS
# ============================================================

def _get_database_table_stats(database_name):
    """
    Read table names, individual row counts and checksums.

    This function can read protected source databases.
    It does not permit restoration into them.
    """

    _validate_database_identifier(database_name)

    conn = _connect_mysql(database_name)

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

            table_names = [
                row[0]
                for row in cur.fetchall()
            ]

            if not table_names:
                raise RuntimeError(
                    f"No base tables found in {database_name}."
                )

            total_rows = 0
            row_counts = {}
            checksums = {}

            safe_database = database_name.replace("`", "``")

            for table_name in table_names:

                safe_table = table_name.replace("`", "``")

                # Count records.
                cur.execute(
                    f"SELECT COUNT(*) "
                    f"FROM `{safe_database}`.`{safe_table}`"
                )

                row_count = int(
                    cur.fetchone()[0]
                )

                total_rows += row_count
                row_counts[table_name] = row_count

                # Calculate MySQL table checksum.
                cur.execute(
                    f"CHECKSUM TABLE "
                    f"`{safe_database}`.`{safe_table}` EXTENDED"
                )

                checksum = cur.fetchone()[1]

                if checksum is None:
                    raise RuntimeError(
                        f"Could not calculate checksum for "
                        f"{database_name}.{table_name}."
                    )

                checksums[table_name] = int(checksum)

            return {
                "table_names": table_names,
                "row_count": total_rows,
                "row_counts": row_counts,
                "checksums": checksums,
            }

        finally:
            cur.close()

    finally:
        conn.close()


# ============================================================
# BACKUP-TIME MANIFEST
# ============================================================

def _get_backup_table_manifest(backup_id):
    """Retrieve the expected table data captured for a backup."""

    conn = get_conn()

    try:
        cur = conn.cursor(dictionary=True)

        try:
            cur.execute(
                load_sql("get_backup_table_manifest"),
                (backup_id,),
            )

            rows = cur.fetchall()

            if not rows:
                raise ValueError(
                    f"No data manifest exists for backup ID {backup_id}. "
                    "This backup predates manifest tracking. "
                    "Create a new backup before testing."
                )

            manifest = {}

            for row in rows:
                manifest[row["table_name"]] = {
                    "row_count": int(row["row_count"]),
                    "checksum": int(row["checksum"]),
                }

            return manifest

        finally:
            cur.close()

    finally:
        conn.close()


# ============================================================
# TEMPORARY TEST DATABASE
# ============================================================

def _create_test_database(database_name):
    """Create a uniquely named temporary database."""

    _validate_target_database(database_name)

    conn = _connect_mysql()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT SCHEMA_NAME
                FROM INFORMATION_SCHEMA.SCHEMATA
                WHERE SCHEMA_NAME = %s
                """,
                (database_name,),
            )

            if cur.fetchone():
                raise ValueError(
                    f"Temporary database already exists: {database_name}"
                )

            cur.execute(
                f"CREATE DATABASE `{database_name}`"
            )

        finally:
            cur.close()

    finally:
        conn.close()


def _drop_test_database(database_name):
    """Drop only databases created by our automated test."""

    if not re.fullmatch(
        r"backupvault_test_[0-9]+_[a-f0-9]{8}",
        database_name,
    ):
        raise ValueError(
            "Refusing to drop an unrecognised test database."
        )

    _validate_target_database(database_name)

    conn = _connect_mysql()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                f"DROP DATABASE IF EXISTS `{database_name}`"
            )

        finally:
            cur.close()

    finally:
        conn.close()


# ============================================================
# AUTOMATED TEST METADATA
# ============================================================

def _save_restore_test_result(
    test_id,
    row_count_original,
    row_count_restored,
    checksum_match,
    status,
    error_message,
):
    """Save the final automated test result."""

    conn = get_conn()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                load_sql("update_restore_test"),
                (
                    row_count_original,
                    row_count_restored,
                    checksum_match,
                    status,
                    str(error_message)[:4000]
                    if error_message
                    else None,
                    test_id,
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
# RESTORE TEST FAILURE ALERT
# ============================================================

def _create_restore_test_failure_alert(
    backup_id,
    test_id,
    test_database,
    error_message,
):
    """
    Record a RESTORE_TEST_FAILED alert and attempt email delivery.

    If email delivery fails, the alert remains pending with is_sent = 0.
    """

    alert_id = None

    try:
        from backend.app.services.alert_service import (
            create_alert,
            send_pending_alerts,
        )

        message = (
            f"Automated restore test {test_id} failed for "
            f"backup {backup_id}. "
            f"Test database: {test_database}. "
            f"Reason: {error_message or 'Unknown error'}"
        )

        alert_id = create_alert(
            alert_type="RESTORE_TEST_FAILED",
            message=message,
            backup_id=backup_id,
        )

        logger.warning(
            "Restore-test failure alert created: alert_id=%s",
            alert_id,
        )

        # Attempt email delivery immediately.
        # Failed delivery remains pending for scheduler retry.
        delivery = send_pending_alerts(limit=100)

        logger.info(
            "Restore-test alert delivery result: %s",
            delivery,
        )

    except Exception:
        logger.exception(
            "Could not create or deliver restore-test failure alert "
            "for backup %s, test %s.",
            backup_id,
            test_id,
        )

    return alert_id


# ============================================================
# AUTOMATED RESTORE TEST
# ============================================================

def test_restore_auto(backup_id):
    """
    Automatically test a backup by:

    1. Reading its saved backup-time manifest.
    2. Creating an isolated temporary database.
    3. Restoring the selected backup.
    4. Comparing recovered tables, row counts and checksums.
    5. Recording PASS or FAIL.
    6. Removing the temporary database.
    7. Creating and attempting delivery of a failure alert.
    """

    # --------------------------------------------------------
    # 1. Retrieve backup metadata.
    # --------------------------------------------------------

    backup = get_backup_by_id(backup_id)

    if not backup:
        raise ValueError(
            f"Backup ID {backup_id} was not found."
        )

    if str(backup.get("status", "")).upper() != "SUCCESS":
        raise ValueError(
            "Only successful backups can be tested."
        )

    _get_backup_file(backup)

    test_database = (
        f"backupvault_test_{backup_id}_{uuid.uuid4().hex[:8]}"
    )

    # --------------------------------------------------------
    # 2. Insert RUNNING test record.
    # --------------------------------------------------------

    conn = get_conn()

    try:
        cur = conn.cursor()

        try:
            cur.execute(
                load_sql("insert_restore_test"),
                (backup_id, test_database),
            )

            test_id = cur.lastrowid
            conn.commit()

        finally:
            cur.close()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    # --------------------------------------------------------
    # 3. Initialise test result values.
    # --------------------------------------------------------

    row_count_original = None
    row_count_restored = None
    checksum_match = None

    status = "FAIL"
    error_message = None

    database_created = False
    interrupted = False

    # --------------------------------------------------------
    # 4. Execute automated restore test.
    # --------------------------------------------------------

    try:
        # Read the manifest captured when this backup was created.
        expected_manifest = _get_backup_table_manifest(
            backup_id
        )

        expected_table_names = sorted(
            expected_manifest.keys()
        )

        expected_row_counts = {
            name: item["row_count"]
            for name, item in expected_manifest.items()
        }

        expected_checksums = {
            name: item["checksum"]
            for name, item in expected_manifest.items()
        }

        row_count_original = sum(
            expected_row_counts.values()
        )

        # Create isolated temporary database.
        _create_test_database(test_database)
        database_created = True

        # Restore selected backup.
        restore_result = restore_backup(
            backup["file_name"],
            test_database,
            confirm=True,
            restored_by="automated_test",
        )

        if restore_result.get("status") != "SUCCESS":
            raise RuntimeError(
                restore_result.get(
                    "error",
                    "Restoration into the test database failed.",
                )
            )

        # Read recovered database statistics.
        restored_stats = _get_database_table_stats(
            test_database
        )

        row_count_restored = restored_stats["row_count"]

        # Compare table names.
        same_tables = (
            expected_table_names
            == restored_stats["table_names"]
        )

        # Compare individual table row counts.
        same_row_counts = (
            expected_row_counts
            == restored_stats["row_counts"]
        )

        # Compare table checksums.
        checksum_match = (
            same_tables
            and expected_checksums
            == restored_stats["checksums"]
        )

        if (
            same_tables
            and same_row_counts
            and checksum_match
        ):
            status = "PASS"

        else:
            error_message = (
                "Restored database does not match its "
                "backup-time manifest. Check table names, "
                "row counts and checksums."
            )

    except KeyboardInterrupt:
        status = "FAIL"
        error_message = "Automated restore test was interrupted."
        interrupted = True

    except Exception as exc:
        status = "FAIL"
        error_message = str(exc)

        logger.exception(
            "Automated restore test failed for backup %s.",
            backup_id,
        )

    finally:
        # ----------------------------------------------------
        # 5. Clean up the temporary database.
        # ----------------------------------------------------

        if database_created:

            try:
                _drop_test_database(test_database)

            except Exception as cleanup_error:

                status = "FAIL"

                cleanup_message = (
                    "Temporary database cleanup failed: "
                    f"{cleanup_error}"
                )

                error_message = (
                    f"{error_message}; {cleanup_message}"
                    if error_message
                    else cleanup_message
                )

                logger.exception(
                    "Could not clean up test database %s.",
                    test_database,
                )

        # ----------------------------------------------------
        # 6. Save final test result.
        # ----------------------------------------------------

        metadata_error = None

        try:
            _save_restore_test_result(
                test_id,
                row_count_original,
                row_count_restored,
                checksum_match,
                status,
                error_message,
            )

        except Exception as exc:
            metadata_error = str(exc)

            status = "FAIL"

            error_message = (
                f"{error_message}; Metadata recording failed: "
                f"{metadata_error}"
                if error_message
                else f"Metadata recording failed: {metadata_error}"
            )

            logger.exception(
                "Could not save restore-test result %s.",
                test_id,
            )

        # ----------------------------------------------------
        # 7. Create failure alert after recording the result.
        # ----------------------------------------------------

        alert_id = None

        if status == "FAIL":
            alert_id = _create_restore_test_failure_alert(
                backup_id,
                test_id,
                test_database,
                error_message,
            )

    if interrupted:
        raise KeyboardInterrupt

    # --------------------------------------------------------
    # 8. Return final result.
    # --------------------------------------------------------

    return {
        "test_id": test_id,
        "backup_id": backup_id,
        "test_database": test_database,
        "row_count_original": row_count_original,
        "row_count_restored": row_count_restored,
        "checksum_match": checksum_match,
        "status": status,
        "error_message": error_message,
        "alert_id": alert_id,
    }
