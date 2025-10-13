from app.data_preparation.parsers.base_parser import BaseParser
import os

class TxtParser(BaseParser):
    def __init__(self):
        '''
            Classe permettant d'extraire et de parser le texte des fichiers TXT.
        '''
        super().__init__()
        
    def extract_text(self, file_path: str) -> str:
        '''
            Extrait le texte d’un fichier TXT.
            param:
                file_path: chemin complet du fichier TXT
            return: texte extrait
        '''
        self.logger.info(f"Lecture du fichier texte : {file_path}")

        try:
            if not os.path.exists(file_path):
                self.logger.error(f"Fichier introuvable : {file_path}")
                return ""

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()

            if not text:
                self.logger.warning(f"Fichier vide : {file_path}")
                return ""

            self.logger.info(f"Texte extrait avec succès ({len(text)} caractères)")
            return text

        except Exception as e:
            self.logger.exception(f"Erreur lors de la lecture du fichier texte {file_path}: {e}")
            return ""