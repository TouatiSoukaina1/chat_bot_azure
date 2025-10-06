import os
import re
import logging
class TxtParser:
    def __init__(self, data_dir="data"):
        ''''
            Initialise le parseur de fichiers texte.
            parametres : 
                - data_dir: chemin vers le dossier contenant les fichiers .txt
        '''
        self.data_dir = os.path.abspath(data_dir)
        self.logger = logging.getLogger("app.txtparser")
        if not os.path.exists(self.data_dir):
            self.logger.error(f"Dossier non trouvé : {self.data_dir}")

    def list_txt_files(self):
        '''
            Liste tous les fichiers .txt dans le dossier data_dir.
        '''
        files = [os.path.join(self.data_dir, f) for f in os.listdir(self.data_dir) if f.endswith(".txt")]
        self.logger.info(f"{len(files)} fichiers texte détectés dans {self.data_dir}")
        return files

    @staticmethod
    def clean_text(text: str) -> str:
        '''
            Nettoyage de texte :
                - supprime les espaces multiples,
                - conserve la structure logique (retours à la ligne entre paragraphes).
            param : texte brut
            return : texte nettoyé
        '''
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def parse_txt(self, file_path: str) -> str:
        '''
            Lecture et nettoyage d'un fichier texte.
        '''
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.clean_text(content)

    def load_corpus(self):
        '''
            Chargement et nettoyage de tous les fichiers .txt dans une liste de documents.
        '''
        corpus = []
        for file in self.list_txt_files():
            text = self.parse_txt(file)
            title = os.path.splitext(os.path.basename(file))[0]
            corpus.append({
                "title": title,
                "content": text,
                "path": file
            })
        self.logger.info(f"Corpus chargé avec {len(corpus)} documents.")
        return corpus
