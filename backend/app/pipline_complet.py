from data_preparation.parsers.pdf_parser import PdfParser
from data_preparation.parsers.image_parser import DoctrOCR

import logging

logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)  # on prend tout

# Formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Handler pour logs généraux
fh_app = logging.FileHandler("application.log", encoding="utf-8")
fh_app.setLevel(logging.INFO)  # INFO et plus
fh_app.setFormatter(formatter)

# Handler pour logs d'erreurs uniquement
fh_error = logging.FileHandler("errors.log", encoding="utf-8")
fh_error.setLevel(logging.ERROR)  # seulement ERROR et CRITICAL
fh_error.setFormatter(formatter)

fh_error = logging.FileHandler("warning.log", encoding="utf-8")
fh_error.setLevel(logging.WARNING)  # seulement ERROR et CRITICAL
fh_error.setFormatter(formatter)

# Handler console
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)

# Ajout des handlers au logger
logger.addHandler(fh_app)
logger.addHandler(fh_error)
logger.addHandler(ch)

if __name__ == "__main__":
    pdf_path = "data/batch/disease-handbook-completed_removed.pdf"  # Remplacez par le chemin de votre fichier PDF


    ocr = DoctrOCR(gpu=False)

    image_path = "data/capture1.png"
    text = ocr.extract_text(image_path)

    if text:
        print("\n=== Texte détecté ===")
        print(text[:500])
    else:
        print("❌ Aucun texte extrait.")