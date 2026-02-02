import logging
from typing import List, Dict, Any

class Chunker:
    def __init__(self, chunk_size: int = 1500, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = min(overlap, chunk_size - 1)
        self.logger = logging.getLogger("app.Chunker")

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        # 1) Validation correcte
        if not isinstance(text, str) or not text.strip():
            self.logger.warning("Texte vide ou type invalide de donnée")
            return []

        text = text.strip()
        text_length = len(text)

        if text_length <= self.chunk_size:
            return [{"id": 0, "text": text}]

        chunks: List[Dict[str, Any]] = []
        chunk_id = 0
        start = 0

        step = max(1, self.chunk_size - self.overlap)  # évite boucle infinie
        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            piece = text[start:end].strip()

            # 2) Ne pas créer de chunk vide
            if piece:
                chunks.append({"id": chunk_id, "text": piece})
                chunk_id += 1

            start += step

        return chunks
