import logging
import time
from pathlib import Path

from dotenv import load_dotenv

from backend.app.data_preparation.pipelines.extraction_pipeline import run_global_who_extraction
from backend.app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
from backend.app.workers.indexing_worker import IndexingWorker

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("backend.scripts.run_global_who_pipeline")


def run_extraction() -> int:
    raw_dir = ROOT / "data" / "raw" / "batch_txt"
    logger.info("=== EXTRACTION WHO GLOBAL ===")
    logger.info("Dossier source: %s", raw_dir)

    inserted = run_global_who_extraction(raw_dir=str(raw_dir))
    logger.info("Documents extraits / mis à jour: %s", inserted)
    return inserted


def run_chunking() -> int:
    logger.info("=== CHUNKING ===")
    pipeline = ChunkingPipeline(status_in="parsed", status_out="chunked")
    inserted_chunks = pipeline.run()
    logger.info("Nouveaux chunks: %s", inserted_chunks)
    return inserted_chunks


def run_indexing() -> int:
    logger.info("=== INDEXING ===")
    worker = IndexingWorker(worker_id="global-who-runner")

    total_claimed = 0
    while True:
        claimed = worker.run_once(limit=64, lease_seconds=120)
        if claimed == 0:
            break
        total_claimed += claimed
        time.sleep(1)

    logger.info("Jobs d'indexing traités: %s", total_claimed)
    return total_claimed


def main():
    logger.info("=== START WHO GLOBAL PIPELINE ===")
    run_extraction()
    run_chunking()
    run_indexing()
    logger.info("=== WHO GLOBAL PIPELINE TERMINÉ ===")


if __name__ == "__main__":
    main()