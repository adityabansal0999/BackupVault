# creates one backup: mysqldump -> gzip file on disk -> metadata row in backupvault_meta
# dump gets streamed straight into gzip so a big db never has to fit in ram
# we use MYSQL_PWD env var instead of -pPASSWORD because that flag shows the password in the process list
import gzip
import hashlib
import os
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from backend.app.config import ALERT_EMAIL, BACKUP_DIR, DB_HOST, DB_PASSWORD, DB_PORT, DB_USER, TARGET_DB_NAME
from backend.app.db import get_conn, load_sql
from backend.app.repositories import backup_repo

DUMP_TIMEOUT_SECONDS = 3600


def _run_mysqldump(database_name, output_path):
    # returns (ok, error_text). writes to <file>.part first, renames only on success
    cmd = ["mysqldump", f"-h{DB_HOST}", f"-P{DB_PORT}", f"-u{DB_USER}", "--single-transaction", "--quick", "--routines", "--triggers", database_name]
    env = os.environ.copy()
    env["MYSQL_PWD"] = DB_PASSWORD
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    tmp_path = output_path + ".part"
    try:
        with tempfile.TemporaryFile() as err_file:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err_file, env=env)
            timer = threading.Timer(DUMP_TIMEOUT_SECONDS, proc.kill)
            timer.start()
            try:
                with gzip.open(tmp_path, "wb") as gz:
                    shutil.copyfileobj(proc.stdout, gz, 1024 * 1024)
                proc.wait()
            finally:
                timer.cancel()
            if proc.returncode != 0:
                err_file.seek(0)
                raise RuntimeError(err_file.read().decode(errors="replace")[:500] or f"mysqldump exited with code {proc.returncode}")
        os.replace(tmp_path, output_path)
        return True, ""
    except FileNotFoundError:
        return False, "mysqldump not found (install MySQL client tools / add to PATH)"
    except Exception as e:
        return False, str(e)[:500]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)  # dont leave half written backups behind


def _sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_backup(database_name=None, created_by="scheduler"):
    dbname = database_name or TARGET_DB_NAME
    started = datetime.now()
    file_name = f"backup_{started.strftime('%Y_%m_%d_%H%M%S')}.sql.gz"
    file_path = os.path.join(BACKUP_DIR, file_name)

    # row first with IN_PROGRESS, so even a crash leaves a trace in the history
    backup_id = backup_repo.insert_backup(file_name, file_path, 0, None, dbname, "IN_PROGRESS", started)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(load_sql("update_backup_created_by"), (created_by, backup_id))
    conn.commit()
    cur.close()
    conn.close()

    # do the actual dump
    ok, err = _run_mysqldump(dbname, file_path)
    completed = datetime.now()
    duration = int((completed - started).total_seconds())

    # record the result
    conn = get_conn()
    cur = conn.cursor()
    if ok:
        size = os.path.getsize(file_path)
        cur.execute(load_sql("update_backup_success"), (size, size, _sha256_of_file(file_path), completed, duration, backup_id))
        conn.commit()
        cur.close()
        conn.close()
        return {"backup_id": backup_id, "file_name": file_name, "status": "SUCCESS", "size": size}

    cur.execute(load_sql("update_backup_failed"), (completed, duration, err, backup_id))
    cur.execute(load_sql("insert_alert_backup_failed"), (backup_id, f"Backup failed at {started:%H:%M}: {err[:200]}", ALERT_EMAIL, completed))
    conn.commit()
    cur.close()
    conn.close()
    return {"backup_id": backup_id, "file_name": file_name, "status": "FAILED", "error": err}
