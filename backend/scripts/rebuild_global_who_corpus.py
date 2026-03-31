import os
import time
from pathlib import Path

from dotenv import load_dotenv
from azure.core.exceptions import ResourceNotFoundError

from backend.app.core.database import DocumentRepository
from backend.app.data_preparation.indexing.azure_search_indexer import AzureSearchIndexer
from backend.app.data_preparation.pipelines.extraction_pipeline import run_extraction_from_directory
from backend.app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
from backend.app.workers.indexing_worker import IndexingWorker


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=True)


def cleanup_global_who_cosmos(repo: DocumentRepository):
    print("=== CLEANUP COSMOS: WHO GLOBAL ===")

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
        print("Aucun document WHO/global trouvé dans Cosmos.")
        return

    print(f"Documents trouvés: {len(docs)}")

    deleted_chunks = 0
    deleted_jobs = 0
    deleted_docs = 0

    for doc in docs:
        doc_id = doc["id"]
        file_type = doc["file_type"]

        # 1) chunks liés
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

        # 2) work_items d'indexing liés
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

        # 3) document
        repo.docs_container.delete_item(
            item=doc_id,
            partition_key=file_type,
        )
        deleted_docs += 1

        print(f"Supprimé doc={doc_id} | chunks={len(chunks)} | jobs={len(jobs)}")

    print("=== CLEANUP COSMOS TERMINÉ ===")
    print(f"Documents supprimés : {deleted_docs}")
    print(f"Chunks supprimés    : {deleted_chunks}")
    print(f"Jobs supprimés      : {deleted_jobs}")


def recreate_search_index():
    print("=== RECREATE AZURE SEARCH INDEX ===")
    indexer = AzureSearchIndexer()
    index_name = indexer.index_name

    try:
        indexer.index_client.delete_index(index_name)
        print(f"Index supprimé: {index_name}")
    except ResourceNotFoundError:
        print(f"Index inexistant, création directe: {index_name}")
    except Exception as e:
        print(f"Suppression index ignorée: {e}")

    embedding_dim = int(os.getenv("EMBEDDING_DIM", "1536"))
    indexer.create_or_update_index(embedding_dim=embedding_dim)
    print(f"Index prêt: {index_name}")


def run_extraction():
    print("=== EXTRACTION WHO GLOBAL ===")
    #raw_dir = ROOT / "data" / "raw" / "batch_txt"
    inserted = run_extraction_from_directory(
        raw_dir=ROOT / "data" / "raw" / "batch_txt",
        kb="who",
        scope="global",
        owner_user_id=None,
        source_type="who",
    )
    print(f"Documents extraits: {inserted}")
    return inserted


def run_chunking():
    print("=== CHUNKING ===")
    pipeline = ChunkingPipeline(status_in="parsed", status_out="chunked")
    inserted_chunks = pipeline.run()
    print(f"Nouveaux chunks: {inserted_chunks}")
    return inserted_chunks


def run_indexing():
    print("=== INDEXING ===")
    worker = IndexingWorker(worker_id="rebuild-global-who")

    total_claimed = 0

    while True:
        claimed = worker.run_once(limit=64, lease_seconds=120)
        if claimed == 0:
            break
        total_claimed += claimed
        time.sleep(1)

    print(f"Jobs d'indexing traités: {total_claimed}")
    return total_claimed


def main():
    repo = DocumentRepository()

    cleanup_global_who_cosmos(repo)
    recreate_search_index()
    run_extraction()
    run_chunking()
    run_indexing()

    print("=== REBUILD WHO GLOBAL TERMINÉ ===")


if __name__ == "__main__":
    main()