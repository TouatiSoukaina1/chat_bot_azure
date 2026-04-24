import logging
import os
import re
from typing import Optional

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


logger = logging.getLogger("app.conversation_title")


class ConversationTitleService:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_version: Optional[str] = None,
        chat_deployment: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
        self.chat_deployment = chat_deployment or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")

        if not self.endpoint or not self.chat_deployment:
            self.client = None
            logger.warning("ConversationTitleService désactivé: config Azure OpenAI manquante")
            return

        api_key = api_key or os.getenv("AZURE_OPENAI_KEY")

        if api_key:
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint,
            )
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

    def _fallback_title(self, question: str) -> str:
        text = (question or "").strip()
        if not text:
            return "Nouvelle conversation"

        text = re.sub(r"^(bonjour|salut|hello|bonsoir)\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[?!.]+$", "", text).strip()

        words = text.split()
        if not words:
            return "Nouvelle conversation"

        short = " ".join(words[:8]).strip()
        return short[:1].upper() + short[1:] if short else "Nouvelle conversation"

    def generate_title(self, question: str) -> str:
        fallback = self._fallback_title(question)

        if not self.client:
            return fallback

        q = (question or "").strip()
        if not q:
            return "Nouvelle conversation"

        try:
            resp = self.client.chat.completions.create(
                model=self.chat_deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Tu génères des titres de conversation très courts. "
                            "Retourne uniquement un titre de 3 à 7 mots maximum, "
                            "sans guillemets, sans ponctuation finale."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Question utilisateur : {q}",
                    },
                ],
                temperature=0.2,
                max_tokens=20,
            )

            title = (resp.choices[0].message.content or "").strip()
            title = re.sub(r'["“”]+', "", title).strip()
            title = re.sub(r"[?!.]+$", "", title).strip()

            if not title:
                return fallback

            return title[:1].upper() + title[1:]
        except Exception:
            logger.exception("Échec génération titre conversation")
            return fallback