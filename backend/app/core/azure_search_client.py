# backend/app/data_preparation/processors/search_indexer.py

import os
import logging
from typing import List, Dict, Optional
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchFieldDataType, VectorSearch,
    VectorSearchAlgorithmConfiguration, SearchableField, VectorField
)

class AzureSearchIndexer:
    """
    Indexer Azure AI Search compatible avec IngestionPipeline.
    - create_index()
    - index_documents(chunks, batch_size=100) -> {'indexed': ..., 'failed': ...}
    - get_usage_statistics() -> dict
    - vector_search(query_embedding, top_k=5)
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
        embedding_dimensions: int = 1536
    ):
        self.logger = logging.getLogger("app.AzureSearchIndexer")
        self.endpoint = endpoint or os.getenv("AZURE_SEARCH_ENDPOINT")
        self.key = api_key or os.getenv("AZURE_SEARCH_KEY")
        self.index_name = index_name or os.getenv("AZURE_SEARCH_INDEX", "documents-index")
        self.embedding_dimensions = embedding_dimensions

        if not self.endpoint or not self.key:
            raise ValueError("AZURE_SEARCH_ENDPOINT ou AZURE_SEARCH_KEY manquant.")

        self.credential = AzureKeyCredential(self.key)
        self.index_client = SearchIndexClient(endpoint=self.endpoint, credential=self.credential)
        self.search_client: Optional[SearchClient] = None

    def create_index(self) -> None:
        """
        Crée l’index s’il n’existe pas (idempotent).
        Champs attendus par le pipeline:
          - id (key)
          - document_id (filterable)
          - content (searchable)
          - embedding (vector field)
          - metadata (searchable string)
        """
        try:
            # Si l’index existe déjà, on ne le recrée pas
            try:
                _ = self.index_client.get_index(self.index_name)
                self.logger.info(f"ℹ️ Index '{self.index_name}' existe déjà.")
            except Exception:
                self.logger.info(f"Création de l’index '{self.index_name}'...")
                fields = [
                    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                    SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
                    SearchableField(name="content", type=SearchFieldDataType.String),
                    VectorField(
                        name="embedding",
                        searchable=True,
                        filterable=False,
                        dimensions=self.embedding_dimensions,
                        vector_search_configuration="default"
                    ),
                    # On sérialise le dict metadata en str côté upload
                    SearchableField(name="metadata", type=SearchFieldDataType.String),
                ]

                vector_search = VectorSearch(
                    algorithm_configurations=[
                        VectorSearchAlgorithmConfiguration(
                            name="default",
                            kind="hnsw",
                            parameters={"m": 4, "efConstruction": 400},
                        )
                    ]
                )

                index = SearchIndex(
                    name=self.index_name,
                    fields=fields,
                    vector_search=vector_search,
                )
                self.index_client.create_index(index)
                self.logger.info(f"✅ Index '{self.index_name}' créé.")

            # Toujours (ré)initialiser le SearchClient une fois l’index présent
            self.search_client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=self.credential,
            )

        except Exception as e:
            self.logger.error(f"Erreur création/initialisation index '{self.index_name}': {e}")
            raise

    def index_documents(self, chunks: List[Dict], batch_size: int = 100) -> Dict[str, int]:
        """
        Envoie des chunks déjà enrichis d’embeddings.
        Chaque chunk doit contenir: id, content, embedding, (optionnel) metadata, (optionnel) document_id.
        Retourne {'indexed': n, 'failed': m}.
        """
        if not chunks:
            return {"indexed": 0, "failed": 0}

        if not self.search_client:
            # Sécurité : s’assurer que create_index() a été appelé
            self.create_index()

        total_indexed = 0
        total_failed = 0

        try:
            # Découpage en lots
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                payload = []
                for c in batch:
                    payload.append({
                        "id": c.get("id"),
                        "document_id": c.get("document_id"),
                        "content": c.get("content"),           # ⚠️ pas "text" → le pipeline utilise "content"
                        "embedding": c.get("embedding"),
                        "metadata": str(c.get("metadata", {})), # serialize dict → str
                    })

                results = self.search_client.upload_documents(documents=payload)
                indexed = sum(1 for r in results if r.succeeded)
                failed = len(payload) - indexed

                total_indexed += indexed
                total_failed += failed

                self.logger.info(f"Batch indexé: {indexed}/{len(payload)} (échecs={failed})")

        except Exception as e:
            self.logger.exception(f"Erreur upload vers Azure Search: {e}")
            # On compte tout le batch comme échoué si exception
            total_failed += len(chunks) - total_indexed

        return {"indexed": total_indexed, "failed": total_failed}

    def get_usage_statistics(self) -> Dict:
        """
        Renvoie quelques métriques utiles pour les dashboards/health-checks.
        """
        if not self.search_client:
            self.create_index()

        try:
            count = self.search_client.get_document_count()
        except Exception as e:
            self.logger.warning(f"Impossible de récupérer le nombre de documents: {e}")
            count = None

        return {
            "index_name": self.index_name,
            "document_count": count,
            "embedding_dimensions": self.embedding_dimensions,
            "endpoint": self.endpoint,
        }

    # --------- Bonus : recherche vectorielle (utile côté service de chat) ---------

    def vector_search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """
        Recherche vectorielle simple. Retourne une liste de docs (content, document_id, etc.).
        """
        if not self.search_client:
            self.create_index()

        try:
            # Selon la version de SDK, la signature peut changer.
            # Ici on garde la forme courante utilisée dans ton code.
            results = self.search_client.search(
                vector={"value": query_embedding, "fields": "embedding", "k": top_k},
                select=["id", "content", "document_id", "metadata"],
            )
            return [doc for doc in results]
        except Exception as e:
            self.logger.exception(f"Erreur vector search: {e}")
            return []
