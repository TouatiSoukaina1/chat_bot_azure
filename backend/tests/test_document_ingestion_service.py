import copy
import asyncio
import pytest
from fastapi import HTTPException

from app.services import document_ingestion_service as service_module
from app.services.document_ingestion_service import DocumentIngestionService


class FakeUploadFile:
    def __init__(self, filename, data: bytes, content_type="text/markdown"):
        self.filename = filename
        self.content_type = content_type
        self._data = data

    async def read(self):
        return self._data


class FakeDocsContainer:
    def __init__(self, repo):
        self.repo = repo
        self.last_query = None

    def query_items(self, query, parameters, enable_cross_partition_query=True):
        self.last_query = {
            "query": query,
            "parameters": parameters,
            "enable_cross_partition_query": enable_cross_partition_query,
        }
        return self.repo.duplicate_docs


class FakeRepo:
    def __init__(self, duplicate_docs=None, chunks=None):
        self.duplicate_docs = duplicate_docs or []
        self.chunks = chunks or []
        self.inserted_documents = []
        self.docs_container = FakeDocsContainer(self)

    def insert_document(self, document):
        self.inserted_documents.append(copy.deepcopy(document))

    def get_chunks_by_document(self, document_id: str):
        return self.chunks


class FakeParser:
    def __init__(self, raw_text="## Title\n\nSome content", normalized_text="# Title\n\nSome content"):
        self.raw_text = raw_text
        self.normalized_text = normalized_text
        self.extract_calls = []
        self.normalize_calls = []

    def extract_text(self, path):
        self.extract_calls.append(path)
        return self.raw_text

    def normalize_to_markdown(self, raw_text):
        self.normalize_calls.append(raw_text)
        return self.normalized_text

    def _title_from_filename(self, filename):
        return "my title"


class FakeChunker:
    init_calls = []

    def __init__(self, chunk_size, overlap, mode):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.mode = mode
        FakeChunker.init_calls.append(
            {
                "chunk_size": chunk_size,
                "overlap": overlap,
                "mode": mode,
            }
        )

    def detect_effective_mode(self, text):
        return "markdown"


class FakeChunkingPipeline:
    init_calls = []
    run_calls = []

    def __init__(self, repo=None, chunker=None, status_in="parsed", status_out="chunked"):
        FakeChunkingPipeline.init_calls.append(
            {
                "repo": repo,
                "chunker": chunker,
                "status_in": status_in,
                "status_out": status_out,
            }
        )

    def run(self, document_ids=None):
        FakeChunkingPipeline.run_calls.append({"document_ids": document_ids})
        return 1


class FakeIndexingWorker:
    init_calls = []
    run_once_calls = []

    def __init__(self, repo=None, worker_id=None):
        self.repo = repo
        self.worker_id = worker_id
        FakeIndexingWorker.init_calls.append(
            {
                "repo": repo,
                "worker_id": worker_id,
            }
        )

    def run_once(self, limit=64, lease_seconds=120):
        FakeIndexingWorker.run_once_calls.append(
            {
                "limit": limit,
                "lease_seconds": lease_seconds,
                "worker_id": self.worker_id,
            }
        )
        return 0


@pytest.mark.parametrize(
    "filename, parser_attr",
    [
        ("note.txt", "TxtParser"),
        ("note.md", "MarkdownParser"),
        ("note.pdf", "PdfParser"),
    ],
)
def test_get_parser_returns_expected_parser(monkeypatch, filename, parser_attr):
    created = {}

    class RecorderParser:
        def __init__(self, **kwargs):
            created["kwargs"] = kwargs

    monkeypatch.setattr(service_module, parser_attr, RecorderParser)

    service = DocumentIngestionService(repo=FakeRepo())
    parser = service._get_parser(filename, "tenant123:user123")

    assert isinstance(parser, RecorderParser)
    assert created["kwargs"] == {
        "kb": "user",
        "scope": "private",
        "owner_user_id": "tenant123:user123",
        "source_type": "user_upload",
    }


def test_get_parser_raises_for_unsupported_extension():
    service = DocumentIngestionService(repo=FakeRepo())

    with pytest.raises(HTTPException) as exc:
        service._get_parser("data.csv", "tenant123:user123")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Type de fichier non supporté: .csv"


def test_ingest_uploaded_file_raises_for_missing_filename():
    service = DocumentIngestionService(repo=FakeRepo())
    upload = FakeUploadFile(filename="", data=b"hello")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.ingest_uploaded_file(upload, "tenant123:user123"))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Nom de fichier manquant"


@pytest.mark.parametrize(
    "kwargs, expected_detail",
    [
        ({"chunk_mode": "weird"}, "chunk_mode invalide: weird"),
        ({"chunk_size": 99}, "chunk_size doit être >= 100"),
        ({"overlap": -1}, "overlap doit être >= 0"),
        (
            {"chunk_size": 300, "overlap": 300},
            "overlap doit être strictement inférieur à chunk_size",
        ),
    ],
)
def test_ingest_uploaded_file_validates_chunking_parameters(kwargs, expected_detail):
    service = DocumentIngestionService(repo=FakeRepo())
    upload = FakeUploadFile(filename="doc.md", data=b"# Hello")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.ingest_uploaded_file(upload, "tenant123:user123", **kwargs))

    assert exc.value.status_code == 400
    assert exc.value.detail == expected_detail


def test_ingest_uploaded_file_rejects_empty_file():
    service = DocumentIngestionService(repo=FakeRepo())
    upload = FakeUploadFile(filename="doc.md", data=b"")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.ingest_uploaded_file(upload, "tenant123:user123"))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Fichier vide"


def test_ingest_uploaded_file_rejects_duplicate_document():
    repo = FakeRepo(duplicate_docs=[{"id": "existing-doc"}])
    service = DocumentIngestionService(repo=repo)
    upload = FakeUploadFile(filename="doc.md", data=b"# Hello")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.ingest_uploaded_file(upload, "tenant123:user123"))

    assert exc.value.status_code == 409
    assert exc.value.detail == "Ce document existe déjà dans votre espace privé."


def test_ingest_uploaded_file_raises_when_no_extractable_text(monkeypatch):
    repo = FakeRepo()
    service = DocumentIngestionService(repo=repo)
    parser = FakeParser(raw_text="   ", normalized_text="   ")

    monkeypatch.setattr(service, "_get_parser", lambda filename, owner_user_id: parser)

    upload = FakeUploadFile(filename="doc.md", data=b"# Hello")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.ingest_uploaded_file(upload, "tenant123:user123"))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Aucun texte exploitable extrait du fichier"
    assert len(repo.inserted_documents) == 0


@pytest.mark.parametrize(
    "chunks, expected_status, expected_last_error",
    [
        ([{"id": "c1", "status": "indexed"}, {"id": "c2", "status": "indexed"}], "ready", None),
        ([{"id": "c1", "status": "chunked"}], "chunked", None),
        ([], "failed", "Aucun chunk généré"),
    ],
)
def test_ingest_uploaded_file_sets_final_status(monkeypatch, chunks, expected_status, expected_last_error):
    repo = FakeRepo(chunks=chunks)
    service = DocumentIngestionService(repo=repo)
    parser = FakeParser()

    FakeChunker.init_calls = []
    FakeChunkingPipeline.init_calls = []
    FakeChunkingPipeline.run_calls = []
    FakeIndexingWorker.init_calls = []
    FakeIndexingWorker.run_once_calls = []

    monkeypatch.setattr(service, "_get_parser", lambda filename, owner_user_id: parser)
    monkeypatch.setattr(service_module, "Chunker", FakeChunker)
    monkeypatch.setattr(service_module, "ChunkingPipeline", FakeChunkingPipeline)
    monkeypatch.setattr(service_module, "IndexingWorker", FakeIndexingWorker)
    monkeypatch.setattr(service_module, "uuid4", lambda: "doc-123")
    monkeypatch.setattr(service_module, "utc_now_iso", lambda: "2026-01-01T10:00:00+00:00")

    upload = FakeUploadFile(filename="doc.md", data=b"# Hello world")

    document = asyncio.run(
        service.ingest_uploaded_file(
            upload_file=upload,
            owner_user_id="tenant123:user123",
            chunk_mode="markdown",
            chunk_size=800,
            overlap=80,
        )
    )

    assert document["id"] == "doc-123"
    assert document["owner_user_id"] == "tenant123:user123"
    assert document["filename"] == "doc.md"
    assert document["title"] == "my title"
    assert document["file_type"] == "md"
    assert document["scope"] == "private"
    assert document["source_type"] == "user_upload"
    assert document["kb"] == "user"
    assert document["status"] == expected_status
    assert document["last_error"] == expected_last_error

    assert document["chunking_config"] == {
        "requested_mode": "markdown",
        "effective_mode": "markdown",
        "chunk_size": 800,
        "overlap": 80,
    }

    assert len(repo.inserted_documents) == 2
    assert repo.inserted_documents[0]["status"] == "parsed"
    assert repo.inserted_documents[1]["status"] == expected_status

    assert FakeChunker.init_calls[0] == {
        "chunk_size": 800,
        "overlap": 80,
        "mode": "markdown",
    }
    assert FakeChunkingPipeline.run_calls[0]["document_ids"] == ["doc-123"]
    assert FakeIndexingWorker.init_calls[0]["worker_id"] == "upload-doc-123"
    assert FakeIndexingWorker.run_once_calls[0]["limit"] == 64
    assert FakeIndexingWorker.run_once_calls[0]["lease_seconds"] == 120


def test_ingest_uploaded_file_builds_logical_path_and_hash(monkeypatch):
    repo = FakeRepo(chunks=[{"id": "c1", "status": "indexed"}])
    service = DocumentIngestionService(repo=repo)
    parser = FakeParser()

    FakeChunker.init_calls = []
    FakeChunkingPipeline.init_calls = []
    FakeChunkingPipeline.run_calls = []
    FakeIndexingWorker.init_calls = []
    FakeIndexingWorker.run_once_calls = []

    monkeypatch.setattr(service, "_get_parser", lambda filename, owner_user_id: parser)
    monkeypatch.setattr(service_module, "Chunker", FakeChunker)
    monkeypatch.setattr(service_module, "ChunkingPipeline", FakeChunkingPipeline)
    monkeypatch.setattr(service_module, "IndexingWorker", FakeIndexingWorker)
    monkeypatch.setattr(service_module, "uuid4", lambda: "doc-xyz")
    monkeypatch.setattr(service_module, "utc_now_iso", lambda: "2026-01-01T10:00:00+00:00")

    payload = b"# Uploaded\n\nHello world"
    upload = FakeUploadFile(filename="guide.md", data=payload)

    document = asyncio.run(service.ingest_uploaded_file(upload, "tenant123:user123"))

    expected_hash = service_module.hashlib.sha256(payload).hexdigest()

    assert document["path"] == "user_upload/tenant123:user123/doc-xyz/guide.md"
    assert document["file_hash"] == expected_hash
    assert document["file_size"] == len(payload)
    assert document["mime_type"] == "text/markdown"