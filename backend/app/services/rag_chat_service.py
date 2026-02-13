import os
import logging
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


class RagChatService:
    """
    RAG chat:
    - retrieve top_k chunks via AzureSearchRetriever
    - construit un prompt avec citations
    - appelle Azure OpenAI (API key ou keyless)
    """

    def __init__(
        self,
        retriever,
        endpoint: Optional[str] = None,
        api_version: Optional[str] = None,
        chat_deployment: Optional[str] = None,
        api_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger("app.RagChatService")
        self.retriever = retriever

        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
        self.chat_deployment = chat_deployment or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")

        if not self.endpoint or not self.chat_deployment:
            raise ValueError("Config Azure OpenAI manquante (AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_CHAT_DEPLOYMENT).")

        api_key = api_key or os.getenv("AZURE_OPENAI_KEY")

        # Auth: API key si fournie, sinon keyless (Entra ID)
        if api_key:
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint,
            )
            self.logger.info("RagChatService auth=api_key")
        else:
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            self.client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_version=self.api_version,
                azure_ad_token_provider=token_provider,
            )
            self.logger.info("RagChatService auth=default_azure_credential (keyless)")

    @staticmethod
    def _build_context(chunks: List[Dict[str, Any]], max_chars: int = 12000) -> str:
        """
        Formate le contexte avec citations courtes.
        """
        parts: List[str] = []
        total = 0
        for i, ch in enumerate(chunks, start=1):
            cid = ch.get("id")
            path = ch.get("source_path") or ""
            order = ch.get("chunk_order")
            content = (ch.get("content") or "").strip()

            cite = f"[{i}] id={cid} source={path} chunk={order}"
            block = f"{cite}\n{content}\n"

            if total + len(block) > max_chars:
                break

            parts.append(block)
            total += len(block)

        return "\n".join(parts).strip()

    def answer(
        self,
        question: str,
        top_k: int = 5,
        filters: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 600,
    ) -> Dict[str, Any]:
        q = (question or "").strip()
        if not q:
            return {"answer": "", "sources": [], "chunks": []}

        chunks = self.retriever.retrieve(q, top_k=top_k, filters=filters)
        context = self._build_context(chunks)

        system = (
            "Tu es un assistant RAG. "
            "Réponds en te basant uniquement sur le CONTEXTE si possible. "
            "Si le contexte ne suffit pas, dis-le clairement. "
            "Ajoute des citations sous forme [1], [2] correspondant aux blocs du contexte."
        )

        user = (
            f"QUESTION:\n{q}\n\n"
            f"CONTEXTE:\n{context if context else '(aucun contexte trouvé)'}"
        )

        resp = self.client.chat.completions.create(
            model=self.chat_deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        answer_text = (resp.choices[0].message.content or "").strip()

        sources = []
        for i, ch in enumerate(chunks, start=1):
            sources.append({
                "ref": f"[{i}]",
                "id": ch.get("id"),
                "source_path": ch.get("source_path"),
                "document_id": ch.get("document_id"),
                "chunk_order": ch.get("chunk_order"),
                "score": ch.get("score"),
            })

        return {
            "answer": answer_text,
            "sources": sources,
            "chunks": chunks,
        }
