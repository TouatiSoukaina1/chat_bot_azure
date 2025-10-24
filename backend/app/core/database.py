# app/core/database.py

import os
import logging
from typing import List, Dict, Optional, Iterable
from azure.cosmos import CosmosClient, exceptions


class DocumentRepository:
    """
    Accès à Azure Cosmos DB (containers :
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
            raise ValueError("Configuration Cosmos DB incomplète (URI/KEY/DATABASE/CONTAINERS manquants).")

        try:
            self.client = CosmosClient(self.uri, credential=self.key)
            self.database = self.client.get_database_client(self.database_name)
            self.docs_container = self.database.get_container_client(self.container_documents)
            self.chunks_container = self.database.get_container_client(self.container_chunks)
            self.logger.info("✓ Connexion Cosmos DB initialisée.")
        except exceptions.CosmosHttpResponseError as e:
            self.logger.error(f"Erreur connexion Cosmos DB: {e}")
            raise

    # -------------------- INSERT / UPSERT DOCUMENTS --------------------

    def insert_document(self, document: Dict) -> None:
        try:
            self.docs_container.upsert_item(document)
        except Exception as e:
            self.logger.exception(f"Erreur insert_document: {e}")
            raise

    def insert_documents(self, documents: Iterable[Dict]) -> int:
        count = 0
        for doc in documents:
            self.insert_document(doc)
            count += 1
        return count

    # -------------------- READ DOCUMENTS --------------------

    def get_document_by_path(self, path: str) -> Optional[Dict]:
        query = "SELECT * FROM c WHERE c.path = @path"
        params = [{"name": "@path", "value": path}]
        items = list(self.docs_container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
        return items[0] if items else None

    def get_documents_by_status(
        self, status: Optional[str] = "parsed", file_types: Optional[List[str]] = None, limit: Optional[int] = None
    ) -> List[Dict]:
        clauses, params = [], []
        if status:
            clauses.append("c.status = @status")
            params.append({"name": "@status", "value": status})
        if file_types:
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
        try:
            doc = self.docs_container.read_item(item=document_id, partition_key=file_type)
            doc["status"] = "error"
            doc["error_message"] = message
            self.docs_container.upsert_item(doc)
        except exceptions.CosmosResourceNotFoundError:
            self.logger.warning(f"Document introuvable pour erreur: id={document_id}, pk={file_type}")

    # -------------------- INSERT / UPSERT CHUNKS --------------------

    def insert_chunk(self, chunk: Dict) -> None:
        try:
            self.chunks_container.upsert_item(chunk)
        except Exception as e:
            self.logger.exception(f"Erreur insert_chunk: {e}")
            raise

    def insert_chunks(self, chunks: Iterable[Dict]) -> int:
        count = 0
        for ch in chunks:
            self.insert_chunk(ch)
            count += 1
        return count

    # -------------------- READ CHUNKS --------------------

    def get_chunks(
        self, status: Optional[str] = None, document_ids: Optional[List[str]] = None, limit: Optional[int] = None
    ) -> List[Dict]:
        clauses, params = [], []
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

    def _read_chunk_by_id(self, chunk_id: str) -> Optional[Dict]:
        """Récupère un chunk par son id, sans connaître document_id."""
        query = "SELECT * FROM c WHERE c.id = @id"
        params = [{"name": "@id", "value": chunk_id}]
        items = list(self.chunks_container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
        return items[0] if items else None

    def update_chunk_status(
        self,
        chunk_id: str,
        status: str,
        last_error: Optional[str] = None,
        inc_retry: bool = False,
        retry_count: Optional[int] = None,
        document_id: Optional[str] = None,
    ) -> None:
        """
        Met à jour le statut d’un chunk (compatible avec IngestionPipeline).
        """
        try:
            if document_id:
                chunk = self.chunks_container.read_item(item=chunk_id, partition_key=document_id)
            else:
                chunk = self._read_chunk_by_id(chunk_id)
                if not chunk:
                    self.logger.warning(f"Chunk introuvable: id={chunk_id}")
                    return
                document_id = chunk.get("document_id")

            chunk["status"] = status

            # Gestion du last_error
            if last_error is None:
                chunk.pop("last_error", None)
            else:
                chunk["last_error"] = last_error

            # Gestion du retry_count
            current_retry = int(chunk.get("retry_count", 0))
            if retry_count is not None:
                chunk["retry_count"] = retry_count
            elif inc_retry:
                chunk["retry_count"] = current_retry + 1
            else:
                chunk["retry_count"] = current_retry

            self.chunks_container.upsert_item(chunk)

        except exceptions.CosmosResourceNotFoundError:
            self.logger.warning(f"Chunk introuvable: id={chunk_id}")
        except Exception as e:
            self.logger.exception(f"Erreur update_chunk_status: {e}")

    def save_chunk_embedding(
        self,
        chunk_id: str,
        embedding: List[float],
        mark_status: Optional[str] = "embedded",
        document_id: Optional[str] = None,
    ) -> None:
        """
        Ajoute/met à jour l'embedding d'un chunk et (optionnel) change son statut.
        """
        try:
            if document_id:
                chunk = self.chunks_container.read_item(item=chunk_id, partition_key=document_id)
            else:
                chunk = self._read_chunk_by_id(chunk_id)
                if not chunk:
                    self.logger.warning(f"Chunk introuvable: id={chunk_id}")
                    return
                document_id = chunk.get("document_id")

            chunk["embedding"] = embedding
            if mark_status:
                chunk["status"] = mark_status
            chunk.pop("last_error", None)

            self.chunks_container.upsert_item(chunk)

        except Exception as e:
            self.logger.exception(f"Erreur save_chunk_embedding: {e}")

    # -------------------- RACCOURCIS --------------------

    def get_chunks_to_index(self, limit: Optional[int] = None) -> List[Dict]:
        return self.get_chunks(status="chunked", limit=limit)

    def get_failed_chunks(self, limit: Optional[int] = None) -> List[Dict]:
        return self.get_chunks(status="failed", limit=limit)

    # -------------------- SUPPRESSION --------------------

    def delete_document(self, document_id: str, file_type: str) -> bool:
        try:
            self.docs_container.delete_item(item=document_id, partition_key=file_type)
            return True
        except exceptions.CosmosResourceNotFoundError:
            return False
        except Exception as e:
            self.logger.exception(f"Erreur delete_document: {e}")
            return False

    def delete_chunks_by_document(self, document_id: str) -> int:
        chunks = self.get_chunks_by_document(document_id)
        deleted = 0
        for ch in chunks:
            try:
                self.chunks_container.delete_item(item=ch["id"], partition_key=document_id)
                deleted += 1
            except Exception as e:
                self.logger.warning(f"Suppression chunk échouée: {ch.get('id')} ({e})")
        return deleted

    def get_chunks_by_document(self, document_id: str, status: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        clauses = ["c.document_id = @did"]
        params = [{"name": "@did", "value": document_id}]
        if status:
            clauses.append("c.status = @st")
            params.append({"name": "@st", "value": status})
        where = " WHERE " + " AND ".join(clauses)
        query = f"SELECT * FROM c{where}"
        it = self.chunks_container.query_items(query=query, parameters=params, enable_cross_partition_query=True)
        out = []
        for i, item in enumerate(it):
            out.append(item)
            if limit and i + 1 >= limit:
                break
        return out
