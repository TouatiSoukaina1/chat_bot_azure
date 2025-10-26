#chat_bot_azure/backend/app/data_preparation/pipelines/extraction_pipeline.py
from app.data_preparation.parsers import DoctrOCR, PdfParser, TxtParser
import logging

logger = logging.getLogger(__name__)

def run_extraction():
    """
    Pipeline d'extraction : OCR pour images, PDF et texte brut.
    """
    parsers = [DoctrOCR(), PdfParser(), TxtParser()]
    for parser in parsers:
        parser.process_file()
    logging.info("Extraction terminée.")