#chat_bot_azure/backend/app/data_preparation/parsers/pdf_parser.py
from app.data_preparation.parsers.base_parser import BaseParser
import os, pdfplumber


class PdfParser(BaseParser):
    def __init__(self):
        '''
            Classe permettant d'extraire et de parser le texte des fichiers PDF.
        '''
        super().__init__()

    def extract_text(self, file_path: str) -> str:
        '''
            Extrait le texte d’un fichier PDF.
            param:
                file_path: chemin complet du fichier PDF
            return: texte extrait
        '''
        self.logger.info(f"Extraction du texte depuis le PDF : {file_path}")

        try:
            if not os.path.exists(file_path):
                self.logger.error(f"Fichier introuvable : {file_path}")
                return ""

            text = ""
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text() or ""
                    if not page_text.strip():
                        self.logger.warning(f"Aucun texte trouvé à la page {i} ({file_path})")
                    text += page_text + "\n"

            text = text.strip()
            if text:
                self.logger.info(f"Texte extrait avec succès ({len(text)} caractères)")
            else:
                self.logger.warning(f"Aucun texte extrait du fichier {file_path}")

            return text

        except Exception as e:
            self.logger.exception(f"Erreur lors de l’extraction du PDF {file_path}: {e}")
            return ""
