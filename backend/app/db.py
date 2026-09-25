# small MySQL connection pool for the metadata db (backupvault_meta)
# also has a helper to load .sql files from sql/queries so we dont
# hardcode sql strings inside the python files
import os
import mysql.connector.pooling
from backend.app import config

_pool = None

SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "sql", "queries")

_sql_cache = {}


def get_pool():
    global _pool
    if _pool is None:
        _pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="backupvault_pool",
            pool_size=5,
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            autocommit=False,
        )
    return _pool


def get_conn():
    return get_pool().get_connection()


def load_sql(name):
    # name is the file name without .sql, eg "insert_backup"
    if name in _sql_cache:
        return _sql_cache[name]
    path = os.path.join(SQL_DIR, name + ".sql")
    with open(path, "r") as f:
        query = f.read()
    _sql_cache[name] = query
    return query
