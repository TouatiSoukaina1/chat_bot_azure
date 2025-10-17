import os
import logging
from typing import List, Dict
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchFieldDataType, VectorSearch,
    VectorSearchAlgorithmConfiguration, SearchableField, VectorField
)
from azure.core.credentials import AzureKeyCredential

class AzureSearchService:
    """Service pour gérer l'index vectoriel Azure AI Search"""

    def __init__(self):
        self.logger = logging.getLogger("app.AzureSearchService")
        self.endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.key = os.getenv("AZURE_SEARCH_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX", "documents-index")

        if not self.endpoint or not self.key:
            raise ValueError("Clé ou endpoint Azure Search manquant.")

        self.credential = AzureKeyCredential(self.key)
        self.index_client = SearchIndexClient(endpoint=self.endpoint, credential=self.credential)
        self.search_client = SearchClient(endpoint=self.endpoint, index_name=self.index_name, credential=self.credential)

    def create_index(self, dimensions: int = 1536):
        '''
            Crée un index de recherche Azure avec une configuration de recherche vectorielle.
            params :
                embedding_dimention (int): dimension des vecteurs d'embedding
        '''
        try:
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
                SearchableField(name="content", type=SearchFieldDataType.String),
                VectorField(name="embedding", searchable=True, filterable=False, dimensions=dimensions,
                            vector_search_configuration="default"),
                SearchableField(name="metadata", type=SearchFieldDataType.String)
            ]

            vector_search = VectorSearch(
                algorithm_configurations=[
                    VectorSearchAlgorithmConfiguration(
                        name="default",
                        kind="hnsw",
                        parameters={"m": 4, "efConstruction": 400}
                    )
                ]
            )

            index = SearchIndex(
                name=self.index_name,
                fields=fields,
                vector_search=vector_search
            )

            self.index_client.create_index(index)
            
        except Exception as e:
            if "already exists" in str(e).lower():
                self.logger.info(f"ℹ️ Index '{self.index_name}' existe déjà.")
            else:
                self.logger.error(f"Erreur lors de la création de l’index : {e}")

    def upload_documents(self, docs: List[Dict]):
        '''
            Upload une liste de documents dans l'index Azure Search.
            params :
                docs (List[Dict]): liste des documents à uploader
        '''
        try:
            if not docs:
                self.logger.warning("Aucun document à uploader")
                return

            batch = []
            for doc in docs:
                batch.append({
                    "id": doc.get("id"),
                    "document_id": doc.get("document_id"),
                    "content": doc.get("text"),
                    "embedding": doc.get("embedding"),
                    "metadata": str(doc.get("metadata", {}))
                })

            result = self.search_client.upload_documents(documents=batch)
            succeeded = sum(1 for r in result if r.succeeded)
            self.logger.info(f"Upload terminé : {succeeded}/{len(batch)} documents indexés.")
        except Exception as e:
            self.logger.exception(f"Erreur upload documents : {e}")
    
    def vector_search(self, query_embedding: list, top_k: int = 5):
        """Recherche vectorielle dans Azure Cognitive Search."""
        try:
            results = self.search_client.search(
                vector={"value": query_embedding, "fields": "embedding", "k": top_k},
                select=["content", "source"]
            )
            return [doc for doc in results]
        except Exception as e:
            self.logger.exception(f"Erreur lors de la recherche vectorielle : {e}")
            return []
