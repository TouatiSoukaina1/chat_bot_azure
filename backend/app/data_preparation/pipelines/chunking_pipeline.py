import logging
from app.core.database import DocumentRepository
from app.data_preparation.processors.chunker import Chunker

class ChunkingPipeline:
    def __init__(self, repo=None, chunker=None, status_in="parsed", status_out="chunked"):
        self.logger = logging.getLogger("app.ChunkingPipeline")
        self.repo = repo or DocumentRepository()
        self.chunker = chunker or Chunker(chunk_size=500, overlap=50)
        self.status_in = status_in
        self.status_out = status_out

    def run(self):
        docs = self.repo.get_documents_by_status(self.status_in)
        if not docs:
            self.logger.info("Aucun document à découper. Fin du pipeline.")
            return 0

        total_chunks = 0
        for doc in docs:
            doc_id = doc.get("id")
            path = doc.get("path")
            text = doc.get("text_content")
            ftype = doc.get("file_type", "txt")

            if not text:
                self.logger.warning(f"Document vide ignoré : {path}")
                continue

            chunks = self.chunker.chunk_text(text)
            if not chunks:
                self.logger.warning(f"Aucun chunk généré pour : {path}")
                continue

            # persist
            for ch in chunks:
                self.repo.insert_chunk({
                    "id": f"{doc_id}_chunk_{ch['id']}",
                    "document_id": doc_id,
                    "text": ch["text"],
                    "order": ch["id"],
                    "status": self.status_out,
                    "type": ftype,
                    "source_path": path
                })

            self.repo.update_document_status(document_id=doc_id, new_status=self.status_out, partition_key=ftype)
            total_chunks += len(chunks)
            self.logger.info(f"✅ {path} → {len(chunks)} chunks")

        self.logger.info(f"Chunking terminé : {total_chunks} chunks créés")
        return total_chunks
