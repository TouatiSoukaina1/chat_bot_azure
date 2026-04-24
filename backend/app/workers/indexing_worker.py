import time
import random
import logging
from typing import List, Dict

from azure.cosmos import exceptions

from app.core.database import DocumentRepository
from app.data_preparation.processors.embedder import Embedder
from app.data_preparation.indexing.azure_search_indexer import AzureSearchIndexer

logging.basicConfig(level=logging.INFO)

WORK_TYPE = "indexing"


def compute_backoff_s(attempts: int, base: int = 5, cap: int = 300) -> int:
    exp = min(cap, base * (2 ** max(0, attempts)))
    jitter = random.randint(0, 3)
    return min(cap, exp + jitter)


class IndexingWorker:
    def __init__(
        self,
        repo=None,
        embedder=None,
        indexer=None,
        worker_id: str = "worker-1",
        claim_limit: int = 64,
        lease_seconds: int = 90,
        max_attempts: int = 5,
        sleep_s: float = 2.0,
    ):
        self.logger = logging.getLogger("app.IndexingWorker")
        self.repo = repo or DocumentRepository()
        self.embedder = embedder or Embedder(batch_size=16)
        self.indexer = indexer or AzureSearchIndexer()

        self.worker_id = worker_id
        self.claim_limit = claim_limit
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.sleep_s = sleep_s

    def run_once(self, limit: int | None = None, lease_seconds: int | None = None) -> int:
        jobs = self.repo.claim_work_items(
            work_type=WORK_TYPE,
            limit=limit or self.claim_limit,
            lease_seconds=lease_seconds or self.lease_seconds,
            worker_id=self.worker_id,
        )

        if not jobs:
            self.logger.info("Aucun job à traiter (queue vide).")
            return 0

        self.logger.info("✅ %s jobs claimés par %s", len(jobs), self.worker_id)

        for i in range(0, len(jobs), 16):
            self._process_batch(jobs[i : i + 16])

        return len(jobs)

    def run_forever(self):
        self.logger.info("IndexingWorker started (worker_id=%s)", self.worker_id)

        while True:
            jobs = self.repo.claim_work_items(
                work_type=WORK_TYPE,
                limit=self.claim_limit,
                lease_seconds=self.lease_seconds,
                worker_id=self.worker_id,
            )

            if not jobs:
                time.sleep(self.sleep_s)
                continue

            self.logger.info("✅ %s jobs claimés par %s", len(jobs), self.worker_id)

            for i in range(0, len(jobs), 16):
                self._process_batch(jobs[i : i + 16])

    def _process_batch(self, jobs: List[Dict]):
        chunks: List[Dict] = []
        texts: List[str] = []
        job_by_chunk: Dict[str, Dict] = {}

        self.logger.info("📦 Début traitement batch de %s jobs", len(jobs))

        for job in jobs:
            work_id = job.get("id")
            chunk_id = job.get("chunk_id")
            doc_id = job.get("document_id")

            if not work_id or not chunk_id or not doc_id:
                self.logger.warning("Job invalide ignoré: %s", job)
                continue

            if "max_attempts" not in job:
                job["max_attempts"] = self.max_attempts

            try:
                ch = self.repo.chunks_container.read_item(item=chunk_id, partition_key=doc_id)
            except exceptions.CosmosResourceNotFoundError:
                self.logger.warning("❌ Chunk introuvable chunk_id=%s doc_id=%s", chunk_id, doc_id)
                self.repo.dead_letter_work_item(work_id, WORK_TYPE, "chunk not found")
                continue
            except Exception as e:
                attempts = int(job.get("attempts", 0))
                backoff = compute_backoff_s(attempts)
                self.logger.exception("Erreur lecture chunk Cosmos chunk_id=%s: %s", chunk_id, e)
                self.repo.requeue_work_item(work_id, WORK_TYPE, f"cosmos read error: {e}", backoff)
                continue

            content = (ch.get("content") or "").strip()
            if not content:
                self.logger.warning("⚠️ Chunk vide chunk_id=%s doc_id=%s", chunk_id, doc_id)
                self.repo.update_chunk_status(
                    chunk_id,
                    "skipped_empty",
                    last_error="empty content",
                    document_id=doc_id,
                )
                self.repo.complete_work_item(work_id, WORK_TYPE)
                continue

            chunks.append(ch)
            texts.append(content)
            job_by_chunk[chunk_id] = job

        if not chunks:
            self.logger.info("Aucun chunk exploitable dans ce batch.")
            return

        # ===== LOG 1 : après lecture des chunks Cosmos =====
        self.logger.info(
            "🧩 %s chunks valides lus depuis Cosmos. Exemple: id=%s scope=%s owner=%s source_type=%s",
            len(chunks),
            chunks[0].get("id"),
            chunks[0].get("scope"),
            chunks[0].get("owner_user_id"),
            chunks[0].get("source_type"),
        )

        embeddings = self.embedder.generate_embeddings(texts)

        docs_to_upload: List[Dict] = []
        for ch, emb in zip(chunks, embeddings):
            chunk_id = ch["id"]
            doc_id = ch.get("document_id")
            job = job_by_chunk.get(chunk_id)
            if job is None:
                continue

            work_id = job["id"]
            attempts = int(job.get("attempts", 0))
            max_attempts = int(job.get("max_attempts", self.max_attempts))

            if emb is None:
                self.logger.warning("❌ Embedding None pour chunk_id=%s", chunk_id)
                self.repo.update_chunk_status(
                    chunk_id,
                    "embedding_failed",
                    last_error="embedding=None",
                    inc_retry=True,
                    document_id=doc_id,
                )
                if attempts + 1 >= max_attempts:
                    self.repo.dead_letter_work_item(work_id, WORK_TYPE, "embedding failed (None)")
                else:
                    backoff = compute_backoff_s(attempts)
                    self.repo.requeue_work_item(work_id, WORK_TYPE, "embedding failed (None)", backoff)
                continue

            docs_to_upload.append({
                "id": chunk_id,
                "content": ch.get("content", ""),
                "content_vector": emb,
                "document_id": doc_id,
                "chunk_order": int(ch.get("chunk_order", 0)),
                "source_path": ch.get("source_path", ""),
                "file_type": ch.get("file_type", ""),

                # métadonnées filtrage / sécurité
                "scope": ch.get("scope", "global"),
                "owner_user_id": ch.get("owner_user_id"),
                "source_type": ch.get("source_type", "who"),
                "kb": ch.get("kb", "who"),

                # métadonnées utiles UI
                "doc_title": ch.get("doc_title", ""),
                "section_title": ch.get("section_title", ""),
                "filename": ch.get("filename", ""),
            })

        if not docs_to_upload:
            self.logger.info("Aucun document prêt à uploader dans Azure Search.")
            return

        # ===== LOG 2 : juste avant upload Azure Search =====
        sample = docs_to_upload[0]
        self.logger.info(
            "🚀 Upload Azure Search de %s chunks. Exemple: id=%s scope=%s owner=%s source_type=%s chunk_order=%s",
            len(docs_to_upload),
            sample.get("id"),
            sample.get("scope"),
            sample.get("owner_user_id"),
            sample.get("source_type"),
            sample.get("chunk_order"),
        )

        chunk_meta: Dict[str, Dict] = {}
        for doc in docs_to_upload:
            cid = doc["id"]
            job = job_by_chunk.get(cid)
            if not job:
                continue
            chunk_meta[cid] = {
                "document_id": doc.get("document_id"),
                "work_id": job.get("id"),
                "attempts": int(job.get("attempts", 0)),
                "max_attempts": int(job.get("max_attempts", self.max_attempts)),
            }

        succeeded_ids, failed = self.indexer.upload(docs_to_upload, batch_size=500)

        # ===== LOG 3 : après upload Azure Search =====
        self.logger.info(
            "📊 Résultat upload Azure Search: succès=%s | échecs=%s",
            len(succeeded_ids),
            len(failed),
        )

        for chunk_id in succeeded_ids:
            meta = chunk_meta.get(chunk_id)
            if not meta:
                continue
            doc_id = meta["document_id"]
            work_id = meta["work_id"]

            self.repo.update_chunk_status(
                chunk_id=chunk_id,
                status="indexed",
                document_id=doc_id,
            )
            self.repo.complete_work_item(work_id, WORK_TYPE)

        for f in failed:
            chunk_id = f.get("id")
            err = f.get("error", "upload failed")

            meta = chunk_meta.get(chunk_id)
            if not meta:
                continue
            doc_id = meta["document_id"]
            work_id = meta["work_id"]
            attempts = meta["attempts"]
            max_attempts = meta["max_attempts"]

            self.logger.warning("❌ Upload Search échoué chunk_id=%s err=%s", chunk_id, err)

            self.repo.update_chunk_status(
                chunk_id=chunk_id,
                status="index_failed",
                last_error=err,
                inc_retry=True,
                document_id=doc_id,
            )

            if attempts + 1 >= max_attempts:
                self.repo.dead_letter_work_item(work_id, WORK_TYPE, f"search upload failed: {err}")
            else:
                backoff = compute_backoff_s(attempts)
                self.repo.requeue_work_item(
                    work_id,
                    WORK_TYPE,
                    f"search upload failed: {err}",
                    backoff,
                )