# app/data_preparation/indexing/azure_search_indexer.py
import os
import logging
from typing import List, Dict, Optional, Any, Tuple

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchField, SearchFieldDataType,
    VectorSearch, VectorSearchProfile, HnswAlgorithmConfiguration,
    SemanticSearch, SemanticConfiguration, SemanticPrioritizedFields, SemanticField,
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
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=embedding_dim,
                vector_search_profile_name="vprofile",
            ),
            SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="chunk_order", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(name="source_path", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="file_type", type=SearchFieldDataType.String, filterable=True),
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
                        content_fields=[SemanticField(field_name="content")]
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

    def upload(self, docs: List[Dict[str, Any]], batch_size: int = 500) -> Tuple[List[str], List[Dict[str, Any]]]:
        if not docs:
            return [], []

        succeeded_ids: List[str] = []
        failed: List[Dict[str, Any]] = []

        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]

            try:
                results = self.search_client.upload_documents(documents=batch)
            except Exception as e:
                # ❌ si le call plante, on marque tout le batch en failed
                err = f"upload_documents exception: {e}"
                self.logger.exception(err)
                for doc in batch:
                    failed.append({"id": doc.get("id"), "error": err})
                continue

            for doc, r in zip(batch, results):
                doc_id = doc.get("id")
                if getattr(r, "succeeded", False):
                    if doc_id:
                        succeeded_ids.append(doc_id)
                else:
                    err = getattr(r, "error_message", None) or str(r)
                    failed.append({"id": doc_id, "error": err})

            # warning par batch (plus lisible)
            batch_failed = [f for f in failed if f["id"] in {d.get("id") for d in batch}]
            if batch_failed:
                self.logger.warning("⚠️ Upload: %s échecs sur %s (batch)", len(batch_failed), len(batch))

        return succeeded_ids, failed