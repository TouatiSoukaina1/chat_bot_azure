from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import CurrentUser, get_current_user
from app.core.database import DocumentRepository
from app.data_preparation.indexing.azure_search_indexer import AzureSearchIndexer
from app.schemas.documents import DocumentRead, DocumentUploadResponse
from app.services.document_ingestion_service import DocumentIngestionService

router = APIRouter(tags=["documents"])


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    service = DocumentIngestionService()
    document = await service.ingest_uploaded_file(
        upload_file=file,
        owner_user_id=current_user.user_id,
    )
    return {"document": document}


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = DocumentRepository()

    query = """
    SELECT * FROM c
    WHERE c.owner_user_id = @owner_user_id
    ORDER BY c._ts DESC
    """
    params = [{"name": "@owner_user_id", "value": current_user.user_id}]

    items = list(
        repo.docs_container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True,
        )
    )
    return items


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = DocumentRepository()

    query = """
    SELECT * FROM c
    WHERE c.id = @id AND c.owner_user_id = @owner_user_id
    """
    params = [
        {"name": "@id", "value": document_id},
        {"name": "@owner_user_id", "value": current_user.user_id},
    ]

    items = list(
        repo.docs_container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True,
        )
    )

    if not items:
        raise HTTPException(status_code=404, detail="Document introuvable")

    return items[0]


@router.get("/documents/{document_id}/chunks")
def get_document_chunks(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = DocumentRepository()

    query_doc = """
    SELECT * FROM c
    WHERE c.id = @id
      AND c.owner_user_id = @owner_user_id
    """
    doc_params = [
        {"name": "@id", "value": document_id},
        {"name": "@owner_user_id", "value": current_user.user_id},
    ]

    docs = list(
        repo.docs_container.query_items(
            query=query_doc,
            parameters=doc_params,
            enable_cross_partition_query=True,
        )
    )

    if not docs:
        raise HTTPException(status_code=404, detail="Document introuvable")

    chunks = repo.get_chunks_by_document(document_id=document_id)
    return chunks


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = DocumentRepository()
    indexer = AzureSearchIndexer()

    query_doc = """
    SELECT * FROM c
    WHERE c.id = @id
      AND c.owner_user_id = @owner_user_id
    """
    doc_params = [
        {"name": "@id", "value": document_id},
        {"name": "@owner_user_id", "value": current_user.user_id},
    ]

    docs = list(
        repo.docs_container.query_items(
            query=query_doc,
            parameters=doc_params,
            enable_cross_partition_query=True,
        )
    )

    if not docs:
        raise HTTPException(status_code=404, detail="Document introuvable")

    doc = docs[0]
    file_type = doc["file_type"]

    # 1) récupérer les chunks liés
    chunks = repo.get_chunks_by_document(document_id=document_id)
    chunk_ids = [chunk["id"] for chunk in chunks]

    # 2) supprimer les chunks de l'index Azure Search
    if chunk_ids:
        try:
            indexer.delete_documents(chunk_ids)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur suppression Azure Search: {exc}",
            )

    # 3) supprimer les chunks Cosmos
    for chunk in chunks:
        try:
            repo.chunks_container.delete_item(
                item=chunk["id"],
                partition_key=document_id,
            )
        except Exception:
            pass

    # 4) supprimer les work_items liés
    work_items = list(
        repo.work_container.query_items(
            query="""
            SELECT * FROM c
            WHERE c.document_id = @document_id
            """,
            parameters=[{"name": "@document_id", "value": document_id}],
            enable_cross_partition_query=True,
        )
    )

    for item in work_items:
        try:
            repo.work_container.delete_item(
                item=item["id"],
                partition_key=item["work_type"],
            )
        except Exception:
            pass

    # 5) supprimer le document lui-même
    try:
        repo.docs_container.delete_item(
            item=document_id,
            partition_key=file_type,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur suppression document: {exc}",
        )

    return {"status": "deleted"}