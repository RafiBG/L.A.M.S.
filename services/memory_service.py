import threading
from langchain_chroma import Chroma
from langchain_community.embeddings import OllamaEmbeddings


class MemoryService:
    def __init__(self, config):
        self.config = config
        self._lock = threading.Lock()

        self.embeddings = OllamaEmbeddings(
            model="embeddinggemma:300m",
            base_url=config.OLLAMA_HOST  # example: http://localhost:11434
        )

        self.vector_db = Chroma(
            persist_directory="./bot_memory_storage",
            embedding_function=self.embeddings,
            collection_name="slack_long_term_memory"
        )

    def save(self, conversation_id: str, text: str):
        with self._lock:
            self.vector_db.add_texts(
                texts=[text],
                metadatas=[{"conversation_id": conversation_id}]
            )
            self.vector_db.persist()

    def search(self, conversation_id: str, query: str, k: int = 3):
        docs = self.vector_db.similarity_search(
            query,
            k=k,
            filter={"conversation_id": conversation_id}
        )

        if not docs:
            return []

        return [d.page_content for d in docs]

    def clear(self, conversation_id: str):
        with self._lock:
            self.vector_db.delete(where={"conversation_id": conversation_id})
            self.vector_db.persist()