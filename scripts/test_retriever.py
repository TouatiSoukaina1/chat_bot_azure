import os 
from backend.app.data_preparation.processors.embedder import Embedder
from backend.app.data_preparation.retrieval.azure_search_retriever import AzureSearchRetriever
from dotenv import load_dotenv
from pathlib import Path

# Charge le .env de la racine projet (chat_bot_azure/.env)
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)

def main():
    #assert os.getenv("AZURE_SEARCH_INDEX") == "documents-index", "AZURE_SEARCH_INDEX doit être documents-index"
    required = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Variables manquantes: {missing}. Chargé depuis: {ROOT / '.env'}")

    emb = Embedder(batch_size=16)  # ton embedder OK
    retriever = AzureSearchRetriever(embedder=emb)

    q = "C'est quoi les symptomes de Mpx ?"
    hits = retriever.retrieve(q, top_k=5)

    print("hits =", len(hits))
    for h in hits[:5]:
        print("-", h["id"], "score=", h["score"], "path=", h["source_path"])
        print("  ", (h["content"] or "")[:120].replace("\n", " "), "...\n")

if __name__ == "__main__":
    main()
