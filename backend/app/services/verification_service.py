import os
import gzip
import hashlib
from datetime import datetime
from backend.app.db import get_conn, load_sql
from backend.app.repositories import backup_repo

def _check_gzip_valid(path):
    try:
        with gzip.open(path, 'rb') as f:
            f.read(1)
        return True
    except:
        return False

def _checksum_match(path, stored):
    if not stored:
        return None
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest() == stored
    except:
        return False

def verify_backup(backup_id):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(load_sql("get_backup_by_id"), (backup_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return {"result": "FAIL", "error": "backup not found"}
        path = row["file_path"]
        file_exists = os.path.exists(path)
        file_size_ok = False
        gzip_valid = False
        checksum_ok = None
        if file_exists:
            try:
                size = os.path.getsize(path)
                file_size_ok = size > 1024
            except:
                file_size_ok = False
            gzip_valid = _check_gzip_valid(path)
            checksum_ok = _checksum_match(path, row["checksum_sha256"])
        result = "PASS" if (file_exists and file_size_ok and gzip_valid and (checksum_ok is None or checksum_ok)) else "FAIL"
        checked_at = datetime.now()
        cur = conn.cursor()
        cur.execute(load_sql("insert_verification"), (backup_id, checked_at, result, file_exists, file_size_ok, gzip_valid, checksum_ok))
        conn.commit()
        cur.execute(load_sql("update_verification_status"), (result, backup_id))
        conn.commit()
        cur.close()
        return {
            "backup_id": backup_id,
            "result": result,
            "file_exists": file_exists,
            "file_size_ok": file_size_ok,
            "gzip_valid": gzip_valid,
            "checksum_match": checksum_ok,
            "checked_at": checked_at.isoformat()
        }
    finally:
        conn.close()
