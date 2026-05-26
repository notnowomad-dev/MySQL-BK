import os
import shutil
import sqlite3
from typing import List, Optional
from models.job import BackupJob

DB_PATH = os.path.join(os.path.expanduser("~"), ".database_backup_scheduler", "jobs.db")
_OLD_DB_PATH = os.path.join(os.path.expanduser("~"), ".mysql_backup_scheduler", "jobs.db")

# Migrate from old folder name on first run after rename
if os.path.exists(_OLD_DB_PATH) and not os.path.exists(DB_PATH):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    shutil.copy2(_OLD_DB_PATH, DB_PATH)


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id                TEXT PRIMARY KEY,
                    name              TEXT NOT NULL,
                    host              TEXT NOT NULL,
                    port              INTEGER NOT NULL,
                    username          TEXT NOT NULL,
                    password          TEXT NOT NULL,
                    databases         TEXT NOT NULL,
                    tables            TEXT NOT NULL,
                    schedule_type     TEXT NOT NULL,
                    schedule_time     TEXT NOT NULL,
                    schedule_weekday  INTEGER NOT NULL,
                    schedule_day      INTEGER NOT NULL,
                    schedule_cron     TEXT NOT NULL,
                    output_dir        TEXT NOT NULL,
                    output_type       TEXT NOT NULL,
                    use_zip           INTEGER NOT NULL,
                    zip_password      TEXT NOT NULL,
                    zip_path          TEXT NOT NULL,
                    enabled           INTEGER NOT NULL,
                    last_run          TEXT,
                    last_status       TEXT NOT NULL DEFAULT '',
                    mysqldump_path    TEXT NOT NULL DEFAULT 'mysqldump',
                    hex_blob          INTEGER NOT NULL DEFAULT 1,
                    db_type           TEXT NOT NULL DEFAULT 'mysql',
                    mssql_driver          TEXT NOT NULL DEFAULT 'ODBC Driver 17 for SQL Server',
                    windows_auth          INTEGER NOT NULL DEFAULT 0,
                    mssql_backup_format   TEXT NOT NULL DEFAULT 'sql',
                    alt_dest_enabled      INTEGER NOT NULL DEFAULT 0,
                    alt_dest              TEXT NOT NULL DEFAULT '',
                    alt_dest_user         TEXT NOT NULL DEFAULT '',
                    alt_dest_pass         TEXT NOT NULL DEFAULT '',
                    retention_days        INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id     TEXT NOT NULL,
                    job_name   TEXT NOT NULL,
                    timestamp  TEXT NOT NULL,
                    status     TEXT NOT NULL,
                    message    TEXT NOT NULL
                )
            """)
            # Add columns for existing installs (migrations)
            for ddl in [
                "ALTER TABLE jobs ADD COLUMN mysqldump_path TEXT NOT NULL DEFAULT 'mysqldump'",
                "ALTER TABLE jobs ADD COLUMN hex_blob INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE jobs ADD COLUMN db_type TEXT NOT NULL DEFAULT 'mysql'",
                "ALTER TABLE jobs ADD COLUMN mssql_driver TEXT NOT NULL DEFAULT 'ODBC Driver 17 for SQL Server'",
                "ALTER TABLE jobs ADD COLUMN windows_auth INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE jobs ADD COLUMN mssql_backup_format TEXT NOT NULL DEFAULT 'sql'",
                "ALTER TABLE jobs ADD COLUMN alt_dest_enabled INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE jobs ADD COLUMN alt_dest TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE jobs ADD COLUMN alt_dest_user TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE jobs ADD COLUMN alt_dest_pass TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE jobs ADD COLUMN retention_days INTEGER NOT NULL DEFAULT 0",
            ]:
                try:
                    conn.execute(ddl)
                except Exception:
                    pass
            conn.commit()

    # ------------------------------------------------------------------ jobs --

    def save_job(self, job: BackupJob):
        d = job.to_dict()
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO jobs VALUES (
                    :id, :name, :host, :port, :username, :password,
                    :databases, :tables, :schedule_type, :schedule_time,
                    :schedule_weekday, :schedule_day, :schedule_cron,
                    :output_dir, :output_type, :use_zip, :zip_password,
                    :zip_path, :enabled, :last_run, :last_status, :mysqldump_path,
                    :hex_blob, :db_type, :mssql_driver, :windows_auth, :mssql_backup_format,
                    :alt_dest_enabled, :alt_dest, :alt_dest_user, :alt_dest_pass,
                    :retention_days
                )
            """, d)
            conn.commit()

    def delete_job(self, job_id: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()

    def get_all_jobs(self) -> List[BackupJob]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY name").fetchall()
            return [BackupJob.from_dict(dict(row)) for row in rows]

    def get_job(self, job_id: str) -> Optional[BackupJob]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return BackupJob.from_dict(dict(row)) if row else None

    def update_job_status(self, job_id: str, last_run: str, status: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET last_run = ?, last_status = ? WHERE id = ?",
                (last_run, status, job_id),
            )
            conn.commit()

    # ------------------------------------------------------------------ logs --

    def add_log(self, job_id: str, job_name: str, timestamp: str, status: str, message: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO logs (job_id, job_name, timestamp, status, message) VALUES (?, ?, ?, ?, ?)",
                (job_id, job_name, timestamp, status, message),
            )
            conn.commit()

    def get_logs(self, job_id: str = None, limit: int = 100) -> list:
        with self._connect() as conn:
            if job_id:
                rows = conn.execute(
                    "SELECT * FROM logs WHERE job_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (job_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(row) for row in rows]

    def clear_logs(self, job_id: str = None):
        with self._connect() as conn:
            if job_id:
                conn.execute("DELETE FROM logs WHERE job_id = ?", (job_id,))
            else:
                conn.execute("DELETE FROM logs")
            conn.commit()
