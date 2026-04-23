from backend.app.core.database import DocumentRepository
from backend.app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
from backend.app.data_preparation.pipelines.extraction_pipeline import *

import json
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys

from backend.app.core.logging_config import setup_logging
setup_logging(app_name="app") 
# logging.basicConfig(
#     level=logging.INFO,  # mets DEBUG si tu veux tout voir
#     format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
#     stream=sys.stdout,
#     force=True,  # IMPORTANT: écrase une config existante
# )
def main():
    repo = DocumentRepository()

    # change si besoin
    status = "chunked"
    limit = 20

    chunks = repo.get_chunks(status=status, limit=limit)
    if not chunks:
        print(f"Aucun chunk status={status}")
        return

    print(f"chunks={len(chunks)} (status={status})\n")

    for i, ch in enumerate(chunks, start=1):
        content = (ch.get("content") or "").replace("\n", " ")
        preview = content[:200] + ("..." if len(content) > 200 else "")

        print("=" * 90)
        print(f"[{i}] id={ch.get('id')}")
        print(f" document_id={ch.get('document_id')}  order={ch.get('order')}  status={ch.get('status')}")
        print(f" section_title={ch.get('section_title')}  doc_title={ch.get('doc_title')}")
        print(f" source_path={ch.get('source_path')}")
        print(f" len(content)={len(ch.get('content') or '')}")
        print("\nPREVIEW:\n", preview)


if __name__ == "__main__":
    main()
    
    #run_extraction()
    #chunking_pipeline = ChunkingPipeline()
    #chunking_pipeline.run()

# az containerapp job create \
#   --name who-global-job \
#   --resource-group <RG_NAME> \
#   --environment <CONTAINER_APPS_ENV_NAME> \
#   --trigger-type Schedule \
#   --cron-expression "0 2 * * *" \
#   --replica-timeout 1800 \
#   --replica-retry-limit 1 \
#   --parallelism 1 \
#   --replica-completion-count 1 \
#   --image <ACR_NAME>.azurecr.io/<IMAGE_NAME>:<TAG> \
#   --cpu 1.0 \
#   --memory 2Gi \
#   --command "python" \
#   --args "-m" "backend.scripts.run_global_who_pipeline"


python -m pytest tests/test_parsers.py
python -m pytest tests/test_extraction_pipeline.py
python -m pytest tests/test_chunking_pipeline.py
python -m pytest tests/test_document_ingestion_service.py
python -m pytest tests/test_indexing_worker.py