# app/data_preparation/indexing/azure_search_indexer.py
import os
import logging
from typing import List, Dict, Optional

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

    def upload(self, docs: List[Dict], batch_size: int = 500) -> int:
        if not docs:
            return 0
        sent = 0
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i + batch_size]
            results = self.search_client.upload_documents(documents=batch)
            failed = [r for r in results if not r.succeeded]
            if failed:
                self.logger.warning("⚠️ Upload: %s échecs sur %s", len(failed), len(batch))
            sent += len(batch)
        return sent
