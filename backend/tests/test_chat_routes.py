from app.api.routes import chat as chat_module
from .conftest import get_test_client


class FakeChatHistoryRepository:
    added_messages = []
    created_calls = []
    get_calls = []

    def __init__(self):
        pass

    def create_or_get_conversation(self, user_id, conversation_id=None):
        FakeChatHistoryRepository.created_calls.append(
            {"user_id": user_id, "conversation_id": conversation_id}
        )
        return {"id": "conv-1"}

    def get_conversation(self, conversation_id, user_id):
        FakeChatHistoryRepository.get_calls.append(
            {"conversation_id": conversation_id, "user_id": user_id}
        )
        return {
            "id": "conv-1",
            "messages": [
                {"role": "user", "content": "Parle-moi du Mpox"},
                {"role": "assistant", "content": "Le Mpox est une maladie virale."},
            ],
        }

    def add_message(self, **kwargs):
        FakeChatHistoryRepository.added_messages.append(kwargs)


class FakeRagService:
    last_call = None

    def answer(self, question, history_messages=None, top_k=5, filters=None):
        FakeRagService.last_call = {
            "question": question,
            "history_messages": history_messages,
            "top_k": top_k,
            "filters": filters,
        }
        return {
            "answer": "Les symptômes incluent la fièvre et une éruption cutanée.",
            "sources": [
                {
                    "title": "mpox-who.md",
                    "excerpt": "Common symptoms include fever and rash.",
                    "source_type": "who",
                }
            ],
        }


def test_chat_returns_400_for_empty_message():
    client = get_test_client()

    response = client.post(
        "/api/chat",
        json={
            "message": "   ",
            "knowledge_scope": "all",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Le message est vide"


def test_chat_creates_conversation_and_returns_answer(monkeypatch):
    FakeChatHistoryRepository.added_messages = []
    FakeChatHistoryRepository.created_calls = []
    FakeChatHistoryRepository.get_calls = []
    FakeRagService.last_call = None

    monkeypatch.setattr(chat_module, "ChatHistoryRepository", FakeChatHistoryRepository)
    monkeypatch.setattr(chat_module, "get_rag_service", lambda: FakeRagService())

    client = get_test_client()

    response = client.post(
        "/api/chat",
        json={
            "message": "Quels sont les symptômes ?",
            "knowledge_scope": "private",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["conversation_id"] == "conv-1"
    assert data["answer"] == "Les symptômes incluent la fièvre et une éruption cutanée."
    assert len(data["sources"]) == 1
    assert data["sources"][0]["title"] == "[WHO] mpox-who.md"

    assert len(FakeChatHistoryRepository.added_messages) == 2
    assert FakeChatHistoryRepository.added_messages[0]["role"] == "user"
    assert FakeChatHistoryRepository.added_messages[0]["content"] == "Quels sont les symptômes ?"
    assert FakeChatHistoryRepository.added_messages[1]["role"] == "assistant"


def test_chat_passes_history_and_private_filter_to_rag(monkeypatch):
    FakeChatHistoryRepository.added_messages = []
    FakeRagService.last_call = None

    monkeypatch.setattr(chat_module, "ChatHistoryRepository", FakeChatHistoryRepository)
    monkeypatch.setattr(chat_module, "get_rag_service", lambda: FakeRagService())

    client = get_test_client()

    response = client.post(
        "/api/chat",
        json={
            "message": "Et le traitement ?",
            "conversation_id": "conv-1",
            "knowledge_scope": "private",
        },
    )

    assert response.status_code == 200
    assert FakeRagService.last_call is not None
    assert FakeRagService.last_call["question"] == "Et le traitement ?"
    assert len(FakeRagService.last_call["history_messages"]) == 2
    assert (
        FakeRagService.last_call["filters"]
        == "scope eq 'private' and owner_user_id eq 'tenant123:user123'"
    )


def test_chat_passes_all_scope_filter_to_rag(monkeypatch):
    FakeChatHistoryRepository.added_messages = []
    FakeRagService.last_call = None

    monkeypatch.setattr(chat_module, "ChatHistoryRepository", FakeChatHistoryRepository)
    monkeypatch.setattr(chat_module, "get_rag_service", lambda: FakeRagService())

    client = get_test_client()

    response = client.post(
        "/api/chat",
        json={
            "message": "Compare WHO et mes documents",
            "knowledge_scope": "all",
        },
    )

    assert response.status_code == 200
    assert (
        FakeRagService.last_call["filters"]
        == "(scope eq 'global') or (scope eq 'private' and owner_user_id eq 'tenant123:user123')"
    )