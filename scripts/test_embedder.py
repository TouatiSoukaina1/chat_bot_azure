import os
from pathlib import Path
from dotenv import load_dotenv

# Charge le .env de la racine projet (chat_bot_azure/.env)
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)

from app.data_preparation.processors.embedder import Embedder


def main():
    required = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Variables manquantes: {missing}. Chargé depuis: {ROOT / '.env'}")

    emb = Embedder(batch_size=16)

    v = emb.generate_embedding("Hello from RAG!")
    assert v is not None and len(v) > 100, "Embedding invalide (None ou trop court)"

    stats = emb.get_statistics()
    print("✅ Embedder OK")
    print("dims =", len(v))
    print("stats =", stats)

    print(v)
if __name__ == "__main__":
    main()
