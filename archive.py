from backend.app.core.database import DocumentRepository

if __name__ == "__main__":
    repo = DocumentRepository()
    print("📂 Lecture des documents dans le conteneur 'documents'...")

    documents = repo.docs_container.query_items(
        query="SELECT * FROM c",
        enable_cross_partition_query=True
    )

    count = 0
    for doc in documents:
        count += 1
        print(f"\n📝 Document {count}:")
        print(f"ID: {doc.get('id')}")
        print(f"Filename: {doc.get('filename')}")
        print(f"Type: {doc.get('file_type')}")
        print(f"Status: {doc.get('status')}")
        text_preview = (doc.get('text_content') or "")[:300]
        print(f"Texte extrait (aperçu): {text_preview}...")
        print("-" * 80)

    print(f"\n✅ Total de documents extraits : {count}")
