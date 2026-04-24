from app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline


class FakeChunker:
    def chunk_text(self, text, doc_title=None):
        return [
            {
                "id": 0,
                "text": "[DOC] autism\n[SECTION] Intro\n\nChunk content 1",
                "section_title": "Intro",
                "doc_title": doc_title,
            },
            {
                "id": 1,
                "text": "[DOC] autism\n[SECTION] Symptoms\n\nChunk content 2",
                "section_title": "Symptoms",
                "doc_title": doc_title,
            },
        ]


class FakeRepo:
    def __init__(self):
        self.inserted_chunks = []
        self.enqueued_jobs = []
        self.updated_documents = []

    def get_documents_by_status(self, status):
        return [
            {
                "id": "doc-1",
                "path": "user_upload/tenant123:user123/doc-1/autism.md",
                "file_type": "md",
                "title": "autism",
                "filename": "autism.md",
                "text_content": "# Intro\n\nHello\n\n## Symptoms\n\nWorld",
                "kb": "user",
                "scope": "private",
                "owner_user_id": "tenant123:user123",
                "source_type": "user_upload",
            }
        ]

    def chunk_exists(self, chunk_id, document_id):
        return False

    def insert_chunk(self, chunk):
        self.inserted_chunks.append(chunk)

    def work_item_exists(self, work_id, work_type):
        return False

    def enqueue_work_item(self, work_item):
        self.enqueued_jobs.append(work_item)

    def update_document_status(self, document_id, file_type, new_status):
        self.updated_documents.append(
            {
                "document_id": document_id,
                "file_type": file_type,
                "new_status": new_status,
            }
        )


def test_chunking_pipeline_creates_chunks_and_jobs():
    repo = FakeRepo()
    pipeline = ChunkingPipeline(repo=repo, chunker=FakeChunker())

    inserted = pipeline.run()

    assert inserted == 2
    assert len(repo.inserted_chunks) == 2
    assert len(repo.enqueued_jobs) == 2
    assert len(repo.updated_documents) == 1

    first_chunk = repo.inserted_chunks[0]
    assert first_chunk["document_id"] == "doc-1"
    assert first_chunk["order"] == 0
    assert first_chunk["type"] == "md"
    assert first_chunk["scope"] == "private"
    assert first_chunk["owner_user_id"] == "tenant123:user123"
    assert first_chunk["source_type"] == "user_upload"
    assert first_chunk["kb"] == "user"
    assert first_chunk["filename"] == "autism.md"
    assert first_chunk["doc_title"] == "autism"
    assert first_chunk["section_title"] == "Intro"

    first_job = repo.enqueued_jobs[0]
    assert first_job["work_type"] == "indexing"
    assert first_job["document_id"] == "doc-1"
    assert first_job["chunk_id"] == "doc-1_chunk_0"
    assert first_job["status"] == "queued"

    assert repo.updated_documents[0]["new_status"] == "chunked"


def test_chunking_pipeline_skips_empty_documents():
    class EmptyRepo(FakeRepo):
        def get_documents_by_status(self, status):
            return [
                {
                    "id": "doc-empty",
                    "path": "user_upload/x/doc-empty/file.md",
                    "file_type": "md",
                    "title": "empty",
                    "filename": "empty.md",
                    "text_content": "   ",
                    "kb": "user",
                    "scope": "private",
                    "owner_user_id": "tenant123:user123",
                    "source_type": "user_upload",
                }
            ]

    repo = EmptyRepo()
    pipeline = ChunkingPipeline(repo=repo, chunker=FakeChunker())

    inserted = pipeline.run()

    assert inserted == 0
    assert repo.inserted_chunks == []
    assert repo.enqueued_jobs == []
    assert repo.updated_documents == []


def test_chunking_pipeline_does_not_reinsert_existing_chunks():
    class ExistingChunkRepo(FakeRepo):
        def chunk_exists(self, chunk_id, document_id):
            return True

    repo = ExistingChunkRepo()
    pipeline = ChunkingPipeline(repo=repo, chunker=FakeChunker())

    inserted = pipeline.run()

    assert inserted == 0
    assert repo.inserted_chunks == []
    assert len(repo.enqueued_jobs) == 2


def test_chunking_pipeline_does_not_enqueue_existing_work_items():
    class ExistingJobRepo(FakeRepo):
        def work_item_exists(self, work_id, work_type):
            return True

    repo = ExistingJobRepo()
    pipeline = ChunkingPipeline(repo=repo, chunker=FakeChunker())

    inserted = pipeline.run()

    assert inserted == 2
    assert len(repo.inserted_chunks) == 2
    assert repo.enqueued_jobs == []
    assert len(repo.updated_documents) == 1


def test_chunking_pipeline_returns_zero_when_no_documents():
    class NoDocsRepo(FakeRepo):
        def get_documents_by_status(self, status):
            return []

    repo = NoDocsRepo()
    pipeline = ChunkingPipeline(repo=repo, chunker=FakeChunker())

    inserted = pipeline.run()

    assert inserted == 0
    assert repo.inserted_chunks == []
    assert repo.enqueued_jobs == []
    assert repo.updated_documents == []