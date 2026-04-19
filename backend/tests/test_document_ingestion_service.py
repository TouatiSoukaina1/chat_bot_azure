import asyncio

from app.services import document_ingestion_service as service_module


class FakeUploadFile:
    def __init__(self, filename, content, content_type="text/markdown"):
        self.filename = filename
        self._content = content
        self.content_type = content_type

    async def read(self):
        return self._content


class FakeParser:
    @staticmethod
    def _title_from_filename(filename):
        return filename.rsplit(".", 1)[0]

    def extract_text(self, file_path):
        return "# Uploaded title\n\nSome uploaded content"

    def normalize_to_markdown(self, text):
        return text.strip()


class FakeRepo:
    def __init__(self):
        self.inserted_documents = []

    def insert_document(self, document):
        self.inserted_documents.append(document)

    def get_chunks_by_document(self, document_id):
        return [
            {"id": f"{document_id}_chunk_0", "status": "indexed"},
            {"id": f"{document_id}_chunk_1", "status": "indexed"},
        ]


class FakeChunkingPipeline:
    called = False

    def __init__(self, status_in="parsed", status_out="chunked"):
        self.status_in = status_in
        self.status_out = status_out

    def run(self):
        FakeChunkingPipeline.called = True
        return 2


class FakeIndexingWorker:
    calls = 0

    def __init__(self, worker_id="worker-1"):
        self.worker_id = worker_id

    def run_once(self, limit=64, lease_seconds=120):
        FakeIndexingWorker.calls += 1
        if FakeIndexingWorker.calls == 1:
            return 1
        return 0


def test_document_ingestion_service_ingests_private_file(monkeypatch):
    repo = FakeRepo()
    service = service_module.DocumentIngestionService(repo=repo)

    FakeChunkingPipeline.called = False
    FakeIndexingWorker.calls = 0

    monkeypatch.setattr(service, "_get_parser", lambda filename, owner_user_id: FakeParser())
    monkeypatch.setattr(service_module, "ChunkingPipeline", FakeChunkingPipeline)
    monkeypatch.setattr(service_module, "IndexingWorker", FakeIndexingWorker)

    upload = FakeUploadFile(
        filename="private.md",
        content=b"# Uploaded title\n\nSome uploaded content",
        content_type="text/markdown",
    )

    document = asyncio.run(
        service.ingest_uploaded_file(
            upload_file=upload,
            owner_user_id="tenant123:user123",
        )
    )

    assert document["owner_user_id"] == "tenant123:user123"
    assert document["filename"] == "private.md"
    assert document["file_type"] == "md"
    assert document["scope"] == "private"
    assert document["source_type"] == "user_upload"
    assert document["kb"] == "user"
    assert document["status"] == "ready"
    assert "# Uploaded title" in document["text_content"]

    assert len(repo.inserted_documents) >= 2
    assert FakeChunkingPipeline.called is True
    assert FakeIndexingWorker.calls >= 2


def test_document_ingestion_service_rejects_empty_file():
    repo = FakeRepo()
    service = service_module.DocumentIngestionService(repo=repo)

    upload = FakeUploadFile(
        filename="empty.md",
        content=b"",
        content_type="text/markdown",
    )

    try:
        asyncio.run(
            service.ingest_uploaded_file(
                upload_file=upload,
                owner_user_id="tenant123:user123",
            )
        )
        assert False, "Une exception HTTPException était attendue"
    except Exception as exc:
        assert "Fichier vide" in str(exc)


def test_document_ingestion_service_rejects_unsupported_extension():
    repo = FakeRepo()
    service = service_module.DocumentIngestionService(repo=repo)

    upload = FakeUploadFile(
        filename="archive.zip",
        content=b"fake content",
        content_type="application/zip",
    )

    try:
        asyncio.run(
            service.ingest_uploaded_file(
                upload_file=upload,
                owner_user_id="tenant123:user123",
            )
        )
        assert False, "Une exception HTTPException était attendue"
    except Exception as exc:
        assert "Type de fichier non supporté" in str(exc)


def test_document_ingestion_service_rejects_unextractable_text(monkeypatch):
    repo = FakeRepo()
    service = service_module.DocumentIngestionService(repo=repo)

    class EmptyParser(FakeParser):
        def extract_text(self, file_path):
            return "   "

    monkeypatch.setattr(service, "_get_parser", lambda filename, owner_user_id: EmptyParser())

    upload = FakeUploadFile(
        filename="empty.md",
        content=b"# header",
        content_type="text/markdown",
    )

    try:
        asyncio.run(
            service.ingest_uploaded_file(
                upload_file=upload,
                owner_user_id="tenant123:user123",
            )
        )
        assert False, "Une exception HTTPException était attendue"
    except Exception as exc:
        assert "Aucun texte exploitable extrait du fichier" in str(exc)