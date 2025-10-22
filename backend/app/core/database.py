# app/core/database.py

import os
import logging
from typing import List, Dict, Optional, Iterable
from azure.cosmos import CosmosClient, exceptions

class DocumentRepository:
    """
    Accès à Azure Cosmos DB (containers:
      - documents  (pk: /file_type)
      - chunks     (pk: /document_id)
    ) pour piloter les pipelines d'extraction, chunking, embedding & indexing.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        key: Optional[str] = None,
        database_name: Optional[str] = None,
        container_documents: Optional[str] = None,
        container_chunks: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger("app.repository")
        self.uri = uri or os.getenv("COSMOSDB_URI")
        self.key = key or os.getenv("COSMOS_KEY")
        self.database_name = database_name or os.getenv("COSMOS_DATABASE")
        self.container_documents = container_documents or os.getenv("COSMOSDB_CONTAINER_DOCUMENTS")
        self.container_chunks = container_chunks or os.getenv("COSMOSDB_CONTAINER_CHUNKS")

        if not all([self.uri, self.key, self.database_name, self.container_documents, self.container_chunks]):
            raise ValueError("Config Cosmos DB incomplète (URI/KEY/DATABASE/CONTAINERS manquants).")

        try:
            self.client = CosmosClient(self.uri, credential=self.key)
            self.database = self.client.get_database_client(self.database_name)
            self.docs_container = self.database.get_container_client(self.container_documents)
            self.chunks_container = self.database.get_container_client(self.container_chunks)
            self.logger.info("✓ Connexion Cosmos DB initialisée.")
        except exceptions.CosmosHttpResponseError as e:
            self.logger.error(f"Erreur connexion Cosmos DB: {e}")
            raise

    # -------------------- INSERT/UPSERT DOCUMENTS --------------------

    def insert_document(self, document: Dict) -> None:
        """
        Upsert d'un document (container 'documents').
        Exige: document['id'], document['file_type'] (pk), document['path'], 'status', 'text_content' (optionnel).
        """
        try:
            self.docs_container.upsert_item(document)
        except exceptions.CosmosHttpResponseError as e:
            self.logger.error(f"Erreur HTTP Cosmos (documents): {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Erreur inattendue insert_document: {e}")
            raise

    def insert_documents(self, documents: Iterable[Dict]) -> int:
        """Upsert en lot (documents). Retourne le nombre inséré/mis à jour."""
        count = 0
        for doc in documents:
            self.insert_document(doc)
            count += 1
        return count

    # -------------------- READ/QUERY DOCUMENTS --------------------

    def get_document_by_path(self, path: str) -> Optional[Dict]:
        """
        Récupère un document par son chemin (unique logique côté app).
        """
        query = "SELECT * FROM c WHERE c.path = @path"
        params = [{"name": "@path", "value": path}]
        items = list(self.docs_container.query_items(
            query=query, parameters=params, enable_cross_partition_query=True
        ))
        return items[0] if items else None

    def get_documents_by_status(self, status: Optional[str] = "parsed", file_types: Optional[List[str]] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Récupère les documents par statut, optionnellement filtrés par types.
        """
        clauses = []
        params = []
        if status:
            clauses.append("c.status = @status")
            params.append({"name": "@status", "value": status})
        if file_types:
            # IN requires array contains; build OR
            ors = []
            for i, ft in enumerate(file_types):
                pname = f"@ft{i}"
                ors.append(f"c.file_type = {pname}")
                params.append({"name": pname, "value": ft})
            clauses.append("(" + " OR ".join(ors) + ")")

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM c{where}"
        it = self.docs_container.query_items(query=query, parameters=params, enable_cross_partition_query=True)

        items = []
        for i, item in enumerate(it):
            items.append(item)
            if limit and i + 1 >= limit:
                break
        return items

    # -------------------- UPDATE DOCUMENTS --------------------

    def update_document_status(self, document_id: str, file_type: str, new_status: str) -> None:
        """
        Met à jour le statut d’un document.
        - pk = file_type (container 'documents')
        """
        try:
            doc = self.docs_container.read_item(item=document_id, partition_key=file_type)
            doc["status"] = new_status
            self.docs_container.upsert_item(doc)
        except exceptions.CosmosResourceNotFoundError:
            self.logger.warning(f"Document introuvable: id={document_id}, pk={file_type}")
        except Exception as e:
            self.logger.exception(f"Erreur update_document_status: {e}")
            raise

    def mark_document_error(self, document_id: str, file_type: str, message: str) -> None:
        """
        Marque un document en erreur (status='error' + message facultatif).
        """
        try:
            doc = self.docs_container.read_item(item=document_id, partition_key=file_type)
            doc["status"] = "error"
            doc["error_message"] = message
            self.docs_container.upsert_item(doc)
        except exceptions.CosmosResourceNotFoundError:
            self.logger.warning(f"Document introuvable pour erreur: id={document_id}, pk={file_type}")
        except Exception as e:
            self.logger.exception(f"Erreur mark_document_error: {e}")
            raise

    # -------------------- INSERT/UPSERT CHUNKS --------------------

    def insert_chunk(self, chunk: Dict) -> None:
        """
        Upsert d’un chunk (container 'chunks').
        Exige: chunk['id'], chunk['document_id'] (pk), chunk['content'] ou 'text', 'status'.
        """
        try:
            self.chunks_container.upsert_item(chunk)
        except exceptions.CosmosHttpResponseError as e:
            self.logger.error(f"Erreur HTTP Cosmos (chunks): {e}")
            raise
        except Exception as e:
            self.logger.exception(f"Erreur inattendue insert_chunk: {e}")
            raise

    def insert_chunks(self, chunks: Iterable[Dict]) -> int:
        """Upsert en lot (chunks). Retourne le nombre inséré/mis à jour."""
        count = 0
        for ch in chunks:
            self.insert_chunk(ch)
            count += 1
        return count

    # -------------------- READ/QUERY CHUNKS --------------------

    def get_chunks(self, status: Optional[str] = None, document_ids: Optional[List[str]] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Récupère les chunks par statut et/ou par liste d’IDs documents.
        """
        clauses = []
        params = []
        if status:
            clauses.append("c.status = @status")
            params.append({"name": "@status", "value": status})
        if document_ids:
            ors = []
            for i, did in enumerate(document_ids):
                pname = f"@did{i}"
                ors.append(f"c.document_id = {pname}")
                params.append({"name": pname, "value": did})
            clauses.append("(" + " OR ".join(ors) + ")")

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM c{where}"
        it = self.chunks_container.query_items(query=query, parameters=params, enable_cross_partition_query=True)

        items = []
        for i, item in enumerate(it):
            items.append(item)
            if limit and i + 1 >= limit:
                break
        return items

    # -------------------- UPDATE CHUNKS --------------------

    def update_chunk_status(self, chunk_id: str, document_id: str, status: str) -> None:
        """
        Met à jour le statut d’un chunk.
        - pk = document_id (container 'chunks')
        """
        try:
            ch = self.chunks_container.read_item(item=chunk_id, partition_key=document_id)
            ch["status"] = status
            self.chunks_container.upsert_item(ch)
        except exceptions.CosmosResourceNotFoundError:
            self.logger.warning(f"Chunk introuvable: id={chunk_id}, pk={document_id}")
        except Exception as e:
            self.logger.exception(f"Erreur update_chunk_status: {e}")
            raise
