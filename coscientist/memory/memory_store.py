import logging
from typing import List, Dict, Any, Optional

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from coscientist.configs.config import settings

logger = logging.getLogger(__name__)

class SemanticMemory:
    """
    Long-term semantic memory for the Co-Scientist system,
    using ChromaDB to store past hypotheses, feedback, and tournament results.
    """
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )
        self.vector_store = Chroma(
            collection_name="coscientist_memory",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )
        
    def add_memory(self, text: str, metadata: Dict[str, Any]):
        """Add a memory text with associated metadata to the vector store."""
        try:
            doc = Document(page_content=text, metadata=metadata)
            self.vector_store.add_documents([doc])
        except Exception as e:
            logger.error(f"Failed to add memory to ChromaDB: {e}")

    def add_hypothesis(self, uid: str, hypothesis_text: str, elo: float):
        """Helper to store a generated hypothesis."""
        metadata = {
            "type": "hypothesis",
            "uid": uid,
            "elo": elo
        }
        self.add_memory(hypothesis_text, metadata)

    def add_feedback(self, uid: str, feedback_text: str):
        """Helper to store reflection feedback."""
        metadata = {
            "type": "feedback",
            "uid": uid
        }
        self.add_memory(feedback_text, metadata)

    def retrieve_relevant_memories(self, query: str, k: int = 5, filter_type: Optional[str] = None) -> List[Document]:
        """
        Retrieve top-k relevant memories based on semantic similarity.
        Optionally filter by metadata type.
        """
        try:
            filter_kwargs = {}
            if filter_type:
                filter_kwargs["filter"] = {"type": filter_type}
                
            results = self.vector_store.similarity_search(query, k=k, **filter_kwargs)
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve from ChromaDB: {e}")
            return []

# Singleton memory instance
semantic_memory = SemanticMemory()
