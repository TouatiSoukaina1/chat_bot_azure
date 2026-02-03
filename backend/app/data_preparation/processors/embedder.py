# chat_bot_azure/backend/app/data_preparation/processors/embedder.py

import os
import time
import random
import hashlib
import logging
from typing import List, Optional, Dict
from openai import (
    AzureOpenAI,
    RateLimitError,
    APIError,
    APIConnectionError,
    APITimeoutError,
)
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

class Embedder:
    """
    Génère des embeddings via Azure OpenAI, avec :
    - Batch natif (<=16 items)
    - Retry exponentiel avec jitter
    - Suivi détaillé des stats
    - Cache optionnel (désactivé par défaut)
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
        enable_cache: bool = False,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger("app.embedder")

        # --- Config depuis env ---
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        #self.api_key = api_key or os.getenv("AZURE_OPENAI_KEY")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION")
        self.deployment_name = deployment_name or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        self.embedding_dimensions = embedding_dimensions

        if not all([self.endpoint, self.api_version, self.deployment_name]):
            raise ValueError("Config Azure OpenAI incomplète (ENDPOINT / API_VERSION / EMBEDDING_DEPLOYMENT).")

        self.batch_size = min(max(batch_size, 1), 16)  
        self.max_retries = max(0, max_retries)
        self.base_retry_delay = max(0.1, base_retry_delay)

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )

        # Client Azure
        self.client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_version=self.api_version,
                    azure_ad_token_provider=token_provider,
                )

        # Stats
        self._total_calls = 0
        self._total_items = 0
        self._total_failed = 0
        self._total_retries = 0
        self._total_latency = 0.0
        self._last_error: Optional[str] = None
        self._last_call_time: Optional[float] = None

        # Cache optionnel (clé = hash du texte)
        self._cache: Dict[str, List[float]] = {} if enable_cache else None

        self.logger.info(
            f"✓ Embedder initialisé (deployment={self.deployment_name}, batch_size={self.batch_size}, cache={'on' if enable_cache else 'off'})"
        )

    # ---------- API publique attendue par le pipeline ----------

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Embedding d'un seul texte."""
        if not isinstance(text, str) or not text.strip():
            self.logger.warning("Texte vide/invalide : embedding ignoré.")
            return None

        # Vérifie cache local
        if self._cache is not None:
            h = self._hash_text(text)
            if h in self._cache:
                return self._cache[h]

        emb = self._call_with_retry([text])[0]

        # Enregistre en cache
        if emb and self._cache is not None:
            self._cache[h] = emb
        return emb

    def generate_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Embeddings d'une liste de textes (conserve l'ordre)."""
        if not texts:
            return []
        results: List[Optional[List[float]]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            results.extend(self._call_with_retry(batch))
        return results

    def get_statistics(self) -> Dict:
        """Retourne les métriques d'utilisation."""
        avg_latency = self._total_latency / self._total_calls if self._total_calls else 0.0
        retry_rate = self._total_retries / self._total_calls if self._total_calls else 0.0

        return {
            "total_api_calls": self._total_calls,
            "total_items": self._total_items,
            "total_failed": self._total_failed,
            "success_rate": (self._total_items - self._total_failed) / self._total_items if self._total_items else 0.0,
            "average_latency_s": round(avg_latency, 3),
            "retry_rate": round(retry_rate, 3),
            "deployment": self.deployment_name,
            "embedding_dimensions": self.embedding_dimensions,
            "last_error": self._last_error,
            "last_call_time": self._last_call_time,
        }

    # ---------- Méthodes internes ----------

    def _call_with_retry(self, inputs: List[str]) -> List[Optional[List[float]]]:
        """
        Appel embeddings (batch <= 16) avec retry exponentiel + jitter.
        Retourne une liste alignée de embeddings (None si échec).
        """
        attempt = 0
        delay = self.base_retry_delay
        self._total_calls += 1
        self._total_items += len(inputs)
        start_time = time.time()

        while True:
            try:
                resp = self.client.embeddings.create(input=inputs, model=self.deployment_name)
                data_sorted = sorted(resp.data, key=lambda d: d.index)

                embeddings: List[Optional[List[float]]] = []
                for item in data_sorted:
                    emb = getattr(item, "embedding", None)
                    if not emb:
                        self._total_failed += 1
                        embeddings.append(None)
                    else:
                        # Validation dimension
                        if self.embedding_dimensions and len(emb) != self.embedding_dimensions:
                            self.logger.warning(
                                f"Embedding dimension mismatch ({len(emb)} vs {self.embedding_dimensions})"
                            )
                        embeddings.append(emb)

                latency = time.time() - start_time
                self._total_latency += latency
                self._last_call_time = time.time()
                return embeddings

            except (RateLimitError, APIError, APIConnectionError, APITimeoutError) as e:
                self._last_error = str(e)
                if attempt < self.max_retries:
                    self._total_retries += 1
                    self.logger.warning(
                        f"Retry embeddings (tentative {attempt + 1}/{self.max_retries}) après erreur: {e}"
                    )
                    # Backoff exponentiel avec jitter
                    time.sleep(delay + random.uniform(0, 0.5))
                    attempt += 1
                    delay *= 2
                    continue
                self.logger.error(f"Échec embeddings après {self.max_retries} tentatives: {e}")
                self._total_failed += len(inputs)
                return [None] * len(inputs)

            except Exception as e:
                self._last_error = str(e)
                self.logger.exception(f"Erreur inattendue embeddings: {e}")
                self._total_failed += len(inputs)
                return [None] * len(inputs)

    @staticmethod
    def _hash_text(text: str) -> str:
        """Crée un hash unique pour le cache local."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()
