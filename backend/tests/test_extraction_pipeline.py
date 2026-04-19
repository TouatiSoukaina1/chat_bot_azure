from app.data_preparation.pipelines import extraction_pipeline as extraction_module


class FakeRepo:
    def __init__(self, existing=None):
        self.existing = existing or set()

    def get_document_by_id(self, doc_id, file_type):
        if (doc_id, file_type) in self.existing:
            return {"id": doc_id, "file_type": file_type}
        return None


class FakeParser:
    def __init__(self, name):
        self.name = name
        self.received = []

    def process_file(self, file_paths, document_overrides_by_path=None):
        self.received.append(
            {
                "file_paths": file_paths,
                "document_overrides_by_path": document_overrides_by_path,
            }
        )
        return len(file_paths)


def test_run_extraction_from_files_dispatches_by_extension(monkeypatch):
    txt_parser = FakeParser("txt")
    md_parser = FakeParser("md")
    pdf_parser = FakeParser("pdf")

    monkeypatch.setattr(extraction_module, "DocumentRepository", lambda: FakeRepo())
    monkeypatch.setattr(
        extraction_module,
        "_build_parsers",
        lambda kb, scope, owner_user_id, source_type: [
            (txt_parser, [".txt"]),
            (md_parser, [".md", ".markdown"]),
            (pdf_parser, [".pdf"]),
        ],
    )

    count = extraction_module.run_extraction_from_files(
        file_paths=[
            "/tmp/doc1.txt",
            "/tmp/doc2.md",
            "/tmp/doc3.pdf",
            "/tmp/doc4.markdown",
        ],
        kb="who",
        scope="global",
        owner_user_id=None,
        source_type="who",
    )

    assert count == 4
    assert txt_parser.received[0]["file_paths"] == ["/tmp/doc1.txt"]
    assert md_parser.received[0]["file_paths"] == ["/tmp/doc2.md", "/tmp/doc4.markdown"]
    assert pdf_parser.received[0]["file_paths"] == ["/tmp/doc3.pdf"]


def test_run_extraction_from_files_skips_already_processed(monkeypatch):
    existing_doc_id = extraction_module._make_doc_id("/tmp/already.txt")
    existing = {(existing_doc_id, "txt")}

    txt_parser = FakeParser("txt")

    monkeypatch.setattr(extraction_module, "DocumentRepository", lambda: FakeRepo(existing=existing))
    monkeypatch.setattr(
        extraction_module,
        "_build_parsers",
        lambda kb, scope, owner_user_id, source_type: [
            (txt_parser, [".txt"]),
        ],
    )

    count = extraction_module.run_extraction_from_files(
        file_paths=[
            "/tmp/already.txt",
            "/tmp/new.txt",
        ],
        kb="who",
        scope="global",
        owner_user_id=None,
        source_type="who",
    )

    assert count == 1
    assert txt_parser.received[0]["file_paths"] == ["/tmp/new.txt"]


def test_run_extraction_from_files_passes_relevant_overrides(monkeypatch):
    md_parser = FakeParser("md")

    monkeypatch.setattr(extraction_module, "DocumentRepository", lambda: FakeRepo())
    monkeypatch.setattr(
        extraction_module,
        "_build_parsers",
        lambda kb, scope, owner_user_id, source_type: [
            (md_parser, [".md"]),
        ],
    )

    overrides = {
        "/tmp/doc1.md": {"id": "doc-1"},
        "/tmp/doc2.md": {"id": "doc-2"},
        "/tmp/ignored.txt": {"id": "ignored"},
    }

    count = extraction_module.run_extraction_from_files(
        file_paths=["/tmp/doc1.md", "/tmp/doc2.md"],
        kb="user",
        scope="private",
        owner_user_id="tenant123:user123",
        source_type="user_upload",
        document_overrides_by_path=overrides,
    )

    assert count == 2
    passed = md_parser.received[0]["document_overrides_by_path"]
    assert passed == {
        "/tmp/doc1.md": {"id": "doc-1"},
        "/tmp/doc2.md": {"id": "doc-2"},
    }


def test_run_extraction_from_files_returns_zero_when_no_files():
    count = extraction_module.run_extraction_from_files(
        file_paths=[],
        kb="who",
        scope="global",
        owner_user_id=None,
        source_type="who",
    )

    assert count == 0


def test_run_private_user_extraction_sets_private_scope(monkeypatch):
    captured = {}

    def fake_run_extraction_from_files(**kwargs):
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(extraction_module, "run_extraction_from_files", fake_run_extraction_from_files)

    result = extraction_module.run_private_user_extraction(
        file_paths=["/tmp/private.md"],
        owner_user_id="tenant123:user123",
        kb="user",
    )

    assert result == 1
    assert captured["scope"] == "private"
    assert captured["owner_user_id"] == "tenant123:user123"
    assert captured["source_type"] == "user_upload"
    assert captured["kb"] == "user"


def test_run_global_who_extraction_sets_global_scope(monkeypatch):
    captured = {}

    def fake_run_extraction_from_directory(**kwargs):
        captured.update(kwargs)
        return 2

    monkeypatch.setattr(extraction_module, "run_extraction_from_directory", fake_run_extraction_from_directory)

    result = extraction_module.run_global_who_extraction(raw_dir="/tmp/who")

    assert result == 2
    assert captured["raw_dir"] == "/tmp/who"
    assert captured["scope"] == "global"
    assert captured["owner_user_id"] is None
    assert captured["source_type"] == "who"
    assert captured["kb"] == "who"