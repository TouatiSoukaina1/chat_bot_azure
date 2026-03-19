import os
import glob
import logging
from typing import Optional, List

from backend.app.data_preparation.parsers.pdf_parser import PdfParser
from backend.app.data_preparation.parsers.txt_parser import TxtParser
from backend.app.data_preparation.parsers.markdown_parser import MarkdownParser

logger = logging.getLogger("app.extraction")


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


def run_extraction_from_files(
    file_paths: List[str],
    kb: str = "who",
    scope: str = "global",
    owner_user_id: Optional[str] = None,
    source_type: str = "who",
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

    for parser, extensions in parser_specs:
        matching_files = [
            path for path in file_paths
            if os.path.splitext(path)[1].lower() in extensions
        ]

        if not matching_files:
            continue

        logger.info(
            "🚀 %s fichiers envoyés à %s [scope=%s, owner=%s, source_type=%s]",
            len(matching_files),
            parser.__class__.__name__,
            scope,
            owner_user_id,
            source_type,
        )

        inserted = parser.process_file(file_paths=matching_files)
        total_inserted += inserted

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

    logger.info("🔍 Scanning %s for files...", raw_dir)

    return run_extraction_from_files(
        file_paths=all_files,
        kb=kb,
        scope=scope,
        owner_user_id=owner_user_id,
        source_type=source_type,
    )