import os
import time
from backend.app.core.database import DocumentRepository
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)

def main():
    required = [
        "COSMOSDB_URI", "COSMOS_DATABASE",
        "COSMOSDB_CONTAINER_DOCUMENTS", "COSMOSDB_CONTAINER_CHUNKS", "COSMOSDB_CONTAINER_WORK_ITEMS"
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Variables manquantes: {missing}")

    repo = DocumentRepository()
    now = int(time.time())

    # 1) insert doc
    doc = {
        "id": "smoke_doc",
        "file_type": "txt",   # pk documents
        "path": "smoke",
        "status": "parsed",
        "text_content": "Texte test pour chunking."
    }
    repo.docs_container.upsert_item(doc)
    print("✅ Document upsert OK")

    # 2) create chunk if absent
    chunk = {
        "id": "smoke_doc_chunk_0",
        "document_id": "smoke_doc",  # pk chunks
        "content": "chunk test",
        "order": 0,
        "status": "chunked",
        "type": "txt",
        "source_path": "smoke",
        "created_at": now,
    }
    created = repo.create_chunk_if_absent(chunk)
    print("✅ Chunk create_if_absent =", created)

    # 3) create work item if absent
    wi = {
        "id": "indexing::smoke_doc_chunk_0",
        "work_type": "indexing",     # pk work_items
        "status": "queued",
        "chunk_id": "smoke_doc_chunk_0",
        "document_id": "smoke_doc",
        "attempts": 0,
        "max_attempts": 3,
        "lease_until": 0,
        "next_run_at": 0,
        "created_at": now,
        "updated_at": now,
    }
    created_wi = repo.create_work_item_if_absent(wi)
    print("✅ WorkItem create_if_absent =", created_wi)

    # 4) claim 1 job
    jobs = repo.claim_work_items(work_type="indexing", limit=1, lease_seconds=30, worker_id="smoke-worker")
    print("✅ claim_work_items ->", len(jobs))

    print("✅ Cosmos smoke test OK")

if __name__ == "__main__":
    main()
