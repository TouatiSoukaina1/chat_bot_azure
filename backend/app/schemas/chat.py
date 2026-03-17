from pydantic import BaseModel
from typing import List, Optional, Literal


class SourceItem(BaseModel):
    title: str
    excerpt: str


class MessageRead(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    sources: List[SourceItem] = []


class ConversationRead(BaseModel):
    id: str
    title: str
    user_id: str
    created_at: str
    updated_at: str
    message_count: int
    messages: List[MessageRead] = []


class ConversationCreate(BaseModel):
    title: Optional[str] = "Nouvelle conversation"


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    knowledge_scope: Literal["global", "private", "all"] = "all"

class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: List[SourceItem] = []