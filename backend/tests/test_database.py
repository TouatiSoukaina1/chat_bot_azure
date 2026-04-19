import pytest

from app.core import database as db_module


class FakeResourceNotFoundError(Exception):
    pass


class FakeCosmosHttpResponseError(Exception):
    def __init__(self, status_code, message=None):
        super().__init__(message or f"status={status_code}")
        self.status_code = status_code


class FakeQueryResult:
    def __init__(self, items):
        self.items = list(items)

    def __iter__(self):
        return iter(self.items)

    def by_page(self):
        yield self.items


class FakeContainer:
    def __init__(self, pk_field):
        self.pk_field = pk_field
        self.items = {}

    def _key(self, item):
        return (item["id"], item[self.pk_field])

    def upsert_item(self, item):
        self.items[self._key(item)] = dict(item)

    def create_item(self, body):
        key = self._key(body)
        if key in self.items:
            raise FakeCosmosHttpResponseError(409, "Conflict")
        self.items[key] = dict(body)

    def read_item(self, item, partition_key):
        key = (item, partition_key)
        if key not in self.items:
            raise FakeResourceNotFoundError()
        return dict(self.items[key])

    def delete_item(self, item, partition_key):
        key = (item, partition_key)
        if key not in self.items:
            raise FakeResourceNotFoundError()
        del self.items[key]

    def replace_item(self, item, body, etag=None, match_condition=None):
        self.upsert_item(body)

    def query_items(
        self,
        query,
        parameters=None,
        enable_cross_partition_query=False,
        partition_key=None,
        max_item_count=None,
    ):
        parameters = parameters or []
        params = {p["name"]: p["value"] for p in parameters}
        values = list(self.items.values())

        if partition_key is not None:
            values = [v for v in values if v.get(self.pk_field) == partition_key]

        if "SELECT VALUE COUNT(1)" in query and "@path" in params:
            count = sum(1 for v in values if v.get("path") == params["@path"])
            return FakeQueryResult([count])

        if "@path" in params:
            values = [v for v in values if v.get("path") == params["@path"]]

        if "@id" in params:
            values = [v for v in values if v.get("id") == params["@id"]]

        if "@status" in params:
            values = [v for v in values if v.get("status") == params["@status"]]

        ft_values = [value for key, value in params.items() if key.startswith("@ft")]
        if ft_values:
            values = [v for v in values if v.get("file_type") in ft_values]

        did_values = [value for key, value in params.items() if key.startswith("@did")]
        if did_values:
            values = [v for v in values if v.get("document_id") in did_values]

        if "@st" in params:
            values = [v for v in values if v.get("status") == params["@st"]]

        if "@wt" in params:
            values = [v for v in values if v.get("work_type") == params["@wt"]]

        if "@doc_id" in params:
            values = [v for v in values if v.get("document_id") == params["@doc_id"]]

        if "@now" in params:
            now = params["@now"]
            filtered = []
            for v in values:
                status_ok = (
                    v.get("status") == "queued"
                    or (
                        v.get("status") == "processing"
                        and v.get("lease_until", 0) < now
                    )
                )
                next_run_ok = ("next_run_at" not in v) or (v["next_run_at"] <= now)
                attempts_ok = (
                    ("max_attempts" not in v)
                    or ("attempts" not in v)
                    or (v["attempts"] < v["max_attempts"])
                )
                if status_ok and next_run_ok and attempts_ok:
                    filtered.append(v)
            values = filtered

        if "ORDER BY c._ts ASC" in query:
            values = sorted(values, key=lambda x: x.get("_ts", 0))

        if "@limit" in params:
            values = values[: int(params["@limit"])]

        if max_item_count is not None:
            values = values[:max_item_count]

        return FakeQueryResult(values)


class FakeDatabase:
    def __init__(self):
        self.containers = {
            "documents": FakeContainer(pk_field="file_type"),
            "chunks": FakeContainer(pk_field="document_id"),
            "work_items": FakeContainer(pk_field="work_type"),
        }

    def get_container_client(self, name):
        return self.containers[name]


class FakeCosmosClient:
    def __init__(self, uri, credential=None):
        self.uri = uri
        self.credential = credential
        self.database = FakeDatabase()
        self.closed = False

    def get_database_client(self, database_name):
        return self.database

    def close(self):
        self.closed = True


def patch_cosmos(monkeypatch):
    monkeypatch.setattr(db_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(db_module, "CosmosClient", FakeCosmosClient)
    monkeypatch.setattr(
        db_module.exceptions,
        "CosmosResourceNotFoundError",
        FakeResourceNotFoundError,
    )
    monkeypatch.setattr(
        db_module.exceptions,
        "CosmosHttpResponseError",
        FakeCosmosHttpResponseError,
    )


def make_repo(monkeypatch):
    patch_cosmos(monkeypatch)
    return db_module.DocumentRepository(
        uri="https://cosmos.test",
        database_name="db",
        container_documents="documents",
        container_chunks="chunks",
        container_work_items="work_items",
    )


def test_init_raises_when_config_missing(monkeypatch):
    monkeypatch.delenv("COSMOSDB_URI", raising=False)
    monkeypatch.delenv("COSMOS_DATABASE", raising=False)
    monkeypatch.delenv("COSMOSDB_CONTAINER_DOCUMENTS", raising=False)
    monkeypatch.delenv("COSMOSDB_CONTAINER_CHUNKS", raising=False)
    monkeypatch.delenv("COSMOSDB_CONTAINER_WORK_ITEMS", raising=False)

    with pytest.raises(ValueError) as exc:
        db_module.DocumentRepository()

    assert "Config Cosmos incomplète" in str(exc.value)


def test_lazy_connection_properties_and_close(monkeypatch):
    repo = make_repo(monkeypatch)

    assert repo._client is None
    assert repo._database is None
    assert repo._docs_container is None

    docs = repo.docs_container
    assert docs is not None
    assert repo.client is not None
    assert repo.database is not None
    assert repo.chunks_container is not None
    assert repo.work_container is not None

    client = repo.client
    repo.close()

    assert client.closed is True
    assert repo._client is None
    assert repo._database is None
    assert repo._docs_container is None
    assert repo._chunks_container is None
    assert repo._work_container is None


def test_iter_all_documents_and_is_processed(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.insert_document(
        {
            "id": "doc-1",
            "file_type": "md",
            "path": "user_upload/u1/doc-1/file.md",
            "status": "parsed",
        }
    )
    repo.insert_document(
        {
            "id": "doc-2",
            "file_type": "txt",
            "path": "user_upload/u1/doc-2/file.txt",
            "status": "parsed",
        }
    )

    all_docs = list(repo.iter_all_documents())
    assert len(all_docs) == 2

    md_docs = list(repo.iter_all_documents(partition_key="md"))
    assert len(md_docs) == 1
    assert md_docs[0]["id"] == "doc-1"

    assert repo.is_processed("user_upload/u1/doc-1/file.md") is True
    assert repo.is_processed("missing-path") is False


def test_insert_documents_get_document_by_path_and_get_documents_by_status(monkeypatch):
    repo = make_repo(monkeypatch)

    inserted = repo.insert_documents(
        [
            {
                "id": "doc-1",
                "file_type": "md",
                "path": "p1",
                "status": "chunked",
            },
            {
                "id": "doc-2",
                "file_type": "txt",
                "path": "p2",
                "status": "chunked",
            },
            {
                "id": "doc-3",
                "file_type": "pdf",
                "path": "p3",
                "status": "parsed",
            },
        ]
    )

    assert inserted == 3

    found = repo.get_document_by_path("p2")
    assert found is not None
    assert found["id"] == "doc-2"

    chunked_docs = repo.get_documents_by_status(status="chunked")
    assert {d["id"] for d in chunked_docs} == {"doc-1", "doc-2"}

    limited = repo.get_documents_by_status(status="chunked", file_types=["md", "txt"], limit=1)
    assert len(limited) == 1


def test_update_document_status_mark_error_and_get_document_by_id(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.insert_document(
        {
            "id": "doc-1",
            "file_type": "md",
            "path": "p1",
            "status": "parsed",
        }
    )

    repo.update_document_status("doc-1", "md", "chunked")
    doc = repo.get_document_by_id("doc-1", "md")
    assert doc["status"] == "chunked"

    repo.mark_document_error("doc-1", "md", "boom")
    doc = repo.get_document_by_id("doc-1", "md")
    assert doc["status"] == "failed"
    assert doc["last_error"] == "boom"

    assert repo.get_document_by_id("missing", "md") is None


def test_insert_chunks_get_chunks_and_helpers(monkeypatch):
    repo = make_repo(monkeypatch)

    inserted = repo.insert_chunks(
        [
            {
                "id": "chunk-1",
                "document_id": "doc-1",
                "status": "chunked",
                "content": "hello",
            },
            {
                "id": "chunk-2",
                "document_id": "doc-1",
                "status": "embedded",
                "content": "world",
            },
            {
                "id": "chunk-3",
                "document_id": "doc-2",
                "status": "failed",
                "content": "oops",
            },
        ]
    )

    assert inserted == 3

    by_doc = repo.get_chunks(document_ids=["doc-1"])
    assert {c["id"] for c in by_doc} == {"chunk-1", "chunk-2"}

    embedded = repo.get_chunks_to_index()
    assert len(embedded) == 1
    assert embedded[0]["id"] == "chunk-2"

    failed = repo.get_failed_chunks()
    assert len(failed) == 1
    assert failed[0]["id"] == "chunk-3"

    by_doc_filtered = repo.get_chunks_by_document("doc-1", status="embedded")
    assert len(by_doc_filtered) == 1
    assert by_doc_filtered[0]["id"] == "chunk-2"


def test_update_chunk_status_and_save_chunk_embedding(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.insert_chunk(
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "status": "chunked",
            "retry_count": 0,
            "content": "hello",
        }
    )

    repo.update_chunk_status(
        chunk_id="chunk-1",
        status="embedding_failed",
        last_error="embedding=None",
        inc_retry=True,
        document_id="doc-1",
    )

    chunk = repo.chunks_container.read_item("chunk-1", "doc-1")
    assert chunk["status"] == "embedding_failed"
    assert chunk["last_error"] == "embedding=None"
    assert chunk["retry_count"] == 1

    repo.save_chunk_embedding(
        chunk_id="chunk-1",
        embedding=[0.1, 0.2],
        mark_status="embedded",
        document_id="doc-1",
    )

    chunk = repo.chunks_container.read_item("chunk-1", "doc-1")
    assert chunk["status"] == "embedded"
    assert chunk["embedding"] == [0.1, 0.2]
    assert "last_error" not in chunk


def test_update_chunk_status_and_save_embedding_without_document_id(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.insert_chunk(
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "status": "chunked",
            "retry_count": 0,
            "content": "hello",
        }
    )

    repo.update_chunk_status(
        chunk_id="chunk-1",
        status="indexed",
        document_id=None,
    )

    chunk = repo.chunks_container.read_item("chunk-1", "doc-1")
    assert chunk["status"] == "indexed"

    repo.save_chunk_embedding(
        chunk_id="chunk-1",
        embedding=[0.3, 0.4],
        mark_status="embedded",
        document_id=None,
    )

    chunk = repo.chunks_container.read_item("chunk-1", "doc-1")
    assert chunk["embedding"] == [0.3, 0.4]
    assert chunk["status"] == "embedded"


def test_create_chunk_if_absent_and_create_work_item_if_absent(monkeypatch):
    repo = make_repo(monkeypatch)

    assert repo.create_chunk_if_absent(
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "status": "chunked",
        }
    ) is True

    assert repo.create_chunk_if_absent(
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "status": "chunked",
        }
    ) is False

    assert repo.create_work_item_if_absent(
        {
            "id": "job-1",
            "work_type": "indexing",
            "status": "queued",
        }
    ) is True

    assert repo.create_work_item_if_absent(
        {
            "id": "job-1",
            "work_type": "indexing",
            "status": "queued",
        }
    ) is False


def test_enqueue_claim_complete_fail_and_exists_helpers(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.enqueue_work_item(
        {
            "id": "job-1",
            "work_type": "indexing",
            "status": "queued",
            "attempts": 0,
            "_etag": "etag-1",
            "_ts": 1,
        }
    )
    repo.enqueue_work_item(
        {
            "id": "job-2",
            "work_type": "indexing",
            "status": "processing",
            "lease_until": 5,
            "attempts": 0,
            "_etag": "etag-2",
            "_ts": 2,
        }
    )
    repo.enqueue_work_item(
        {
            "id": "job-3",
            "work_type": "indexing",
            "status": "queued",
            "attempts": 5,
            "max_attempts": 5,
            "_etag": "etag-3",
            "_ts": 3,
        }
    )

    claimed = repo.claim_work_items(
        work_type="indexing",
        worker_id="worker-1",
        limit=10,
        lease_seconds=60,
        now=10,
    )

    claimed_ids = {j["id"] for j in claimed}
    assert claimed_ids == {"job-1", "job-2"}

    for job in claimed:
        assert job["status"] == "processing"
        assert job["worker_id"] == "worker-1"
        assert job["lease_until"] == 70

    repo.complete_work_item("job-1", "indexing")
    completed = repo.work_container.read_item("job-1", "indexing")
    assert completed["status"] == "done"
    assert completed["lease_until"] == 0

    repo.fail_work_item("job-2", "indexing", "boom", inc_attempts=True)
    failed = repo.work_container.read_item("job-2", "indexing")
    assert failed["status"] == "failed"
    assert failed["last_error"] == "boom"
    assert failed["attempts"] == 1

    repo.insert_document(
        {
            "id": "doc-1",
            "file_type": "md",
            "path": "p1",
            "status": "parsed",
        }
    )
    repo.insert_chunk(
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "status": "chunked",
            "content": "hello",
        }
    )

    assert repo.chunk_exists("chunk-1", "doc-1") is True
    assert repo.chunk_exists("missing", "doc-1") is False
    assert repo.work_item_exists("job-1", "indexing") is True
    assert repo.work_item_exists("missing", "indexing") is False


def test_ensure_connected_raises_on_cosmos_error(monkeypatch):
    class FailingCosmosClient:
        def __init__(self, uri, credential=None):
            raise FakeCosmosHttpResponseError(500, "cannot connect")

    monkeypatch.setattr(db_module, "DefaultAzureCredential", lambda: object())
    monkeypatch.setattr(db_module, "CosmosClient", FailingCosmosClient)
    monkeypatch.setattr(
        db_module.exceptions,
        "CosmosHttpResponseError",
        FakeCosmosHttpResponseError,
    )

    repo = db_module.DocumentRepository(
        uri="https://cosmos.test",
        database_name="db",
        container_documents="documents",
        container_chunks="chunks",
        container_work_items="work_items",
    )

    with pytest.raises(FakeCosmosHttpResponseError):
        _ = repo.docs_container


def test_is_processed_returns_false_on_query_exception(monkeypatch):
    repo = make_repo(monkeypatch)
    _ = repo.docs_container

    def boom(*args, **kwargs):
        raise RuntimeError("query failed")

    repo._docs_container.query_items = boom

    assert repo.is_processed("p1") is False


def test_update_document_status_ignores_not_found(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.update_document_status("missing-doc", "md", "chunked")


def test_update_document_status_reraises_unexpected_exception(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.insert_document(
        {
            "id": "doc-1",
            "file_type": "md",
            "path": "p1",
            "status": "parsed",
        }
    )

    _ = repo.docs_container

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected read failure")

    repo._docs_container.read_item = boom

    with pytest.raises(RuntimeError):
        repo.update_document_status("doc-1", "md", "chunked")


def test_mark_document_error_ignores_not_found(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.mark_document_error("missing-doc", "md", "boom")


def test_update_chunk_status_returns_when_chunk_missing_without_document_id(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.update_chunk_status(
        chunk_id="missing-chunk",
        status="indexed",
        document_id=None,
    )


def test_update_chunk_status_retries_on_429_then_succeeds(monkeypatch):
    repo = make_repo(monkeypatch)
    monkeypatch.setattr(db_module.time, "sleep", lambda *_args, **_kwargs: None)

    repo.insert_chunk(
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "status": "chunked",
            "retry_count": 0,
            "content": "hello",
        }
    )

    _ = repo.chunks_container
    original_upsert = repo._chunks_container.upsert_item
    calls = {"n": 0}

    def flaky_upsert(item):
        if calls["n"] == 0:
            calls["n"] += 1
            raise FakeCosmosHttpResponseError(429, "throttled")
        return original_upsert(item)

    repo._chunks_container.upsert_item = flaky_upsert

    repo.update_chunk_status(
        chunk_id="chunk-1",
        status="indexed",
        document_id="doc-1",
    )

    chunk = repo.chunks_container.read_item("chunk-1", "doc-1")
    assert chunk["status"] == "indexed"


def test_update_chunk_status_swallows_generic_exception(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.insert_chunk(
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "status": "chunked",
            "content": "hello",
        }
    )

    _ = repo.chunks_container

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected upsert failure")

    repo._chunks_container.upsert_item = boom

    repo.update_chunk_status(
        chunk_id="chunk-1",
        status="indexed",
        document_id="doc-1",
    )


def test_save_chunk_embedding_returns_when_chunk_missing_without_document_id(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.save_chunk_embedding(
        chunk_id="missing-chunk",
        embedding=[0.1, 0.2],
        document_id=None,
    )


def test_save_chunk_embedding_retries_on_429_then_succeeds(monkeypatch):
    repo = make_repo(monkeypatch)
    monkeypatch.setattr(db_module.time, "sleep", lambda *_args, **_kwargs: None)

    repo.insert_chunk(
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "status": "chunked",
            "content": "hello",
        }
    )

    _ = repo.chunks_container
    original_upsert = repo._chunks_container.upsert_item
    calls = {"n": 0}

    def flaky_upsert(item):
        if calls["n"] == 0:
            calls["n"] += 1
            raise FakeCosmosHttpResponseError(429, "throttled")
        return original_upsert(item)

    repo._chunks_container.upsert_item = flaky_upsert

    repo.save_chunk_embedding(
        chunk_id="chunk-1",
        embedding=[0.7, 0.8],
        mark_status="embedded",
        document_id="doc-1",
    )

    chunk = repo.chunks_container.read_item("chunk-1", "doc-1")
    assert chunk["status"] == "embedded"
    assert chunk["embedding"] == [0.7, 0.8]


def test_save_chunk_embedding_swallows_generic_exception(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.insert_chunk(
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "status": "chunked",
            "content": "hello",
        }
    )

    _ = repo.chunks_container

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected upsert failure")

    repo._chunks_container.upsert_item = boom

    repo.save_chunk_embedding(
        chunk_id="chunk-1",
        embedding=[0.1, 0.2],
        document_id="doc-1",
    )


def test_create_chunk_if_absent_reraises_non_409(monkeypatch):
    repo = make_repo(monkeypatch)
    _ = repo.chunks_container

    def boom(body):
        raise FakeCosmosHttpResponseError(500, "server error")

    repo._chunks_container.create_item = boom

    with pytest.raises(FakeCosmosHttpResponseError):
        repo.create_chunk_if_absent(
            {
                "id": "chunk-1",
                "document_id": "doc-1",
                "status": "chunked",
            }
        )


def test_create_work_item_if_absent_reraises_non_409(monkeypatch):
    repo = make_repo(monkeypatch)
    _ = repo.work_container

    def boom(body):
        raise FakeCosmosHttpResponseError(500, "server error")

    repo._work_container.create_item = boom

    with pytest.raises(FakeCosmosHttpResponseError):
        repo.create_work_item_if_absent(
            {
                "id": "job-1",
                "work_type": "indexing",
                "status": "queued",
            }
        )


def test_enqueue_work_item_raises_when_required_fields_missing(monkeypatch):
    repo = make_repo(monkeypatch)

    with pytest.raises(ValueError):
        repo.enqueue_work_item({"work_type": "indexing"})

    with pytest.raises(ValueError):
        repo.enqueue_work_item({"id": "job-1"})


def test_claim_work_items_ignores_409_and_412_conflicts(monkeypatch):
    repo = make_repo(monkeypatch)

    repo.enqueue_work_item(
        {
            "id": "job-1",
            "work_type": "indexing",
            "status": "queued",
            "attempts": 0,
            "_etag": "etag-1",
            "_ts": 1,
        }
    )
    repo.enqueue_work_item(
        {
            "id": "job-2",
            "work_type": "indexing",
            "status": "queued",
            "attempts": 0,
            "_etag": "etag-2",
            "_ts": 2,
        }
    )

    _ = repo.work_container
    calls = {"n": 0}

    def conflict_replace(item, body, etag=None, match_condition=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise FakeCosmosHttpResponseError(409, "conflict")
        raise FakeCosmosHttpResponseError(412, "precondition failed")

    repo._work_container.replace_item = conflict_replace

    claimed = repo.claim_work_items(
        work_type="indexing",
        worker_id="worker-1",
        limit=10,
        lease_seconds=60,
        now=10,
    )

    assert claimed == []


def test_complete_work_item_swallows_cosmos_error(monkeypatch):
    repo = make_repo(monkeypatch)
    _ = repo.work_container

    def boom(*args, **kwargs):
        raise FakeCosmosHttpResponseError(500, "read failure")

    repo._work_container.read_item = boom

    repo.complete_work_item("job-1", "indexing")


def test_fail_work_item_swallows_cosmos_error(monkeypatch):
    repo = make_repo(monkeypatch)
    _ = repo.work_container

    def boom(*args, **kwargs):
        raise FakeCosmosHttpResponseError(500, "read failure")

    repo._work_container.read_item = boom

    repo.fail_work_item("job-1", "indexing", "boom", inc_attempts=True)


def test_get_document_by_id_returns_none_on_generic_exception(monkeypatch):
    repo = make_repo(monkeypatch)
    _ = repo.docs_container

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected read failure")

    repo._docs_container.read_item = boom

    assert repo.get_document_by_id("doc-1", "md") is None


def test_chunk_exists_and_work_item_exists_return_false_on_generic_exception(monkeypatch):
    repo = make_repo(monkeypatch)
    _ = repo.chunks_container
    _ = repo.work_container

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected read failure")

    repo._chunks_container.read_item = boom
    repo._work_container.read_item = boom

    assert repo.chunk_exists("chunk-1", "doc-1") is False
    assert repo.work_item_exists("job-1", "indexing") is False


def test_close_swallows_client_close_exception(monkeypatch):
    repo = make_repo(monkeypatch)

    class BadClient:
        def close(self):
            raise RuntimeError("close failed")

    repo._client = BadClient()
    repo._database = object()
    repo._docs_container = object()
    repo._chunks_container = object()
    repo._work_container = object()
    repo._credential = object()

    repo.close()

    assert repo._client is None
    assert repo._database is None
    assert repo._docs_container is None
    assert repo._chunks_container is None
    assert repo._work_container is None
    assert repo._credential is None