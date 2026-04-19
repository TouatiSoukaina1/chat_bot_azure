from app.main import app
from app.core.auth import get_current_user
from app.api.routes import documents as documents_module
from app.api.routes import chat as chat_module
from .conftest import get_test_client, fake_current_user


class UserA:
    user_id = "tenant123:userA"
    oid = "userA"
    tid = "tenant123"
    display_name = "User A"
    preferred_username = "a@example.com"
    raw_claims = {}


class UserB:
    user_id = "tenant123:userB"
    oid = "userB"
    tid = "tenant123"
    display_name = "User B"
    preferred_username = "b@example.com"
    raw_claims = {}


def override_user(user_obj):
    def _inner():
        return user_obj
    return _inner


class FakeDocsContainer:
    def __init__(self, items):
        self._items = items

    def query_items(self, query, parameters, enable_cross_partition_query=True):
        params = {p["name"]: p["value"] for p in parameters}

        if "@owner_user_id" in params and "@id" not in params:
            return [item for item in self._items if item["owner_user_id"] == params["@owner_user_id"]]

        if "@owner_user_id" in params and "@id" in params:
            return [
                item
                for item in self._items
                if item["owner_user_id"] == params["@owner_user_id"] and item["id"] == params["@id"]
            ]

        return []


class FakeDocumentRepository:
    def __init__(self):
        self.docs_container = FakeDocsContainer(
            [
                {
                    "id": "doc-a",
                    "owner_user_id": "tenant123:userA",
                    "filename": "a.md",
                    "title": "Doc A",
                    "path": "user_upload/tenant123:userA/doc-a/a.md",
                    "file_type": "md",
                    "mime_type": "text/markdown",
                    "file_size": 100,
                    "status": "ready",
                    "scope": "private",
                    "source_type": "user_upload",
                    "kb": "user",
                    "text_content": "Content A",
                    "created_at": "2026-01-01T10:00:00Z",
                    "updated_at": "2026-01-01T10:00:00Z",
                    "last_error": None,
                },
                {
                    "id": "doc-b",
                    "owner_user_id": "tenant123:userB",
                    "filename": "b.md",
                    "title": "Doc B",
                    "path": "user_upload/tenant123:userB/doc-b/b.md",
                    "file_type": "md",
                    "mime_type": "text/markdown",
                    "file_size": 100,
                    "status": "ready",
                    "scope": "private",
                    "source_type": "user_upload",
                    "kb": "user",
                    "text_content": "Content B",
                    "created_at": "2026-01-01T10:00:00Z",
                    "updated_at": "2026-01-01T10:00:00Z",
                    "last_error": None,
                },
            ]
        )

    def get_chunks_by_document(self, document_id: str):
        return []


class FakeChatHistoryRepository:
    def create_or_get_conversation(self, user_id, conversation_id=None):
        return {"id": "conv-1"}

    def get_conversation(self, conversation_id, user_id):
        return {"id": "conv-1", "messages": []}

    def add_message(self, **kwargs):
        return None


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
            "answer": "Test answer",
            "sources": [],
        }


def test_documents_list_is_isolated_per_user(monkeypatch):
    monkeypatch.setattr(documents_module, "DocumentRepository", FakeDocumentRepository)

    app.dependency_overrides[get_current_user] = override_user(UserA())
    client = get_test_client()
    response_a = client.get("/api/documents")

    assert response_a.status_code == 200
    data_a = response_a.json()
    assert len(data_a) == 1
    assert data_a[0]["id"] == "doc-a"

    app.dependency_overrides[get_current_user] = override_user(UserB())
    client = get_test_client()
    response_b = client.get("/api/documents")

    assert response_b.status_code == 200
    data_b = response_b.json()
    assert len(data_b) == 1
    assert data_b[0]["id"] == "doc-b"

    app.dependency_overrides[get_current_user] = fake_current_user


def test_chat_private_scope_uses_current_user_id(monkeypatch):
    monkeypatch.setattr(chat_module, "ChatHistoryRepository", FakeChatHistoryRepository)
    monkeypatch.setattr(chat_module, "get_rag_service", lambda: FakeRagService())

    app.dependency_overrides[get_current_user] = override_user(UserB())
    client = get_test_client()

    response = client.post(
        "/api/chat",
        json={
            "message": "Question privée",
            "knowledge_scope": "private",
        },
    )

    assert response.status_code == 200
    assert (
        FakeRagService.last_call["filters"]
        == "scope eq 'private' and owner_user_id eq 'tenant123:userB'"
    )

    app.dependency_overrides[get_current_user] = fake_current_user