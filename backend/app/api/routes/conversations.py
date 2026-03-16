from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, get_current_user
from app.core.chat_history_repository import ChatHistoryRepository
from app.schemas.chat import ConversationCreate, ConversationRead

router = APIRouter(tags=["conversations"])


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(current_user: CurrentUser = Depends(get_current_user)):
    repo = ChatHistoryRepository()
    return repo.list_conversations(user_id=current_user.user_id)


@router.post("/conversations", response_model=ConversationRead)
def create_conversation(
    payload: ConversationCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = ChatHistoryRepository()
    return repo.create_conversation(
        user_id=current_user.user_id,
        title=payload.title or "Nouvelle conversation",
        metadata={
            "oid": current_user.oid,
            "tid": current_user.tid,
            "display_name": current_user.display_name,
            "preferred_username": current_user.preferred_username,
        },
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = ChatHistoryRepository()
    conversation = repo.get_conversation(
        conversation_id=conversation_id,
        user_id=current_user.user_id,
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    return conversation


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    repo = ChatHistoryRepository()
    deleted = repo.delete_conversation(
        conversation_id=conversation_id,
        user_id=current_user.user_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    return {"status": "deleted"}