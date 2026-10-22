from backend.app.db import get_conn, load_sql

def insert_backup(file_name, file_path, file_size, checksum, database_name, status, created_at):
    conn = get_conn()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(load_sql("insert_backup"), (file_name, file_path, file_size, checksum, database_name, status, created_at))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        if cur:
            cur.close()
        conn.close()

def list_backups(limit=50, offset=0, date_from=None, date_to=None):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        params = {"limit": limit, "offset": offset, "date_from": date_from, "date_to": date_to}
        cur.execute(load_sql("list_backups"), params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def get_backup_by_id(backup_id):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(load_sql("get_backup_by_id"), (backup_id,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()

def get_backup_by_filename(file_name):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(load_sql("get_backup_by_filename"), (file_name,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()

def get_verifications(backup_id, limit=20):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(load_sql("get_verifications"), (backup_id, limit))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def get_history(limit=20, offset=0, date_from=None, date_to=None):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(load_sql("get_history"), {"limit": limit, "offset": offset, "date_from": date_from, "date_to": date_to})
        rows = cur.fetchall()
        cur.execute(load_sql("get_history_count"), {"date_from": date_from, "date_to": date_to})
        total = cur.fetchone()["total"]
        cur.execute(load_sql("get_history_storage"), {"date_from": date_from, "date_to": date_to})
        storage = cur.fetchone()["total_storage"]
        return {"items": rows, "total": total, "total_storage": storage or 0, "limit": limit, "offset": offset}
    finally:
        cur.close()
        conn.close()

def update_verification_status(backup_id, result):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(load_sql("update_verification_status"), (result, backup_id))
        conn.commit()
    finally:
        cur.close()
        conn.close()

def get_status_summary():
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(load_sql("get_status_summary"))
        row = cur.fetchone()
        return row or {
            "last_file": None,
            "last_status": None,
            "last_time": None,
            "total_storage": 0,
            "success_rate": None,
            "total": 0,
            "next_run_at": None,
            "cron_expression": "0 2 * * *"
        }
    finally:
        cur.close()
        conn.close()
