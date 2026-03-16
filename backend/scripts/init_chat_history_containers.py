import os

from dotenv import load_dotenv
from azure.cosmos import CosmosClient, PartitionKey
from azure.identity import DefaultAzureCredential

load_dotenv()

uri = os.getenv("COSMOSDB_URI")
database_name = os.getenv("COSMOS_DATABASE")
container_conversations = os.getenv("COSMOSDB_CONTAINER_CONVERSATIONS", "conversations")
container_messages = os.getenv("COSMOSDB_CONTAINER_MESSAGES", "messages")

credential = DefaultAzureCredential()
client = CosmosClient(uri, credential=credential)
database = client.create_database_if_not_exists(id=database_name)

database.create_container_if_not_exists(
    id=container_conversations,
    partition_key=PartitionKey(path="/user_id"),
)

database.create_contcainer_if_not_exists(
    id=container_messages,
    partition_key=PartitionKey(path="/conversation_id"),
)

print("✅ Containers conversations/messages prêts.")