# modules/database.py
import sqlite3
from datetime import datetime

class HistoryDB:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS processed_files (file_id TEXT PRIMARY KEY, status TEXT)")
        self.conn.commit()

    def is_processed(self, file_id):
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM processed_files WHERE file_id=?", (file_id,))
        return cur.fetchone() is not None

    def log_success(self, file_id):
        self.conn.execute("INSERT OR REPLACE INTO processed_files VALUES (?, ?)", (file_id, "SUCCESS"))
        self.conn.commit()