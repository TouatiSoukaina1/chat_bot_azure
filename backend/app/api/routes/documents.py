from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from app.core.auth import CurrentUser, get_current_user
from app.core.database import DocumentRepository
from app.data_preparation.indexing.azure_search_indexer import AzureSearchIndexer
from app.schemas.documents import DocumentRead, DocumentUploadResponse
from app.services.document_ingestion_service import DocumentIngestionService
import logging
logger = logging.getLogger("app.documents")

router = APIRouter(tags=["documents"])


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    chunk_mode: str = Form("auto"),
    chunk_size: int = Form(1500),
    overlap: int = Form(150),
    current_user: CurrentUser = Depends(get_current_user),
):
    logger.info(
        "Upload document demandé | user_id=%s filename=%s chunk_mode=%s chunk_size=%s overlap=%s",
        current_user.user_id,
        file.filename,
        chunk_mode,
        chunk_size,
        overlap,
    )

    service = DocumentIngestionService()
    document = await service.ingest_uploaded_file(
        upload_file=file,
        owner_user_id=current_user.user_id,
        chunk_mode=chunk_mode,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    logger.info(
        "Upload document terminé | user_id=%s document_id=%s filename=%s",
        current_user.user_id,
        document.get("id") if isinstance(document, dict) else getattr(document, "id", None),
        file.filename,
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

    logger.info(
        "Liste des documents récupérée | user_id=%s count=%s",
        current_user.user_id,
        len(items),
    )
    return items


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = DocumentRepository()

    logger.info(
        "Lecture document demandée | user_id=%s document_id=%s",
        current_user.user_id,
        document_id,
    )

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
        logger.warning(
            "Document introuvable | user_id=%s document_id=%s",
            current_user.user_id,
            document_id,
        )
        raise HTTPException(status_code=404, detail="Document introuvable")

    logger.info(
        "Document récupéré | user_id=%s document_id=%s",
        current_user.user_id,
        document_id,
    )
    return items[0]


@router.get("/documents/{document_id}/chunks")
def get_document_chunks(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = DocumentRepository()
    
    logger.info(
        "Lecture des chunks demandée | user_id=%s document_id=%s",
        current_user.user_id,
        document_id,
    )

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
        logger.warning(
            "Document introuvable pour récupération des chunks | user_id=%s document_id=%s",
            current_user.user_id,
            document_id,
        )
        raise HTTPException(status_code=404, detail="Document introuvable")

    chunks = repo.get_chunks_by_document(document_id=document_id)

    logger.info(
        "Chunks récupérés | user_id=%s document_id=%s chunk_count=%s",
        current_user.user_id,
        document_id,
        len(chunks),
    )
    return chunks


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = DocumentRepository()
    indexer = AzureSearchIndexer()

    logger.info(
        "Suppression demandée | user_id=%s document_id=%s",
        current_user.user_id,
        document_id,
    )

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
        logger.warning(
            "Document introuvable pour suppression | user_id=%s document_id=%s",
            current_user.user_id,
            document_id,
        )
        raise HTTPException(status_code=404, detail="Document introuvable")

    doc = docs[0]
    file_type = doc["file_type"]

    logger.info(
        "Document trouvé pour suppression | user_id=%s document_id=%s file_type=%s",
        current_user.user_id,
        document_id,
        file_type,
    )

    # 1) récupérer les chunks liés
    chunks = repo.get_chunks_by_document(document_id=document_id)
    chunk_ids = [chunk["id"] for chunk in chunks]

    logger.info(
        "Chunks associés récupérés | document_id=%s chunk_count=%s",
        document_id,
        len(chunk_ids),
    )

    # 2) supprimer les chunks de l'index Azure Search
    if chunk_ids:
        try:
            logger.info(
                "Suppression Azure Search démarrée | document_id=%s chunk_count=%s",
                document_id,
                len(chunk_ids),
            )
            indexer.delete_documents(chunk_ids)
            logger.info(
                "Suppression Azure Search terminée | document_id=%s",
                document_id,
            )
        except Exception as exc:
            logger.exception(
                "Erreur suppression Azure Search | document_id=%s error=%s",
                document_id,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Erreur suppression Azure Search: {exc}",
            )
    logger.info(
        "Suppression chunks | document_id=%s chunk_count=%s",
        document_id,
        len(chunks),
    )
    logger.info(
        "Suppression Azure Search | document_id=%s chunk_ids=%s",
        document_id,
        [chunk["id"] for chunk in chunks],
    )
    # 3) supprimer les chunks Cosmos
    for chunk in chunks:
        try:
            repo.chunks_container.delete_item(
                item=chunk["id"],
                partition_key=document_id,
            )
        except Exception as exc:
            logger.warning(
                "Échec suppression chunk Cosmos | document_id=%s chunk_id=%s error=%s",
                document_id,
                chunk["id"],
                exc,
            )
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

    logger.info(
        "Work items récupérés | document_id=%s work_item_count=%s",
        document_id,
        len(work_items),
    )

    for item in work_items:
        try:
            repo.work_container.delete_item(
                item=item["id"],
                partition_key=item["work_type"],
            )
        except Exception as exc:
            logger.warning(
                "Échec suppression work item | document_id=%s work_item_id=%s work_type=%s error=%s",
                document_id,
                item["id"],
                item["work_type"],
                exc,
            )
            pass

    # 5) supprimer le document lui-même
    try:
        repo.docs_container.delete_item(
            item=document_id,
            partition_key=file_type,
        )
    except Exception as exc:
        logger.exception(
            "Erreur suppression document Cosmos | user_id=%s document_id=%s error=%s",
            current_user.user_id,
            document_id,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur suppression document: {exc}",
        )
    logger.info(
        "Suppression document terminée | user_id=%s document_id=%s",
        current_user.user_id,
        document_id,
    )
    return {"status": "deleted"}