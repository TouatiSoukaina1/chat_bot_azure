import time
import logging

from backend.app.core.logging_config import setup_logging
from backend.app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
from backend.app.workers.indexing_worker import IndexingWorker


def main():
    setup_logging(app_name="app")
    log = logging.getLogger("scripts.run_full_pipeline")

    # 1) PARSING (si tu veux tout faire en une commande)
    # -----------------------------------------------
    # Exemple (à adapter) :
    # parser = WhoPdfParser()
    # parser.process_file(file_paths=[...])  # ou ton pipeline d'extraction

    # 2) CHUNKING
    # -----------------------------------------------
    # log.info("=== CHUNKING ===")
    # ChunkingPipeline().run()

    # 3) BACKFILL (au cas où)
    # -----------------------------------------------
    # log.info("=== BACKFILL work_items (indexing) ===")
    from scripts.backfill_indexing_jobs import main as backfill
    backfill(limit_chunks=5000)

    # 4) INDEXING WORKER (embedding + upload Azure Search)
    # -----------------------------------------------
    log.info("=== INDEXING WORKER ===")
    worker = IndexingWorker(worker_id="local-worker")

    total = 0
    while True:
        n = worker.run_once(limit=10, lease_seconds=300)
        if n == 0:
            break
        total += n
        time.sleep(0.2)

    log.info("✅ Pipeline terminé. Jobs traités=%s", total)

if __name__ == "__main__":
    main()
