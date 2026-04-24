# scripts/list_indexing_work_items.py
import time
from app.core.database import DocumentRepository

def main():
    repo = DocumentRepository()
    now = int(time.time())

    q = """
    SELECT c.id, c.status, c.lease_until, c.next_run_at, c.attempts, c.max_attempts, c.worker_id
    FROM c
    WHERE c.work_type = @wt
    ORDER BY c._ts DESC
    """
    items = list(repo.work_container.query_items(
        query=q,
        parameters=[{"name":"@wt","value":"indexing"}],
        enable_cross_partition_query=True
    ))

    print("now =", now, "items =", len(items))
    for it in items[:20]:
        print(it)

if __name__ == "__main__":
    main()
