import os
from pathlib import Path
from dotenv import load_dotenv

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from app.data_preparation.processors.embedder import Embedder
from app.data_preparation.retrieval.azure_search_retriever import AzureSearchRetriever


# Charge le .env de la racine projet (optionnel)
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)


def build_context(hits):
    """
    Construit un contexte numéroté [1], [2], ... pour forcer les citations.
    """
    blocks = []
    for i, h in enumerate(hits, start=1):
        doc_title = h.get("doc_title", "")
        section = h.get("section_title", "")
        source_path = h.get("source_path", "")
        chunk_id = h.get("id", "")
        content = (h.get("content") or "").strip()

        blocks.append(
            f"[{i}] id={chunk_id}\n"
            f"doc_title={doc_title} | section={section}\n"
            f"source={source_path}\n"
            f"content:\n{content}\n"
        )
    return "\n---\n".join(blocks)


def get_aoai_client():
    """
    Supporte:
    - clé API (AZURE_OPENAI_KEY)
    - keyless Entra ID via DefaultAzureCredential si pas de clé
    """
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")

    if not endpoint or not api_version:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_VERSION manquants")

    api_key = os.getenv("AZURE_OPENAI_KEY")
    if api_key:
        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_version=api_version,
            api_key=api_key,
        )

    # keyless (Entra ID)
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_version=api_version,
        azure_ad_token_provider=token_provider,
    )


def main():
    # --- Config ---
    chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
    top_k = int(os.getenv("RAG_TOP_K", "5"))

    # --- Init retrieval ---
    emb = Embedder(batch_size=16)
    retriever = AzureSearchRetriever(embedder=emb)

    # --- Question ---
    q = input("Question: ").strip()
    if not q:
        return

    hits = retriever.retrieve(q, top_k=top_k)
    print(f"\n✅ Retrieved hits = {len(hits)}")

    if not hits:
        print("Aucun contexte trouvé dans Azure Search.")
        return

    # --- Build context for the LLM ---
    context = build_context(hits)

    system_prompt = (
        "Tu es un assistant médical basé uniquement sur les sources fournies.\n"
        "Règles:\n"
        "1) Réponds en français.\n"
        "2) N'invente rien. Si l'info n'est pas dans les sources, dis-le clairement.\n"
        "3) Cite tes sources sous la forme [1], [2], etc. après chaque phrase importante.\n"
        "4) Sois clair, structuré, et concis.\n"
    )

    user_prompt = (
        f"Question: {q}\n\n"
        f"Sources:\n{context}\n\n"
        "Réponds à la question en te basant UNIQUEMENT sur les sources. "
        "Ajoute les citations [n] correspondantes."
    )

    client = get_aoai_client()

    resp = client.chat.completions.create(
        model=chat_deployment,  # Azure deployment name
        temperature=0.2,
        max_tokens=600,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    answer = resp.choices[0].message.content
    print("\n" + "=" * 90)
    print("✅ RAG ANSWER\n")
    print(answer)

    print("\n" + "=" * 90)
    print("🔎 SOURCES USED (top hits)\n")
    for i, h in enumerate(hits, start=1):
        print(f"[{i}] {h.get('doc_title')} | {h.get('section_title')} | {h.get('source_path')} | id={h.get('id')}")


if __name__ == "__main__":
    main()
