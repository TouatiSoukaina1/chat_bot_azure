from fastapi import APIRouter, Depends, HTTPException
import logging

from app.core.auth import CurrentUser, get_current_user
from app.core.chat_history_repository import ChatHistoryRepository
from app.core.rag_runtime import get_rag_service
from app.schemas.chat import ChatRequest, ChatResponse, SourceItem
from app.services.conversation_title_service import ConversationTitleService

logger = logging.getLogger("app.chat")

router = APIRouter(tags=["chat"])


def build_search_filter(user_id: str, knowledge_scope: str) -> str | None:
    """
    Retourne un filtre OData pour Azure AI Search.

    global  -> corpus WHO/global uniquement
    private -> documents privés utilisateur uniquement
    all     -> global + privé utilisateur
    """
    if knowledge_scope == "global":
        return "scope eq 'global'"

    if knowledge_scope == "private":
        return f"scope eq 'private' and owner_user_id eq '{user_id}'"

    if knowledge_scope == "all":
        return (
            f"(scope eq 'global') or "
            f"(scope eq 'private' and owner_user_id eq '{user_id}')"
        )

    return None


def normalize_sources(raw_sources: list[dict]) -> list[SourceItem]:
    normalized: list[SourceItem] = []

    for src in raw_sources:
        source_type = src.get("source_type") or "source"
        title = src.get("title") or "Source inconnue"
        excerpt = src.get("excerpt") or ""

        if source_type == "who":
            title = f"[WHO] {title}"
        elif source_type == "user_upload":
            title = f"[Privé] {title}"

        normalized.append(
            SourceItem(
                title=title,
                excerpt=excerpt,
            )
        )

    return normalized


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ChatResponse:
    question = payload.message.strip()
    if not question:
        logger.warning(
            "Message vide refusé | user_id=%s conversation_id=%s",
            current_user.user_id,
            payload.conversation_id,
        )
        raise HTTPException(status_code=400, detail="Le message est vide")

    repo = ChatHistoryRepository()
    rag = get_rag_service()

    logger.info(
        "Question reçue | user_id=%s scope=%s conversation_id=%s",
        current_user.user_id,
        payload.knowledge_scope,
        payload.conversation_id,
    )

    conversation = repo.create_or_get_conversation(
        user_id=current_user.user_id,
        conversation_id=payload.conversation_id,
    )

    existing_conversation = repo.get_conversation(
        conversation_id=conversation["id"],
        user_id=current_user.user_id,
    )
    history_messages = existing_conversation.get("messages", []) if existing_conversation else []
    is_first_user_message = len(history_messages) == 0

    repo.add_message(
        conversation_id=conversation["id"],
        user_id=current_user.user_id,
        role="user",
        content=question,
    )

    search_filter = build_search_filter(
        user_id=current_user.user_id,
        knowledge_scope=payload.knowledge_scope,
    )

    logger.info(
        "Filtre recherche construit | user_id=%s filter=%s",
        current_user.user_id,
        search_filter,
    )

    try:
        rag_output = rag.answer(
            question=question,
            history_messages=history_messages,
            top_k=5,
            filters=search_filter,
        )
        logger.info(
            "Réponse RAG générée | user_id=%s conversation_id=%s",
            current_user.user_id,
            conversation["id"],
        )
    except Exception as exc:
        logger.exception(
            "Erreur route chat | user_id=%s conversation_id=%s",
            current_user.user_id,
            conversation["id"],
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur RAG: {exc}",
        )

    answer = rag_output.get("answer", "Aucune réponse générée.")
    raw_sources = rag_output.get("sources", [])
    sources = normalize_sources(raw_sources)

    repo.add_message(
        conversation_id=conversation["id"],
        user_id=current_user.user_id,
        role="assistant",
        content=answer,
        sources=[source.model_dump() for source in sources],
    )

    logger.info(
        "Réponse assistant enregistrée | user_id=%s conversation_id=%s sources_count=%s",
        current_user.user_id,
        conversation["id"],
        len(sources),
    )

    if is_first_user_message and conversation.get("title") == "Nouvelle conversation":
        title_service = ConversationTitleService()
        generated_title = title_service.generate_title(question)

        repo.update_conversation_title(
            conversation_id=conversation["id"],
            user_id=current_user.user_id,
            title=generated_title,
        )

        logger.info(
            "Titre conversation généré | conversation_id=%s title=%s",
            conversation["id"],
            generated_title,
        )

    return ChatResponse(
        answer=answer,
        conversation_id=conversation["id"],
        sources=sources,
    )