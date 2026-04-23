from typing import Optional, List
from pydantic import BaseModel


class ChunkingConfigRead(BaseModel):
    requested_mode: Optional[str] = None
    effective_mode: Optional[str] = None
    chunk_size: Optional[int] = None
    overlap: Optional[int] = None


class DocumentRead(BaseModel):
    id: str
    title: str
    filename: str
    status: str

    owner_user_id: Optional[str] = None
    path: Optional[str] = None
    file_type: Optional[str] = None
    scope: Optional[str] = None
    source_type: Optional[str] = None
    kb: Optional[str] = None

    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None

    text_content: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_error: Optional[str] = None

    chunking_config: Optional[ChunkingConfigRead] = None


class DocumentUploadResponse(BaseModel):
    document: DocumentRead