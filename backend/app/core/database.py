import sqlite3
import hashlib
import logging

class DocumentRepository:
    def __init__(self, db_path="backend/data/database/tracker.db"):
        self.db_path = db_path
        self.logger = logging.getLogger("app.DocumentRepository")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            path TEXT UNIQUE NOT NULL,
            file_type TEXT CHECK(file_type IN ('pdf', 'image', 'txt')),
            file_hash TEXT UNIQUE,
            text_content TEXT,
            status TEXT CHECK(status IN ('parsed', 'ingested', 'error')) DEFAULT 'parsed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()
        conn.close()

    def compute_hash(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def is_processed(self, file_path: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM documents WHERE path = ?", (file_path,))
        result = cur.fetchone()
        conn.close()
        return result is not None

    def mark_as_processed(self, file_path: str, file_type: str, text_content: str):
        filename = file_path.split("/")[-1]
        file_hash = self.compute_hash(file_path)
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO documents (filename, path, file_type, file_hash, text_content, status)
        VALUES (?, ?, ?, ?, ?, 'parsed')
        """, (filename, file_path, file_type, file_hash, text_content))
        conn.commit()
        conn.close()
        self.logger.info(f"Fichier ajouté à la base : {filename}")

    def update_status(self, file_path: str, new_status: str):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        UPDATE documents
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE path = ?
        """, (new_status, file_path))
        conn.commit()
        conn.close()
