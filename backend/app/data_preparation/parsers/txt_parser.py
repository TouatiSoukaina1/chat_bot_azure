# backend/app/data_preparation/parsers/txt_parser.py
from backend.app.data_preparation.parsers.base_parser import BaseParser
import os
import logging

class TxtParser(BaseParser):
    """
    Classe de parsing pour les fichiers texte (.txt).
    Lit et renvoie le contenu du fichier brut.
    """
    supported_extensions = [".txt"]

    def __init__(self, encoding="utf-8"):
        super().__init__()
        self.encoding = encoding
        self.logger = logging.getLogger("app.txtparser")
        self.logger.info("TxtParser initialisé avec encodage UTF-8.")

    def extract_text(self, file_path: str) -> str:
        """
        Extrait le texte d’un fichier texte (.txt).
        param :
            file_path : chemin du fichier
        return :
            contenu texte
        """
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"Fichier introuvable : {file_path}")
                return ""

            with open(file_path, "r", encoding=self.encoding) as f:
                content = f.read().strip()

            self.logger.info(f"Texte extrait depuis {file_path} ({len(content)} caractères).")
            return content

        except UnicodeDecodeError:
            self.logger.warning(f"Problème d’encodage sur {file_path}, tentative en latin-1.")
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read().strip()
                return content
            except Exception as e:
                self.logger.exception(f"Erreur d’encodage sur {file_path} : {e}")
                return ""

        except Exception as e:
            self.logger.exception(f"Erreur lors de la lecture du fichier texte : {e}")
            return ""
