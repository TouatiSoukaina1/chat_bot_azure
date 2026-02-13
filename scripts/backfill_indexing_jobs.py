import time
import logging

from backend.app.core.logging_config import setup_logging
from backend.app.core.database import DocumentRepository

WORK_TYPE = "indexing"

def main(limit_chunks: int = 2000):
    setup_logging(app_name="app")
    log = logging.getLogger("scripts.backfill_indexing_jobs")

    repo = DocumentRepository()
    now = int(time.time())

    chunks = repo.get_chunks(status="chunked", limit=limit_chunks)
    if not chunks:
        log.info("Aucun chunk status=chunked.")
        return

    created = 0
    for ch in chunks:
        chunk_id = ch["id"]
        doc_id = ch.get("document_id")
        if not doc_id:
            continue

        work_id = f"{WORK_TYPE}::{chunk_id}"

        if repo.work_item_exists(work_id=work_id, work_type=WORK_TYPE):
            continue

        repo.enqueue_work_item({
            "id": work_id,
            "work_type": WORK_TYPE,   # pk
            "status": "queued",
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "attempts": 0,
            "created_at": now,
        })
        created += 1

    log.info("Backfill terminé: %s nouveaux work_items créés.", created)

if __name__ == "__main__":
    main()
