from abc import ABC, abstractmethod
from typing import Dict, Optional
import logging
import os, glob
from app.core.database import DocumentRepository

class BaseParser(ABC):
    ''' 
        Classe abstraite pour les parseurs de données ( texte, image, PDF).
    '''

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
        
        self.source_dir = os.path.join(base_dir, "data", "raw")
        self.repository = DocumentRepository()

    @abstractmethod
    def extract_text(self, file_path: str, **kwargs) -> str:
        '''
           Méthode abstraite pour extraire le texte d'un fichier.
        '''
        pass
    def process_file(self, extensions=None, **kwargs):
        '''
            Traite les fichiers du répertoire source et stocke directement les résultats dans la base de donnée.
        '''
        if extensions is None:
            extensions = ['.txt', '.pdf', '.png', '.jpg', '.jpeg']

        all_paths = []
        for ext in extensions:
            all_paths.extend(glob.glob(os.path.join(self.source_dir, f"**/*{ext}"), recursive=True))

        if not all_paths:
            self.logger.warning(f"Aucun fichier trouvé dans {self.source_dir} avec les extensions {extensions}")
            return

        for path in all_paths:
            filename = os.path.basename(path)
            file_ext = os.path.splitext(path)[1].lower()

            # Vérifie si le document a déjà été traité
            if self.repository.is_processed(path):
                self.logger.debug(f"Fichier déjà traité, passage : {path}")
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
                        "status": "parsed"
                    }
                    self.repository.insert_document(document)
                    self.logger.info(f"✅ Document ajouté : {filename}")
                else:
                    self.logger.warning(f"⚠️ Aucun texte extrait de {path}")

            except Exception as e:
                self.logger.exception(f"Erreur lors du traitement de {path}: {e}")

        self.logger.info("Extraction OCR/PDF/TXT terminée et synchronisée avec CosmosDB.")
