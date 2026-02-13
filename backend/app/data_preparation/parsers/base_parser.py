from abc import ABC, abstractmethod
from typing import List, Optional
import logging
import os
import re
import hashlib

from backend.app.core.database import DocumentRepository


class BaseParser(ABC):
    """
    Parseur abstrait: extrait du texte et l'insère dans CosmosDB.
    Ajouts:
      - id stable (hash path)
      - title (depuis filename)
      - kb (optionnel)
      - normalisation texte (clean + option markdown headings)
    """

    def __init__(self, kb: str = "who"):
        self.logger = logging.getLogger(self.__class__.__name__)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        self.source_dir = os.path.join(base_dir, "data", "raw")
        self.repository = DocumentRepository()
        self.kb = kb

    @abstractmethod
    def extract_text(self, file_path: str, **kwargs) -> str:
        pass

    # ---------- helpers ----------

    @staticmethod
    def _make_doc_id(path: str) -> str:
        # id stable même si tu changes filename; évite collisions
        return hashlib.md5(path.encode("utf-8")).hexdigest()

    @staticmethod
    def _title_from_filename(filename: str) -> str:
        name = os.path.splitext(filename)[0]
        name = name.replace("_", " ").replace("-", " ").strip()
        return re.sub(r"\s+", " ", name)

    @staticmethod
    def _basic_clean(text: str) -> str:
        text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        # supprime espaces inutiles
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text.strip()

    def normalize_to_markdown(self, text: str) -> str:
        """
        Option: ici tu pourras convertir tes docs WHO en format # Overview, # Symptoms, etc.
        Pour le moment, on fait juste un clean.
        """
        return self._basic_clean(text)

    # ---------- main ----------

    def process_file(self, file_paths: Optional[List[str]] = None, **kwargs):
        if not file_paths:
            self.logger.warning("Aucun fichier à traiter.")
            return 0

        inserted = 0

        for path in file_paths:
            filename = os.path.basename(path)
            file_ext = os.path.splitext(path)[1].lower()
            file_type = file_ext.replace(".", "")

            # ✅ id stable
            doc_id = self._make_doc_id(path)

            # Vérifie si le document existe déjà (mieux que path seul)
            if self.repository.get_document_by_id(doc_id, file_type=file_type):
                self.logger.debug(f"⏭️ Doc déjà présent, ignoré : {path}")
                continue

            try:
                raw_text = self.extract_text(path, **kwargs)
                text = self.normalize_to_markdown(raw_text)
                print(f"✅ Doc traité: {text[:100]}... (id={doc_id}, type={file_type})")
                if text:
                    title = self._title_from_filename(filename)
                    document = {
                        "id": doc_id,
                        "filename": filename,
                        "title": title,
                        "path": path,
                        "file_type": file_type,
                        "text_content": text,
                        "status": "parsed",
                        "kb": self.kb,
                    }
                    self.repository.insert_document(document)
                    inserted += 1
                    self.logger.info(f"✅ Document ajouté : {title} ({filename})")
                else:
                    self.logger.warning(f"⚠️ Aucun texte extrait de {path}")

            except Exception as e:
                self.logger.exception(f"Erreur lors du traitement de {path}: {e}")

        self.logger.info(f"📦 Traitement terminé: {inserted}/{len(file_paths)} docs insérés.")
        return inserted
