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


def get_backup_by_filename(file_name):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(load_sql("get_backup_by_filename"), (file_name,))
        return cur.fetchone()
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
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()
