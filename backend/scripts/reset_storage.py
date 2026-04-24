import argparse
import logging
import os
from collections import defaultdict

from dotenv import load_dotenv

from app.core.database import DocumentRepository
from app.data_preparation.indexing.azure_search_indexer import AzureSearchIndexer

load_dotenv()

logger = logging.getLogger("scripts.reset_storage")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def collect_all_chunks(repo: DocumentRepository) -> list[dict]:
    chunks = list(
        repo.chunks_container.query_items(
            query="SELECT * FROM c",
            parameters=[],
            enable_cross_partition_query=True,
        )
    )
    return chunks


def collect_all_documents(repo: DocumentRepository) -> list[dict]:
    docs = list(
        repo.docs_container.query_items(
            query="SELECT * FROM c",
            parameters=[],
            enable_cross_partition_query=True,
        )
    )
    return docs


def collect_all_work_items(repo: DocumentRepository) -> list[dict]:
    items = list(
        repo.work_container.query_items(
            query="SELECT * FROM c",
            parameters=[],
            enable_cross_partition_query=True,
        )
    )
    return items


def delete_all_search_documents(indexer: AzureSearchIndexer, batch_size: int = 500) -> int:
    logger.info("Lecture des ids Azure Search...")
    results = indexer.search_client.search(
        search_text="*",
        select=["id"],
        top=1000,
    )

    ids = []
    for item in results:
        doc_id = item.get("id")
        if doc_id:
            ids.append(doc_id)

    if not ids:
        logger.info("Aucun document trouvé dans Azure Search.")
        return 0

    logger.info("Suppression Azure Search | count=%s", len(ids))

    deleted = 0
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
        docs = [{"id": doc_id} for doc_id in batch_ids]
        result = indexer.search_client.delete_documents(documents=docs)

        batch_deleted = sum(1 for r in result if getattr(r, "succeeded", False))
        deleted += batch_deleted

        logger.info(
            "Suppression Azure Search batch | requested=%s deleted=%s",
            len(batch_ids),
            batch_deleted,
        )

    return deleted


def delete_all_chunks(repo: DocumentRepository) -> int:
    chunks = collect_all_chunks(repo)
    if not chunks:
        logger.info("Aucun chunk à supprimer.")
        return 0

    deleted = 0
    for chunk in chunks:
        try:
            repo.chunks_container.delete_item(
                item=chunk["id"],
                partition_key=chunk["document_id"],
            )
            deleted += 1
        except Exception:
            logger.exception(
                "Erreur suppression chunk | chunk_id=%s document_id=%s",
                chunk.get("id"),
                chunk.get("document_id"),
            )

    logger.info("Chunks supprimés | count=%s", deleted)
    return deleted


def delete_all_documents(repo: DocumentRepository) -> int:
    docs = collect_all_documents(repo)
    if not docs:
        logger.info("Aucun document à supprimer.")
        return 0

    deleted = 0
    for doc in docs:
        try:
            repo.docs_container.delete_item(
                item=doc["id"],
                partition_key=doc["file_type"],
            )
            deleted += 1
        except Exception:
            logger.exception(
                "Erreur suppression document | document_id=%s file_type=%s",
                doc.get("id"),
                doc.get("file_type"),
            )

    logger.info("Documents supprimés | count=%s", deleted)
    return deleted


def delete_all_work_items(repo: DocumentRepository) -> int:
    items = collect_all_work_items(repo)
    if not items:
        logger.info("Aucun work item à supprimer.")
        return 0

    deleted = 0
    for item in items:
        try:
            repo.work_container.delete_item(
                item=item["id"],
                partition_key=item["work_type"],
            )
            deleted += 1
        except Exception:
            logger.exception(
                "Erreur suppression work item | work_id=%s work_type=%s",
                item.get("id"),
                item.get("work_type"),
            )

    logger.info("Work items supprimés | count=%s", deleted)
    return deleted


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Purge Cosmos (documents/chunks/work_items) + Azure Search."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Exécute la purge sans confirmation interactive.",
    )
    parser.add_argument(
        "--skip-search",
        action="store_true",
        help="Ne supprime pas les documents dans Azure Search.",
    )
    args = parser.parse_args()

    if not args.yes:
        confirm = input(
            "⚠️ Cette opération va supprimer TOUS les documents, chunks, work_items et indexes. Continuer ? (yes/no): "
        ).strip().lower()
        if confirm != "yes":
            logger.info("Purge annulée.")
            return

    repo = DocumentRepository()

    docs = collect_all_documents(repo)
    chunks = collect_all_chunks(repo)
    work_items = collect_all_work_items(repo)

    logger.info(
        "Etat avant purge | documents=%s chunks=%s work_items=%s",
        len(docs),
        len(chunks),
        len(work_items),
    )

    deleted_search = 0
    if not args.skip_search:
        indexer = AzureSearchIndexer()
        deleted_search = delete_all_search_documents(indexer=indexer)

    deleted_chunks = delete_all_chunks(repo)
    deleted_work_items = delete_all_work_items(repo)
    deleted_docs = delete_all_documents(repo)

    logger.info(
        "Purge terminée | search=%s chunks=%s work_items=%s documents=%s",
        deleted_search,
        deleted_chunks,
        deleted_work_items,
        deleted_docs,
    )


if __name__ == "__main__":
    main()