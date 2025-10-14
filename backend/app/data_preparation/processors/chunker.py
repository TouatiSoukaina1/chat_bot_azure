import logging
from typing import List, Dict

class Chunker:
    '''
        Classe responsable du découpage de texte en chunks
    '''

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        ''''
            Initialisation des paramétres de découpage
            params :
                chunk_size : taille maximale d'un chunk
                overlap (int): nombre de caractères en commun entre deux chunks
        '''
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.logger = logging.getLogger("app.Chunker")
        
    def chunk_text(self, text: str) -> List[str]:
        '''
            Découpe le texte en chunks avec overlap
            params :
                text (str): texte à découper
            return : liste des dictionnaires 
        '''
        if not text or not isinstance(text, str) == False:
            self.logger.warning("Texte vide ou type invalide de donnée")
            return []

        text = text.strip()
        text_length = len(text)

        if text_length <= self.chunk_size:
            return [{"id":0, "text": text}] 
        
        chunks = []
        chunk_id = 0
        start = 0
        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            chunk_text = text[start:end].strip()
            chunks.append({"id": chunk_id, "text": chunk_text})
            
            chunk_id += 1
            start += self.chunk_size - self.overlap

            if start >= text_length:
                break
        return chunks