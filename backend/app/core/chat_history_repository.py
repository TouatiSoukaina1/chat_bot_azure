import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from dotenv import load_dotenv
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

load_dotenv()


class ChatHistoryRepository:
    def __init__(
        self,
        uri: Optional[str] = None,
        database_name: Optional[str] = None,
        container_conversations: Optional[str] = None,
        container_messages: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger("app.chat_history_repository")

        self.uri = uri or os.getenv("COSMOSDB_URI")
        self.database_name = database_name or os.getenv("COSMOS_DATABASE")
        self.container_conversations = (
            container_conversations or os.getenv("COSMOSDB_CONTAINER_CONVERSATIONS")
        )
        self.container_messages = (
            container_messages or os.getenv("COSMOSDB_CONTAINER_MESSAGES")
        )

        credential = DefaultAzureCredential()
        self.client = CosmosClient(self.uri, credential=credential)
        self.database = self.client.get_database_client(self.database_name)
        self.conversations_container = self.database.get_container_client(
            self.container_conversations
        )
        self.messages_container = self.database.get_container_client(
            self.container_messages
        )

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _build_title_from_first_message(message: str) -> str:
        value = message.strip()
        if not value:
            return "Nouvelle conversation"
        return value[:36] + ("..." if len(value) > 36 else "")

    def create_conversation(
        self,
        user_id: str,
        title: str = "Nouvelle conversation",
        metadata: Optional[Dict] = None,
    ) -> Dict:
        now = self._utc_now_iso()

        conversation = {
            "id": str(uuid4()),
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
            "kind": "conversation",
            "metadata": metadata or {},
        }

        self.conversations_container.upsert_item(conversation)
        return conversation

    def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Dict]:
        items = list(
            self.conversations_container.query_items(
                query="""
                    SELECT * FROM c
                    WHERE c.id = @id AND c.user_id = @user_id
                """,
                parameters=[
                    {"name": "@id", "value": conversation_id},
                    {"name": "@user_id", "value": user_id},
                ],
                enable_cross_partition_query=True,
            )
        )

        if not items:
            return None

        conversation = items[0]

        messages = list(
            self.messages_container.query_items(
                query="""
                    SELECT * FROM c
                    WHERE c.conversation_id = @conversation_id
                    ORDER BY c.created_at ASC
                """,
                parameters=[
                    {"name": "@conversation_id", "value": conversation_id},
                ],
                partition_key=conversation_id,
            )
        )

        conversation["messages"] = messages
        return conversation

    def list_conversations(self, user_id: str, limit: int = 100) -> List[Dict]:
        conversations = list(
            self.conversations_container.query_items(
                query="""
                    SELECT * FROM c
                    WHERE c.user_id = @user_id
                    ORDER BY c.updated_at DESC
                """,
                parameters=[{"name": "@user_id", "value": user_id}],
                partition_key=user_id,
                max_item_count=limit,
            )
        )

        result = []
        for conv in conversations[:limit]:
            hydrated = self.get_conversation(conv["id"], user_id)
            if hydrated:
                result.append(hydrated)
        return result

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            return False

        messages = list(
            self.messages_container.query_items(
                query="""
                    SELECT c.id FROM c
                    WHERE c.conversation_id = @conversation_id
                """,
                parameters=[{"name": "@conversation_id", "value": conversation_id}],
                partition_key=conversation_id,
            )
        )

        for message in messages:
            self.messages_container.delete_item(
                item=message["id"],
                partition_key=conversation_id,
            )

        self.conversations_container.delete_item(
            item=conversation_id,
            partition_key=user_id,
        )
        return True

    def add_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        sources: Optional[List[Dict]] = None,
    ) -> Dict:
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError(
                f"Conversation introuvable: id={conversation_id}, user_id={user_id}"
            )

        now = self._utc_now_iso()

        message = {
            "id": str(uuid4()),
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "sources": sources or [],
            "created_at": now,
            "kind": "message",
        }

        self.messages_container.upsert_item(message)

        conversation["updated_at"] = now
        conversation["message_count"] = int(conversation.get("message_count", 0)) + 1

        if role == "user" and conversation.get("title") == "Nouvelle conversation":
            conversation["title"] = self._build_title_from_first_message(content)

        conversation.pop("messages", None)
        self.conversations_container.upsert_item(conversation)

        return message

    def create_or_get_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        title: str = "Nouvelle conversation",
    ) -> Dict:
        if conversation_id:
            existing = self.get_conversation(conversation_id, user_id)
            if existing:
                return existing
        return self.create_conversation(user_id=user_id, title=title)