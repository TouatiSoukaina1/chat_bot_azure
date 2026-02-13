from backend.app.data_preparation.processors.embedder import Embedder
from backend.app.data_preparation.retrieval.azure_search_retriever import AzureSearchRetriever
from backend.app.services.rag_chat_service import RagChatService
from dotenv import load_dotenv
from pathlib import Path
import os
# Charge le .env de la racine projet (chat_bot_azure/.env)
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)

def main():

    required = ["AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_INDEX"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Variables manquantes: {missing}")


    emb = Embedder(batch_size=16)
    retriever = AzureSearchRetriever(embedder=emb)
    rag = RagChatService(retriever=retriever)

    q = "Explique le contenu principal et cite tes sources."
    out = rag.answer(q, top_k=5)

    print("\n=== ANSWER ===\n", out["answer"])
    print("\n=== SOURCES ===")
    for s in out["sources"]:
        print(s["ref"], s["source_path"], "id=", s["id"], "score=", s["score"])

if __name__ == "__main__":
    main()
