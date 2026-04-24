import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from azure.core.exceptions import ResourceNotFoundError

from app.core.database import DocumentRepository
from app.data_preparation.indexing.azure_search_indexer import AzureSearchIndexer
from app.data_preparation.pipelines.extraction_pipeline import run_global_who_extraction
from app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
from app.workers.indexing_worker import IndexingWorker

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("backend.scripts.rebuild_global_who_corpus")


def cleanup_global_who_cosmos(repo: DocumentRepository):
    logger.info("=== CLEANUP COSMOS: WHO GLOBAL ===")

    docs = list(
        repo.docs_container.query_items(
            query="""
            SELECT * FROM c
            WHERE
                (IS_DEFINED(c.kb) AND c.kb = @kb)
                OR
                (IS_DEFINED(c.source_type) AND c.source_type = @source_type)
                OR
                (IS_DEFINED(c.scope) AND c.scope = @scope)
            """,
            parameters=[
                {"name": "@kb", "value": "who"},
                {"name": "@source_type", "value": "who"},
                {"name": "@scope", "value": "global"},
            ],
            enable_cross_partition_query=True,
        )
    )

    if not docs:
        logger.info("Aucun document WHO/global trouvé dans Cosmos.")
        return

    logger.info("Documents trouvés: %s", len(docs))

    deleted_chunks = 0
    deleted_jobs = 0
    deleted_docs = 0

    for doc in docs:
        doc_id = doc["id"]
        file_type = doc["file_type"]

        chunks = list(
            repo.chunks_container.query_items(
                query="SELECT c.id FROM c WHERE c.document_id = @doc_id",
                parameters=[{"name": "@doc_id", "value": doc_id}],
                partition_key=doc_id,
            )
        )

        for ch in chunks:
            repo.chunks_container.delete_item(
                item=ch["id"],
                partition_key=doc_id,
            )
            deleted_chunks += 1

        jobs = list(
            repo.work_container.query_items(
                query="""
                SELECT * FROM c
                WHERE c.work_type = @wt
                  AND c.document_id = @doc_id
                """,
                parameters=[
                    {"name": "@wt", "value": "indexing"},
                    {"name": "@doc_id", "value": doc_id},
                ],
                partition_key="indexing",
            )
        )

        for job in jobs:
            repo.work_container.delete_item(
                item=job["id"],
                partition_key="indexing",
            )
            deleted_jobs += 1

        repo.docs_container.delete_item(
            item=doc_id,
            partition_key=file_type,
        )
        deleted_docs += 1

        logger.info(
            "Supprimé doc=%s | chunks=%s | jobs=%s",
            doc_id,
            len(chunks),
            len(jobs),
        )

    logger.info("=== CLEANUP COSMOS TERMINÉ ===")
    logger.info("Documents supprimés : %s", deleted_docs)
    logger.info("Chunks supprimés    : %s", deleted_chunks)
    logger.info("Jobs supprimés      : %s", deleted_jobs)


def recreate_search_index():
    logger.info("=== RECREATE AZURE SEARCH INDEX ===")
    indexer = AzureSearchIndexer()
    index_name = indexer.index_name

    try:
        indexer.index_client.delete_index(index_name)
        logger.info("Index supprimé: %s", index_name)
    except ResourceNotFoundError:
        logger.info("Index inexistant, création directe: %s", index_name)
    except Exception as e:
        logger.warning("Suppression index ignorée: %s", e)

    embedding_dim = int(os.getenv("EMBEDDING_DIM", "1536"))
    indexer.create_or_update_index(embedding_dim=embedding_dim)
    logger.info("Index prêt: %s", index_name)


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
    worker = IndexingWorker(worker_id="rebuild-global-who")

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
    logger.info("=== START REBUILD WHO GLOBAL ===")
    repo = DocumentRepository()

    cleanup_global_who_cosmos(repo)
    recreate_search_index()
    run_extraction()
    run_chunking()
    run_indexing()

    logger.info("=== REBUILD WHO GLOBAL TERMINÉ ===")


if __name__ == "__main__":
    main()