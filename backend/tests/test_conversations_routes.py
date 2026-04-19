from app.api.routes import conversations as conversations_module
from .conftest import get_test_client


class FakeChatHistoryRepository:
    def __init__(self):
        self.created = []
        self.deleted = []

    def list_conversations(self, user_id: str):
        return [
            {
                "id": "conv-1",
                "title": "Première conversation",
                "user_id": user_id,
                "message_count": 0,
                "messages": [],
                "created_at": "2026-01-01T10:00:00Z",
                "updated_at": "2026-01-01T10:00:00Z",
            },
            {
                "id": "conv-2",
                "title": "Deuxième conversation",
                "user_id": user_id,
                "message_count": 1,
                "messages": [
                    {
                        "id": "msg-1",
                        "role": "user",
                        "content": "Bonjour",
                        "created_at": "2026-01-01T11:00:00Z",
                        "sources": [],
                    }
                ],
                "created_at": "2026-01-01T11:00:00Z",
                "updated_at": "2026-01-01T11:05:00Z",
            },
        ]

    def create_conversation(self, user_id: str, title: str, metadata: dict):
        self.created.append(
            {
                "user_id": user_id,
                "title": title,
                "metadata": metadata,
            }
        )
        return {
            "id": "conv-new",
            "title": title,
            "user_id": user_id,
            "message_count": 0,
            "messages": [],
            "created_at": "2026-01-02T09:00:00Z",
            "updated_at": "2026-01-02T09:00:00Z",
        }

    def get_conversation(self, conversation_id: str, user_id: str):
        if conversation_id == "conv-1":
            return {
                "id": "conv-1",
                "title": "Première conversation",
                "user_id": user_id,
                "message_count": 2,
                "messages": [
                    {
                        "id": "msg-1",
                        "role": "user",
                        "content": "Question test",
                        "created_at": "2026-01-01T10:01:00Z",
                        "sources": [],
                    },
                    {
                        "id": "msg-2",
                        "role": "assistant",
                        "content": "Réponse test",
                        "created_at": "2026-01-01T10:02:00Z",
                        "sources": [],
                    },
                ],
                "created_at": "2026-01-01T10:00:00Z",
                "updated_at": "2026-01-01T10:05:00Z",
            }
        return None

    def delete_conversation(self, conversation_id: str, user_id: str):
        self.deleted.append(
            {
                "conversation_id": conversation_id,
                "user_id": user_id,
            }
        )
        return conversation_id == "conv-1"


def test_list_conversations_returns_current_user_conversations(monkeypatch):
    monkeypatch.setattr(
        conversations_module,
        "ChatHistoryRepository",
        FakeChatHistoryRepository,
    )

    client = get_test_client()
    response = client.get("/api/conversations")

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == "conv-1"
    assert data[0]["title"] == "Première conversation"
    assert data[0]["message_count"] == 0


def test_create_conversation_returns_new_conversation(monkeypatch):
    monkeypatch.setattr(
        conversations_module,
        "ChatHistoryRepository",
        FakeChatHistoryRepository,
    )

    client = get_test_client()
    response = client.post("/api/conversations", json={})

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "conv-new"
    assert data["title"] == "Nouvelle conversation"
    assert data["message_count"] == 0
    assert data["messages"] == []


def test_create_conversation_with_custom_title(monkeypatch):
    monkeypatch.setattr(
        conversations_module,
        "ChatHistoryRepository",
        FakeChatHistoryRepository,
    )

    client = get_test_client()
    response = client.post("/api/conversations", json={"title": "Mon titre"})

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "conv-new"
    assert data["title"] == "Mon titre"


def test_get_conversation_returns_existing_conversation(monkeypatch):
    monkeypatch.setattr(
        conversations_module,
        "ChatHistoryRepository",
        FakeChatHistoryRepository,
    )

    client = get_test_client()
    response = client.get("/api/conversations/conv-1")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "conv-1"
    assert data["title"] == "Première conversation"
    assert data["message_count"] == 2
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"


def test_get_conversation_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(
        conversations_module,
        "ChatHistoryRepository",
        FakeChatHistoryRepository,
    )

    client = get_test_client()
    response = client.get("/api/conversations/unknown-conv")

    assert response.status_code == 404
    assert "introuvable" in response.json()["detail"].lower()


def test_delete_conversation_returns_success(monkeypatch):
    monkeypatch.setattr(
        conversations_module,
        "ChatHistoryRepository",
        FakeChatHistoryRepository,
    )

    client = get_test_client()
    response = client.delete("/api/conversations/conv-1")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "deleted"


def test_delete_conversation_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(
        conversations_module,
        "ChatHistoryRepository",
        FakeChatHistoryRepository,
    )

    client = get_test_client()
    response = client.delete("/api/conversations/unknown-conv")

    assert response.status_code == 404
    assert "introuvable" in response.json()["detail"].lower()