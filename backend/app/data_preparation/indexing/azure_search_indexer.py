import os
import logging
from typing import List, Dict, Optional, Any, Tuple

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    SemanticSearch,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
)


class AzureSearchIndexer:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        index_name: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger("app.AzureSearchIndexer")
        self.endpoint = endpoint or os.getenv("AZURE_SEARCH_ENDPOINT")
        self.index_name = index_name or os.getenv("AZURE_SEARCH_INDEX")

        if not all([self.endpoint, self.index_name]):
            raise ValueError("Config Azure Search manquante (ENDPOINT / INDEX).")

        credential = DefaultAzureCredential()
        self.index_client = SearchIndexClient(self.endpoint, credential)
        self.search_client = SearchClient(self.endpoint, self.index_name, credential)

    def create_or_update_index(self, embedding_dim: int):
        fields = [
            # clé
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),

            # contenu principal
            SearchableField(name="content", type=SearchFieldDataType.String),

            # vecteur
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=embedding_dim,
                vector_search_profile_name="vprofile",
            ),

            # métadonnées document / chunk
            SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="chunk_order", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(name="source_path", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="file_type", type=SearchFieldDataType.String, filterable=True),

            # métadonnées d'accès / filtrage
            SimpleField(name="scope", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="owner_user_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="source_type", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="kb", type=SearchFieldDataType.String, filterable=True),

            # métadonnées utiles pour affichage / sémantique
            SearchableField(name="doc_title", type=SearchFieldDataType.String),
            SearchableField(name="section_title", type=SearchFieldDataType.String),
            SearchableField(name="filename", type=SearchFieldDataType.String),
        ]

        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            profiles=[VectorSearchProfile(name="vprofile", algorithm_configuration_name="hnsw")],
        )

        semantic = SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name="semcfg",
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="doc_title"),
                        content_fields=[
                            SemanticField(field_name="content"),
                            SemanticField(field_name="section_title"),
                        ],
                    ),
                )
            ]
        )

        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic,
        )

        self.index_client.create_or_update_index(index)
        self.logger.info("✅ Index '%s' prêt (dim=%s)", self.index_name, embedding_dim)

    def upload(
        self,
        docs: List[Dict[str, Any]],
        batch_size: int = 500,
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        if not docs:
            return [], []

        succeeded_ids: List[str] = []
        failed: List[Dict[str, Any]] = []

        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]

            # Normalisation légère avant upload
            normalized_batch = []
            for doc in batch:
                normalized_batch.append({
                    "id": doc.get("id"),
                    "content": doc.get("content", ""),
                    "content_vector": doc.get("content_vector"),
                    "document_id": doc.get("document_id", ""),
                    "chunk_order": doc.get("chunk_order", 0),
                    "source_path": doc.get("source_path", ""),
                    "file_type": doc.get("file_type", ""),

                    "scope": doc.get("scope", "global"),
                    "owner_user_id": doc.get("owner_user_id") or "",
                    "source_type": doc.get("source_type", "who"),
                    "kb": doc.get("kb", "who"),

                    "doc_title": doc.get("doc_title", ""),
                    "section_title": doc.get("section_title", ""),
                    "filename": doc.get("filename", ""),
                })

            try:
                results = self.search_client.upload_documents(documents=normalized_batch)
            except Exception as e:
                err = f"upload_documents exception: {e}"
                self.logger.exception(err)
                for doc in normalized_batch:
                    failed.append({"id": doc.get("id"), "error": err})
                continue

            for doc, r in zip(normalized_batch, results):
                doc_id = doc.get("id")
                if getattr(r, "succeeded", False):
                    if doc_id:
                        succeeded_ids.append(doc_id)
                else:
                    err = getattr(r, "error_message", None) or str(r)
                    failed.append({"id": doc_id, "error": err})

            batch_failed = [f for f in failed if f["id"] in {d.get("id") for d in normalized_batch}]
            if batch_failed:
                self.logger.warning("⚠️ Upload: %s échecs sur %s (batch)", len(batch_failed), len(normalized_batch))

        return succeeded_ids, failed