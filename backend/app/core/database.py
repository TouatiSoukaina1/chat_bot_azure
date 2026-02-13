import os
import time
import logging
from typing import List, Dict, Optional, Iterable,Iterator
from azure.cosmos import CosmosClient, exceptions
from dotenv import load_dotenv
load_dotenv()
# Optionnel si tu veux relier au monitoring Prometheus
# from app.core.metrics import record_chunk
from azure.cosmos import exceptions
from azure.core import MatchConditions
from azure.identity import DefaultAzureCredential

class DocumentRepository:
    def __init__(
        self,
        uri: Optional[str] = None,
        database_name: Optional[str] = None,
        container_documents: Optional[str] = None,
        container_chunks: Optional[str] = None,
        container_work_items: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger("app.repository")

        self.uri = uri or os.getenv("COSMOSDB_URI")
        self.database_name = database_name or os.getenv("COSMOS_DATABASE")
        self.container_documents = container_documents or os.getenv("COSMOSDB_CONTAINER_DOCUMENTS")
        self.container_chunks = container_chunks or os.getenv("COSMOSDB_CONTAINER_CHUNKS")
        self.container_work_items = container_work_items or os.getenv("COSMOSDB_CONTAINER_WORK_ITEMS")
        if not all([self.uri, self.database_name, self.container_documents, self.container_chunks, self.container_work_items]):
            raise ValueError("Config Cosmos incomplète (URI/DATABASE/CONTAINERS).")

        try:
            credential = DefaultAzureCredential()
            self.client = CosmosClient(self.uri, credential=credential)
            self.database = self.client.get_database_client(self.database_name)
            self.docs_container = self.database.get_container_client(self.container_documents)
            self.chunks_container = self.database.get_container_client(self.container_chunks)
            self.work_container = self.database.get_container_client(self.container_work_items)  
            self.logger.info("✅ Connexion Cosmos DB (keyless) OK.")
        except exceptions.CosmosHttpResponseError as e:
            self.logger.error("❌ Erreur connexion Cosmos DB: %s", e)
            raise

    # -------------------------------------------------------------------------
    # INSERT / UPSERT DOCUMENTS
    # -------------------------------------------------------------------------
    def iter_all_documents(
        self,
        max_item_count: int = 200,
        partition_key: Optional[str] = None,
    ) -> Iterator[Dict]:
        """
        Itère sur tous les documents du container documents.
        - partition_key: si tu connais une valeur de PK (ex: file_type), c'est plus rapide/moins coûteux.
        """
        query = "SELECT * FROM c"

        if partition_key is not None:
            it = self.docs_container.query_items(
                query=query,
                parameters=[],
                partition_key=partition_key,
                max_item_count=max_item_count,
            )
        else:
            it = self.docs_container.query_items(
                query=query,
                parameters=[],
                enable_cross_partition_query=True,
                max_item_count=max_item_count,
            )

        # Pagination automatique via by_page()
        for page in it.by_page():
            for item in page:
                yield item
    def is_processed(self, path: str) -> bool:
        """Vérifie si un document avec ce chemin a déjà été inséré."""
        try:
            query = "SELECT VALUE COUNT(1) FROM c WHERE c.path = @path"
            params = [{"name": "@path", "value": path}]
            result = list(self.docs_container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
            return result and result[0] > 0
        except Exception as e:
            self.logger.warning(f"Erreur is_processed({path}): {e}")
            return False
        
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
        self.logger.info(f"✅ {count} documents insérés dans CosmosDB.")
        return count

    # -------------------------------------------------------------------------
    # READ DOCUMENTS
    # -------------------------------------------------------------------------
    def get_document_by_path(self, path: str) -> Optional[Dict]:
        query = "SELECT * FROM c WHERE c.path = @path"
        params = [{"name": "@path", "value": path}]
        items = list(self.docs_container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
        return items[0] if items else None

    def get_documents_by_status(
        self, status: Optional[str] = "chunked", file_types: Optional[List[str]] = None, limit: Optional[int] = None
    ) -> List[Dict]:
        """Récupère les documents selon leur statut (par défaut 'chunked')."""
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

    # -------------------------------------------------------------------------
    # UPDATE DOCUMENTS
    # -------------------------------------------------------------------------
    def update_document_status(self, document_id: str, file_type: str, new_status: str) -> None:
        try:
            doc = self.docs_container.read_item(item=document_id, partition_key=file_type)
            doc["status"] = new_status
            self.docs_container.upsert_item(doc)
            self.logger.info(f"[Cosmos] Document {document_id} → {new_status}")
        except exceptions.CosmosResourceNotFoundError:
            self.logger.warning(f"Document introuvable: id={document_id}, pk={file_type}")
        except Exception as e:
            self.logger.exception(f"Erreur update_document_status: {e}")
            raise

    def mark_document_error(self, document_id: str, file_type: str, message: str) -> None:
        try:
            doc = self.docs_container.read_item(item=document_id, partition_key=file_type)
            doc["status"] = "failed"
            doc["last_error"] = message
            self.docs_container.upsert_item(doc)
            self.logger.warning(f"[Cosmos] Document {document_id} marqué failed: {message}")
        except exceptions.CosmosResourceNotFoundError:
            self.logger.warning(f"Document introuvable pour erreur: id={document_id}, pk={file_type}")

    # -------------------------------------------------------------------------
    # INSERT / UPSERT CHUNKS
    # -------------------------------------------------------------------------
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
        self.logger.info(f"✅ {count} chunks insérés dans CosmosDB.")
        return count

    # -------------------------------------------------------------------------
    # READ CHUNKS
    # -------------------------------------------------------------------------
    def _read_chunk_by_id(self, chunk_id: str) -> Optional[Dict]:
        query = "SELECT * FROM c WHERE c.id = @id"
        params = [{"name": "@id", "value": chunk_id}]
        items = list(self.chunks_container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
        return items[0] if items else None

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

    # -------------------------------------------------------------------------
    # UPDATE CHUNKS (avec retry et logs enrichis)
    # -------------------------------------------------------------------------
    def update_chunk_status(
        self,
        chunk_id: str,
        status: str,
        last_error: Optional[str] = None,
        inc_retry: bool = False,
        retry_count: Optional[int] = None,
        document_id: Optional[str] = None,
    ) -> None:
        """Met à jour le statut d’un chunk avec gestion d’erreurs et retry Cosmos."""
        for attempt in range(3):
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
                if last_error is None:
                    chunk.pop("last_error", None)
                else:
                    chunk["last_error"] = last_error

                current_retry = int(chunk.get("retry_count", 0))
                if retry_count is not None:
                    chunk["retry_count"] = retry_count
                elif inc_retry:
                    chunk["retry_count"] = current_retry + 1

                self.chunks_container.upsert_item(chunk)
                self.logger.info(f"[Cosmos] Chunk {chunk_id} → {status}")
                # record_chunk("db_update", "success")
                return

            except exceptions.CosmosHttpResponseError as e:
                if e.status_code == 429:
                    delay = (2 ** attempt) * 0.5
                    self.logger.warning(f"⚠️ Throttling CosmosDB, retry dans {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                self.logger.exception(f"Erreur Cosmos update_chunk_status: {e}")
                # record_chunk("db_update", "failed")
                break
            except Exception as e:
                self.logger.exception(f"Erreur update_chunk_status: {e}")
                # record_chunk("db_update", "failed")
                break

    def save_chunk_embedding(
        self,
        chunk_id: str,
        embedding: List[float],
        mark_status: Optional[str] = "embedded",
        document_id: Optional[str] = None,
    ) -> None:
        """Ajoute/met à jour l'embedding d'un chunk avec retry et logs."""
        for attempt in range(3):
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
                self.logger.info(f"[Cosmos] Embedding enregistré pour chunk {chunk_id}")
                # record_chunk("embedding_save", "success")
                return

            except exceptions.CosmosHttpResponseError as e:
                if e.status_code == 429:
                    delay = (2 ** attempt) * 0.5
                    self.logger.warning(f"⚠️ Throttling CosmosDB, retry dans {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                self.logger.exception(f"Erreur Cosmos save_chunk_embedding: {e}")
                # record_chunk("embedding_save", "failed")
                break
            except Exception as e:
                self.logger.exception(f"Erreur save_chunk_embedding: {e}")
                # record_chunk("embedding_save", "failed")
                break

    # -------------------------------------------------------------------------
    # RACCOURCIS
    # -------------------------------------------------------------------------
    def create_chunk_if_absent(self, chunk: Dict) -> bool:
        """
        Tente de créer un chunk. Retourne True si créé, False si déjà présent.
        (Plus économique que read-before-write)
        """
        try:
            self.chunks_container.create_item(body=chunk)
            return True
        except exceptions.CosmosHttpResponseError as e:
            # 409 Conflict => item déjà existe
            if getattr(e, "status_code", None) == 409:
                return False
            raise

    def create_work_item_if_absent(self, work_item: Dict) -> bool:
        """
        Tente de créer un work_item. Retourne True si créé, False si déjà présent.
        Container work_items PK = /work_type
        """
        try:
            self.work_container.create_item(body=work_item)
            return True
        except exceptions.CosmosHttpResponseError as e:
            if getattr(e, "status_code", None) == 409:
                return False
            raise
    
    def get_chunks_to_index(self, limit: Optional[int] = None) -> List[Dict]:
        return self.get_chunks(status="embedded", limit=limit)

    def get_failed_chunks(self, limit: Optional[int] = None) -> List[Dict]:
        return self.get_chunks(status="failed", limit=limit)

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
    
    def enqueue_work_item(self, work_item: Dict) -> None:
        """
        Upsert d'un work item.
        Container work_items: PK = /work_type
        """
        if "id" not in work_item or "work_type" not in work_item:
            raise ValueError("work_item doit contenir 'id' et 'work_type'.")

        self.work_container.upsert_item(work_item)

    def claim_work_items(
        self,
        work_type: str,
        worker_id: str,
        limit: int = 10,
        lease_seconds: int = 60,
        now: Optional[int] = None,
    ) -> List[Dict]:
        """
        Claim des work_items :
        - status=queued
        - OU status=processing si lease expiré
        - next_run_at <= now (si défini)
        """
        now = int(now or time.time())

        query = """
        SELECT TOP @limit * FROM c
        WHERE c.work_type = @wt
          AND (
            c.status = "queued"
            OR (c.status = "processing" AND c.lease_until < @now)
          )
          AND (NOT IS_DEFINED(c.next_run_at) OR c.next_run_at <= @now)
          AND (NOT IS_DEFINED(c.max_attempts) OR NOT IS_DEFINED(c.attempts) OR c.attempts < c.max_attempts)
        ORDER BY c._ts ASC
        """

        params = [
            {"name": "@limit", "value": int(limit)},
            {"name": "@wt", "value": work_type},
            {"name": "@now", "value": now},
        ]

        # On cible la bonne partition (= work_type)
        candidates = list(
            self.work_container.query_items(
                query=query,
                parameters=params,
                partition_key=work_type,
            )
        )

        claimed: List[Dict] = []

        for job in candidates:
            # Tentative de "lock" optimiste via etag (évite double claim)
            try:
                job["status"] = "processing"
                job["worker_id"] = worker_id
                job["lease_until"] = now + int(lease_seconds)
                job["updated_at"] = now

                self.work_container.replace_item(
                    item=job["id"],
                    body=job,
                    etag=job.get("_etag"),
                    match_condition=MatchConditions.IfNotModified,
                )
                claimed.append(job)

            except exceptions.CosmosHttpResponseError as e:
                # Conflit (quelqu’un l’a claim juste avant), on ignore
                if getattr(e, "status_code", None) in (409, 412):
                    continue
                raise

        return claimed

    def complete_work_item(self, work_id: str, work_type: str) -> None:
        now = int(time.time())
        try:
            item = self.work_container.read_item(item=work_id, partition_key=work_type)
            item["status"] = "done"
            item["lease_until"] = 0
            item["updated_at"] = now
            item.pop("last_error", None)
            self.work_container.upsert_item(item)
        except exceptions.CosmosHttpResponseError as e:
            self.logger.warning(f"complete_work_item failed: {work_id} err={e}")

    def fail_work_item(self, work_id: str, work_type: str, error: str, inc_attempts: bool = True) -> None:
        now = int(time.time())
        try:
            item = self.work_container.read_item(item=work_id, partition_key=work_type)
            item["status"] = "failed"
            item["lease_until"] = 0
            item["updated_at"] = now
            item["last_error"] = error
            if inc_attempts:
                item["attempts"] = int(item.get("attempts", 0)) + 1
            self.work_container.upsert_item(item)
        except exceptions.CosmosHttpResponseError as e:
            self.logger.warning(f"fail_work_item failed: {work_id} err={e}")
    
    def get_document_by_id(self, document_id: str, file_type: str) -> Optional[Dict]:
        """
        Récupère un document par son id Cosmos.
        Nécessite la partition key (pk) -> ici /file_type.

        Args:
            document_id: id du document (champ "id")
            file_type: valeur de la pk (ex: "pdf", "txt", "png")

        Returns:
            dict du document ou None si introuvable.
        """
        try:
            return self.docs_container.read_item(item=document_id, partition_key=file_type)
        except exceptions.CosmosResourceNotFoundError:
            return None
        except Exception as e:
            self.logger.exception(f"Erreur get_document_by_id(id={document_id}, pk={file_type}): {e}")
            return None
    
    def chunk_exists(self, chunk_id: str, document_id: str) -> bool:
        """
        Vérifie si un chunk existe déjà dans le container chunks.
        PK chunks = /document_id

        Args:
            chunk_id: id du chunk (ex: "doc123_chunk_0")
            document_id: valeur de la partition key (document_id)

        Returns:
            True si existe, False sinon.
        """
        try:
            _ = self.chunks_container.read_item(item=chunk_id, partition_key=document_id)
            return True
        except exceptions.CosmosResourceNotFoundError:
            return False
        except Exception as e:
            self.logger.exception(f"Erreur chunk_exists(id={chunk_id}, pk={document_id}): {e}")
            return False
    def work_item_exists(self, work_id: str, work_type: str) -> bool:
        """
        Vérifie si un work_item existe déjà.
        PK work_items = /work_type

        Args:
            work_id: id du work item (ex: "indexing::doc_chunk_0")
            work_type: valeur de la pk (ex: "indexing")

        Returns:
            True si existe, False sinon.
        """
        try:
            _ = self.work_container.read_item(item=work_id, partition_key=work_type)
            return True
        except exceptions.CosmosResourceNotFoundError:
            return False
        except Exception as e:
            self.logger.exception(f"Erreur work_item_exists(id={work_id}, pk={work_type}): {e}")
            return False