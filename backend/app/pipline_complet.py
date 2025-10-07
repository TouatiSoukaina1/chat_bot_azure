from data_preparation.parsers.pdf_parser import PdfParser
from data_preparation.parsers.image_parser import DoctrOCR
import os, glob
import logging

LOG_DIR = os.path.join(os.getcwd(), "logs") 
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("app")
logger.setLevel(logging.DEBUG)  # on prend tout

# Formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Handler pour logs généraux
app_logs_path = os.path.join(LOG_DIR, "application.log") 
fh_app = logging.FileHandler(app_logs_path, encoding="utf-8")
fh_app.setLevel(logging.INFO)  # INFO et plus
fh_app.setFormatter(formatter)

# Handler pour logs d'erreurs uniquement
error_logs_path = os.path.join(LOG_DIR, "errors.log") 
fh_error = logging.FileHandler(error_logs_path, encoding="utf-8")
fh_error.setLevel(logging.ERROR)  # seulement ERROR et CRITICAL
fh_error.setFormatter(formatter)

warning_logs_path = os.path.join(LOG_DIR, "warning.log") 
fh_error = logging.FileHandler(warning_logs_path, encoding="utf-8")
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
    PDF_PATH = "data/pdf"  
    IMAGES_PATH = "data/images"
    TXT_PATH = "data/txt"

    ocr = DoctrOCR(gpu=False)
    pdf_parser = PdfParser(PDF_PATH)    
    list_images= glob.glob(os.path.join(IMAGES_PATH, "*.jpg"))
    list_pdfs = glob.glob(os.path.join(PDF_PATH, "*.pdf"))
    
    data_pdf =  pdf_parser.parse()
    #text_dict = ocr.process_batch(list_images)
    if data_pdf:
        print("\n=== Texte détecté ===")
        print(data_pdf)
    else:
        print("❌ Aucun texte extrait.")