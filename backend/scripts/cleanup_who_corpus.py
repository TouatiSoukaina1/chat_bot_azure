from pathlib import Path
from dotenv import load_dotenv

from app.core.database import DocumentRepository

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=True)


def main():
    repo = DocumentRepository()

    print("=== CLEANUP WHO CORPUS (COSMOS ONLY) ===")

    # On cible le corpus WHO ancien + nouveau
    docs = list(
        repo.docs_container.query_items(
            query="""
            SELECT * FROM c
            WHERE
                (IS_DEFINED(c.kb) AND c.kb = @kb)
                OR
                (IS_DEFINED(c.source_type) AND c.source_type = @source_type)
            """,
            parameters=[
                {"name": "@kb", "value": "who"},
                {"name": "@source_type", "value": "who"},
            ],
            enable_cross_partition_query=True,
        )
    )

    if not docs:
        print("Aucun document WHO trouvé.")
        return

    print(f"Documents WHO trouvés: {len(docs)}")

    deleted_chunks = 0
    deleted_jobs = 0
    deleted_docs = 0

    for doc in docs:
        doc_id = doc["id"]
        file_type = doc["file_type"]

        # 1) supprimer les chunks liés
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

        # 2) supprimer les work_items d'indexing liés
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

        # 3) supprimer le document
        repo.docs_container.delete_item(
            item=doc_id,
            partition_key=file_type,
        )
        deleted_docs += 1

        print(f"Supprimé: doc={doc_id} | chunks={len(chunks)} | jobs={len(jobs)}")

    print("=== CLEANUP TERMINÉ ===")
    print(f"Documents supprimés : {deleted_docs}")
    print(f"Chunks supprimés    : {deleted_chunks}")
    print(f"Jobs supprimés      : {deleted_jobs}")


if __name__ == "__main__":
    main()