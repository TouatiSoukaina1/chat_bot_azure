import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


class RagChatService:
    """
    RAG chat conversationnel :
    - reformule la question avec l’historique
    - retrieve top_k chunks avec la question reformulée
    - génère la réponse finale avec historique + contexte documentaire
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
            raise ValueError(
                "Config Azure OpenAI manquante "
                "(AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_CHAT_DEPLOYMENT)."
            )

        api_key = api_key or os.getenv("AZURE_OPENAI_KEY")

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

    @staticmethod
    def _format_history(history_messages: Optional[List[Dict[str, Any]]], max_messages: int = 8, max_chars: int = 4000) -> str:
        if not history_messages:
            return ""

        recent = history_messages[-max_messages:]
        lines: List[str] = []
        total = 0

        for msg in recent:
            role = msg.get("role", "user")
            content = (msg.get("content") or "").strip()
            if not content:
                continue

            speaker = "Utilisateur" if role == "user" else "Assistant"
            line = f"{speaker}: {content}"

            if total + len(line) > max_chars:
                break

            lines.append(line)
            total += len(line)

        return "\n".join(lines).strip()

    def _rewrite_question(self, question: str, history_text: str) -> str:
        """
        Reformule la dernière question en question autonome,
        afin d'améliorer le retrieval.
        """
        q = (question or "").strip()
        if not q:
            return ""

        if not history_text:
            return q

        system = (
            "Tu es un assistant spécialisé dans la reformulation de questions "
            "pour un système RAG. "
            "Ta tâche consiste à reformuler la dernière question utilisateur "
            "en une question autonome, claire et concise. "
            "Ne réponds pas à la question. "
            "Ne donne aucune explication. "
            "Retourne uniquement la question reformulée."
        )

        user = (
            f"Historique récent:\n{history_text}\n\n"
            f"Dernière question utilisateur:\n{q}\n\n"
            "Question reformulée autonome:"
        )

        resp = self.client.chat.completions.create(
            model=self.chat_deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            max_tokens=120,
        )

        standalone = (resp.choices[0].message.content or "").strip()
        return standalone or q

    def answer(
        self,
        question: str,
        history_messages: Optional[List[Dict[str, Any]]] = None,
        top_k: int = 5,
        filters: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 700,
    ) -> Dict[str, Any]:
        q = (question or "").strip()
        if not q:
            return {
                "answer": "",
                "sources": [],
                "chunks": [],
                "standalone_question": "",
                "history_used": "",
            }

        history_text = self._format_history(history_messages, max_messages=8)
        standalone_question = self._rewrite_question(q, history_text)

        self.logger.info("Question originale: %s", q)
        self.logger.info("Question reformulée: %s", standalone_question)

        chunks = self.retriever.retrieve(standalone_question, top_k=top_k, filters=filters)
        context = self._build_context(chunks)

        system = (
            "Tu es un assistant RAG conversationnel. "
            "Réponds en priorité à partir du CONTEXTE documentaire fourni. "
            "Tu peux t'aider de l'historique récent pour comprendre la conversation. "
            "Si le contexte ne suffit pas, dis-le clairement. "
            "Ajoute des citations sous forme [1], [2], [3] correspondant aux blocs du contexte. "
            "Ne fabrique pas de sources inexistantes."
        )

        user = (
            f"HISTORIQUE RÉCENT:\n{history_text if history_text else '(aucun historique)'}\n\n"
            f"QUESTION ORIGINALE:\n{q}\n\n"
            f"QUESTION REFORMULÉE:\n{standalone_question}\n\n"
            f"CONTEXTE DOCUMENTAIRE:\n{context if context else '(aucun contexte trouvé)'}\n\n"
            "Réponds de manière claire, utile et structurée."
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
            source_path = ch.get("source_path") or ""
            title = Path(source_path).name if source_path else f"Source {i}"

            content = (ch.get("content") or "").strip()
            excerpt = content[:500] + ("..." if len(content) > 500 else "")

            sources.append({
                "ref": f"[{i}]",
                "id": ch.get("id"),
                "source_path": ch.get("source_path"),
                "document_id": ch.get("document_id"),
                "chunk_order": ch.get("chunk_order"),
                "score": ch.get("score"),
                "title": title,
                "excerpt": excerpt,
            })

        return {
            "answer": answer_text,
            "sources": sources,
            "chunks": chunks,
            "standalone_question": standalone_question,
            "history_used": history_text,
        }