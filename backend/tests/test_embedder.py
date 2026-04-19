import pytest

from app.data_preparation.processors import embedder as embedder_module


class FakeEmbeddingItem:
    def __init__(self, index, embedding):
        self.index = index
        self.embedding = embedding


class FakeEmbeddingsResponse:
    def __init__(self, embeddings):
        self.data = [
            FakeEmbeddingItem(index=i, embedding=emb)
            for i, emb in enumerate(embeddings)
        ]


class FakeEmbeddingsAPI:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, input, model):
        self.calls.append(
            {
                "input": input,
                "model": model,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeEmbeddingsResponse(outcome)


class FakeAzureOpenAIClient:
    def __init__(self, embeddings_api, init_kwargs=None):
        self.embeddings = embeddings_api
        self.init_kwargs = init_kwargs or {}


class FakeRateLimitError(Exception):
    pass


class FakeAPIError(Exception):
    pass


def make_embedder(
    monkeypatch,
    outcomes,
    *,
    endpoint="https://openai.test",
    api_version="2024-10-21",
    deployment_name="text-embedding-test",
    batch_size=16,
    max_retries=3,
    base_retry_delay=1.0,
    enable_cache=False,
    embedding_dimensions=None,
):
    embeddings_api = FakeEmbeddingsAPI(outcomes)
    holder = {}

    def fake_azure_openai(**kwargs):
        client = FakeAzureOpenAIClient(embeddings_api, init_kwargs=kwargs)
        holder["client"] = client
        return client

    monkeypatch.setattr(embedder_module, "AzureOpenAI", fake_azure_openai)
    monkeypatch.setattr(embedder_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(
        embedder_module,
        "get_bearer_token_provider",
        lambda credential, scope: "fake-token-provider",
    )

    emb = embedder_module.Embedder(
        endpoint=endpoint,
        api_version=api_version,
        deployment_name=deployment_name,
        batch_size=batch_size,
        max_retries=max_retries,
        base_retry_delay=base_retry_delay,
        enable_cache=enable_cache,
        embedding_dimensions=embedding_dimensions,
    )
    return emb, holder["client"], embeddings_api


def test_init_raises_when_config_missing(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", raising=False)

    with pytest.raises(ValueError) as exc:
        embedder_module.Embedder(
            endpoint=None,
            api_version=None,
            deployment_name=None,
        )

    assert "Config Azure OpenAI incomplète" in str(exc.value)


def test_init_clamps_batch_size_and_retry_delay(monkeypatch):
    emb, fake_client, _ = make_embedder(
        monkeypatch,
        outcomes=[],
        batch_size=99,
        base_retry_delay=0.0,
    )

    assert emb.batch_size == 16
    assert emb.base_retry_delay == 0.1
    assert fake_client.init_kwargs["azure_endpoint"] == "https://openai.test"
    assert fake_client.init_kwargs["api_version"] == "2024-10-21"
    assert fake_client.init_kwargs["azure_ad_token_provider"] == "fake-token-provider"


def test_generate_embedding_returns_none_for_blank_text(monkeypatch):
    emb, _, api = make_embedder(monkeypatch, outcomes=[])

    assert emb.generate_embedding("   ") is None
    assert api.calls == []


def test_generate_embedding_uses_cache_when_enabled(monkeypatch):
    emb, _, api = make_embedder(
        monkeypatch,
        outcomes=[[[0.1, 0.2, 0.3]]],
        enable_cache=True,
    )

    first = emb.generate_embedding("bonjour")
    second = emb.generate_embedding("bonjour")

    assert first == [0.1, 0.2, 0.3]
    assert second == [0.1, 0.2, 0.3]
    assert len(api.calls) == 1


def test_generate_embeddings_batches_requests(monkeypatch):
    emb, _, api = make_embedder(
        monkeypatch,
        outcomes=[
            [[0.1], [0.2]],
            [[0.3]],
        ],
        batch_size=2,
    )

    out = emb.generate_embeddings(["a", "b", "c"])

    assert out == [[0.1], [0.2], [0.3]]
    assert len(api.calls) == 2
    assert api.calls[0]["input"] == ["a", "b"]
    assert api.calls[1]["input"] == ["c"]


def test_generate_embedding_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(embedder_module, "RateLimitError", FakeRateLimitError)
    monkeypatch.setattr(embedder_module, "APIError", FakeAPIError)
    monkeypatch.setattr(embedder_module.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(embedder_module.random, "uniform", lambda a, b: 0.0)

    emb, _, api = make_embedder(
        monkeypatch,
        outcomes=[
            FakeRateLimitError("rate limited"),
            [[0.4, 0.5]],
        ],
        max_retries=2,
    )

    out = emb.generate_embedding("test")

    assert out == [0.4, 0.5]
    assert len(api.calls) == 2

    stats = emb.get_statistics()
    assert stats["total_api_calls"] == 1
    assert stats["total_items"] == 1
    assert stats["total_failed"] == 0
    assert stats["retry_rate"] == 1.0


def test_generate_embedding_returns_none_after_retry_exhausted(monkeypatch):
    monkeypatch.setattr(embedder_module, "RateLimitError", FakeRateLimitError)
    monkeypatch.setattr(embedder_module.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(embedder_module.random, "uniform", lambda a, b: 0.0)

    emb, _, api = make_embedder(
        monkeypatch,
        outcomes=[
            FakeRateLimitError("retry 1"),
            FakeRateLimitError("retry 2"),
        ],
        max_retries=1,
    )

    out = emb.generate_embedding("test")

    assert out is None
    assert len(api.calls) == 2

    stats = emb.get_statistics()
    assert stats["total_failed"] == 1
    assert stats["retry_rate"] == 1.0
    assert stats["last_error"] is not None


def test_generate_embeddings_returns_none_list_on_unexpected_error(monkeypatch):
    emb, _, api = make_embedder(
        monkeypatch,
        outcomes=[
            RuntimeError("unexpected boom"),
        ],
        batch_size=2,
    )

    out = emb.generate_embeddings(["a", "b"])

    assert out == [None, None]
    assert len(api.calls) == 1

    stats = emb.get_statistics()
    assert stats["total_failed"] == 2
    assert stats["last_error"] == "unexpected boom"


def test_generate_embeddings_marks_missing_embedding_as_none(monkeypatch):
    emb, _, _ = make_embedder(
        monkeypatch,
        outcomes=[
            [[0.1, 0.2], None],
        ],
        batch_size=2,
        embedding_dimensions=2,
    )

    out = emb.generate_embeddings(["a", "b"])

    assert out == [[0.1, 0.2], None]

    stats = emb.get_statistics()
    assert stats["total_failed"] == 1
    assert stats["total_items"] == 2