import sqlite3
import hashlib
import logging
from typing import List, Tuple, Optional
import os 

class DocumentRepository:
    def __init__(self, db_path="backend/data/database/tracker.db"):
        ''''
            Classe responsable de la gestion des documents traités dans la base de données SQLite.
        '''
        self.db_path = db_path
        self.logger = logging.getLogger("app.DocumentRepository")
        self._init_db()

    def _init_db(self):
        '''
            Creation de la table documents si elle n'existe pas déjà
        '''
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
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

    def compute_hash(self, file_path: str) -> str:
        '''
            Calcule le hash SHA256 d'un fichier.
        '''
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def is_processed(self, file_path: str) -> bool:
        '''
            Vérifie si un document a déjà été traité
            params :
                file_path (str): chemin du fichier
                return : True si le document est déjà traité, False sinon
        '''
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM documents WHERE path = ?", (file_path,))
            result = cur.fetchone()
        return result is not None

    def mark_as_processed(self, file_path: str, file_type: str, text_content: str):
        '''
            Ajoute un document traité dans la base de données
            params :
                file_path (str): chemin du fichier
        
                file_type (str): type du fichier ('pdf', 'image', 'txt')
                text_content (str): contenu textuel extrait du fichier  

        '''
        filename = os.path.basename(file_path)
        file_hash = self.compute_hash(file_path)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO documents (filename, path, file_type, file_hash, text_content, status)
                VALUES (?, ?, ?, ?, ?, 'parsed')
            """, (filename, file_path, file_type, file_hash, text_content))
            conn.commit()


    def update_status(self, file_path: str, new_status: str):
        '''
            Mise à jour du statut d’un document
        '''
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE documents
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE path = ?
            """, (new_status, file_path))
            conn.commit()

    def get_documents(self, status: str = "parsed") -> List[Tuple[str, Optional[str]]]:
        '''
            Récupère les documents avec un statut spécifique
            params :
                status (str): statut des documents à récupérer
                return : liste des tuples (path, text_content)
        '''
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT path, text_content FROM documents WHERE status = ?", (status,))
            results = cur.fetchall()
        return results
