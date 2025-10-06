import os
import logging
from doctr.io import DocumentFile
from doctr.models import ocr_predictor


class DoctrOCR:
    def __init__(self, det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", gpu=True):
        '''
            Classe OCR utilisant Doctr.
        '''
        self.logger = logging.getLogger("app.imageparser")
        self.model = ocr_predictor(det_arch=det_arch, reco_arch=reco_arch, pretrained=True)
        self.device = "cuda" if gpu else "cpu"

        self.logger.info(f"Modèle OCR chargé avec det_arch={det_arch}, reco_arch={reco_arch}, device={self.device}")

    def extract_text(self, image_path: str) -> str:
        '''
            Extrait le texte d'une image à l'aide de Doctr.
            param :
                image_path: chemin vers le fichier image (.png, .jpg, etc.)
            return: texte extrait (chaîne)
        '''
        self.logger.info(f"Traitement OCR de l'image : {image_path}")

        try:
            if not os.path.exists(image_path):
                self.logger.error(f"Fichier introuvable : {image_path}")
                raise FileNotFoundError(f"Fichier introuvable : {image_path}")

            doc = DocumentFile.from_images(image_path)
            if not doc:
                self.logger.error(f"Impossible de lire l'image : {image_path}")
                raise ValueError(f"Impossible de lire l'image : {image_path}")

            result = self.model(doc)
            texts = []
            for page_idx, page in enumerate(result.pages, start=1):
                self.logger.debug(f"Extraction du texte de la page {page_idx}")
                for block in page.blocks:
                    for line in block.lines:
                        line_text = " ".join([word.value for word in line.words])
                        texts.append(line_text)

            text_output = "\n".join(texts).strip()

            if not text_output:
                self.logger.warning(f"Aucun texte détecté dans l'image : {image_path}")
            else:
                self.logger.info(f"Texte extrait avec succès ({len(text_output)} caractères)")

            return text_output

        except FileNotFoundError as e:
            self.logger.error(e)
        except ValueError as e:
            self.logger.error(e)
        except Exception as e:
            self.logger.exception(f"Erreur inattendue lors du traitement de {image_path}: {e}")
        return ""

    def process_batch(self, image_paths: list) -> dict:
        '''
            Traite un lot d'images et retourne un dictionnaire avec les résultats.
            param :
                image_paths: liste de chemins vers les fichiers images
            return: dictionnaire {chemin_image: texte_extrait}
        '''
        self.logger.info(f"Traitement en lot de {len(image_paths)} images")
        results = {}
        for path in image_paths:
            results[path] = self.extract_text(path)
        self.logger.info("Traitement OCR du lot terminé")
        return results
