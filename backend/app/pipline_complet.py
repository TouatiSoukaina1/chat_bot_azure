from data_preparation.parsers.pdf_parser import PdfParser
from data_preparation.parsers.image_parser import DoctrOCR
from data_preparation.parsers.txt_parser import TxtParser
from utils.logging_config import *
import logging

def data_preparation_pipeline(pdf_dir="data/pdf", img_dir="data/images", txt_dir="data/batch_txt"):
    logger = logging.getLogger("app.pipeline")
    logger.info("🚀 Lancement du pipeline complet")


    image_parser = DoctrOCR(gpu=False, images_path=img_dir)
    pdf_parser = PdfParser(pdf_dir)    
    text_parser = TxtParser(txt_dir)

    data_pdf = pdf_parser.process_directory()
    data_images = image_parser.process_batch()
    data_txt = text_parser.load_corpus()

    logger.info("Pipeline terminé avec succès")

    return data_images, data_pdf, data_txt
    
    
if __name__ == "__main__":
    
    data_images, data_pdf, data_txt = data_preparation_pipeline()
    print(data_images)

