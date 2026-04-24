import time
from app.core.database import DocumentRepository

def main():
    repo = DocumentRepository()
    now = int(time.time())

    # ⚠️ Mets un chunk_id qui existe VRAIMENT dans ton container chunks
    # Exemple: récupère 1 chunk chunked
    chunks = repo.get_chunks(status="chunked", limit=1)
    if not chunks:
        print("Aucun chunk status=chunked. Lance chunking pipeline d'abord.")
        return

    ch = chunks[0]
    chunk_id = ch["id"]
    doc_id = ch.get("document_id")

    work_item = {
        "id": f"indexing::{chunk_id}",
        "work_type": "indexing",     # pk=/work_type
        "status": "queued",
        "chunk_id": chunk_id,
        "document_id": doc_id,
        "attempts": 0,
        "max_attempts": 3,
        "lease_until": 0,
        "next_run_at": 0,
        "created_at": now,
        "updated_at": now,
    }

    # si tu as déjà create_work_item_if_absent
    created = repo.create_work_item_if_absent(work_item)
    print("✅ Work item queued:", created, work_item["id"])

if __name__ == "__main__":
    main()
