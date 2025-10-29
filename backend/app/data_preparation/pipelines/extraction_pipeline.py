import os
import glob
import logging
from backend.app.data_preparation.parsers import DoctrOCR, PdfParser, TxtParser

logger = logging.getLogger("app.extraction")


def run_extraction():
    """
    Pipeline d'extraction centralisé :
      - Détecte les fichiers dans data/raw
      - Filtre par type (TXT, PDF, image)
      - Envoie les fichiers au parseur correspondant
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    raw_dir = os.path.join(base_dir, "data", "raw")
    print("---------- ",raw_dir)
    parser_map = {
        TxtParser(): [".txt"],
        PdfParser(): [".pdf"],
        DoctrOCR(): [".jpg", ".jpeg", ".png", ".bmp", ".tiff"],
    }

    total_files = 0

    for parser, extensions in parser_map.items():
        matching_files = []
        for ext in extensions:
            matching_files.extend(glob.glob(os.path.join(raw_dir, f"**/*{ext}"), recursive=True))

        if not matching_files:
            print("🔸 Aucun fichier {extensions} trouvé pour {parser.__class__.__name__}")
            logger.info(f"🔸 Aucun fichier {extensions} trouvé pour {parser.__class__.__name__}")
            continue

        total_files += len(matching_files)
        logger.info(f"🚀 {len(matching_files)} fichiers envoyés à {parser.__class__.__name__}")
        parser.process_file(file_paths=matching_files)

    if total_files == 0:
        logger.warning("⚠️ Aucun fichier trouvé dans data/raw pour aucun parseur.")
        print("⚠️ Aucun fichier trouvé dans data/raw pour aucun parseur.")
    else:
        logger.info(f"🏁 Extraction terminée — {total_files} fichiers traités au total.")
        print("🏁 Extraction terminée — {total_files} fichiers traités au total.")
