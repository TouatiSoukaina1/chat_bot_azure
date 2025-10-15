from azure.cosmos import CosmosClient, PartitionKey, exceptions
from dotenv import load_dotenv
import os 
import logging

load_dotenv()

class DocumentRepository:
    ''''
        Classe pour interagir avec Azure Cosmos DB.
    '''
    def __init__(self):

        self.uri = os.getenv("COSMOSDB_URI")
        self.key = os.getenv("COSMOS_KEY")
        self.database_name = os.getenv("COSMOS_DATABASE")

        self.container_documents = os.getenv("COSMOSDB_CONTAINER_DOCUMENTS")
        self.container_chunks = os.getenv("COSMOSDB_CONTAINER_CHUNKS")
        self.logger = logging.getLogger("app.CosmosDBClient")
        try:
            self.client = CosmosClient(self.uri, self.key)
            self.database = self.client.get_database_client(id=self.database_name)
            self.docs_container = self.database.get_container_client(self.container_documents)
            self.chunks_container = self.database.get_container_client(self.container_chunks)
        except exceptions.CosmosHttpResponseError as e:
            self.logger(f"Error connecting to Cosmos DB: {e}")
            raise

    def insert_document(self, document):
        try:
            self.docs_container.upsert_item(document)
        except exceptions.CosmosHttpResponseError as e:
            self.logger.error(f"Erreur HTTP Cosmos ({e.status_code}): {e.message}")
        except Exception as e:
            self.logger.exception(f"Erreur inattendue lors de l’insertion du document: {document.get('filename')} {e}")
    
    def insert_chunk(self, chunk):
        try:
            self.chunks_container.upsert_item(chunk)
        except exceptions.CosmosHttpResponseError as e:
            self.logger.error(f"Erreur HTTP Cosmos ({e.status_code}): {e.message}")
        except Exception as e:
            self.logger.exception(f"Erreur inattendue lors de l’insertion du chunk: {e}")
    
    def get_documents_by_status(self, status="parsed"):
        '''
            Récupère les documents d'un certain statut depuis le conteneur Cosmos DB.''
            Args:
                status (str): Le statut des documents à récupérer. Par défaut, "parsed".
            Returns:
                list: Une liste de documents correspondant au statut spécifié.
            '''
        
        try:    
            query = "SELECT * FROM c WHERE c.status = '{status}'"
            return list(self.docs_container.query_items(query=query,enable_cross_partition_query=True)) 
        except Exception as e:
            self.logger.exception(f"Erreur inattendue lors de la récupération des documents avec le statut {status}: {e}")
            return []

    def update_document_status(self, document_id: str, new_status:str, partition_key: str):
        ''' 
            Met à jour le statut d'un document dans le conteneur Cosmos DB. 
            Args:
                document_id (str): L'ID du document à mettre à jour.
                new_status (str): Le nouveau statut à attribuer au document.
                partition_key (str): La clé de partition du document.
        '''
        try:
            document = self.container_documents.read_item(item=document_id, partition_key=partition_key)
            document['status'] = new_status
            self.docs_container.upsert_item(document)
        except exceptions.CosmosResourceNotFoundError:
            self.logger.warning(f"Document introuvable : {document_id}")
        except Exception as e:
            self.logger.exception(f"Erreur inattendue lors de la mise à jour du statut du document {document_id}: {e}")

    
