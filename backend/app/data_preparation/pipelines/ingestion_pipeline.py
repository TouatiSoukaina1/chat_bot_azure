# chat_bot_azure/backend/app/data_preparation/pipelines/ingestion_pipeline.py
import logging
import time
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field

from app.core.database import DocumentRepository
from app.data_preparation.processors.embedder import Embedder
from app.core.azure_search_client import AzureSearchIndexer
from app.core.metrics import record_latency, record_chunk, embedding_latency


@dataclass
class IngestionStats:
    total_chunks: int = 0
    embedded: int = 0
    indexed: int = 0
    failed: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "total_chunks": self.total_chunks,
            "embedded": self.embedded,
            "indexed": self.indexed,
            "failed": self.failed,
            "duration_seconds": self.duration_seconds,
            "success_rate": (self.embedded / self.total_chunks) if self.total_chunks else 0.0,
            "errors": self.errors,
        }


class IngestionPipeline:
    """
    Pipeline industriel :
    - Étapes : Chunking → Embedding → Indexation Azure Search
    - Idempotent et traçable
    - Gestion des erreurs et relances robustes
    """

    def __init__(
        self,
        repository: Optional[DocumentRepository] = None,
        embedder: Optional[Embedder] = None,
        indexer: Optional[AzureSearchIndexer] = None,
        batch_size: int = 100,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ):
        self.logger = logging.getLogger("app.pipeline.ingestion")
        self.repo = repository or DocumentRepository()
        self.embedder = embedder or Embedder()
        self.indexer = indexer or AzureSearchIndexer()
        self.batch_size = max(1, batch_size)
        self.on_progress = on_progress

    # -------------------------------------------------------------------------
    # PIPELINE PRINCIPAL
    # -------------------------------------------------------------------------
    def run(self, document_ids: Optional[List[str]] = None, force_reindex: bool = False) -> IngestionStats:
        """Pipeline principal : Embeddings + Indexation Azure Search"""
        stats = IngestionStats()
        start = time.time()

        # 1️⃣ Vérifie que l’index Azure existe
        if not self._prepare_index():
            stats.errors.append("Index creation failed")
            return stats

        # 2️⃣ Récupère les chunks à traiter
        status = None if force_reindex else "chunked"
        chunks = self.repo.get_chunks(status=status, document_ids=document_ids)
        stats.total_chunks = len(chunks)
        if not chunks:
            self.logger.info("Aucun chunk à traiter.")
            return stats

        # 3️⃣ Génère les embeddings
        enriched_chunks = self._generate_embeddings(chunks, stats)

        # 4️⃣ Indexation Azure Search
        res = self._index_chunks(enriched_chunks)
        stats.indexed = len(res["succeeded"])
        stats.failed += len(res["failed"])

        stats.duration_seconds = time.time() - start
        self._log_summary(stats, title="Pipeline terminé")
        return stats

    # -------------------------------------------------------------------------
    # ♻️ RELANCE DES EMBEDDINGS ÉCHOUÉS
    # -------------------------------------------------------------------------
    def rerun_failed_embeddings(self, limit: Optional[int] = None) -> Dict:
        """
        Relance robuste des embeddings échoués.
        - Sélectionne uniquement les chunks encore 'failed' avec erreur d'embedding.
        - Batchs avec backoff léger.
        - Mise à jour Cosmos DB fiable.
        - Retourne un rapport complet : embedded, failed, IDs corrigés.
        """
        self.logger.info("♻️ Relance industrielle des embeddings échoués...")
        stats = IngestionStats()
        fixed_ids, still_failed = [], []

        failed_chunks = self.repo.get_failed_chunks(limit=limit)
        embedding_failed = [
            c for c in failed_chunks
            if c.get("status") == "failed" and "embedding" in str(c.get("last_error", "")).lower()
        ]

        total = len(embedding_failed)
        if not embedding_failed:
            self.logger.info("Aucun chunk à retraiter pour l’étape d’embedding.")
            return stats.to_dict()

        batch_size = self.embedder.batch_size
        self.logger.info(f"➡️ {total} chunks à retraiter (embedding). Batch size = {batch_size}")

        for start in range(0, total, batch_size):
            batch = embedding_failed[start:start + batch_size]
            texts = [c.get("content", "") for c in batch]

            if self.on_progress:
                self.on_progress(min(start + batch_size, total), total)

            try:
                embeddings = self.embedder.generate_embeddings(texts)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur embedding batch ({start}-{start+batch_size}): {e}")
                embeddings = [self.embedder.generate_embedding(t) for t in texts]

            for c, emb in zip(batch, embeddings):
                cid = c["id"]
                try:
                    if emb:
                        self.repo.save_chunk_embedding(chunk_id=cid, embedding=emb)
                        self.repo.update_chunk_status(chunk_id=cid, status="embedded", last_error=None)
                        stats.embedded += 1
                        fixed_ids.append(cid)
                    else:
                        raise ValueError("Embedding vide ou invalide")
                except Exception as e2:
                    stats.failed += 1
                    still_failed.append(cid)
                    err = f"Erreur embedding (chunk={cid}): {e2}"
                    stats.errors.append(err)
                    self.logger.warning(err)
                    try:
                        self.repo.update_chunk_status(chunk_id=cid, status="failed", last_error=str(e2))
                    except Exception as e3:
                        self.logger.warning(f"⚠️ Échec update status pour {cid}: {e3}")

            time.sleep(0.3)

        self.logger.info(f"🔁 Relance terminée : {stats.embedded} corrigés / {stats.failed} échecs persistants.")
        return {**stats.to_dict(), "fixed_ids": fixed_ids, "still_failed_ids": still_failed}

    # -------------------------------------------------------------------------
    # RELANCE DES INDEXATIONS ÉCHOUÉES
    # -------------------------------------------------------------------------
    def rerun_failed_indexation(self, limit: Optional[int] = None) -> Dict:
        """Relance uniquement les chunks échoués à l’étape d’indexation Azure Search."""
        self.logger.info("♻️ Relance des indexations échouées...")
        stats = IngestionStats()

        failed_chunks = self.repo.get_failed_chunks(limit=limit)
        index_failed = [
            c for c in failed_chunks
            if c.get("last_error") and any(k in c["last_error"].lower() for k in ["index", "azure search"])
        ]

        if not index_failed:
            self.logger.info("Aucun chunk échoué à l’étape d’indexation.")
            return stats.to_dict()

        total = len(index_failed)
        self.logger.info(f"➡️ {total} chunks à réindexer (Azure Search).")

        ready_to_index = []
        for c in index_failed:
            if not c.get("embedding"):
                doc_chunks = self.repo.get_chunks_by_document(c["document_id"])
                found = next((ch.get("embedding") for ch in doc_chunks if ch.get("id") == c["id"]), None)
                if not found:
                    self.logger.warning(f"⚠️ Embedding manquant pour chunk {c['id']} (ignoré).")
                    stats.failed += 1
                    continue
                c["embedding"] = found
            ready_to_index.append(c)

        if not ready_to_index:
            self.logger.info("Aucun chunk prêt à réindexer (embedding manquant pour tous).")
            return stats.to_dict()

        try:
            self.indexer.create_index()
            result = self.indexer.index_documents(ready_to_index)
            stats.indexed += result.get("indexed", 0)
            stats.failed += result.get("failed", 0)
            self.logger.info(f"🔁 Réindexation: {stats.indexed} succès / {stats.failed} échecs.")
            for c in ready_to_index:
                self.repo.update_chunk_status(chunk_id=c["id"], status="indexed", last_error=None)
        except Exception as e:
            self.logger.exception(f"Erreur lors de la réindexation: {e}")
            stats.failed += len(ready_to_index)
            stats.errors.append(str(e))

        self.logger.info(f"Relance indexation terminée : {stats.indexed} corrigés, {stats.failed} toujours en échec.")
        return stats.to_dict()

    # -------------------------------------------------------------------------
    #  CYCLE COMPLET D'INGESTION
    # -------------------------------------------------------------------------
    def full_ingestion_cycle(self) -> Dict[str, Dict]:
        """Exécute le pipeline complet + relances automatiques"""
        self.logger.info("🚀 Démarrage du cycle complet d’ingestion...")
        stats_run = self.run()
        stats_emb = self.rerun_failed_embeddings()
        stats_idx = self.rerun_failed_indexation()
        self.logger.info("✅ Cycle complet terminé.")
        return {
            "initial_run": stats_run.to_dict(),
            "retry_embeddings": stats_emb,
            "retry_indexation": stats_idx,
        }

    # -------------------------------------------------------------------------
    #  MÉTHODES INTERNES
    # -------------------------------------------------------------------------
    def _prepare_index(self) -> bool:
        try:
            self.indexer.create_index()
            return True
        except Exception as e:
            self.logger.error(f"Create index failed: {e}", exc_info=True)
            return False

    def _generate_embeddings(self, chunks: List[Dict], stats: IngestionStats) -> List[Dict]:
        """Embeddings par lots (optimisé via Embedder.generate_embeddings)."""
        enriched = []
        total = len(chunks)
        batch_size = self.embedder.batch_size

        for start in range(0, total, batch_size):
            batch = chunks[start:start + batch_size]
            texts = [c.get("content", "") for c in batch]

            if self.on_progress:
                self.on_progress(min(start + batch_size, total), total)

            try:
                embeddings = self.embedder.generate_embeddings(texts)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur embedding batch ({start}-{start+batch_size}): {e}")
                embeddings = [self.embedder.generate_embedding(t) for t in texts]

            for c, emb in zip(batch, embeddings):
                if emb:
                    try:
                        self.repo.save_chunk_embedding(chunk_id=c["id"], embedding=emb)
                        enriched.append({**c, "embedding": emb})
                        stats.embedded += 1
                    except Exception as e2:
                        stats.failed += 1
                        err = f"Erreur sauvegarde embedding (chunk {c.get('id')}): {e2}"
                        stats.errors.append(err)
                        self.logger.warning(err)
                else:
                    stats.failed += 1
                    err = f"Embedding vide pour chunk {c.get('id')}"
                    stats.errors.append(err)
                    self.logger.warning(err)
                    self.repo.update_chunk_status(chunk_id=c["id"], status="failed", last_error="Empty embedding")

        self.logger.info(f"✅ Embeddings générés pour {stats.embedded}/{stats.total_chunks} chunks.")
        return enriched

    def _index_chunks(self, chunks: List[Dict]) -> Dict[str, List[str]]:
        """Indexation robuste et traçable."""
        succeeded_all, failed_all = [], []

        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start:start + self.batch_size]
            self.logger.info(f"🚀 Indexation batch {start}-{start + len(batch)} ({len(batch)} docs)...")

            try:
                res = self.indexer.index_documents(batch)
                succeeded_ids = res.get("succeeded_ids", [])
                failed_ids = res.get("failed_ids", [])

                succeeded_all.extend(succeeded_ids)
                failed_all.extend(failed_ids)

                for cid in succeeded_ids:
                    try:
                        self.repo.update_chunk_status(chunk_id=cid, status="indexed", last_error=None)
                    except Exception as e2:
                        self.logger.warning(f"⚠️ Impossible de marquer 'indexed' pour {cid}: {e2}")

                for cid in failed_ids:
                    try:
                        self.repo.update_chunk_status(chunk_id=cid, status="failed", last_error="Indexation partielle échouée")
                    except Exception as e2:
                        self.logger.warning(f"⚠️ Impossible de marquer 'failed' pour {cid}: {e2}")

                self.logger.info(f"✅ Batch terminé: {len(succeeded_ids)} succès / {len(failed_ids)} échecs")

            except Exception as e:
                self.logger.error(f"🔥 Erreur critique indexation batch: {e}", exc_info=True)
                for c in batch:
                    failed_all.append(c["id"])
                    try:
                        self.repo.update_chunk_status(chunk_id=c["id"], status="failed", last_error=str(e))
                    except Exception as e2:
                        self.logger.warning(f"⚠️ Impossible de marquer 'failed' pour {c['id']}: {e2}")

        return {"succeeded": succeeded_all, "failed": failed_all}

    def _log_summary(self, stats: IngestionStats, title: str) -> None:
        self.logger.info("=" * 50)
        self.logger.info(title)
        self.logger.info(f"Chunks : {stats.total_chunks}")
        self.logger.info(f"Embedded : {stats.embedded}")
        self.logger.info(f"Indexés : {stats.indexed}")
        self.logger.info(f"Échecs : {stats.failed}")
        self.logger.info(f"Durée : {stats.duration_seconds:.2f}s")
        if stats.errors:
            self.logger.info(f"Erreurs : {len(stats.errors)} (voir logs détaillés)")
        self.logger.info("=" * 50)
