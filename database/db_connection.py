from __future__ import annotations
import os, sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv('OIL_MONITOR_DB', Path(__file__).resolve().parents[1] / 'data' / 'oil_monitor.db'))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
