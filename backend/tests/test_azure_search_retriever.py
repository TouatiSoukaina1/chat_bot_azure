from app.data_preparation.retrieval import azure_search_retriever as retriever_module
import pytest 

class FakeEmbedder:
    def generate_embedding(self, query):
        return [0.11, 0.22, 0.33]


class NoneEmbedder:
    def generate_embedding(self, query):
        return None


class FakeSearchClient:
    def __init__(self):
        self.last_search_kwargs = None

    def search(self, **kwargs):
        self.last_search_kwargs = kwargs
        return [
            {
                "id": "chunk-1",
                "content": "Symptoms include fever and rash.",
                "@search.score": 0.98,
                "document_id": "doc-1",
                "chunk_order": 0,
                "source_path": "who/mpox.md",
                "file_type": "md",
            },
            {
                "id": "chunk-2",
                "content": "Treatment is mainly supportive care.",
                "@search.score": 0.95,
                "document_id": "doc-1",
                "chunk_order": 1,
                "source_path": "who/mpox.md",
                "file_type": "md",
            },
        ]


def make_retriever(monkeypatch, embedder, api_key=None, fake_client=None):
    fake_client = fake_client or FakeSearchClient()

    monkeypatch.setattr(retriever_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(retriever_module, "AzureKeyCredential", lambda key: object())
    monkeypatch.setattr(
        retriever_module,
        "SearchClient",
        lambda endpoint, index_name, credential: fake_client,
    )
    monkeypatch.setattr(
        retriever_module,
        "VectorizedQuery",
        lambda vector, k_nearest_neighbors, fields: {
            "vector": vector,
            "k_nearest_neighbors": k_nearest_neighbors,
            "fields": fields,
        },
    )

    retriever = retriever_module.AzureSearchRetriever(
        embedder=embedder,
        endpoint="https://search.test",
        index_name="my-index",
        api_key=api_key,
    )
    return retriever, fake_client


def test_init_raises_when_config_missing(monkeypatch):
    monkeypatch.delenv("AZURE_SEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_INDEX", raising=False)

    with pytest.raises(ValueError) as exc:
        retriever_module.AzureSearchRetriever(
            embedder=FakeEmbedder(),
            endpoint=None,
            index_name=None,
        )

    assert "Config Azure Search manquante" in str(exc.value)


def test_retrieve_returns_empty_for_blank_query(monkeypatch):
    retriever, _ = make_retriever(monkeypatch, embedder=FakeEmbedder())

    out = retriever.retrieve(query="   ")

    assert out == []


def test_retrieve_returns_empty_when_embedding_is_none(monkeypatch):
    retriever, _ = make_retriever(monkeypatch, embedder=NoneEmbedder())

    out = retriever.retrieve(query="What is mpox?")

    assert out == []


def test_retrieve_raises_when_vectorized_query_is_missing(monkeypatch):
    fake_client = FakeSearchClient()

    monkeypatch.setattr(retriever_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(retriever_module, "AzureKeyCredential", lambda key: object())
    monkeypatch.setattr(
        retriever_module,
        "SearchClient",
        lambda endpoint, index_name, credential: fake_client,
    )
    monkeypatch.setattr(retriever_module, "VectorizedQuery", None)

    retriever = retriever_module.AzureSearchRetriever(
        embedder=FakeEmbedder(),
        endpoint="https://search.test",
        index_name="my-index",
        api_key="fake-key",
    )

    try:
        retriever.retrieve(query="What is mpox?")
        assert False, "Une RuntimeError était attendue"
    except RuntimeError as exc:
        assert "VectorizedQuery indisponible" in str(exc)


def test_retrieve_returns_mapped_chunks_with_default_select(monkeypatch):
    retriever, fake_client = make_retriever(
        monkeypatch,
        embedder=FakeEmbedder(),
        api_key="fake-key",
    )

    out = retriever.retrieve(
        query="What are the symptoms?",
        top_k=2,
        filters="scope eq 'global'",
    )

    assert len(out) == 2
    assert out[0]["id"] == "chunk-1"
    assert out[0]["content"] == "Symptoms include fever and rash."
    assert out[0]["score"] == 0.98
    assert out[0]["document_id"] == "doc-1"
    assert out[0]["chunk_order"] == 0
    assert out[0]["source_path"] == "who/mpox.md"
    assert out[0]["file_type"] == "md"

    assert fake_client.last_search_kwargs["search_text"] == ""
    assert fake_client.last_search_kwargs["top"] == 2
    assert fake_client.last_search_kwargs["filter"] == "scope eq 'global'"
    select_fields = fake_client.last_search_kwargs["select"]

    assert "id" in select_fields
    assert "content" in select_fields
    assert "document_id" in select_fields
    assert "chunk_order" in select_fields
    assert "source_path" in select_fields
    assert "file_type" in select_fields

    vector_query = fake_client.last_search_kwargs["vector_queries"][0]
    assert vector_query["vector"] == [0.11, 0.22, 0.33]
    assert vector_query["k_nearest_neighbors"] == 2
    assert vector_query["fields"] == "content_vector"


def test_retrieve_uses_custom_select_fields(monkeypatch):
    retriever, fake_client = make_retriever(
        monkeypatch,
        embedder=FakeEmbedder(),
    )

    out = retriever.retrieve(
        query="What are the symptoms?",
        top_k=3,
        filters=None,
        select_fields=["id", "content"],
    )

    assert len(out) == 2
    assert fake_client.last_search_kwargs["top"] == 3
    assert fake_client.last_search_kwargs["filter"] is None
    assert fake_client.last_search_kwargs["select"] == ["id", "content"]