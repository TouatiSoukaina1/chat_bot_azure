from app.data_preparation.indexing import azure_search_indexer as indexer_module
import pytest

class FakeIndexClient:
    def __init__(self):
        self.received_index = None

    def create_or_update_index(self, index):
        self.received_index = index


class FakeUploadResult:
    def __init__(self, succeeded, error_message=None):
        self.succeeded = succeeded
        self.error_message = error_message


class FakeSearchClient:
    def __init__(self, results=None, raise_on_upload=False):
        self.results = results or []
        self.raise_on_upload = raise_on_upload
        self.uploaded_documents = None

    def upload_documents(self, documents):
        self.uploaded_documents = documents
        if self.raise_on_upload:
            raise RuntimeError("boom")
        return self.results


def make_indexer(monkeypatch, fake_index_client=None, fake_search_client=None):
    fake_index_client = fake_index_client or FakeIndexClient()
    fake_search_client = fake_search_client or FakeSearchClient()

    monkeypatch.setattr(indexer_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(
        indexer_module,
        "SearchIndexClient",
        lambda endpoint, credential: fake_index_client,
    )
    monkeypatch.setattr(
        indexer_module,
        "SearchClient",
        lambda endpoint, index_name, credential: fake_search_client,
    )

    indexer = indexer_module.AzureSearchIndexer(
        endpoint="https://search.test",
        index_name="my-index",
    )
    return indexer, fake_index_client, fake_search_client


def test_init_raises_when_config_missing(monkeypatch):
    monkeypatch.delenv("AZURE_SEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_INDEX", raising=False)

    with pytest.raises(ValueError) as exc:
        indexer_module.AzureSearchIndexer(endpoint=None, index_name=None)

    assert "Config Azure Search manquante" in str(exc.value)


def test_create_or_update_index_builds_expected_schema(monkeypatch):
    indexer, fake_index_client, _ = make_indexer(monkeypatch)

    indexer.create_or_update_index(embedding_dim=1536)

    assert fake_index_client.received_index is not None
    idx = fake_index_client.received_index

    assert idx.name == "my-index"

    field_names = [field.name for field in idx.fields]
    assert "id" in field_names
    assert "content" in field_names
    assert "content_vector" in field_names
    assert "document_id" in field_names
    assert "chunk_order" in field_names
    assert "source_path" in field_names
    assert "file_type" in field_names
    assert "scope" in field_names
    assert "owner_user_id" in field_names
    assert "source_type" in field_names
    assert "kb" in field_names
    assert "doc_title" in field_names
    assert "section_title" in field_names
    assert "filename" in field_names

    vector_field = next(f for f in idx.fields if f.name == "content_vector")
    assert vector_field.vector_search_dimensions == 1536
    assert vector_field.vector_search_profile_name == "vprofile"

    assert idx.vector_search is not None
    assert len(idx.vector_search.algorithms) == 1
    assert idx.vector_search.algorithms[0].name == "hnsw"
    assert len(idx.vector_search.profiles) == 1
    assert idx.vector_search.profiles[0].name == "vprofile"

    assert idx.semantic_search is not None
    assert len(idx.semantic_search.configurations) == 1
    semcfg = idx.semantic_search.configurations[0]
    assert semcfg.name == "semcfg"
    assert semcfg.prioritized_fields.title_field.field_name == "doc_title"
    content_field_names = [f.field_name for f in semcfg.prioritized_fields.content_fields]
    assert "content" in content_field_names
    assert "section_title" in content_field_names


def test_upload_returns_empty_on_empty_input(monkeypatch):
    indexer, _, fake_search_client = make_indexer(monkeypatch)

    succeeded_ids, failed = indexer.upload([])

    assert succeeded_ids == []
    assert failed == []
    assert fake_search_client.uploaded_documents is None


def test_upload_normalizes_documents_and_collects_success_and_failure(monkeypatch):
    fake_search_client = FakeSearchClient(
        results=[
            FakeUploadResult(True),
            FakeUploadResult(False, error_message="upload failed"),
        ]
    )
    indexer, _, fake_search_client = make_indexer(
        monkeypatch,
        fake_search_client=fake_search_client,
    )

    docs = [
        {
            "id": "chunk-1",
            "content": "hello",
            "content_vector": [0.1, 0.2],
            "document_id": "doc-1",
            "chunk_order": 3,
            "source_path": "user_upload/u1/doc1.md",
            "file_type": "md",
            "scope": "private",
            "owner_user_id": "tenant:user",
            "source_type": "user_upload",
            "kb": "user",
            "doc_title": "Doc 1",
            "section_title": "Intro",
            "filename": "doc1.md",
        },
        {
            "id": "chunk-2",
            "content": "world",
            "content_vector": [0.3, 0.4],
            "document_id": "doc-2",
        },
    ]

    succeeded_ids, failed = indexer.upload(docs)

    assert succeeded_ids == ["chunk-1"]
    assert failed == [{"id": "chunk-2", "error": "upload failed"}]

    uploaded = fake_search_client.uploaded_documents
    assert uploaded is not None
    assert len(uploaded) == 2

    assert uploaded[0]["id"] == "chunk-1"
    assert uploaded[0]["scope"] == "private"
    assert uploaded[0]["owner_user_id"] == "tenant:user"
    assert uploaded[0]["source_type"] == "user_upload"
    assert uploaded[0]["kb"] == "user"
    assert uploaded[0]["doc_title"] == "Doc 1"
    assert uploaded[0]["section_title"] == "Intro"
    assert uploaded[0]["filename"] == "doc1.md"
    assert uploaded[0]["chunk_order"] == 3

    # valeurs par défaut
    assert uploaded[1]["id"] == "chunk-2"
    assert uploaded[1]["content"] == "world"
    assert uploaded[1]["document_id"] == "doc-2"
    assert uploaded[1]["chunk_order"] == 0
    assert uploaded[1]["source_path"] == ""
    assert uploaded[1]["file_type"] == ""
    assert uploaded[1]["scope"] == "global"
    assert uploaded[1]["owner_user_id"] == ""
    assert uploaded[1]["source_type"] == "who"
    assert uploaded[1]["kb"] == "who"
    assert uploaded[1]["doc_title"] == ""
    assert uploaded[1]["section_title"] == ""
    assert uploaded[1]["filename"] == ""


def test_upload_marks_whole_batch_failed_when_client_raises(monkeypatch):
    fake_search_client = FakeSearchClient(raise_on_upload=True)
    indexer, _, _ = make_indexer(
        monkeypatch,
        fake_search_client=fake_search_client,
    )

    docs = [
        {
            "id": "chunk-1",
            "content": "hello",
            "content_vector": [0.1, 0.2],
            "document_id": "doc-1",
        },
        {
            "id": "chunk-2",
            "content": "world",
            "content_vector": [0.3, 0.4],
            "document_id": "doc-2",
        },
    ]

    succeeded_ids, failed = indexer.upload(docs)

    assert succeeded_ids == []
    assert len(failed) == 2
    assert failed[0]["id"] == "chunk-1"
    assert failed[1]["id"] == "chunk-2"
    assert "upload_documents exception" in failed[0]["error"]


def test_upload_handles_multiple_batches(monkeypatch):
    fake_search_client = FakeSearchClient(
        results=[
            FakeUploadResult(True),
            FakeUploadResult(True),
        ]
    )
    indexer, _, fake_search_client = make_indexer(
        monkeypatch,
        fake_search_client=fake_search_client,
    )

    docs = [
        {"id": "chunk-1", "content": "a", "content_vector": [0.1], "document_id": "doc-1"},
        {"id": "chunk-2", "content": "b", "content_vector": [0.2], "document_id": "doc-2"},
    ]

    succeeded_ids, failed = indexer.upload(docs, batch_size=1)

    assert succeeded_ids == ["chunk-1", "chunk-2"]
    assert failed == []