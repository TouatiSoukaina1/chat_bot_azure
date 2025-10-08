import os, glob
import logging
import re
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

class DoctrOCR:
    def __init__(self, det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", gpu=True, images_path=None):
        '''
            Classe OCR utilisant Doctr.
        '''
        self.logger = logging.getLogger("app.imageparser")
        self.model = ocr_predictor(det_arch=det_arch, reco_arch=reco_arch, pretrained=True)
        self.device = "cuda" if gpu else "cpu"
        self.images_path =images_path
        self.logger.info(f"Modèle OCR chargé avec det_arch={det_arch}, reco_arch={reco_arch}, device={self.device}")

    def _nettoyer_texte(self, texte: str, mots_a_supprimer=None) -> str:
        """Nettoie le texte extrait : supprime les mots indésirables et normalise les espaces"""
        if mots_a_supprimer is None:
            mots_a_supprimer = ["Français", "Espanol", "Pyccknn", "py", "a"]

        # Supprimer les mots-clés
        pattern = r'\b(?:' + '|'.join(re.escape(m) for m in mots_a_supprimer) + r')\b'
        texte = re.sub(pattern, '', texte, flags=re.IGNORECASE)

        # Remplacer les sauts de ligne et espaces multiples par un seul espace
        texte = re.sub(r'\s+', ' ', texte).strip()

        return texte

    def extract_text(self, image_path: str, nettoyer=True) -> str:
        '''
            Extrait le texte d'une image à l'aide de Doctr.
            param : 
                image_path: chemin vers le fichier image (.png, .jpg, etc.)
                nettoyer: bool, si True applique le nettoyage du texte
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

            if nettoyer:
                text_output = self._nettoyer_texte(text_output)

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

    def process_batch(self, nettoyer=True) -> dict:
        '''
            Traite un lot d'images et retourne un dictionnaire avec les résultats.
            param :
                nettoyer: bool, si True applique le nettoyage du texte
            return: dictionnaire {chemin_image: texte_extrait}
        '''
        self.logger.info(f"Traitement en lot de {len(self.images_path)} images")
        results={}
        list_path = glob.glob(os.path.join(self.images_path, "**", "*.jpg"), recursive=True)
        for path in list_path:
            results[path] = self.extract_text(path, nettoyer=nettoyer)
        self.logger.info("Traitement OCR du lot terminé")
        return results
