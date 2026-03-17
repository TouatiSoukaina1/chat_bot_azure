import os
import logging
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

try:
    # SDK >= 11.4
    from azure.search.documents.models import VectorizedQuery
except Exception:  # pragma: no cover
    VectorizedQuery = None


class AzureSearchRetriever:
    """
    Vector retriever (Azure AI Search):
    - embed la question (via ton Embedder)
    - vector search sur content_vector
    - retourne top_k chunks + score + metadata
    """

    def __init__(
        self,
        embedder,
        endpoint: Optional[str] = None,
        index_name: Optional[str] = None,
        vector_field: str = "content_vector",
        content_field: str = "content",
        api_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger("app.AzureSearchRetriever")

        self.endpoint = endpoint or os.getenv("AZURE_SEARCH_ENDPOINT")
        self.index_name = index_name or os.getenv("AZURE_SEARCH_INDEX")
        self.vector_field = vector_field
        self.content_field = content_field

        if not self.endpoint or not self.index_name:
            raise ValueError("Config Azure Search manquante (AZURE_SEARCH_ENDPOINT / AZURE_SEARCH_INDEX).")

        # Auth: key si fournie, sinon keyless (DefaultAzureCredential)
        api_key = api_key or os.getenv("AZURE_SEARCH_API_KEY")
        if api_key:
            credential = AzureKeyCredential(api_key)
            self.logger.info("AzureSearchRetriever auth=api_key")
        else:
            credential = DefaultAzureCredential()
            self.logger.info("AzureSearchRetriever auth=default_azure_credential (keyless)")

        self.client = SearchClient(endpoint=self.endpoint, index_name=self.index_name, credential=credential)
        self.embedder = embedder

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[str] = None,
        select_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Args:
          query: question utilisateur
          top_k: nb de chunks retournés
          filters: filtre OData (ex: "document_id eq 'doc1'")
          select_fields: champs retournés (sinon default)

        Returns:
          List[{"id","content","score","document_id","chunk_order","source_path","file_type"}]
        """
        q = (query or "").strip()
        if not q:
            return []

        q_emb = self.embedder.generate_embedding(q)
        if q_emb is None:
            self.logger.warning("Embedding query = None (retrieve aborted).")
            return []

        if VectorizedQuery is None:
            raise RuntimeError(
                "VectorizedQuery indisponible. Mets à jour azure-search-documents (>= 11.4) "
                "ou adapte l'appel vector search."
            )

        select = select_fields or [
            "id",
            self.content_field,
            "document_id",
            "chunk_order",
            "source_path",
            "file_type",
            "scope",
            "owner_user_id",
            "source_type",
        ]

        vector_query = VectorizedQuery(
            vector=q_emb,
            k_nearest_neighbors=top_k,
            fields=self.vector_field,
        )

        results = self.client.search(
            search_text="",               # vector-only
            vector_queries=[vector_query],
            top=top_k,
            filter=filters,
            select=select,
        )

        out: List[Dict[str, Any]] = []
        for r in results:
            out.append({
                "id": r.get("id"),
                "content": r.get(self.content_field),
                "score": r.get("@search.score"),
                "document_id": r.get("document_id"),
                "chunk_order": r.get("chunk_order"),
                "source_path": r.get("source_path"),
                "file_type": r.get("file_type"),
                "scope": r.get("scope"),
                "owner_user_id": r.get("owner_user_id"),
                "source_type": r.get("source_type"),
            })
        return out
