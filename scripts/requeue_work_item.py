import time
from backend.app.core.database import DocumentRepository

def main():
    repo = DocumentRepository()
    work_id = "indexing::smoke_doc_chunk_0"
    pk = "indexing"

    wi = repo.work_container.read_item(item=work_id, partition_key=pk)

    now = int(time.time())
    wi["status"] = "queued"
    wi["lease_until"] = 0
    wi["next_run_at"] = 0
    wi["updated_at"] = now
    wi.pop("worker_id", None)

    repo.work_container.upsert_item(wi)
    print("✅ Re-queued:", work_id)

if __name__ == "__main__":
    main()
