# app/core/azure_search_client.py (extrait simplifié)

import logging
from typing import List, Dict
from azure.core.exceptions import AzureError
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex
from azure.identity import AzureKeyCredential
import os

class AzureSearchIndexer:
    """
    Client d'indexation Azure Search avec gestion des erreurs
    et suivi des documents indexés/échoués.
    """

    def __init__(self, endpoint: str = None, key: str = None, index_name: str = None, logger: logging.Logger = None):
        

        self.endpoint = endpoint or os.getenv("AZURE_SEARCH_ENDPOINT")
        self.key = key or os.getenv("AZURE_SEARCH_ADMIN_KEY")
        self.index_name = index_name or os.getenv("AZURE_SEARCH_INDEX_NAME")
        self.logger = logger or logging.getLogger("app.azure_search")

        if not all([self.endpoint, self.key, self.index_name]):
            raise ValueError("Configuration Azure Search incomplète")

        self.credential = AzureKeyCredential(self.key)
        self.client = SearchClient(endpoint=self.endpoint, index_name=self.index_name, credential=self.credential)
        self.index_client = SearchIndexClient(endpoint=self.endpoint, credential=self.credential)

    # ---------------------------------------------------------------------
    def create_index(self) -> None:
        """Crée l'index s'il n'existe pas déjà."""
        try:
            indexes = [i.name for i in self.index_client.list_indexes()]
            if self.index_name not in indexes:
                self.logger.info(f"Création de l'index Azure Search : {self.index_name}")
                # Tu peux adapter le schéma selon ton cas
                schema = SearchIndex(
                    name=self.index_name,
                    fields=[
                        {"name": "id", "type": "Edm.String", "key": True},
                        {"name": "content", "type": "Edm.String"},
                        {"name": "embedding", "type": "Collection(Edm.Single)"},
                        {"name": "document_id", "type": "Edm.String"},
                    ],
                )
                self.index_client.create_index(schema)
        except AzureError as e:
            self.logger.error(f"Erreur création index Azure Search : {e}")
            raise

    # ---------------------------------------------------------------------
    def index_documents(self, docs: List[Dict]) -> Dict[str, List[str]]:
        """
        Indexe les documents dans Azure Search.
        Retourne les IDs indexés et échoués pour suivi précis.
        """
        succeeded_ids, failed_ids = [], []
        try:
            batch = [{"id": d["id"], **d} for d in docs]
            result = self.client.upload_documents(documents=batch)

            for r in result:
                if r.succeeded:
                    succeeded_ids.append(r.key)
                else:
                    failed_ids.append(r.key)

            self.logger.info(f"Indexation terminée : {len(succeeded_ids)} succès / {len(failed_ids)} échecs")

            return {
                "succeeded_ids": succeeded_ids,
                "failed_ids": failed_ids,
                "indexed": len(succeeded_ids),
                "failed": len(failed_ids),
            }

        except AzureError as e:
            self.logger.error(f"Erreur Azure Search lors de l’indexation : {e}")
            # Tous les documents du batch sont considérés comme échoués
            failed_ids = [d["id"] for d in docs]
            return {
                "succeeded_ids": [],
                "failed_ids": failed_ids,
                "indexed": 0,
                "failed": len(failed_ids),
            }
