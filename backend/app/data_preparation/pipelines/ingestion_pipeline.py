# app/data_preparation/pipelines/ingestion_pipeline.py
import logging
import time
from typing import List, Dict, Optional, Callable, Iterable
from dataclasses import dataclass, field

from app.core.database import DocumentRepository
from app.data_preparation.processors.embeder import Embedder
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
    - Retry contrôlé pour les chunks en échec
    - Injection de dépendances (testable)
    """

    def __init__(
        self,
        repository: Optional[DocumentRepository] = None,
        embedder: Optional[Embedder] = None,
        indexer: Optional[AzureSearchIndexer] = None,
        batch_size: int = 100,
        max_retries_per_chunk: int = 3,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ):
        self.logger = logging.getLogger("app.pipeline.ingestion")
        self.repo = repository or DocumentRepository()
        self.embedder = embedder or Embedder()
        self.indexer = indexer or AzureSearchIndexer()
        self.batch_size = max(1, batch_size)
        self.max_retries_per_chunk = max(0, max_retries_per_chunk)
        self.on_progress = on_progress

    # --------- PUBLIC API ---------

    def run(self, document_ids: Optional[List[str]] = None, force_reindex: bool = False) -> IngestionStats:
        """Pipeline principal: embed + index pour les chunks prêts (status='chunked') ou tous si force_reindex."""
        stats = IngestionStats()
        start = time.time()

        # 1) Index prêt
        if not self._prepare_index():
            stats.errors.append("Index creation failed")
            return stats

        # 2) Récupérer les chunks à traiter
        status = None if force_reindex else "chunked"
        chunks = self.repo.get_chunks(status=status, document_ids=document_ids)  # [{id, content, ...}]
        stats.total_chunks = len(chunks)
        if not chunks:
            self.logger.info("Aucun chunk à traiter.")
            return stats

        # 3) Générer embeddings
        chunks = self._generate_embeddings(chunks, stats)

        # 4) Indexation
        indexed = self._index_chunks(chunks)
        stats.indexed = indexed

        # 5) Mettre à jour statut
        self._mark_indexed(chunks)

        stats.duration_seconds = time.time() - start
        self._log_summary(stats, title="Pipeline terminé")
        return stats

    def retry_failed_chunks(
        self,
        document_ids: Optional[List[str]] = None,
        hard_reset: bool = False,
    ) -> IngestionStats:
        """
        Retente UNIQUEMENT les chunks en échec (status='failed'), en respectant un plafond de tentatives.
        - hard_reset=True : remet retry_count=0 pour tout le monde avant de relancer.
        """
        failed = self.repo.get_chunks(status="failed", document_ids=document_ids)
        if not failed:
            self.logger.info("Aucun chunk en échec à retraiter.")
            return IngestionStats()

        # Filtrer ceux qui ont dépassé le plafond de retry
        if not hard_reset:
            failed = [c for c in failed if (c.get("retry_count", 0) < self.max_retries_per_chunk)]

        if not failed:
            self.logger.info("Tous les chunks échoués ont atteint le plafond de retries.")
            return IngestionStats(errors=["retry_limit_reached"])

        # Réarmer le statut et (optionnel) le compteur
        for c in failed:
            new_retry_count = 0 if hard_reset else (c.get("retry_count", 0) + 1)
            self.repo.update_chunk_status(
                chunk_id=c["id"],
                status="chunked",
                last_error=None,
                retry_count=new_retry_count,
            )

        # Relancer le pipeline mais ciblé uniquement sur les documents concernés
        doc_ids = sorted({c.get("document_id") for c in failed if c.get("document_id")})
        self.logger.info(f"Relance sur {len(failed)} chunks échoués (docs ciblés: {len(doc_ids)})")
        stats = self.run(document_ids=doc_ids, force_reindex=False)
        return stats

    def _prepare_index(self) -> bool:
        try:
            self.indexer.create_index()
            return True
        except Exception as e:
            self.logger.error(f"Create index failed: {e}", exc_info=True)
            return False

    def _generate_embeddings(self, chunks: List[Dict], stats: IngestionStats) -> List[Dict]:
        """Embeddings one-by-one (fiable). Pour du gros volume : regrouper par batch."""
        enriched = []
        total = len(chunks)
        for i, chunk in enumerate(chunks, 1):
            if self.on_progress:
                self.on_progress(i, total)

            try:
                emb = self.embedder.generate_embedding(chunk.get("content", ""))
                if not emb:
                    raise ValueError("Empty embedding")

                # Persister côté repo (optionnel mais utile en cas de crash avant indexation)
                self.repo.save_chunk_embedding(chunk_id=chunk["id"], embedding=emb)

                enriched.append({**chunk, "embedding": emb})
            except Exception as e:
                stats.failed += 1
                err = f"Embedding failed for {chunk.get('id')}: {e}"
                stats.errors.append(err)
                self.logger.warning(err)
                # Marquer le chunk en échec + stocker l’erreur + incrémenter le compteur
                self.repo.update_chunk_status(
                    chunk_id=chunk["id"],
                    status="failed",
                    last_error=str(e),
                    inc_retry=True,
                )
            else:
                stats.embedded += 1

        return enriched

    def _index_chunks(self, chunks: List[Dict]) -> int:
        """Indexation par batch dans Azure Search. Retourne le nombre indexé."""
        if not chunks:
            return 0

        total = 0
        batch: List[Dict] = []

        def flush(b: Iterable[Dict]) -> int:
            if not b:
                return 0
            try:
                res = self.indexer.index_documents(list(b), batch_size=self.batch_size)
                return int(res.get("indexed", 0))
            except Exception as e:
                self.logger.error(f"Indexation batch erreur: {e}", exc_info=True)
                # Marquer en failed tous les chunks du batch
                for c in b:
                    self.repo.update_chunk_status(
                        chunk_id=c["id"], status="failed", last_error=str(e), inc_retry=True
                    )
                return 0

        for c in chunks:
            batch.append({
                "id": c["id"],
                "content": c["content"],
                "embedding": c["embedding"],
                "metadata": c.get("metadata", {}),
            })
            if len(batch) >= self.batch_size:
                total += flush(batch)
                batch = []

        total += flush(batch)
        return total

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
