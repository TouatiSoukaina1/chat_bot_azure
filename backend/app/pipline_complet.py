from data_preparation.parsers.pdf_parser import PdfParser
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

# Handler console
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)

# Ajout des handlers au logger
logger.addHandler(fh_app)
logger.addHandler(fh_error)
logger.addHandler(ch)

if __name__ == "__main__":
    pdf_path = "data/batch/disease-handbook-complete.pdf"  # Remplacez par le chemin de votre fichier PDF
    parser = PdfParser(pdf_path)
    content = parser.parse()
    print(content)