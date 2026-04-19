from app.services import rag_chat_service as rag_module
import pytest

class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.outputs.pop(0)
        return FakeResponse(content)


class FakeChat:
    def __init__(self, outputs):
        self.completions = FakeCompletions(outputs)


class FakeAzureOpenAI:
    def __init__(self, outputs=None, **kwargs):
        self.init_kwargs = kwargs
        self.chat = FakeChat(outputs or [])


class FakeRetriever:
    def __init__(self, chunks=None):
        self.chunks = chunks or []
        self.calls = []

    def retrieve(self, query, top_k=5, filters=None):
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "filters": filters,
            }
        )
        return self.chunks


def make_service(
    monkeypatch,
    retriever=None,
    llm_outputs=None,
    endpoint="https://openai.test",
    deployment="gpt-test",
    api_key="fake-key",
):
    fake_client = FakeAzureOpenAI(
        outputs=llm_outputs or [],
        api_key=api_key,
        api_version="2024-10-21",
        azure_endpoint=endpoint,
    )

    monkeypatch.setattr(rag_module, "AzureOpenAI", lambda **kwargs: fake_client)
    monkeypatch.setattr(rag_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(
        rag_module,
        "get_bearer_token_provider",
        lambda credential, scope: "fake-token-provider",
    )

    service = rag_module.RagChatService(
        retriever=retriever or FakeRetriever(),
        endpoint=endpoint,
        chat_deployment=deployment,
        api_key=api_key,
    )
    return service, fake_client


def test_init_raises_when_config_missing(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_CHAT_DEPLOYMENT", raising=False)

    with pytest.raises(ValueError) as exc:
        rag_module.RagChatService(
            retriever=FakeRetriever(),
            endpoint=None,
            chat_deployment=None,
            api_key="fake-key",
        )

    assert "Config Azure OpenAI manquante" in str(exc.value)


def test_init_uses_api_key_auth(monkeypatch):
    fake_client = FakeAzureOpenAI(outputs=[])

    monkeypatch.setattr(rag_module, "AzureOpenAI", lambda **kwargs: fake_client)

    service = rag_module.RagChatService(
        retriever=FakeRetriever(),
        endpoint="https://openai.test",
        chat_deployment="gpt-test",
        api_key="fake-key",
    )

    assert service.client is fake_client


def test_init_uses_keyless_auth(monkeypatch):
    fake_client = FakeAzureOpenAI(outputs=[])

    monkeypatch.setattr(rag_module, "AzureOpenAI", lambda **kwargs: fake_client)
    monkeypatch.setattr(rag_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(
        rag_module,
        "get_bearer_token_provider",
        lambda credential, scope: "fake-token-provider",
    )

    service = rag_module.RagChatService(
        retriever=FakeRetriever(),
        endpoint="https://openai.test",
        chat_deployment="gpt-test",
        api_key=None,
    )

    assert service.client is fake_client


def test_build_context_builds_blocks_and_respects_limit():
    chunks = [
        {
            "id": "chunk-1",
            "source_path": "who/mpox.md",
            "chunk_order": 0,
            "content": "A" * 40,
        },
        {
            "id": "chunk-2",
            "source_path": "who/mpox.md",
            "chunk_order": 1,
            "content": "B" * 200,
        },
    ]

    context = rag_module.RagChatService._build_context(chunks, max_chars=120)

    assert "[1] id=chunk-1 source=who/mpox.md chunk=0" in context
    assert "A" * 40 in context
    assert "chunk-2" not in context


def test_format_history_empty_and_roles():
    assert rag_module.RagChatService._format_history([]) == ""
    assert rag_module.RagChatService._format_history(None) == ""

    history = [
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Salut"},
        {"role": "user", "content": "   "},
    ]

    formatted = rag_module.RagChatService._format_history(history)

    assert "Utilisateur: Bonjour" in formatted
    assert "Assistant: Salut" in formatted
    assert "   " not in formatted


def test_format_history_limits_messages_and_chars():
    history = [{"role": "user", "content": f"msg {i}"} for i in range(10)]

    formatted = rag_module.RagChatService._format_history(
        history,
        max_messages=3,
        max_chars=1000,
    )

    assert "msg 0" not in formatted
    assert "msg 7" in formatted
    assert "msg 8" in formatted
    assert "msg 9" in formatted


def test_rewrite_question_returns_empty_for_blank(monkeypatch):
    service, _ = make_service(monkeypatch, llm_outputs=[])

    out = service._rewrite_question("   ", "Historique")
    assert out == ""


def test_rewrite_question_returns_original_without_history(monkeypatch):
    service, _ = make_service(monkeypatch, llm_outputs=[])

    out = service._rewrite_question("Quelle est la cause ?", "")
    assert out == "Quelle est la cause ?"


def test_rewrite_question_uses_llm_with_history(monkeypatch):
    service, fake_client = make_service(
        monkeypatch,
        llm_outputs=["Quelle est la cause du Mpox ?"],
    )

    out = service._rewrite_question(
        "Et la cause ?",
        "Utilisateur: Parle-moi du Mpox",
    )

    assert out == "Quelle est la cause du Mpox ?"
    assert len(fake_client.chat.completions.calls) == 1

    call = fake_client.chat.completions.calls[0]
    assert call["model"] == "gpt-test"
    assert call["temperature"] == 0.0
    assert call["max_tokens"] == 120
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][1]["role"] == "user"
    assert "Historique récent" in call["messages"][1]["content"]


def test_rewrite_question_falls_back_to_original_if_llm_returns_blank(monkeypatch):
    service, _ = make_service(
        monkeypatch,
        llm_outputs=["   "],
    )

    out = service._rewrite_question(
        "Et la cause ?",
        "Utilisateur: Parle-moi du Mpox",
    )

    assert out == "Et la cause ?"


def test_answer_returns_empty_payload_for_blank_question(monkeypatch):
    service, _ = make_service(monkeypatch, llm_outputs=[])

    out = service.answer("   ")

    assert out == {
        "answer": "",
        "sources": [],
        "chunks": [],
        "standalone_question": "",
        "history_used": "",
    }


def test_answer_nominal_builds_response_and_sources(monkeypatch):
    chunks = [
        {
            "id": "chunk-1",
            "content": "Symptoms include fever and rash.",
            "document_id": "doc-1",
            "chunk_order": 0,
            "source_path": "who/mpox.md",
            "score": 0.98,
            "scope": "global",
            "owner_user_id": "",
            "source_type": "who",
        },
        {
            "id": "chunk-2",
            "content": "Treatment is mainly supportive care.",
            "document_id": "doc-1",
            "chunk_order": 1,
            "source_path": "private/notes.md",
            "score": 0.91,
            "scope": "private",
            "owner_user_id": "tenant:user",
            "source_type": "user_upload",
        },
    ]
    retriever = FakeRetriever(chunks=chunks)

    service, fake_client = make_service(
        monkeypatch,
        retriever=retriever,
        llm_outputs=[
            "Quelle est la cause du Mpox ?",
            "Les symptômes incluent la fièvre et les éruptions cutanées [1].",
        ],
    )

    history = [
        {"role": "user", "content": "Parle-moi du Mpox"},
        {"role": "assistant", "content": "C'est une maladie virale."},
        {"role": "user", "content": "Et les symptômes ?"},
    ]

    out = service.answer(
        question="Et les symptômes ?",
        history_messages=history,
        top_k=3,
        filters="scope eq 'global'",
        temperature=0.3,
        max_tokens=500,
    )

    assert out["answer"] == "Les symptômes incluent la fièvre et les éruptions cutanées [1]."
    assert out["standalone_question"] == "Quelle est la cause du Mpox ?"
    assert "Utilisateur: Parle-moi du Mpox" in out["history_used"]
    assert out["chunks"] == chunks

    assert len(out["sources"]) == 2
    assert out["sources"][0]["ref"] == "[1]"
    assert out["sources"][0]["title"] == "mpox.md"
    assert out["sources"][0]["source_type"] == "who"
    assert out["sources"][1]["title"] == "notes.md"
    assert out["sources"][1]["source_type"] == "user_upload"

    assert len(retriever.calls) == 1
    assert retriever.calls[0]["query"] == "Quelle est la cause du Mpox ?"
    assert retriever.calls[0]["top_k"] == 3
    assert retriever.calls[0]["filters"] == "scope eq 'global'"

    assert len(fake_client.chat.completions.calls) == 2
    final_call = fake_client.chat.completions.calls[1]
    assert final_call["model"] == "gpt-test"
    assert final_call["temperature"] == 0.3
    assert final_call["max_tokens"] == 500
    assert "CONTEXTE DOCUMENTAIRE" in final_call["messages"][1]["content"]
    assert "Symptoms include fever and rash." in final_call["messages"][1]["content"]


def test_answer_handles_no_chunks(monkeypatch):
    retriever = FakeRetriever(chunks=[])

    service, _ = make_service(
        monkeypatch,
        retriever=retriever,
        llm_outputs=[
            "Question autonome",
            "Je n'ai trouvé aucun contexte suffisant.",
        ],
    )

    out = service.answer(
        question="Question test",
        history_messages=[{"role": "user", "content": "Bonjour"}],
    )

    assert out["answer"] == "Je n'ai trouvé aucun contexte suffisant."
    assert out["sources"] == []
    assert out["chunks"] == []
    assert out["standalone_question"] == "Question autonome"