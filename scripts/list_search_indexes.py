import os
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient

def main():
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT manquant")

    cred = DefaultAzureCredential()
    client = SearchIndexClient(endpoint=endpoint, credential=cred)

    print("Indexes:")
    for idx in client.list_indexes():
        print("-", idx.name)

if __name__ == "__main__":
    main()
