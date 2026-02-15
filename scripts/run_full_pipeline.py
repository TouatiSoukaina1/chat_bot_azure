import time
import logging

from backend.app.core.logging_config import setup_logging
from backend.app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
from backend.app.workers.indexing_worker import IndexingWorker
from backend.app.data_preparation.pipelines.extraction_pipeline import run_extraction
from scripts.backfill_indexing_jobs import main as backfill

def main():
    setup_logging(app_name="app")
    log = logging.getLogger("scripts.run_full_pipeline")

    # Parsing 
    run_extraction()
    
    # Run chunking pipeline 
    ChunkingPipeline().run()

    # BACKFILL 

    backfill(limit_chunks=5000)

    # INDEXING WORKER (embedding + upload Azure Search)
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
