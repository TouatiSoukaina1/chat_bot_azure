import logging
import time
import hashlib

from app.core.database import DocumentRepository
from app.data_preparation.processors.chunker import Chunker


def _hash_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class ChunkingPipeline:
    def __init__(self, repo=None, chunker=None, status_in="parsed", status_out="chunked"):
        self.logger = logging.getLogger("app.ChunkingPipeline")
        self.repo = repo or DocumentRepository()

        self.chunker = chunker or Chunker(chunk_size=1500, overlap=150)

        self.status_in = status_in
        self.status_out = status_out

    def run(self):
        docs = self.repo.get_documents_by_status(self.status_in)
        if not docs:
            self.logger.info("Aucun document à découper. Fin du pipeline.")
            return 0

        total_chunks_inserted = 0
        total_jobs_enqueued = 0

        for doc in docs:
            doc_id = doc.get("id")
            path = doc.get("path")
            ftype = doc.get("file_type", "txt")
            now = int(time.time())

            text = (doc.get("text_content") or "").strip()
            self.logger.info(
                f"[DEBUG] doc={doc_id} path={path} len(text_content)={len(text)} preview={repr(text[:120])}"
            )
            if not text:
                self.logger.warning(f"Document vide (après strip) ignoré : {path}")
                continue

            chunks = self.chunker.chunk_text(text)
            if not chunks:
                self.logger.warning(f"Aucun chunk généré pour : {path}")
                continue

            inserted_for_doc = 0
            enqueued_for_doc = 0

            for ch in chunks:
                content = (ch.get("text") or "").strip()
                if not content:
                    continue

                order = int(ch["id"])
                chunk_id = f"{doc_id}_chunk_{order}"
                content_hash = _hash_text(content)

                # 1) Insert chunk seulement s'il n'existe pas déjà
                if not self.repo.chunk_exists(chunk_id=chunk_id, document_id=doc_id):
                    self.repo.insert_chunk({
                        "id": chunk_id,
                        "document_id": doc_id,       # pk
                        "content": content,
                        "content_hash": content_hash,
                        "order": order,
                        "status": self.status_out,   # chunked
                        "type": ftype,
                        "source_path": path,
                        "created_at": now,
                    })
                    inserted_for_doc += 1
                else:
                    self.logger.debug("Chunk déjà présent, skip insert: %s", chunk_id)

                # 2) Enqueue job indexing seulement s'il n'existe pas
                work_id = f"indexing::{chunk_id}"
                work_type = "indexing"  # pk work_items

                if not self.repo.work_item_exists(work_id=work_id, work_type=work_type):
                    self.repo.enqueue_work_item({
                        "id": work_id,
                        "work_type": work_type,
                        "status": "queued",
                        "chunk_id": chunk_id,
                        "document_id": doc_id,
                        "attempts": 0,
                        "created_at": now,
                    })
                    enqueued_for_doc += 1
                else:
                    self.logger.debug("Work item déjà présent, skip enqueue: %s", work_id)

            # Update document status uniquement si on a généré du travail utile
            if inserted_for_doc > 0 or enqueued_for_doc > 0:
                self.repo.update_document_status(document_id=doc_id, file_type=ftype, new_status=self.status_out)

            total_chunks_inserted += inserted_for_doc
            total_jobs_enqueued += enqueued_for_doc

            self.logger.info(
                f"✅ {path} → chunks insérés: {inserted_for_doc} | jobs enqueued: {enqueued_for_doc} | total chunks générés: {len(chunks)}"
            )

        self.logger.info(
            f"Chunking terminé : {total_chunks_inserted} nouveaux chunks | {total_jobs_enqueued} nouveaux jobs"
        )
        return total_chunks_inserted
