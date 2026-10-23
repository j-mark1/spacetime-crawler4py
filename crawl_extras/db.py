'''
SQLite file for crawl stats
'''
import os
import sqlite3
import threading
from contextlib import contextmanager

DB_PATH = "crawl_stats.db"

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS pages (page_key TEXT PRIMARY KEY, url TEXT, label TEXT, word_count INTEGER)",
    "CREATE TABLE IF NOT EXISTS words (word TEXT PRIMARY KEY, count INTEGER)",
    "CREATE TABLE IF NOT EXISTS robots (host TEXT PRIMARY KEY, robots_txt TEXT)",
)

_lock = threading.Lock()
_conn = None

# called once from launch.py; --restart starts the stats over, like the frontier does
def open_db(restart, path=DB_PATH):
    global _conn
    if _conn is not None:
        _conn.close()
    if restart:
        for leftover in (path, path + "-journal"):
            if os.path.exists(leftover):
                os.remove(leftover)
    _conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    for statement in _SCHEMA:
        _conn.execute(statement)

# with db.transaction() as conn: ...   everything in the block is saved, or nothing is
@contextmanager
def transaction():
    with _lock:
        _conn.execute("BEGIN")
        try:
            yield _conn
            _conn.execute("COMMIT")
        except BaseException:
            _conn.execute("ROLLBACK")
            raise