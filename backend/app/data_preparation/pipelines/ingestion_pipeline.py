import logging
import time
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field

from app.core.database import DocumentRepository
from app.data_preparation.processors.embedder import Embedder
from app.core.azure_search_client import AzureSearchIndexer


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
    Chunks -> Embeddings -> Index Azure Search
    - Idempotence (pas de doublons)
    - Pas de retry automatique (relance manuelle via méthodes dédiées)
    - Injection de dépendances (testable et maintenable)
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
        chunks = self._generate_embeddings(chunks, stats)

        # 4️⃣ Indexation Azure Search
        indexed = self._index_chunks(chunks)
        stats.indexed = indexed

        # 5️⃣ Mise à jour des statuts
        self._mark_indexed(chunks)

        stats.duration_seconds = time.time() - start
        self._log_summary(stats, title="Pipeline terminé")
        return stats

    # -------------------------------------------------------------------------
    # ♻️ RELANCE DES EMBEDDINGS ÉCHOUÉS
    # -------------------------------------------------------------------------
    def rerun_failed_embeddings(self, limit: Optional[int] = None) -> Dict:
        """
        Relance uniquement les chunks échoués à l’étape d’embedding.
        - Sélectionne status='failed' avec last_error contenant 'embedding'
        - Regénère les embeddings en batch
        - Met à jour les statuts et compte les réussites
        """
        self.logger.info("♻️ Relance des embeddings échoués (mode batch)...")
        stats = IngestionStats()

        # 1️⃣ Récupération des chunks échoués
        failed_chunks = self.repo.get_failed_chunks(limit=limit)
        embedding_failed = [
            c for c in failed_chunks
            if c.get("last_error") and "embedding" in c.get("last_error", "").lower()
        ]

        if not embedding_failed:
            self.logger.info("Aucun chunk échoué à l’étape d’embedding.")
            return stats.to_dict()

        total = len(embedding_failed)
        batch_size = self.embedder.batch_size  # souvent 16
        self.logger.info(f"➡️ {total} chunks à retraiter (embedding). Batch size = {batch_size}")

        for start in range(0, total, batch_size):
            batch = embedding_failed[start:start + batch_size]
            texts = [c.get("content", "") for c in batch]

            if self.on_progress:
                self.on_progress(min(start + batch_size, total), total)

            try:
                embeddings = self.embedder.generate_embeddings(texts)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur batch embedding ({start}-{start+batch_size}): {e}")
                embeddings = [self.embedder.generate_embedding(t) for t in texts]

            # 2️⃣ Traitement des résultats du batch
            for c, emb in zip(batch, embeddings):
                if emb:
                    try:
                        self.repo.save_chunk_embedding(chunk_id=c["id"], embedding=emb)
                        self.repo.update_chunk_status(chunk_id=c["id"], status="embedded", last_error=None)
                        stats.embedded += 1
                    except Exception as e2:
                        stats.failed += 1
                        err = f"Erreur sauvegarde embedding (chunk {c.get('id')}): {e2}"
                        stats.errors.append(err)
                        self.logger.warning(err)
                        self.repo.update_chunk_status(
                            chunk_id=c["id"],
                            status="failed",
                            last_error=str(e2)
                        )
                else:
                    stats.failed += 1
                    err = f"Embedding vide pour chunk {c.get('id')}"
                    stats.errors.append(err)
                    self.logger.warning(err)
                    self.repo.update_chunk_status(
                        chunk_id=c["id"],
                        status="failed",
                        last_error="Empty embedding"
                    )

        self.logger.info(f" Relance embeddings terminée : {stats.embedded} corrigés, {stats.failed} toujours en échec.")
        return stats.to_dict()


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
                # Recharge l’embedding depuis la base si manquant
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
    #  CYCLE COMPLET D'INGESTION (FULL PIPELINE)
    # -------------------------------------------------------------------------
    def full_ingestion_cycle(self) -> Dict[str, Dict]:
        """
        Exécute le pipeline complet + relances automatiques :
        1. run()
        2. rerun_failed_embeddings()
        3. rerun_failed_indexation()
        """
        self.logger.info(" Démarrage du cycle complet d’ingestion...")
        stats_run = self.run()
        stats_emb = self.rerun_failed_embeddings()
        stats_idx = self.rerun_failed_indexation()

        self.logger.info("Cycle complet terminé.")
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
        batch_size = self.embedder.batch_size  # souvent 16

        for start in range(0, total, batch_size):
            batch = chunks[start:start + batch_size]
            texts = [c.get("content", "") for c in batch]

            if self.on_progress:
                self.on_progress(min(start + batch_size, total), total)

            try:
                embeddings = self.embedder.generate_embeddings(texts)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur embedding batch ({start}-{start+batch_size}): {e}")
                # fallback unitaire si le batch échoue
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

        return enriched


    def _index_chunks(self, chunks: List[Dict]) -> int:
        if not chunks:
            return 0

        total_indexed = 0
        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start:start + self.batch_size]
            try:
                res = self.indexer.index_documents(batch)
                total_indexed += res.get("indexed", 0)
            except Exception as e:
                self.logger.error(f"Indexation batch erreur: {e}", exc_info=True)
                for c in batch:
                    self.repo.update_chunk_status(chunk_id=c["id"], status="failed", last_error=str(e))
        return total_indexed

    def _mark_indexed(self, chunks: List[Dict]) -> None:
        for c in chunks:
            try:
                self.repo.update_chunk_status(chunk_id=c["id"], status="indexed", last_error=None)
            except Exception as e:
                self.logger.warning(f"Impossible de marquer 'indexed' {c['id']}: {e}")

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
