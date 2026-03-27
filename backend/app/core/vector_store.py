"""ChromaDB vector store for semantic search"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import os
import logging

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Configure HuggingFace Hub with longer timeout to prevent hangs
# Default is 10s which can timeout on slow connections
os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '60'  # 60 second timeout for downloads
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'  # Disable telemetry to reduce network calls


class VectorStore:
    """Manages vector embeddings and semantic search using ChromaDB"""

    def __init__(self):
        self.chroma_path = settings.chroma_path
        self.collection_name = "intelligence_embeddings"
        self.embedding_model_name = settings.embedding_model

        # Ensure chroma directory exists
        os.makedirs(self.chroma_path, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=self.chroma_path,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )

        # Load embedding model
        logger.info(f"Loading embedding model: {self.embedding_model_name}")
        self.embedding_model = SentenceTransformer(self.embedding_model_name)

        # Get or create collection with cosine distance metric
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Intelligence item embeddings for semantic search",
                     "hnsw:space": "cosine"}  # Use cosine similarity
        )

    def add_item(
        self,
        item_id: int,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an intelligence item to the vector store

        Args:
            item_id: Intelligence item ID
            text: Text to embed (title + content)
            metadata: Additional metadata to store
        """
        try:
            # Generate embedding
            embedding = self.embedding_model.encode(text).tolist()

            # Store in ChromaDB (use upsert to handle re-processing)
            # Note: add() silently fails on duplicate IDs, keeping old embedding!
            self.collection.upsert(
                ids=[str(item_id)],
                embeddings=[embedding],
                metadatas=[metadata or {}],
                documents=[text]
            )
            logger.debug(f"Upserted item {item_id} to vector store")

        except Exception as e:
            logger.error(f"Error adding item {item_id} to vector store: {e}")
            raise

    def add_items_batch(
        self,
        item_ids: List[int],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Add multiple items to the vector store in batch

        Args:
            item_ids: List of intelligence item IDs
            texts: List of texts to embed
            metadatas: List of metadata dicts
        """
        try:
            # Generate embeddings
            embeddings = self.embedding_model.encode(texts).tolist()

            # Store in ChromaDB (use upsert to handle re-processing)
            # Note: add() silently fails on duplicate IDs, keeping old embedding!
            self.collection.upsert(
                ids=[str(id) for id in item_ids],
                embeddings=embeddings,
                metadatas=metadatas or [{} for _ in item_ids],
                documents=texts
            )
            logger.info(f"Upserted {len(item_ids)} items to vector store")

        except Exception as e:
            logger.error(f"Error adding batch to vector store: {e}")
            raise

    def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform semantic search

        Args:
            query: Search query text
            n_results: Number of results to return
            where: Metadata filter conditions

        Returns:
            Dict with 'ids', 'distances', 'metadatas', 'documents'
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()

            # Search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )

            # Convert distances to similarity scores (1 - distance for cosine)
            if results['distances']:
                similarities = [1 - d for d in results['distances'][0]]
                results['similarities'] = [similarities]

            logger.debug(f"Search query '{query}' returned {len(results['ids'][0])} results")
            return results

        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            raise

    def get_embedding(self, item_id: int) -> Optional[List[float]]:
        """
        Get the embedding vector for a specific item

        Args:
            item_id: Intelligence item ID

        Returns:
            Embedding vector as list of floats, or None if not found
        """
        try:
            result = self.collection.get(
                ids=[str(item_id)],
                include=['embeddings']
            )

            if result and result['embeddings'] and len(result['embeddings']) > 0:
                return result['embeddings'][0]
            return None

        except Exception as e:
            logger.error(f"Error getting embedding for item {item_id}: {e}")
            return None

    def delete_item(self, item_id: int) -> None:
        """Delete an item from the vector store"""
        try:
            self.collection.delete(ids=[str(item_id)])
            logger.debug(f"Deleted item {item_id} from vector store")
        except Exception as e:
            logger.error(f"Error deleting item {item_id}: {e}")
            raise

    def get_item_count(self) -> int:
        """Get total number of items in the vector store"""
        return self.collection.count()

    def reset(self) -> None:
        """Delete all items from the collection (use with caution!)"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Intelligence item embeddings for semantic search",
                     "hnsw:space": "cosine"}  # Use cosine similarity
        )
        logger.warning("Vector store has been reset")


# Global instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create global vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
