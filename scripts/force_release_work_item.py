# scripts/force_release_work_item.py
import time
from app.core.database import DocumentRepository

def main():
    repo = DocumentRepository()
    work_id = "indexing::smoke_doc_chunk_0"
    pk = "indexing"

    wi = repo.work_container.read_item(item=work_id, partition_key=pk)

    now = int(time.time())
    wi["status"] = "queued"
    wi["lease_until"] = 0
    wi["next_run_at"] = now - 1
    wi["updated_at"] = now
    wi.pop("worker_id", None)

    repo.work_container.upsert_item(wi)
    print("✅ Forced queued:", wi["id"], "status=", wi["status"], "lease_until=", wi["lease_until"], "next_run_at=", wi["next_run_at"])

if __name__ == "__main__":
    main()
