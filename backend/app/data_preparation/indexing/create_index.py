import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger("Create.index")
load_dotenv()

from app.data_preparation.indexing.azure_search_indexer import AzureSearchIndexer

if __name__ == "__main__":
    dim = int(os.getenv("EMBEDDING_DIM", "1536"))
    AzureSearchIndexer().create_or_update_index(embedding_dim=dim)
    logger.info("Index Azure Search créé/à jour.")
