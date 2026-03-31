from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import CurrentUser, get_current_user
from app.core.database import DocumentRepository
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