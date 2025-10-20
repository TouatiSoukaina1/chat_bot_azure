# app/data_preparation/processors/embedder.py

import os
import time
import logging
from typing import List, Optional, Dict
from openai import AzureOpenAI, RateLimitError, APIError, APIConnectionError

try:
    from app.config.settings import settings
except Exception:
    settings = None  # fallback si settings n'est pas disponible pendant les tests


class Embedder:
    """
    Génère des embeddings via Azure OpenAI, avec :
    - Batch natif (<=16 items)
    - Retry exponentiel (Rate limit / erreurs transitoires)
    - API compatible avec IngestionPipeline:
        * generate_embedding(text: str) -> Optional[List[float]]
        * generate_embeddings(texts: List[str]) -> List[Optional[List[float]]]
        * get_statistics() -> Dict
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        deployment_name: Optional[str] = None,
        embedding_dimensions: Optional[int] = None,
        batch_size: int = 16,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger("app.embedder")

        # --- Config depuis settings ou .env ---
        self.endpoint = endpoint or (settings.AZURE_OPENAI_ENDPOINT if settings else os.getenv("AZURE_OPENAI_ENDPOINT"))
        self.api_key = api_key or (settings.AZURE_OPENAI_KEY if settings else (os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_KEY")))
        self.api_version = api_version or (settings.AZURE_OPENAI_API_VERSION if settings else os.getenv("AZURE_OPENAI_API_VERSION"))
        self.deployment_name = deployment_name or (settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT if settings else os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"))
        self.embedding_dimensions = embedding_dimensions or (getattr(settings, "AZURE_OPENAI_EMBEDDING_DIMENSIONS", None) if settings else None)

        if not all([self.endpoint, self.api_key, self.api_version, self.deployment_name]):
            raise ValueError(
                "Configuration Azure OpenAI incomplète. "
                "Requis: AZURE_OPENAI_ENDPOINT / KEY / API_VERSION / EMBEDDING_DEPLOYMENT."
            )

        self.batch_size = min(max(batch_size, 1), 16)  # Azure limite 16
        self.max_retries = max(0, max_retries)
        self.base_retry_delay = max(0.1, base_retry_delay)

        # Client
        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
        )

        # Stats
        self._total_calls = 0
        self._total_items = 0
        self._total_failed = 0
        self._last_error: Optional[str] = None

        self.logger.info(f"✓ Embedder initialisé (deployment={self.deployment_name}, batch_size={self.batch_size})")

    # ---------- API attendue par IngestionPipeline ----------
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Embedding d'un seul texte. Retourne None si échec.
        """
        if not isinstance(text, str) or not text.strip():
            self.logger.warning("Texte vide/invalide: embedding ignoré.")
            return None
        return self._call_with_retry([text])[0]

    def generate_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Embeddings d'une liste de textes. Conserve l'ordre.
        Retourne une liste d'embeddings ou None par élément en échec.
        """
        if not texts:
            return []
        results: List[Optional[List[float]]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            results.extend(self._call_with_retry(batch))
        return results

    def get_statistics(self) -> Dict:
        """
        Stats utiles pour observabilité (utilisées par le health check du pipeline).
        """
        return {
            "total_api_calls": self._total_calls,
            "total_items": self._total_items,
            "total_failed": self._total_failed,
            "success_rate": (self._total_items - self._total_failed) / self._total_items if self._total_items else 0.0,
            "deployment": self.deployment_name,
            "embedding_dimensions": self.embedding_dimensions,
            "last_error": self._last_error,
        }

    # ---------- Interne ----------
    def _call_with_retry(self, inputs: List[str]) -> List[Optional[List[float]]]:
        """
        Appel embeddings (batch <= 16) avec retry exponentiel.
        Retourne une liste alignée de embeddings (None si échec).
        """
        attempt = 0
        delay = self.base_retry_delay
        self._total_calls += 1
        self._total_items += len(inputs)

        while True:
            try:
                resp = self.client.embeddings.create(input=inputs, model=self.deployment_name)
                data_sorted = sorted(resp.data, key=lambda d: d.index)
                return [item.embedding for item in data_sorted]

            except (RateLimitError, APIError, APIConnectionError) as e:
                self._last_error = str(e)
                if attempt < self.max_retries:
                    self.logger.warning(f"Retry embeddings (tentative {attempt+1}/{self.max_retries}) après erreur: {e}")
                    time.sleep(delay)
                    attempt += 1
                    delay *= 2
                    continue
                self.logger.error(f"Echec embeddings après {self.max_retries} tentatives: {e}")
                self._total_failed += len(inputs)
                return [None] * len(inputs)

            except Exception as e:
                self._last_error = str(e)
                self.logger.exception(f"Erreur inattendue embeddings: {e}")
                self._total_failed += len(inputs)
                return [None] * len(inputs)
