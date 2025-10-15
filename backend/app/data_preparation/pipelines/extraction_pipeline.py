from app.data_preparation.parsers import DoctrOCR, PdfParser, TxtParser
import logging

logger = logging.getLogger(__name__)
def run_extraction():
    '''
        Pipeline de l'extraction de données : image pdf et txt
    '''
    parsers = [DoctrOCR(["jpg", "jpeg", "png", "bmp", "tiff"]), PdfParser(["pdf"]), TxtParser("txt")] 
    for parser in parsers:
        parser.process_file()
        
    logging.info("Extraction terminée.")
    