from backend.app.core.database import DocumentRepository
from app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
from app.data_preparation.pipelines.extraction_pipeline import *
from app.data_preparation.pipelines.ingestion_pipeline import IngestionStats, IngestionPipeline
import json
from pathlib import Path
from dotenv import load_dotenv

# Charge toujours le .env de la racine du projet
load_dotenv(Path(__file__).resolve().parent / ".env")

def show_chunks(chunks, limit=10, content_chars=300):
    print(f"\n✅ {len(chunks)} chunks trouvés. Affichage des {min(limit, len(chunks))} premiers:\n")
    for i, c in enumerate(chunks[:limit], start=1):
        content = (c.get("content") or "")
        print(f"[{i}] id={c.get('id')} doc={c.get('document_id')} status={c.get('status')} len={len(content)}")
        print(content[:content_chars].replace("\n", " "))
        print("-" * 100)
        
if __name__ == "__main__":
    repo = DocumentRepository()
    chunk_pip = ChunkingPipeline()
    chunk_pip.run()
    chunks = repo.get_chunks(status="chunked", document_ids=None)
    show_chunks(chunks, limit=10)

    # # 2) Si tu veux inspecter un chunk en détail
    if chunks:
        print("\n🔎 Chunk complet (JSON) :\n")
        print(json.dumps(chunks[0], ensure_ascii=False, indent=2))

