from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from app.data_preparation.processors.embedder import Embedder
from app.data_preparation.retrieval.azure_search_retriever import AzureSearchRetriever
from app.services.rag_chat_service import RagChatService

# ROOT = Path(__file__).resolve().parents[3]
load_dotenv()


@lru_cache
def get_rag_service() -> RagChatService:
    emb = Embedder(batch_size=16)
    retriever = AzureSearchRetriever(embedder=emb)
    return RagChatService(retriever=retriever)