from backend.app.core.database import DocumentRepository
#from backend.app.data_preparation.pipelines.chunking_pipeline import ChunkingPipeline
#from backend.app.data_preparation.pipelines.extraction_pipeline import *

import json
from pathlib import Path
from dotenv import load_dotenv

if __name__ == "__main__":
    repo = DocumentRepository()
    for doc in repo.iter_all_documents():
        print(doc) 

