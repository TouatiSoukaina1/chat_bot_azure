from app.api.routes import documents as documents_module
from .conftest import get_test_client


class FakeDocsContainer:
    def __init__(self, items):
        self._items = items
        self.deleted_items = []

    def query_items(self, query, parameters, enable_cross_partition_query=True):
        params = {p["name"]: p["value"] for p in parameters}

        if "@owner_user_id" in params and "@id" not in params:
            return [
                item
                for item in self._items
                if item["owner_user_id"] == params["@owner_user_id"]
            ]

        if "@owner_user_id" in params and "@id" in params:
            return [
                item
                for item in self._items
                if item["owner_user_id"] == params["@owner_user_id"]
                and item["id"] == params["@id"]
            ]

        return []

    def delete_item(self, item, partition_key):
        self.deleted_items.append(
            {
                "item": item,
                "partition_key": partition_key,
            }
        )


class FakeChunksContainer:
    def __init__(self, fail_ids=None):
        self.deleted_items = []
        self.fail_ids = set(fail_ids or [])

    def delete_item(self, item, partition_key):
        if item in self.fail_ids:
            raise Exception("chunk delete failed")
        self.deleted_items.append(
            {
                "item": item,
                "partition_key": partition_key,
            }
        )


class FakeWorkContainer:
    def __init__(self, items=None, fail_ids=None):
        self._items = items or []
        self.deleted_items = []
        self.fail_ids = set(fail_ids or [])

    def query_items(self, query, parameters, enable_cross_partition_query=True):
        params = {p["name"]: p["value"] for p in parameters}
        document_id = params.get("@document_id")
        if document_id is None:
            return []
        return [item for item in self._items if item["document_id"] == document_id]

    def delete_item(self, item, partition_key):
        if item in self.fail_ids:
            raise Exception("work item delete failed")
        self.deleted_items.append(
            {
                "item": item,
                "partition_key": partition_key,
            }
        )


class FakeDocumentRepository:
    def __init__(self):
        self.docs = [
            {
                "id": "doc-1",
                "owner_user_id": "tenant123:user123",
                "filename": "autism.md",
                "title": "autism",
                "path": "user_upload/tenant123:user123/doc-1/autism.md",
                "file_type": "md",
                "mime_type": "text/markdown",
                "file_size": 1200,
                "status": "ready",
                "scope": "private",
                "source_type": "user_upload",
                "kb": "user",
                "text_content": "# Autism\n\nSome extracted content",
                "created_at": "2026-01-01T10:00:00Z",
                "updated_at": "2026-01-01T10:00:00Z",
                "last_error": None,
            },
            {
                "id": "doc-2",
                "owner_user_id": "other-tenant:other-user",
                "filename": "other.md",
                "title": "other",
                "path": "user_upload/other/doc-2/other.md",
                "file_type": "md",
                "mime_type": "text/markdown",
                "file_size": 800,
                "status": "ready",
                "scope": "private",
                "source_type": "user_upload",
                "kb": "user",
                "text_content": "# Other\n\nOther content",
                "created_at": "2026-01-01T10:00:00Z",
                "updated_at": "2026-01-01T10:00:00Z",
                "last_error": None,
            },
        ]
        self.docs_container = FakeDocsContainer(self.docs)
        self.chunks_container = FakeChunksContainer()
        self.work_container = FakeWorkContainer(
            items=[
                {
                    "id": "work-1",
                    "document_id": "doc-1",
                    "work_type": "indexing",
                },
                {
                    "id": "work-2",
                    "document_id": "doc-1",
                    "work_type": "embedding",
                },
            ]
        )

    def get_chunks_by_document(self, document_id: str):
        if document_id == "doc-1":
            return [
                {
                    "id": "doc-1_chunk_0",
                    "document_id": "doc-1",
                    "content": "chunk content 0",
                    "chunk_order": 0,
                    "scope": "private",
                    "owner_user_id": "tenant123:user123",
                    "source_type": "user_upload",
                },
                {
                    "id": "doc-1_chunk_1",
                    "document_id": "doc-1",
                    "content": "chunk content 1",
                    "chunk_order": 1,
                    "scope": "private",
                    "owner_user_id": "tenant123:user123",
                    "source_type": "user_upload",
                },
            ]
        return []


class FakeIngestionService:
    last_call = None

    async def ingest_uploaded_file(
        self,
        upload_file,
        owner_user_id: str,
        chunk_mode: str = "auto",
        chunk_size: int = 1500,
        overlap: int = 150,
    ):
        FakeIngestionService.last_call = {
            "upload_file": upload_file,
            "owner_user_id": owner_user_id,
            "chunk_mode": chunk_mode,
            "chunk_size": chunk_size,
            "overlap": overlap,
        }
        return {
            "id": "uploaded-doc-1",
            "owner_user_id": owner_user_id,
            "filename": upload_file.filename,
            "title": "uploaded file",
            "path": f"user_upload/{owner_user_id}/uploaded-doc-1/{upload_file.filename}",
            "file_type": "md",
            "mime_type": "text/markdown",
            "file_size": 42,
            "status": "ready",
            "scope": "private",
            "source_type": "user_upload",
            "kb": "user",
            "text_content": "# Uploaded\n\nHello world",
            "created_at": "2026-01-01T10:00:00Z",
            "updated_at": "2026-01-01T10:00:00Z",
            "last_error": None,
        }


class FakeAzureSearchIndexer:
    def __init__(self):
        self.deleted_document_ids = []

    def delete_documents(self, chunk_ids):
        self.deleted_document_ids.extend(chunk_ids)


class FailingAzureSearchIndexer:
    def delete_documents(self, chunk_ids):
        raise Exception("azure delete failed")


def test_list_documents_returns_only_current_user_documents(monkeypatch):
    monkeypatch.setattr(documents_module, "DocumentRepository", FakeDocumentRepository)

    client = get_test_client()
    response = client.get("/api/documents")

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == "doc-1"
    assert data[0]["owner_user_id"] == "tenant123:user123"


def test_get_document_returns_current_user_document(monkeypatch):
    monkeypatch.setattr(documents_module, "DocumentRepository", FakeDocumentRepository)

    client = get_test_client()
    response = client.get("/api/documents/doc-1")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "doc-1"
    assert data["filename"] == "autism.md"
    assert "text_content" in data


def test_get_document_returns_404_for_other_user_document(monkeypatch):
    monkeypatch.setattr(documents_module, "DocumentRepository", FakeDocumentRepository)

    client = get_test_client()
    response = client.get("/api/documents/doc-2")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document introuvable"


def test_get_document_returns_404_for_unknown_document(monkeypatch):
    monkeypatch.setattr(documents_module, "DocumentRepository", FakeDocumentRepository)

    client = get_test_client()
    response = client.get("/api/documents/doc-999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document introuvable"


def test_get_document_chunks_returns_chunks(monkeypatch):
    monkeypatch.setattr(documents_module, "DocumentRepository", FakeDocumentRepository)

    client = get_test_client()
    response = client.get("/api/documents/doc-1/chunks")

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert data[0]["document_id"] == "doc-1"
    assert data[0]["scope"] == "private"


def test_get_document_chunks_returns_404_for_unknown_document(monkeypatch):
    monkeypatch.setattr(documents_module, "DocumentRepository", FakeDocumentRepository)

    client = get_test_client()
    response = client.get("/api/documents/doc-999/chunks")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document introuvable"


def test_upload_document_calls_ingestion_service(monkeypatch):
    fake_service = FakeIngestionService()
    monkeypatch.setattr(documents_module, "DocumentIngestionService", lambda: fake_service)

    client = get_test_client()
    response = client.post(
        "/api/documents/upload",
        files={"file": ("test.md", b"# Hello\n\nThis is a test", "text/markdown")},
    )

    assert response.status_code == 200
    data = response.json()["document"]

    assert data["id"] == "uploaded-doc-1"
    assert data["owner_user_id"] == "tenant123:user123"
    assert data["scope"] == "private"
    assert data["source_type"] == "user_upload"


def test_upload_document_passes_chunking_parameters(monkeypatch):
    FakeIngestionService.last_call = None
    fake_service = FakeIngestionService()
    monkeypatch.setattr(documents_module, "DocumentIngestionService", lambda: fake_service)

    client = get_test_client()
    response = client.post(
        "/api/documents/upload",
        data={
            "chunk_mode": "markdown",
            "chunk_size": "800",
            "overlap": "80",
        },
        files={"file": ("test.md", b"# Hello\n\nThis is a test", "text/markdown")},
    )

    assert response.status_code == 200
    assert FakeIngestionService.last_call is not None
    assert FakeIngestionService.last_call["owner_user_id"] == "tenant123:user123"
    assert FakeIngestionService.last_call["chunk_mode"] == "markdown"
    assert FakeIngestionService.last_call["chunk_size"] == 800
    assert FakeIngestionService.last_call["overlap"] == 80


def test_delete_document_returns_404_for_unknown_document(monkeypatch):
    repo = FakeDocumentRepository()
    monkeypatch.setattr(documents_module, "DocumentRepository", lambda: repo)
    monkeypatch.setattr(
        documents_module,
        "AzureSearchIndexer",
        lambda: FakeAzureSearchIndexer(),
    )

    client = get_test_client()
    response = client.delete("/api/documents/doc-999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document introuvable"


def test_delete_document_deletes_chunks_work_items_and_document(monkeypatch):
    repo = FakeDocumentRepository()
    indexer = FakeAzureSearchIndexer()

    monkeypatch.setattr(documents_module, "DocumentRepository", lambda: repo)
    monkeypatch.setattr(documents_module, "AzureSearchIndexer", lambda: indexer)

    client = get_test_client()
    response = client.delete("/api/documents/doc-1")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}

    assert indexer.deleted_document_ids == ["doc-1_chunk_0", "doc-1_chunk_1"]

    assert len(repo.chunks_container.deleted_items) == 2
    assert repo.chunks_container.deleted_items[0]["item"] == "doc-1_chunk_0"
    assert repo.chunks_container.deleted_items[0]["partition_key"] == "doc-1"

    assert len(repo.work_container.deleted_items) == 2
    assert repo.work_container.deleted_items[0]["item"] == "work-1"
    assert repo.work_container.deleted_items[0]["partition_key"] == "indexing"
    assert repo.work_container.deleted_items[1]["item"] == "work-2"
    assert repo.work_container.deleted_items[1]["partition_key"] == "embedding"

    assert len(repo.docs_container.deleted_items) == 1
    assert repo.docs_container.deleted_items[0]["item"] == "doc-1"
    assert repo.docs_container.deleted_items[0]["partition_key"] == "md"


def test_delete_document_returns_500_when_azure_search_fails(monkeypatch):
    repo = FakeDocumentRepository()

    monkeypatch.setattr(documents_module, "DocumentRepository", lambda: repo)
    monkeypatch.setattr(
        documents_module,
        "AzureSearchIndexer",
        lambda: FailingAzureSearchIndexer(),
    )

    client = get_test_client()
    response = client.delete("/api/documents/doc-1")

    assert response.status_code == 500
    assert "Erreur suppression Azure Search" in response.json()["detail"]


def test_delete_document_continues_when_chunk_or_work_item_deletion_fails(monkeypatch):
    repo = FakeDocumentRepository()
    repo.chunks_container = FakeChunksContainer(fail_ids={"doc-1_chunk_1"})
    repo.work_container = FakeWorkContainer(
        items=[
            {"id": "work-1", "document_id": "doc-1", "work_type": "indexing"},
            {"id": "work-2", "document_id": "doc-1", "work_type": "embedding"},
        ],
        fail_ids={"work-2"},
    )
    indexer = FakeAzureSearchIndexer()

    monkeypatch.setattr(documents_module, "DocumentRepository", lambda: repo)
    monkeypatch.setattr(documents_module, "AzureSearchIndexer", lambda: indexer)

    client = get_test_client()
    response = client.delete("/api/documents/doc-1")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}

    assert indexer.deleted_document_ids == ["doc-1_chunk_0", "doc-1_chunk_1"]

    assert len(repo.chunks_container.deleted_items) == 1
    assert repo.chunks_container.deleted_items[0]["item"] == "doc-1_chunk_0"

    assert len(repo.work_container.deleted_items) == 1
    assert repo.work_container.deleted_items[0]["item"] == "work-1"

    assert len(repo.docs_container.deleted_items) == 1
    assert repo.docs_container.deleted_items[0]["item"] == "doc-1"


def test_delete_document_without_chunks_still_deletes_document(monkeypatch):
    class NoChunksRepo(FakeDocumentRepository):
        def get_chunks_by_document(self, document_id: str):
            return []

    repo = NoChunksRepo()
    indexer = FakeAzureSearchIndexer()

    monkeypatch.setattr(documents_module, "DocumentRepository", lambda: repo)
    monkeypatch.setattr(documents_module, "AzureSearchIndexer", lambda: indexer)

    client = get_test_client()
    response = client.delete("/api/documents/doc-1")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}
    assert indexer.deleted_document_ids == []
    assert len(repo.docs_container.deleted_items) == 1
    assert repo.docs_container.deleted_items[0]["item"] == "doc-1"