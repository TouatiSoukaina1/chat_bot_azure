from app.core import chat_history_repository as repo_module


class FakeContainer:
    def __init__(self, pk_field: str):
        self.pk_field = pk_field
        self.items = {}

    def _key(self, item):
        return (item["id"], item[self.pk_field])

    def upsert_item(self, item):
        self.items[self._key(item)] = dict(item)

    def read_item(self, item, partition_key):
        key = (item, partition_key)
        if key not in self.items:
            raise KeyError(f"Item not found: id={item}, pk={partition_key}")
        return dict(self.items[key])

    def delete_item(self, item, partition_key):
        key = (item, partition_key)
        if key in self.items:
            del self.items[key]

    def query_items(
        self,
        query,
        parameters=None,
        enable_cross_partition_query=False,
        partition_key=None,
        max_item_count=None,
    ):
        parameters = parameters or []
        params = {p["name"]: p["value"] for p in parameters}
        values = list(self.items.values())

        if "@id" in params and "@user_id" in params:
            values = [
                v
                for v in values
                if v.get("id") == params["@id"] and v.get("user_id") == params["@user_id"]
            ]
        elif "@user_id" in params and "@id" not in params:
            values = [v for v in values if v.get("user_id") == params["@user_id"]]
            values.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        if "@conversation_id" in params:
            values = [
                v
                for v in values
                if v.get("conversation_id") == params["@conversation_id"]
            ]
            if "ORDER BY c.created_at ASC" in query:
                values.sort(key=lambda x: x.get("created_at", ""))

        if "SELECT c.id FROM c" in query:
            values = [{"id": v["id"]} for v in values]

        if max_item_count is not None:
            values = values[:max_item_count]

        return list(values)


class FakeDatabase:
    def __init__(self):
        self.containers = {
            "conversations": FakeContainer(pk_field="user_id"),
            "messages": FakeContainer(pk_field="conversation_id"),
        }

    def get_container_client(self, name):
        return self.containers[name]


class FakeCosmosClient:
    def __init__(self, uri, credential=None):
        self.uri = uri
        self.credential = credential
        self.database = FakeDatabase()

    def get_database_client(self, database_name):
        return self.database


def make_repo(monkeypatch):
    monkeypatch.setattr(repo_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(repo_module, "CosmosClient", FakeCosmosClient)
    return repo_module.ChatHistoryRepository(
        uri="https://cosmos.test",
        database_name="db",
        container_conversations="conversations",
        container_messages="messages",
    )


def test_build_title_from_first_message_blank_and_truncated():
    assert repo_module.ChatHistoryRepository._build_title_from_first_message("   ") == "Nouvelle conversation"

    title = repo_module.ChatHistoryRepository._build_title_from_first_message(
        "a" * 50
    )
    assert title == ("a" * 36) + "..."


def test_create_conversation_persists_defaults_and_metadata(monkeypatch):
    repo = make_repo(monkeypatch)

    conversation = repo.create_conversation(
        user_id="tenant123:user123",
        title="Ma conversation",
        metadata={"display_name": "Soukaina"},
    )

    assert conversation["user_id"] == "tenant123:user123"
    assert conversation["title"] == "Ma conversation"
    assert conversation["message_count"] == 0
    assert conversation["kind"] == "conversation"
    assert conversation["metadata"]["display_name"] == "Soukaina"

    stored = repo.conversations_container.read_item(
        item=conversation["id"],
        partition_key="tenant123:user123",
    )
    assert stored["title"] == "Ma conversation"


def test_get_conversation_returns_hydrated_messages_sorted(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.conversations_container.upsert_item(
        {
            "id": "conv-1",
            "user_id": "tenant123:user123",
            "title": "Test",
            "created_at": "2026-01-01T10:00:00Z",
            "updated_at": "2026-01-01T10:00:00Z",
            "message_count": 2,
            "kind": "conversation",
            "metadata": {},
        }
    )

    repo.messages_container.upsert_item(
        {
            "id": "msg-2",
            "conversation_id": "conv-1",
            "user_id": "tenant123:user123",
            "role": "assistant",
            "content": "Réponse",
            "sources": [],
            "created_at": "2026-01-01T10:02:00Z",
            "kind": "message",
        }
    )
    repo.messages_container.upsert_item(
        {
            "id": "msg-1",
            "conversation_id": "conv-1",
            "user_id": "tenant123:user123",
            "role": "user",
            "content": "Question",
            "sources": [],
            "created_at": "2026-01-01T10:01:00Z",
            "kind": "message",
        }
    )

    conversation = repo.get_conversation("conv-1", "tenant123:user123")

    assert conversation is not None
    assert conversation["id"] == "conv-1"
    assert len(conversation["messages"]) == 2
    assert conversation["messages"][0]["id"] == "msg-1"
    assert conversation["messages"][1]["id"] == "msg-2"


def test_list_conversations_returns_only_current_user_sorted(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.conversations_container.upsert_item(
        {
            "id": "conv-1",
            "user_id": "tenant123:user123",
            "title": "Old",
            "created_at": "2026-01-01T10:00:00Z",
            "updated_at": "2026-01-01T10:00:00Z",
            "message_count": 0,
            "kind": "conversation",
            "metadata": {},
        }
    )
    repo.conversations_container.upsert_item(
        {
            "id": "conv-2",
            "user_id": "tenant123:user123",
            "title": "New",
            "created_at": "2026-01-01T11:00:00Z",
            "updated_at": "2026-01-01T11:00:00Z",
            "message_count": 0,
            "kind": "conversation",
            "metadata": {},
        }
    )
    repo.conversations_container.upsert_item(
        {
            "id": "conv-3",
            "user_id": "other:user",
            "title": "Other",
            "created_at": "2026-01-01T12:00:00Z",
            "updated_at": "2026-01-01T12:00:00Z",
            "message_count": 0,
            "kind": "conversation",
            "metadata": {},
        }
    )

    conversations = repo.list_conversations("tenant123:user123")

    assert len(conversations) == 2
    assert conversations[0]["id"] == "conv-2"
    assert conversations[1]["id"] == "conv-1"


def test_add_message_updates_count_and_first_title(monkeypatch):
    repo = make_repo(monkeypatch)

    conversation = repo.create_conversation(
        user_id="tenant123:user123",
        title="Nouvelle conversation",
        metadata={},
    )

    message = repo.add_message(
        conversation_id=conversation["id"],
        user_id="tenant123:user123",
        role="user",
        content="Voici un premier message très utile pour nommer la conversation",
        sources=[],
    )

    assert message["role"] == "user"
    assert message["conversation_id"] == conversation["id"]

    updated = repo.conversations_container.read_item(
        item=conversation["id"],
        partition_key="tenant123:user123",
    )

    assert updated["message_count"] == 1
    assert updated["title"].startswith("Voici un premier message")
    assert updated["updated_at"] == message["created_at"]


def test_add_message_raises_when_conversation_missing(monkeypatch):
    repo = make_repo(monkeypatch)

    try:
        repo.add_message(
            conversation_id="missing",
            user_id="tenant123:user123",
            role="user",
            content="hello",
        )
        assert False, "Une exception ValueError était attendue"
    except ValueError as exc:
        assert "Conversation introuvable" in str(exc)


def test_delete_conversation_deletes_messages_and_conversation(monkeypatch):
    repo = make_repo(monkeypatch)

    conversation = repo.create_conversation(
        user_id="tenant123:user123",
        title="To delete",
        metadata={},
    )

    repo.messages_container.upsert_item(
        {
            "id": "msg-1",
            "conversation_id": conversation["id"],
            "user_id": "tenant123:user123",
            "role": "user",
            "content": "hello",
            "sources": [],
            "created_at": "2026-01-01T10:01:00Z",
            "kind": "message",
        }
    )
    repo.messages_container.upsert_item(
        {
            "id": "msg-2",
            "conversation_id": conversation["id"],
            "user_id": "tenant123:user123",
            "role": "assistant",
            "content": "world",
            "sources": [],
            "created_at": "2026-01-01T10:02:00Z",
            "kind": "message",
        }
    )

    deleted = repo.delete_conversation(conversation["id"], "tenant123:user123")

    assert deleted is True
    assert repo.get_conversation(conversation["id"], "tenant123:user123") is None
    assert list(
        repo.messages_container.query_items(
            query="SELECT * FROM c WHERE c.conversation_id = @conversation_id",
            parameters=[{"name": "@conversation_id", "value": conversation["id"]}],
            partition_key=conversation["id"],
        )
    ) == []


def test_delete_conversation_returns_false_when_missing(monkeypatch):
    repo = make_repo(monkeypatch)

    deleted = repo.delete_conversation("missing", "tenant123:user123")

    assert deleted is False


def test_create_or_get_conversation_returns_existing_when_found(monkeypatch):
    repo = make_repo(monkeypatch)

    conversation = repo.create_conversation(
        user_id="tenant123:user123",
        title="Existing conversation",
        metadata={},
    )

    same = repo.create_or_get_conversation(
        user_id="tenant123:user123",
        conversation_id=conversation["id"],
    )

    assert same["id"] == conversation["id"]
    assert same["title"] == "Existing conversation"


def test_create_or_get_conversation_creates_new_when_missing(monkeypatch):
    repo = make_repo(monkeypatch)

    created = repo.create_or_get_conversation(
        user_id="tenant123:user123",
        conversation_id="missing-id",
        title="Nouvelle conversation",
    )

    assert created["id"] != "missing-id"
    assert created["title"] == "Nouvelle conversation"
    assert created["user_id"] == "tenant123:user123"