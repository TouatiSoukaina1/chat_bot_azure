from app.data_preparation.parsers import DoctrOCR, PdfParser, TxtParser
import logging

logger = logging.getLogger(__name__)
def run_extraction():
    '''
        Pipeline de l'extraction de données : image pdf et txt
    '''

    parsers = [DoctrOCR(), PdfParser(), TxtParser()] 
    for parser in parsers:
        results = parser.process_file()
        total_processed += len(results)
        logger.info(f"{parser.__class__.__name__}: {len(results)} fichiers traités")

    logger.info(f"✅ Extraction terminée : {total_processed} fichiers traités au total")
    