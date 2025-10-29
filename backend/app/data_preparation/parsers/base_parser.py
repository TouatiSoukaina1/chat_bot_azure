from abc import ABC, abstractmethod
from typing import List, Optional
import logging
import os
from backend.app.core.database import DocumentRepository


class BaseParser(ABC):
    """
    Classe abstraite pour les parseurs de données (texte, image, PDF).
    Gère :
      - La journalisation
      - L’insertion des documents dans la base CosmosDB
      - L’appel de la méthode extract_text() propre à chaque type
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        self.source_dir = os.path.join(base_dir, "data", "raw")
        self.repository = DocumentRepository()

    @abstractmethod
    def extract_text(self, file_path: str, **kwargs) -> str:
        """Méthode à implémenter dans chaque parseur (PDF, image, texte)."""
        pass

    def process_file(self, file_paths: Optional[List[str]] = None, **kwargs):
        """
        Traite une liste de fichiers et insère les résultats dans CosmosDB.
        (Les fichiers sont déjà filtrés par le pipeline principal)
        """
        if not file_paths:
            self.logger.warning("Aucun fichier à traiter.")
            return

        for path in file_paths:
            filename = os.path.basename(path)
            file_ext = os.path.splitext(path)[1].lower()

            # Vérifie si le document est déjà dans la base
            if self.repository.is_processed(path):
                self.logger.debug(f"⏭️ Fichier déjà traité, ignoré : {path}")
                continue

            try:
                text = self.extract_text(path, **kwargs)

                if text:
                    document = {
                        "id": filename,
                        "filename": filename,
                        "path": path,
                        "file_type": file_ext.replace('.', ''),
                        "text_content": text,
                        "status": "parsed",
                    }
                    self.repository.insert_document(document)
                    self.logger.info(f"✅ Document ajouté : {filename}")
                else:
                    self.logger.warning(f"⚠️ Aucun texte extrait de {path}")

            except Exception as e:
                self.logger.exception(f"Erreur lors du traitement de {path}: {e}")

        self.logger.info(f"📦 Traitement terminé pour {len(file_paths)} fichiers.")
