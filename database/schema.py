from .db_connection import connection

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, salt TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT
);
CREATE TABLE IF NOT EXISTS organisations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,name)
);
CREATE TABLE IF NOT EXISTS daily_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT, organisation_id INTEGER NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
 record_date TEXT NOT NULL, total_cost REAL NOT NULL, litres REAL NOT NULL, oil_rate REAL NOT NULL,
 oil_cost REAL NOT NULL, oil_cost_pct REAL NOT NULL, employee_cost REAL NOT NULL,
 transportation_cost REAL NOT NULL, other_costs REAL NOT NULL,
 production_output REAL, operating_hours REAL, number_of_employees REAL, number_of_vehicles REAL,
 distance_travelled REAL, electricity_consumption REAL,
 source_file TEXT, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(organisation_id,record_date)
);
CREATE INDEX IF NOT EXISTS idx_records_org_date ON daily_records(organisation_id,record_date);
CREATE TABLE IF NOT EXISTS import_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 file_name TEXT NOT NULL, organisation_name TEXT, imported_count INTEGER NOT NULL DEFAULT 0,
 skipped_count INTEGER NOT NULL DEFAULT 0, error_count INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL, details TEXT, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS report_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 report_name TEXT NOT NULL, generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
'''

def init_db():
    with connection() as conn:
        conn.executescript(SCHEMA)
