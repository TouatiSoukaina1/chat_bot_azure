import logging
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from app.core.logging_config import setup_logging
from app.data_preparation.pipelines.extraction_pipeline import run_global_who_extraction
from app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
from app.data_preparation.processors.chunker import Chunker
from app.workers.indexing_worker import IndexingWorker

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=True)

setup_logging()
logger = logging.getLogger("scripts.run_global_who_pipeline")

INBOX_DIR = ROOT / "data" / "raw" / "inbox"
ARCHIVE_DIR = ROOT / "data" / "raw" / "archive"
FAILED_DIR = ROOT / "data" / "raw" / "failed"

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf"}

WHO_CHUNK_MODE = "auto"      # "auto" | "markdown" | "fixed"
WHO_CHUNK_SIZE = 1500
WHO_OVERLAP = 150


def ensure_directories() -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)


def move_inbox_to_archive() -> int:
    """
    Déplace les nouveaux fichiers de inbox vers archive avec un chemin stable.
    On conserve la structure relative éventuelle sous inbox/.
    """
    moved_count = 0

    inbox_files = [p for p in INBOX_DIR.rglob("*") if p.is_file()]
    logger.info("Scan inbox terminé | inbox=%s file_count=%s", INBOX_DIR, len(inbox_files))

    for src in inbox_files:
        rel_path = src.relative_to(INBOX_DIR)
        ext = src.suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            failed_target = FAILED_DIR / rel_path
            failed_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(failed_target))
            logger.warning(
                "Fichier non supporté déplacé vers failed | src=%s dst=%s",
                src,
                failed_target,
            )
            continue

        dst = ARCHIVE_DIR / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)

        if dst.exists():
            # Collision de chemin : on ne veut pas écraser ni changer le path canonique
            failed_target = FAILED_DIR / "duplicates" / rel_path
            failed_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(failed_target))
            logger.warning(
                "Collision archive, fichier déplacé vers failed/duplicates | src=%s existing=%s failed=%s",
                src,
                dst,
                failed_target,
            )
            continue

        shutil.move(str(src), str(dst))
        moved_count += 1

        logger.info(
            "Fichier déplacé inbox -> archive | src=%s dst=%s",
            src,
            dst,
        )

    logger.info("Déplacement inbox -> archive terminé | moved_count=%s", moved_count)
    return moved_count


def run_extraction() -> int:
    logger.info("Extraction WHO global démarrée | raw_dir=%s", ARCHIVE_DIR)

    inserted = run_global_who_extraction(raw_dir=str(ARCHIVE_DIR))

    logger.info(
        "Extraction WHO global terminée | documents_insérés_ou_mis_a_jour=%s",
        inserted,
    )
    return inserted


def run_chunking() -> int:
    logger.info(
        "Chunking WHO global démarré | mode=%s chunk_size=%s overlap=%s",
        WHO_CHUNK_MODE,
        WHO_CHUNK_SIZE,
        WHO_OVERLAP,
    )

    chunker = Chunker(
        mode=WHO_CHUNK_MODE,
        chunk_size=WHO_CHUNK_SIZE,
        overlap=WHO_OVERLAP,
    )

    pipeline = ChunkingPipeline(
        chunker=chunker,
        status_in="parsed",
        status_out="chunked",
    )
    inserted_chunks = pipeline.run()

    logger.info(
        "Chunking WHO global terminé | nouveaux_chunks=%s",
        inserted_chunks,
    )
    return inserted_chunks


def run_indexing(max_rounds: int = 50, sleep_seconds: int = 1) -> int:
    logger.info("Indexation WHO global démarrée | max_rounds=%s", max_rounds)

    worker = IndexingWorker(worker_id="global-who-runner")
    total_claimed = 0

    for round_idx in range(1, max_rounds + 1):
        claimed = worker.run_once(limit=64, lease_seconds=120)

        logger.info(
            "Indexation round | round=%s claimed=%s total_claimed=%s",
            round_idx,
            claimed,
            total_claimed + claimed,
        )

        if claimed == 0:
            break

        total_claimed += claimed
        time.sleep(sleep_seconds)

    logger.info("Indexation WHO global terminée | jobs_traités=%s", total_claimed)
    return total_claimed


def main() -> int:
    logger.info("WHO global pipeline démarré")

    try:
        ensure_directories()

        moved_files = move_inbox_to_archive()

        # On lance extraction même si 0 nouveau fichier seulement si tu veux rescan archive.
        # Ici on optimise : pas de nouvel input => on passe directement au chunking/indexing de reprise éventuelle.
        inserted_docs = 0
        if moved_files > 0:
            inserted_docs = run_extraction()
        else:
            logger.info("Aucun nouveau fichier dans inbox | extraction ignorée")

        inserted_chunks = run_chunking()
        indexed_jobs = run_indexing()

        logger.info(
            "WHO global pipeline terminé avec succès | moved_files=%s documents=%s chunks=%s indexing_jobs=%s",
            moved_files,
            inserted_docs,
            inserted_chunks,
            indexed_jobs,
        )
        return 0

    except Exception:
        logger.exception("Echec WHO global pipeline")
        return 1


if __name__ == "__main__":
    sys.exit(main())