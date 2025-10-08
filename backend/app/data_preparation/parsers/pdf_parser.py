import os
import glob
import pdfplumber
import logging

class PdfParser:
    def __init__(self, files_path: str):
        """
        Classe permettant d'extraire et de parser le texte d'un ou plusieurs fichiers PDF.
        """
        self.files_path = files_path
        self.logger = logging.getLogger("app.pdfparser")

        if not os.path.exists(self.files_path):
            self.logger.error(f"Chemin introuvable : {self.files_path}")
            raise FileNotFoundError(f"Chemin introuvable : {self.files_path}")

    def extract_text(self, path: str) -> str:
        """
        Extrait le texte brut d'un fichier PDF.
        return: texte brut extrait du PDF (chaîne)
        """
        if os.path.isdir(path):
            self.logger.error(f"Le chemin {path} est un dossier, pas un fichier PDF.")
            return ""

        self.logger.info(f"Extraction du texte depuis le PDF : {path}")
        text = ""

        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    else:
                        self.logger.warning(f"Aucun texte trouvé à la page {i}")

            if not text.strip():
                self.logger.warning(f"Aucun texte détecté dans le fichier : {path}")
            else:
                self.logger.info(f"Texte extrait avec succès ({len(text)} caractères)")

            return text.strip()

        except Exception as e:
            self.logger.exception(f"Erreur lors de la lecture du PDF {path}: {e}")
            return ""

    def process_directory(self) -> dict:
        """
        Parcourt un dossier et extrait le texte de tous les fichiers PDF trouvés.
        return: dict { 'nom_fichier_sans_extension': 'texte_extrait' }
        """
        self.logger.info(f"Recherche de fichiers PDF dans : {self.files_path}")

        if os.path.isdir(self.files_path):
            list_pdf = glob.glob(os.path.join(self.files_path, "*.pdf"))
        else:
            list_pdf = glob.glob(self.files_path)

        if not list_pdf:
            self.logger.warning(f"Aucun fichier PDF trouvé dans : {self.files_path}")
            return {}

        contenu_fichiers = {}
        for path in list_pdf:
            file_name = os.path.splitext(os.path.basename(path))[0]
            text = self.extract_text(path)

            if not text:
                self.logger.warning(f"Aucun texte extrait du PDF : {path}")
            else:
                contenu_fichiers[path] = text

        self.logger.info(f"{len(contenu_fichiers)} fichiers PDF traités avec succès.")
        return contenu_fichiers
