from app.workers.indexing_worker import IndexingWorker


class FakeChunksContainer:
    def __init__(self, chunk):
        self.chunk = chunk

    def read_item(self, item, partition_key):
        return self.chunk


class FakeRepo:
    def __init__(self, chunk, jobs):
        self.chunks_container = FakeChunksContainer(chunk)
        self.jobs = jobs
        self.updated_chunks = []
        self.completed = []
        self.dead_letters = []
        self.requeued = []

    def claim_work_items(self, work_type, limit, lease_seconds, worker_id):
        return self.jobs

    def update_chunk_status(self, chunk_id, status, document_id=None, last_error=None, inc_retry=False):
        self.updated_chunks.append(
            {
                "chunk_id": chunk_id,
                "status": status,
                "document_id": document_id,
                "last_error": last_error,
                "inc_retry": inc_retry,
            }
        )

    def complete_work_item(self, work_id, work_type):
        self.completed.append({"work_id": work_id, "work_type": work_type})

    def dead_letter_work_item(self, work_id, work_type, reason):
        self.dead_letters.append(
            {
                "work_id": work_id,
                "work_type": work_type,
                "reason": reason,
            }
        )

    def requeue_work_item(self, work_id, work_type, reason, backoff):
        self.requeued.append(
            {
                "work_id": work_id,
                "work_type": work_type,
                "reason": reason,
                "backoff": backoff,
            }
        )


class FakeEmbedder:
    def __init__(self, embeddings):
        self.embeddings = embeddings

    def generate_embeddings(self, texts):
        return self.embeddings


class FakeIndexer:
    def __init__(self, succeeded_ids=None, failed=None):
        self.uploaded_docs = None
        self.succeeded_ids = succeeded_ids or []
        self.failed = failed or []

    def upload(self, docs, batch_size=500):
        self.uploaded_docs = docs
        return self.succeeded_ids, self.failed


def test_indexing_worker_uploads_private_chunk_with_metadata():
    chunk = {
        "id": "doc-1_chunk_0",
        "document_id": "doc-1",
        "content": "chunk content",
        "chunk_order": 0,
        "source_path": "user_upload/tenant123:user123/doc-1/autism.md",
        "file_type": "md",
        "scope": "private",
        "owner_user_id": "tenant123:user123",
        "source_type": "user_upload",
        "kb": "user",
        "doc_title": "autism",
        "section_title": "Symptoms",
        "filename": "autism.md",
    }
    jobs = [
        {
            "id": "indexing::doc-1_chunk_0",
            "chunk_id": "doc-1_chunk_0",
            "document_id": "doc-1",
            "attempts": 0,
            "max_attempts": 5,
        }
    ]

    repo = FakeRepo(chunk=chunk, jobs=jobs)
    indexer = FakeIndexer(succeeded_ids=["doc-1_chunk_0"])
    worker = IndexingWorker(
        repo=repo,
        embedder=FakeEmbedder([[0.1, 0.2, 0.3]]),
        indexer=indexer,
        worker_id="test-worker",
    )

    claimed = worker.run_once()

    assert claimed == 1
    assert indexer.uploaded_docs is not None
    assert len(indexer.uploaded_docs) == 1

    uploaded = indexer.uploaded_docs[0]
    assert uploaded["id"] == "doc-1_chunk_0"
    assert uploaded["scope"] == "private"
    assert uploaded["owner_user_id"] == "tenant123:user123"
    assert uploaded["source_type"] == "user_upload"
    assert uploaded["kb"] == "user"
    assert uploaded["doc_title"] == "autism"
    assert uploaded["section_title"] == "Symptoms"
    assert uploaded["filename"] == "autism.md"
    assert uploaded["chunk_order"] == 0
    assert uploaded["content_vector"] == [0.1, 0.2, 0.3]

    assert repo.updated_chunks[0]["status"] == "indexed"
    assert repo.completed[0]["work_id"] == "indexing::doc-1_chunk_0"


def test_indexing_worker_requeues_when_embedding_is_none():
    chunk = {
        "id": "doc-1_chunk_0",
        "document_id": "doc-1",
        "content": "chunk content",
        "chunk_order": 0,
        "source_path": "user_upload/tenant123:user123/doc-1/autism.md",
        "file_type": "md",
        "scope": "private",
        "owner_user_id": "tenant123:user123",
        "source_type": "user_upload",
        "kb": "user",
    }
    jobs = [
        {
            "id": "indexing::doc-1_chunk_0",
            "chunk_id": "doc-1_chunk_0",
            "document_id": "doc-1",
            "attempts": 0,
            "max_attempts": 5,
        }
    ]

    repo = FakeRepo(chunk=chunk, jobs=jobs)
    worker = IndexingWorker(
        repo=repo,
        embedder=FakeEmbedder([None]),
        indexer=FakeIndexer(),
        worker_id="test-worker",
    )

    claimed = worker.run_once()

    assert claimed == 1
    assert repo.updated_chunks[0]["status"] == "embedding_failed"
    assert repo.updated_chunks[0]["inc_retry"] is True
    assert repo.requeued[0]["work_id"] == "indexing::doc-1_chunk_0"


def test_indexing_worker_marks_empty_chunk_as_skipped():
    chunk = {
        "id": "doc-1_chunk_0",
        "document_id": "doc-1",
        "content": "   ",
        "chunk_order": 0,
    }
    jobs = [
        {
            "id": "indexing::doc-1_chunk_0",
            "chunk_id": "doc-1_chunk_0",
            "document_id": "doc-1",
            "attempts": 0,
            "max_attempts": 5,
        }
    ]

    repo = FakeRepo(chunk=chunk, jobs=jobs)
    worker = IndexingWorker(
        repo=repo,
        embedder=FakeEmbedder([]),
        indexer=FakeIndexer(),
        worker_id="test-worker",
    )

    claimed = worker.run_once()

    assert claimed == 1
    assert repo.updated_chunks[0]["status"] == "skipped_empty"
    assert repo.completed[0]["work_id"] == "indexing::doc-1_chunk_0"


def test_indexing_worker_requeues_when_search_upload_fails():
    chunk = {
        "id": "doc-1_chunk_0",
        "document_id": "doc-1",
        "content": "chunk content",
        "chunk_order": 0,
        "source_path": "user_upload/tenant123:user123/doc-1/autism.md",
        "file_type": "md",
        "scope": "private",
        "owner_user_id": "tenant123:user123",
        "source_type": "user_upload",
        "kb": "user",
    }
    jobs = [
        {
            "id": "indexing::doc-1_chunk_0",
            "chunk_id": "doc-1_chunk_0",
            "document_id": "doc-1",
            "attempts": 0,
            "max_attempts": 5,
        }
    ]

    repo = FakeRepo(chunk=chunk, jobs=jobs)
    indexer = FakeIndexer(
        succeeded_ids=[],
        failed=[{"id": "doc-1_chunk_0", "error": "upload failed"}],
    )

    worker = IndexingWorker(
        repo=repo,
        embedder=FakeEmbedder([[0.1, 0.2, 0.3]]),
        indexer=indexer,
        worker_id="test-worker",
    )

    claimed = worker.run_once()

    assert claimed == 1
    assert repo.updated_chunks[0]["status"] == "index_failed"
    assert repo.updated_chunks[0]["last_error"] == "upload failed"
    assert repo.requeued[0]["work_id"] == "indexing::doc-1_chunk_0"


def test_indexing_worker_dead_letters_after_max_attempts():
    chunk = {
        "id": "doc-1_chunk_0",
        "document_id": "doc-1",
        "content": "chunk content",
        "chunk_order": 0,
        "source_path": "user_upload/tenant123:user123/doc-1/autism.md",
        "file_type": "md",
        "scope": "private",
        "owner_user_id": "tenant123:user123",
        "source_type": "user_upload",
        "kb": "user",
    }
    jobs = [
        {
            "id": "indexing::doc-1_chunk_0",
            "chunk_id": "doc-1_chunk_0",
            "document_id": "doc-1",
            "attempts": 4,
            "max_attempts": 5,
        }
    ]

    repo = FakeRepo(chunk=chunk, jobs=jobs)
    worker = IndexingWorker(
        repo=repo,
        embedder=FakeEmbedder([None]),
        indexer=FakeIndexer(),
        worker_id="test-worker",
    )

    claimed = worker.run_once()

    assert claimed == 1
    assert repo.updated_chunks[0]["status"] == "embedding_failed"
    assert repo.dead_letters[0]["work_id"] == "indexing::doc-1_chunk_0"