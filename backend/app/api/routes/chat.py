from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, get_current_user
from app.core.chat_history_repository import ChatHistoryRepository
from app.core.rag_runtime import get_rag_service
from app.schemas.chat import ChatRequest, ChatResponse, SourceItem

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ChatResponse:
    question = payload.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Le message est vide")

    repo = ChatHistoryRepository()
    rag = get_rag_service()

    conversation = repo.create_or_get_conversation(
        user_id=current_user.user_id,
        conversation_id=payload.conversation_id,
    )

    # Récupération de l'historique AVANT ajout du nouveau message
    existing_conversation = repo.get_conversation(
        conversation_id=conversation["id"],
        user_id=current_user.user_id,
    )
    history_messages = existing_conversation.get("messages", []) if existing_conversation else []

    # Sauvegarde du message user
    repo.add_message(
        conversation_id=conversation["id"],
        user_id=current_user.user_id,
        role="user",
        content=question,
    )

    try:
        rag_output = rag.answer(
            question=question,
            history_messages=history_messages,
            top_k=5,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur RAG conversationnel: {exc}",
        )

    answer = rag_output.get("answer", "Aucune réponse générée.")
    raw_sources = rag_output.get("sources", [])

    sources = [
        SourceItem(
            title=src.get("title", "source_inconnue"),
            excerpt=src.get("excerpt", ""),
        )
        for src in raw_sources
    ]

    repo.add_message(
        conversation_id=conversation["id"],
        user_id=current_user.user_id,
        role="assistant",
        content=answer,
        sources=[src.model_dump() for src in sources],
    )

    return ChatResponse(
        answer=answer,
        conversation_id=conversation["id"],
        sources=sources,
    )