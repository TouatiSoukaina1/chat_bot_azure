#chat_bot_azure/backend/app/data_preparation/parsers/image_parser.py
from app.data_preparation.parsers.base_parser import BaseParser
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import os, logging

class DoctrOCR(BaseParser):
    def __init__(self, det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", gpu=True):
        '''
            Classe OCR utilisant Doctr.
        '''
        super().__init__()
        self.logger = logging.getLogger("app.imageparser")
        self.model = ocr_predictor(det_arch=det_arch, reco_arch=reco_arch, pretrained=True)
        self.device = "cuda" if gpu else "cpu"
        self.logger.info(f"Modèle OCR chargé avec det_arch={det_arch}, reco_arch={reco_arch}, device={self.device}")

    def extract_text(self, image_path: str) -> str:
        '''
            Extrait le texte d'une image en utilisant Doctr OCR.
            param :
                image_path: chemin de l'image
                retourne: texte extrait
        '''
        try:
            if not os.path.exists(image_path):
                self.logger.error(f"Fichier introuvable : {image_path}")
                return ""

            doc = DocumentFile.from_images(image_path)
            result = self.model(doc)
            lines = [
                " ".join([w.value for w in line.words])
                for b in result.pages[0].blocks
                for line in b.lines
            ]
            text = "\n".join(lines).strip()

            return text

        except Exception as e:
            self.logger.exception(f"Erreur OCR sur {image_path}: {e}")
            return ""