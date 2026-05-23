import os
import logging
import threading
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import OllamaEmbeddings

# Disable Chroma telemetry to stop those "capture()" errors in console
os.environ["ANONYMIZED_TELEMETRY"] = "False"
# Logging to see errors in the console
#logging.basicConfig(level=logging.INFO)
#print("Login info for memory_service.py")
logger = logging.getLogger("MemoryService")

class MemoryService:
    def __init__(self, config):
        self.config = config
        self._collections = {}
        self._lock = threading.Lock()
        self.base_path = "./memory_storage"
        
        # Directory Setup 
        try:
            os.makedirs(self.base_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Critical: Could not create memory directory: {e}")

        # Adaptive Embedding Initialization
        provider = self.config.PROVIDER.lower()
        try:
            if provider == "ollama":
                logger.info(f"Initializing Ollama Embeddings (Model: {self.config.EMBEDDING_MODEL})")
                
                # Strip the /v1 ONLY for the embedding service
                ollama_url = str(self.config.OLLAMA_HOST).replace("/v1", "").rstrip("/")
                
                self.embedding_function = OllamaEmbeddings(
                    model=self.config.EMBEDDING_MODEL,
                    base_url=ollama_url
                )
            else:
                logger.info(f"Initializing OpenAI-Compatible Embeddings (Provider: {provider})")
                self.embedding_function = OpenAIEmbeddings(
                    model=self.config.EMBEDDING_MODEL,
                    base_url=self.config.OPEN_AI_HOST if provider == "openai" else "http://localhost:1234/v1",
                    api_key=getattr(self.config, "API_KEY", "not-needed"),
                    chunk_size=1,  # Critical for LM Studio compatibility
                    check_embedding_ctx_length=False
                )
        except Exception as e:
            logger.error(f"Failed to initialize Embedding Function: {e}")

    def _get_collection(self, conversation_id: str):
        """
        Returns a Chroma collection for this specific conversation.
        Creates it if it doesn't exist.
        """
        with self._lock:
            # Check if we already have it in memory
            if conversation_id in self._collections:
                return self._collections[conversation_id]
            
            # Create a unique folder name using the provider and model
            # We replace colons (:) with underscores because Windows doesn't like colons in folder names
            provider = self.config.PROVIDER.lower()
            model_safe_name = self.config.EMBEDDING_MODEL.replace(":", "_")
            
            # Path will look like: ./memory_storage/embedding_model_name
            folder_name = f"{conversation_id}_{provider}_{model_safe_name}"
            persist_path = os.path.join(self.base_path, folder_name)

            try:
                collection = Chroma(
                    collection_name=f"memory_{conversation_id}",
                    embedding_function=self.embedding_function,
                    persist_directory=persist_path
                )
                self._collections[conversation_id] = collection
                return collection
            except Exception as e:
                logger.error(f"Failed to initialize Chroma collection: {e}")
                raise

    def save(self, conversation_id: str, text: str):
        try:
            # Ensure text is a clean string and not empty
            clean_text = str(text).strip()
            if not clean_text:
                return

            collection = self._get_collection(conversation_id)
            
            # Use the clean string in a flat list
            collection.add_texts(texts=[clean_text])
            
            logger.info(f"Successfully saved to memory: {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to save text to memory: {e}")
            raise ConnectionError(f"Database Save Failure: {str(e)}")

    def search(self, conversation_id: str, query: str, k: int = 5):
        try:
            collection = self._get_collection(conversation_id)
            docs = collection.similarity_search(query, k=k)
            return [d.page_content for d in docs]
        except Exception as e:
            logger.error(f"Search failed for {conversation_id}: {e}")
            raise RuntimeError(f"Database Search Failure: {str(e)}")
        
    def index_company_directory(self):
        """
        Reads files from ./company_files, splits them into clean text pieces,
        and indexes them into the global company vector memory space.
        """
        dir_path = "./company_files" 
        global_id = "global_company_rag"
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            return "Internal storage folder created. Add documents to index."

        # Grab all readable files
        files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f)) and not f.startswith('.')]
        if not files:
            return "Indexing completed: No documents found to index in your folder."

        indexed_count = 0
        
        # Simple processing loop to read text out of files
        for filename in files:
            file_path = os.path.join(dir_path, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                
                if not content:
                    continue
                
                # Split text roughly by paragraphs or lines so Chroma can search chunks effectively
                chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
                
                if chunks:
                    collection = self._get_collection(global_id)
                    metadata_list = [{"source": filename, "filename": filename} for _ in chunks]
                    
                    collection.add_texts(texts=chunks, metadatas=metadata_list)
                    indexed_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to read file target {filename} during index phase: {e}")

        return f"Successfully synchronized and indexed {indexed_count} files into global company knowledge base!"