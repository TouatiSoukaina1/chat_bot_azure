from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, get_current_user
from app.core.chat_history_repository import ChatHistoryRepository
from app.schemas.chat import ChatRequest, ChatResponse, SourceItem

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ChatResponse:
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Le message est vide")

    repo = ChatHistoryRepository()

    conversation = repo.create_or_get_conversation(
        user_id=current_user.user_id,
        conversation_id=payload.conversation_id,
    )

    repo.add_message(
        conversation_id=conversation["id"],
        user_id=current_user.user_id,
        role="user",
        content=payload.message,
    )

    answer = f"Réponse simulée pour : {payload.message}"
    sources = [
        SourceItem(
            title="manuel_installation.pdf",
            excerpt="Extrait simulé d'un document source utilisé pour générer la réponse.",
        )
    ]

    repo.add_message(
        conversation_id=conversation["id"],
        user_id=current_user.user_id,
        role="assistant",
        content=answer,
        sources=[source.model_dump() for source in sources],
    )

    return ChatResponse(
        answer=answer,
        conversation_id=conversation["id"],
        sources=sources,
    )