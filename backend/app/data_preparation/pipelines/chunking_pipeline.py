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

    def run(self, document_ids: list[str] | None = None):
        docs = self.repo.get_documents_by_status(self.status_in)

        if document_ids:
            docs = [doc for doc in docs if doc.get("id") in document_ids]

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
            if not text:
                self.logger.warning(f"Document vide (après strip) ignoré : {path}")
                continue

            doc_title = (doc.get("title") or doc.get("document_title") or doc.get("name") or "").strip()

            chunks = self.chunker.chunk_text(text, doc_title=doc_title)
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

                section_title = (ch.get("section_title") or "").strip()
                chunk_doc_title = (ch.get("doc_title") or doc_title or "").strip()

                if not self.repo.chunk_exists(chunk_id=chunk_id, document_id=doc_id):
                    self.repo.insert_chunk({
                        "id": chunk_id,
                        "document_id": doc_id,
                        "content": content,
                        "content_hash": content_hash,
                        "order": order,
                        "status": self.status_out,
                        "type": ftype,
                        "source_path": path,
                        "created_at": now,
                        "section_title": section_title,
                        "doc_title": chunk_doc_title,
                        "scope": doc.get("scope"),
                        "owner_user_id": doc.get("owner_user_id"),
                        "source_type": doc.get("source_type"),
                        "kb": doc.get("kb"),
                        "filename": doc.get("filename"),
                    })
                    inserted_for_doc += 1

                work_id = f"indexing::{chunk_id}"
                work_type = "indexing"

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

            if inserted_for_doc > 0 or enqueued_for_doc > 0:
                self.repo.update_document_status(
                    document_id=doc_id,
                    file_type=ftype,
                    new_status=self.status_out,
                )

            total_chunks_inserted += inserted_for_doc
            total_jobs_enqueued += enqueued_for_doc

            self.logger.info(
                f"✅ {path} → chunks insérés: {inserted_for_doc} | jobs enqueued: {enqueued_for_doc} | total chunks générés: {len(chunks)}"
            )

        self.logger.info(
            f"Chunking terminé : {total_chunks_inserted} nouveaux chunks | {total_jobs_enqueued} nouveaux jobs"
        )
        return total_chunks_inserted