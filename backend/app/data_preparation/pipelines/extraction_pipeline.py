import os
import glob
import logging
import hashlib
from typing import Optional, List

from app.core.database import DocumentRepository
from app.data_preparation.parsers.pdf_parser import PdfParser
from app.data_preparation.parsers.txt_parser import TxtParser
from app.data_preparation.parsers.markdown_parser import MarkdownParser

logger = logging.getLogger("app.extraction")


def _make_doc_id(path: str) -> str:
    return hashlib.md5(path.encode("utf-8")).hexdigest()


def _build_parsers(
    kb: str,
    scope: str,
    owner_user_id: Optional[str],
    source_type: str,
):
    return [
        (
            TxtParser(
                kb=kb,
                scope=scope,
                owner_user_id=owner_user_id,
                source_type=source_type,
            ),
            [".txt"],
        ),
        (
            MarkdownParser(
                kb=kb,
                scope=scope,
                owner_user_id=owner_user_id,
                source_type=source_type,
            ),
            [".md", ".markdown"],
        ),
        (
            PdfParser(
                kb=kb,
                scope=scope,
                owner_user_id=owner_user_id,
                source_type=source_type,
            ),
            [".pdf"],
        ),
    ]


def _filter_unprocessed_files(
    file_paths: List[str],
    repo: DocumentRepository,
) -> List[str]:
    unprocessed = []

    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        file_type = ext.replace(".", "")
        doc_id = _make_doc_id(path)

        existing = repo.get_document_by_id(doc_id, file_type=file_type)
        if existing:
            logger.debug("⏭️ Déjà traité, ignoré : %s", path)
            continue

        unprocessed.append(path)

    return unprocessed


def run_extraction_from_files(
    file_paths: List[str],
    kb: str = "who",
    scope: str = "global",
    owner_user_id: Optional[str] = None,
    source_type: str = "who",
    document_overrides_by_path: Optional[dict] = None,
) -> int:
    if not file_paths:
        logger.warning("Aucun fichier fourni pour l'extraction.")
        return 0

    parser_specs = _build_parsers(
        kb=kb,
        scope=scope,
        owner_user_id=owner_user_id,
        source_type=source_type,
    )

    total_inserted = 0
    repo = DocumentRepository()
    file_paths = sorted(set(file_paths))

    logger.info(
        "📂 Extraction lancée sur %s fichiers candidats [scope=%s, owner=%s, source_type=%s]",
        len(file_paths),
        scope,
        owner_user_id,
        source_type,
    )

    for parser, extensions in parser_specs:
        matching_files = [
            path for path in file_paths
            if os.path.splitext(path)[1].lower() in extensions
        ]

        if not matching_files:
            continue

        unprocessed_files = _filter_unprocessed_files(matching_files, repo)

        logger.info(
            "🔎 %s: %s fichiers trouvés, %s non traités",
            parser.__class__.__name__,
            len(matching_files),
            len(unprocessed_files),
        )

        if not unprocessed_files:
            continue

        relevant_overrides = None
        if document_overrides_by_path:
            relevant_overrides = {
                path: document_overrides_by_path[path]
                for path in unprocessed_files
                if path in document_overrides_by_path
            }

        inserted = parser.process_file(
            file_paths=unprocessed_files,
            document_overrides_by_path=relevant_overrides,
        )
        total_inserted += inserted

        logger.info(
            "✅ %s: %s documents insérés / mis à jour",
            parser.__class__.__name__,
            inserted,
        )

    logger.info(
        "🏁 Extraction fichiers terminée — %s documents insérés/mis à jour [scope=%s, owner=%s, source_type=%s]",
        total_inserted,
        scope,
        owner_user_id,
        source_type,
    )

    return total_inserted


def run_extraction_from_directory(
    raw_dir: str,
    kb: str = "who",
    scope: str = "global",
    owner_user_id: Optional[str] = None,
    source_type: str = "who",
) -> int:
    parser_specs = _build_parsers(
        kb=kb,
        scope=scope,
        owner_user_id=owner_user_id,
        source_type=source_type,
    )

    all_files: List[str] = []

    for _, extensions in parser_specs:
        for ext in extensions:
            all_files.extend(
                glob.glob(os.path.join(raw_dir, f"**/*{ext}"), recursive=True)
            )

    all_files = sorted(set(all_files))

    logger.info("🔍 Scan du dossier %s", raw_dir)
    logger.info("📄 %s fichiers détectés au total", len(all_files))

    return run_extraction_from_files(
        file_paths=all_files,
        kb=kb,
        scope=scope,
        owner_user_id=owner_user_id,
        source_type=source_type,
    )


def run_global_who_extraction(raw_dir: str) -> int:
    return run_extraction_from_directory(
        raw_dir=raw_dir,
        kb="who",
        scope="global",
        owner_user_id=None,
        source_type="who",
    )


def run_private_user_extraction(
    file_paths: List[str],
    owner_user_id: str,
    kb: str = "user",
    document_overrides_by_path: Optional[dict] = None,
) -> int:
    return run_extraction_from_files(
        file_paths=file_paths,
        kb=kb,
        scope="private",
        owner_user_id=owner_user_id,
        source_type="user_upload",
        document_overrides_by_path=document_overrides_by_path,
    )