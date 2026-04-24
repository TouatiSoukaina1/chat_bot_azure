from app.data_preparation.parsers.base_parser import BaseParser
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import os
import logging
import torch


class DoctrOCR(BaseParser):
    """
    Classe OCR basée sur Doctr pour l'extraction de texte depuis des images.
    Gère automatiquement le GPU si disponible et assure une journalisation claire.
    """

    def __init__(self, det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", gpu=True):
        super().__init__()

        # Configuration du logger
        self.logger = logging.getLogger("app.DoctrOCR")

        # Sélection du device
        self.device = "cuda" if gpu and torch.cuda.is_available() else "cpu"

        # Chargement du modèle
        self.model = ocr_predictor(
            det_arch=det_arch,
            reco_arch=reco_arch,
            pretrained=True
        ).to(self.device)

        self.logger.info(
            f"🧠 Modèle Doctr chargé (det_arch={det_arch}, reco_arch={reco_arch}, device={self.device})"
        )

    def extract_text(self, image_path: str) -> str:
        """
        Extrait le texte d'une image à l'aide de Doctr.
        - image_path : chemin de l'image à traiter
        - return : texte extrait (ou chaîne vide si erreur)
        """
        try:
            if not os.path.exists(image_path):
                self.logger.error(f"❌ Fichier introuvable : {image_path}")
                return ""

            # Lecture du fichier image
            doc = DocumentFile.from_images(image_path)

            # Exécution OCR
            result = self.model(doc)

            if not result.pages or not result.pages[0].blocks:
                self.logger.warning(f"⚠️ Aucun texte détecté dans {os.path.basename(image_path)}")
                return ""

            # Reconstruction du texte ligne par ligne
            lines = []
            for block in result.pages[0].blocks:
                for line in block.lines:
                    words = " ".join([w.value for w in line.words])
                    if words.strip():
                        lines.append(words)

            text = "\n".join(lines).strip()

            if text:
                self.logger.debug(f"✅ Texte extrait ({len(text)} caractères) depuis {image_path}")
            else:
                self.logger.warning(f"⚠️ OCR n’a rien détecté dans {image_path}")

            return text

        except Exception as e:
            self.logger.exception(f"💥 Erreur OCR sur {image_path}: {e}")
            return ""
