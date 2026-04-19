from io import BytesIO

from app.api.routes import documents as documents_module
from .conftest import get_test_client


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

    def get_chunks_by_document(self, document_id: str):
        if document_id == "doc-1":
            return [
                {
                    "id": "doc-1_chunk_0",
                    "document_id": "doc-1",
                    "content": "chunk content",
                    "chunk_order": 0,
                    "scope": "private",
                    "owner_user_id": "tenant123:user123",
                    "source_type": "user_upload",
                }
            ]
        return []


class FakeIngestionService:
    async def ingest_uploaded_file(self, upload_file, owner_user_id: str):
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


def test_get_document_chunks_returns_chunks(monkeypatch):
    monkeypatch.setattr(documents_module, "DocumentRepository", FakeDocumentRepository)

    client = get_test_client()
    response = client.get("/api/documents/doc-1/chunks")

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["document_id"] == "doc-1"
    assert data[0]["scope"] == "private"


def test_upload_document_calls_ingestion_service(monkeypatch):
    monkeypatch.setattr(documents_module, "DocumentIngestionService", FakeIngestionService)

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