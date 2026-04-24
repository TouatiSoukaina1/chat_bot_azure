# scripts/inspect_work_item.py
from app.core.database import DocumentRepository

def main():
    repo = DocumentRepository()
    work_id = "indexing::smoke_doc_chunk_0"
    wi = repo.work_container.read_item(item=work_id, partition_key="indexing")
    print(wi)

if __name__ == "__main__":
    main()
