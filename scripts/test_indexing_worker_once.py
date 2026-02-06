from backend.app.workers.indexing_worker import IndexingWorker

def main():
    w = IndexingWorker(worker_id="smoke-worker", claim_limit=16, lease_seconds=60)
    # petite astuce : remplacer run_forever par un seul batch
    jobs = w.repo.claim_work_items("indexing", limit=16, lease_seconds=60, worker_id=w.worker_id)
    if not jobs:
        print("Aucun job à traiter (queue vide).")
        return
    w._process_batch(jobs)  # ok pour test local
    print("✅ Worker batch OK")

if __name__ == "__main__":
    main()
