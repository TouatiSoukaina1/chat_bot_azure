# chat_bot_azure/backend/app/workers/indexing_worker.py

import os
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

            for i in range(0, len(jobs), 16):
                self._process_batch(jobs[i : i + 16])

    def _process_batch(self, jobs: List[Dict]):
        chunks: List[Dict] = []
        texts: List[str] = []
        job_by_chunk: Dict[str, Dict] = {}

        for job in jobs:
            work_id = job.get("id")
            chunk_id = job.get("chunk_id")
            doc_id = job.get("document_id")

            if not work_id or not chunk_id or not doc_id:
                continue

            if "max_attempts" not in job:
                job["max_attempts"] = self.max_attempts

            try:
                ch = self.repo.chunks_container.read_item(item=chunk_id, partition_key=doc_id)
            except exceptions.CosmosResourceNotFoundError:
                self.repo.dead_letter_work_item(work_id, WORK_TYPE, "chunk not found")
                continue
            except Exception as e:
                attempts = int(job.get("attempts", 0))
                backoff = compute_backoff_s(attempts)
                self.repo.requeue_work_item(work_id, WORK_TYPE, f"cosmos read error: {e}", backoff)
                continue

            content = (ch.get("content") or "").strip()
            if not content:
                self.repo.update_chunk_status(chunk_id, "skipped_empty", last_error="empty content", document_id=doc_id)
                self.repo.complete_work_item(work_id, WORK_TYPE)
                continue

            chunks.append(ch)
            texts.append(content)
            job_by_chunk[chunk_id] = job

        if not chunks:
            return

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
                self.repo.update_chunk_status(
                    chunk_id, "embedding_failed", last_error="embedding=None", inc_retry=True, document_id=doc_id
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
                "chunk_order": int(ch.get("order", 0)),
                "source_path": ch.get("source_path", ""),
                "file_type": ch.get("type", ""),
            })

        if not docs_to_upload:
            return

        succeeded_ids, failed = self.indexer.upload(docs_to_upload, batch_size=500)

        for doc in docs_to_upload:
            chunk_id = doc["id"]
            doc_id = doc.get("document_id")
            job = job_by_chunk.get(chunk_id)
            if job is None:
                continue

            work_id = job["id"]
            attempts = int(job.get("attempts", 0))
            max_attempts = int(job.get("max_attempts", self.max_attempts))

            if chunk_id in succeeded_ids:
                self.repo.update_chunk_status(chunk_id, "indexed", document_id=doc_id)
                self.repo.complete_work_item(work_id, WORK_TYPE)
            else:
                err = failed.get(chunk_id, "unknown upload failure")
                self.repo.update_chunk_status(chunk_id, "index_failed", last_error=err, inc_retry=True, document_id=doc_id)

                if attempts + 1 >= max_attempts:
                    self.repo.dead_letter_work_item(work_id, WORK_TYPE, err)
                else:
                    backoff = compute_backoff_s(attempts)
                    self.repo.requeue_work_item(work_id, WORK_TYPE, err, backoff)


if __name__ == "__main__":
    wid = os.getenv("WORKER_ID", "worker-1")
    claim_limit = int(os.getenv("WORKER_CLAIM_LIMIT", "64"))
    lease_seconds = int(os.getenv("WORKER_LEASE_SECONDS", "90"))
    max_attempts = int(os.getenv("WORKER_MAX_ATTEMPTS", "5"))
    sleep_s = float(os.getenv("WORKER_SLEEP_S", "2.0"))

    IndexingWorker(
        worker_id=wid,
        claim_limit=claim_limit,
        lease_seconds=lease_seconds,
        max_attempts=max_attempts,
        sleep_s=sleep_s,
    ).run_forever()
