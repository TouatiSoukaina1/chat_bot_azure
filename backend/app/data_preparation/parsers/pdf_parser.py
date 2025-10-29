# backend/app/data_preparation/parsers/pdf_parser.py
from backend.app.data_preparation.parsers.base_parser import BaseParser
import fitz  # PyMuPDF
import os
import logging

class PdfParser(BaseParser):
    """
    Classe de parsing pour les fichiers PDF.
    Extrait le texte à partir de fichiers PDF en conservant la structure des pages.
    """
    supported_extensions = [".pdf"]

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("app.pdfparser")
        self.logger.info("PdfParser initialisé.")

    def extract_text(self, file_path: str) -> str:
        """
        Extrait le texte d’un fichier PDF.
        param :
            file_path : chemin du fichier PDF
        return :
            texte extrait sous forme de chaîne
        """
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"Fichier introuvable : {file_path}")
                return ""

            text_content = []
            with fitz.open(file_path) as doc:
                for page_num, page in enumerate(doc):
                    page_text = page.get_text("text")
                    if page_text.strip():
                        text_content.append(page_text)
                    else:
                        self.logger.warning(f"Page {page_num + 1} vide dans {file_path}")

            extracted_text = "\n".join(text_content).strip()
            self.logger.info(f"Texte extrait depuis {file_path} ({len(text_content)} pages).")
            return extracted_text

        except Exception as e:
            self.logger.exception(f"Erreur lors de l’extraction PDF : {e}")
            return ""
