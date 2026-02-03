import os
from backend.app.data_preparation.indexing.azure_search_indexer import AzureSearchIndexer

from pathlib import Path
from dotenv import load_dotenv

# Charge le .env de la racine projet (chat_bot_azure/.env)
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)


def main():
    required = ["AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_INDEX"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Variables manquantes: {missing}")

    indexer = AzureSearchIndexer()

    # 1) create/update index (si ton code le permet)
    indexer.create_or_update_index(embedding_dim=int(os.getenv("EMBEDDING_DIM", "1536")))
    print("✅ Index create/update OK")

    # 2) upload d'un doc dummy (vector faux, juste pour tester le data-plane)
    dim = int(os.getenv("EMBEDDING_DIM", "1536"))
    fake_vec = [0.0] * dim

    sent = indexer.upload([{
        "id": "smoke_doc_1",
        "content": "Document de test Azure AI Search",
        "content_vector": fake_vec,
        "document_id": "smoke",
        "chunk_order": 0,
        "source_path": "smoke",
        "file_type": "txt",
    }])

    print("✅ Upload OK, sent =", sent)

if __name__ == "__main__":
    main()
