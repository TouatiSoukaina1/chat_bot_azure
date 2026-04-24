from pathlib import Path
from dotenv import load_dotenv

from app.data_preparation.pipelines.extraction_pipeline import run_private_user_extraction
from app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
from app.workers.indexing_worker import IndexingWorker

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=True)


def main():
    # adapte ici
    owner_user_id = "5038e8e1-8c87-447a-a97c-8e7fde8f8c4b:MON_OID"
    file_paths = [
        str(ROOT / "data" / "raw" / "test_private" / "doc1.md"),
        str(ROOT / "data" / "raw" / "test_private" / "doc2.txt"),
    ]

    print("=== EXTRACTION PRIVATE FILES ===")
    inserted = run_private_user_extraction(
        file_paths=file_paths,
        owner_user_id=owner_user_id,
    )
    print(f"Documents extraits: {inserted}")

    print("=== CHUNKING ===")
    chunked = ChunkingPipeline(status_in="parsed", status_out="chunked").run()
    print(f"Nouveaux chunks: {chunked}")

    print("=== INDEXING ===")
    worker = IndexingWorker(worker_id="private-files-runner")
    total = 0
    while True:
        claimed = worker.run_once(limit=64, lease_seconds=120)
        if claimed == 0:
            break
        total += claimed
    print(f"Jobs indexing traités: {total}")

    print("=== TERMINÉ ===")


if __name__ == "__main__":
    main()