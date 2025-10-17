import logging
import tqdm
from typing import List, Optional
from openai import AzureOpenAI
from dotenv import load_dotenv
import os 

load_dotenv()

class Embeder:
    '''
        Classe responsable de l'embedding de texte en vecteurs
    '''

    def __init__(self, endpoint=None, api_key=None, api_version=None, deployment_name=None):
        ''''
            Initialisation des paramétres d'embedding
            params :
                endpoint : endpoint Azure OpenAI
                api_key : clé API Azure OpenAI
                api_version : version de l'API
                deployment_name : nom du déploiement du modèle d'embedding
        '''
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION")
        self.deployment_name = deployment_name or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

        self.client = AzureOpenAI(
            api_key= self.api_key,
            api_version= self.api_version,
            azure_endpoint= self.endpoint
        )

    
    def embed_text(self, text: str) -> Optional[List[float]]:
        '''
            Génère l'embedding d'un texte
            params :
                text (str): texte à encoder
            return : liste des floats représentant l'embedding ou None en cas d'erreur
        '''
        if not text or not isinstance(text, str):
            logging.warning("Texte vide ou type invalide de donnée")
            return None
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.deployment_name
            )
            return response.data[0].embedding
        except Exception as e:
            logging.exception("Erreur lors de la génération de l'embedding : {e}")
            return None
        
    def  generate_embeddings_batch(self, texts: List[str])-> List[List[float]] : 
        '''
            Génère les embeddings pour une liste de textes
            params :
                texts (List[str]): liste des textes à encoder
            return : liste des embeddings
        '''
        embedings= []
        for t in tqdm.tqdm(texts, desc="Génération des embeddings"):
            emb = self.embed_text(t)
            if emb:
                embedings.append(emb)
            
        return embedings