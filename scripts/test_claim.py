# scripts/test_claim.py
from backend.app.core.database import DocumentRepository

def main():
    repo = DocumentRepository()
    jobs = repo.claim_work_items(work_type="indexing", worker_id="local-test", limit=5, lease_seconds=60)
    print("claimed =", len(jobs))
    for j in jobs:
        print(j["id"], j["status"], j.get("lease_until"))

if __name__ == "__main__":
    main()
