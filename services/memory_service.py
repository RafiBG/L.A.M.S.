import os
import threading
from langchain_chroma import Chroma
from langchain_community.embeddings import OllamaEmbeddings


class MemoryService:
    def __init__(self, config):
        self.config = config
        self._collections = {}
        self._lock = threading.Lock()
        self.base_path = "./memory_storage"

        os.makedirs(self.base_path, exist_ok=True)

        self.embedding_function = OllamaEmbeddings(
            model=self.config.EMBEDDING_MODEL,
            base_url="http://localhost:11434"
        )

    def _get_collection(self, conversation_id: str):
        """
        Returns a Chroma collection for this specific conversation.
        Creates it if it doesn't exist.
        """

        with self._lock:
            if conversation_id not in self._collections:
                persist_path = os.path.join(self.base_path, conversation_id)
                os.makedirs(persist_path, exist_ok=True)

                collection = Chroma(
                    collection_name=f"memory_{conversation_id}",
                    embedding_function=self.embedding_function,
                    persist_directory=persist_path
                )

                self._collections[conversation_id] = collection

            return self._collections[conversation_id]

    def save(self, conversation_id: str, text: str):
        collection = self._get_collection(conversation_id)
        collection.add_texts([text])

    def search(self, conversation_id: str, query: str, k: int = 5):
        collection = self._get_collection(conversation_id)
        docs = collection.similarity_search(query, k=k)
        return [d.page_content for d in docs]