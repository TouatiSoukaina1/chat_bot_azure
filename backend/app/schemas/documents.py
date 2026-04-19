from typing import Literal, Optional
from pydantic import BaseModel


DocumentStatus = Literal[
    "processing",
    "parsed",
    "chunked",
    "indexed",
    "ready",
    "failed",
]


class DocumentRead(BaseModel):
    id: str
    owner_user_id: str
    filename: str
    title: str
    path: str
    file_type: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    status: DocumentStatus
    scope: Literal["global", "private"]
    source_type: str
    kb: str
    text_content: Optional[str] = None
    created_at: str
    updated_at: str
    last_error: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    document: DocumentRead