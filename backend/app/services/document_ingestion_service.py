import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile, HTTPException

from app.core.database import DocumentRepository
from app.data_preparation.parsers.txt_parser import TxtParser
from app.data_preparation.parsers.pdf_parser import PdfParser
from app.data_preparation.parsers.markdown_parser import MarkdownParser
from app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
from app.data_preparation.processors.chunker import Chunker
from app.workers.indexing_worker import IndexingWorker


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocumentIngestionService:
    def __init__(self, repo=None):
        self.repo = repo or DocumentRepository()

    def _get_parser(self, filename: str, owner_user_id: str):
        ext = Path(filename).suffix.lower()

        common_kwargs = {
            "kb": "user",
            "scope": "private",
            "owner_user_id": owner_user_id,
            "source_type": "user_upload",
        }

        if ext == ".txt":
            return TxtParser(**common_kwargs)
        if ext in [".md", ".markdown"]:
            return MarkdownParser(**common_kwargs)
        if ext == ".pdf":
            return PdfParser(**common_kwargs)

        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non supporté: {ext or 'inconnu'}",
        )

    async def ingest_uploaded_file(
        self,
        upload_file: UploadFile,
        owner_user_id: str,
        chunk_mode: str = "auto",
        chunk_size: int = 1500,
        overlap: int = 150,
    ) -> dict:
        if not upload_file.filename:
            raise HTTPException(status_code=400, detail="Nom de fichier manquant")

        allowed_modes = {"auto", "markdown", "fixed"}
        if chunk_mode not in allowed_modes:
            raise HTTPException(
                status_code=400,
                detail=f"chunk_mode invalide: {chunk_mode}",
            )

        if chunk_size < 100:
            raise HTTPException(
                status_code=400,
                detail="chunk_size doit être >= 100",
            )

        if overlap < 0:
            raise HTTPException(
                status_code=400,
                detail="overlap doit être >= 0",
            )

        if overlap >= chunk_size:
            raise HTTPException(
                status_code=400,
                detail="overlap doit être strictement inférieur à chunk_size",
            )

        ext = Path(upload_file.filename).suffix.lower()
        file_type = ext.replace(".", "") or "bin"
        document_id = str(uuid4())
        now = utc_now_iso()

        data = await upload_file.read()
        if not data:
            raise HTTPException(status_code=400, detail="Fichier vide")

        file_hash = hashlib.sha256(data).hexdigest()

        existing_docs = list(
            self.repo.docs_container.query_items(
                query="""
                SELECT * FROM c
                WHERE c.owner_user_id = @owner_user_id
                  AND c.file_hash = @file_hash
                  AND c.status != "failed"
                """,
                parameters=[
                    {"name": "@owner_user_id", "value": owner_user_id},
                    {"name": "@file_hash", "value": file_hash},
                ],
                enable_cross_partition_query=True,
            )
        )

        if existing_docs:
            raise HTTPException(
                status_code=409,
                detail="Ce document existe déjà dans votre espace privé.",
            )

        parser = self._get_parser(upload_file.filename, owner_user_id)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            raw_text = parser.extract_text(tmp_path)
            text = parser.normalize_to_markdown(raw_text)

            if not text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Aucun texte exploitable extrait du fichier",
                )

            title = parser._title_from_filename(upload_file.filename)
            logical_path = f"user_upload/{owner_user_id}/{document_id}/{upload_file.filename}"

            document = {
                "id": document_id,
                "owner_user_id": owner_user_id,
                "filename": upload_file.filename,
                "title": title,
                "path": logical_path,
                "file_type": file_type,
                "mime_type": upload_file.content_type,
                "file_size": len(data),
                "file_hash": file_hash,
                "text_content": text,
                "status": "parsed",
                "scope": "private",
                "source_type": "user_upload",
                "kb": "user",
                "created_at": now,
                "updated_at": now,
                "last_error": None,
                "chunking_config": {
                    "mode": chunk_mode,
                    "effective_mode": None,
                    "chunk_size": chunk_size,
                    "overlap": overlap,
                },
            }

            self.repo.insert_document(document)

            chunker = Chunker(
                chunk_size=chunk_size,
                overlap=overlap,
                mode=chunk_mode,
            )

            effective_mode = chunker.detect_effective_mode(text)

            ChunkingPipeline(
                repo=self.repo,
                chunker=chunker,
                status_in="parsed",
                status_out="chunked",
            ).run(document_ids=[document_id])

            document["chunking_config"] = {
                "requested_mode": chunk_mode,
                "effective_mode": effective_mode,
                "chunk_size": chunk_size,
                "overlap": overlap,
            }

            worker = IndexingWorker(
                repo=self.repo,
                worker_id=f"upload-{document_id}",
            )
            while True:
                claimed = worker.run_once(limit=64, lease_seconds=120)
                if claimed == 0:
                    break

            chunks = self.repo.get_chunks_by_document(document_id=document_id)
            if chunks and all(ch.get("status") == "indexed" for ch in chunks):
                document["status"] = "ready"
            elif chunks:
                document["status"] = "chunked"
            else:
                document["status"] = "failed"
                document["last_error"] = "Aucun chunk généré"

            document["updated_at"] = utc_now_iso()
            self.repo.insert_document(document)

            return document

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)