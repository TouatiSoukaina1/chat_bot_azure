import logging
import time
from typing import List, Dict, Optional, Union
from openai import AzureOpenAI
from openai import RateLimitError, APIError, APIConnectionError
from tqdm import tqdm
from dotenv import load_dotenv
import os 

load_dotenv()
class EmbeddingResult:
    def __init(
            self, 
            embeddings: List[List[float]],
            tokens_used: int,
            duration: float,
            success: bool =True, 
            error: Optional[str]
    ):
        self.embeddings = embeddings
        self.tokens_used = tokens_used
        self.duration = duration
        self.success = success
        self.error = error

    def __repr__(self):
        status = "✓" if self.success else "✗"
        return (
            f"EmbeddingResult({status}, "
            f"{len(self.embeddings)} embeddings, "
            f"{self.tokens_used} tokens, "
            f"{self.duration:.2f}s)"
        )
class EmbeddingGenerator:

    '''
        Générateur d'embedings en utilisant l'API Azure OpenAI
    '''
    def __init__(
            self, 
            batchsize: int = 16,
            max_retries:int = 3,
            retry_delay:float = 1.0,
    ):
        '''
            Initialisation du client OpenAI et des paramètres de génération d'embedings.
            params :
                batchsize (int): nombre d'éléments à traiter par lot
                max_retries (int): nombre maximum de tentatives en cas d'erreur
                retry_delay (float): délai entre les tentatives en secondes
        '''
        self.logger = logging.getLogger("app.EmbeddingGenerator")
    
        self.batchsize = min(batchsize,16) #Limite maximale pour azure openai
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment_name = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

        if not all([self.endpoint, self.api_version, self.api_key, self.deployment_name]):
            self.logger.error("Configuration Azure OpenAI manquante. Veuillez vérifier les variables d'environnement.")
            raise ValueError("Configuration Azure OpenAI incomplète. "
                "Vérifiez AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY et "
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT dans votre configuration.")
        
        #Initialisation de clien Azure OpenAI
        try:
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                endpoint=self.endpoint
            )
            self.logger.info("Client Azure OpenAI initialisé avec succès.")
        except Exception as e:
            self.logger.exception(f"Erreur lors de l'initialisation du client Azure OpenAI: {e}")
            raise

        self.total_embedings_generated = 0
        self.total_tokens_used = 0
        self.total_api_calls = 0

    def genrate_embedding(
            self, 
            text: str, 
            retry_count: int = 0) -> Optional[List[float]]:
        
        '''
            Génère un embedding pour un texte 
            params :
                text (str): texte à encoder
                retry_count (int): nombre de tentatives effectuées
            return : liste des float représentant l'embeding ou None en cas d'erreur
        '''
        if not text or not isinstance(text, str):
            self.logger.warning("Texte vide ou type invalide de donnée")
            return None
        try:
            response = self.client.embeddings.create(
                input=text,
                model = self.deployment_name
            )
            embeding = response['data'][0]['embedding']
            tokens_used = response.usage.total_tokens
            self.total_tokens_used+= tokens_used
            self.total_embeddings_generated += 1
            self.total_api_calls += 1

            return embeding
        except (RateLimitError, APIError, APIConnectionError) as e:
            if retry_count < self.max_retries:
                wait_time = self.retry_delay * (2 ** retry_count)
                self.logger.warning(f"Erreur API Azure OpenAI ({e}). Nouvelle tentative {retry_count + 1}/{self.max_retries} après {self.retry_delay} secondes...")
                time.sleep(wait_time)
                return self.genrate_embedding(text, retry_count + 1)
            else:
                self.logger.error(f"Échec après {self.max_retries} tentatives pour le texte : {text[:30]}... Erreur: {e}")
                return None
        except Exception as e:
            self.logger.exception(f"Erreur inattendue lors de la génération de l'embeding pour le texte : {text[:30]}... Erreur: {e}")
            return None
    
    def generate_embeddings_batch(
            self, 
            texts: List[str], 
            retry_count: int=0)->EmbeddingResult:
        
        if len(texts)> self.batchsize:
            self.logger.warning(f"Le nombre de textes ({len(texts)}) dépasse la taille maximale du lot ({self.batchsize}).")
            raise ValueError("Taille du lot dépasse la limite maximale.")
        
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            self.logger.warning("Aucun texte valide dans le lot.")
            return EmbeddingResult([], 0, 0.0, False, "Aucun texte valide")
        start_time = time.time()
        try:
            response = self.client.embeddings.create(
                input=valid_texts,
                model = self.deployment_name
            )
        except (RateLimitError, APIError, APIConnectionError) as e:
            if retry_count < self.max_retries:
                wait_time = self.retry_delay * (2 ** retry_count)
                self.logger.warning(f"Erreur API Azure OpenAI ({e}). Nouvelle tentative {retry_count + 1}/{self.max_retries} après {self.retry_delay} secondes...")
                time.sleep(wait_time)
                return self.generate_embeddings_batch(texts, retry_count + 1)
            else:
                self.logger.error(f"Échec après {self.max_retries} tentatives pour le lot de textes. Erreur: {e}")
                duration = time.time() - start_time
                return EmbeddingResult([], 0, duration, False, str(e))   
        except Exception as e:
            self.logger.exception(f"Erreur inattendue lors de la génération des embedings pour le lot de textes. Erreur: {e}")
            duration = time.time() - start_time
            return EmbeddingResult([], 0, duration, False, str(e))
    
    def generate_embeddings(
            self, 
            texts: List[str],
            show_progress: bool = True
        ) -> EmbeddingResult:
        '''
            Génère des embedings pour une liste de textes en utilisant le traitement par lot.
            params :
                texts (List[str]): liste des textes à encoder
                show_progress (bool): afficher la barre de progression
            return : EmbeddingResult contenant les embedings générés et les statistiques
        '''
        logging.info(f"Début de la génération des embedings pour {len(texts)} textes avec une taille de lot de {self.batchsize}.")
        

