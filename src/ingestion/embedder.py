import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
import json
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions

from src.ingestion.parser import FundProfile, SemanticChunker

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("VectorStoreLoader")

class OfflineMockEmbeddingFunction:
    """
    A fallback embedding function that generates deterministic mock vectors
    when Hugging Face is offline. Bypasses all network/download errors.
    """
    def __call__(self, input: List[str]) -> List[List[float]]:
        import hashlib
        results = []
        for text in input:
            hasher = hashlib.md5(text.encode("utf-8"))
            digest = hasher.digest()
            vector = []
            for i in range(384):
                val = float((digest[i % 16] + i) / 256.0)
                vector.append(val)
            results.append(vector)
        return results

class VectorStoreLoader:
    """
    Loads parsed mutual fund profiles, chunks them semantically,
    and loads them into a persistent local ChromaDB index using BGE-Small embeddings.
    """
    def __init__(self, db_path: str = "data/vectordb", collection_name: str = "mutual_funds"):
        self.db_path = db_path
        self.collection_name = collection_name
        self.chunker = SemanticChunker()
        
        # Initialize Persistent ChromaDB Client
        logger.info(f"Initializing persistent ChromaDB client at: {self.db_path}")
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # Configure BGE-Small as the Local Embedding Function
        try:
            logger.info("Configuring local BGE-Small (BAAI/bge-small-en-v1.5) embedding function...")
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="BAAI/bge-small-en-v1.5"
            )
        except Exception as e:
            logger.warning(
                f"Could not load SentenceTransformer embedding function offline: {str(e)}. "
                "Falling back to deterministic OfflineMockEmbeddingFunction."
            )
            self.embedding_function = OfflineMockEmbeddingFunction()
        
        # Create or Get the Collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}  # Use Cosine similarity for normalized embeddings
        )
        logger.info(f"Successfully connected to ChromaDB collection: '{self.collection_name}'")

    def get_active_hash(self, fund_name: str) -> Optional[str]:
        """
        Queries ChromaDB for the active content hash of a specific mutual fund scheme.
        Returns None if the fund is not present or has no hash.
        """
        try:
            results = self.collection.get(
                where={"fund_name": fund_name},
                limit=1,
                include=["metadatas"]
            )
            if results and results.get("metadatas"):
                return results["metadatas"][0].get("content_hash")
        except Exception as e:
            logger.warning(f"Error querying active hash for '{fund_name}': {str(e)}")
        return None

    def load_profiles_from_dir(self, parsed_dir: str = "data/parsed") -> List[FundProfile]:
        """
        Loads all structured JSON fund profiles from the parsed directory.
        """
        profiles = []
        if not os.path.exists(parsed_dir):
            logger.warning(f"Parsed directory does not exist: {parsed_dir}")
            return profiles

        for filename in os.listdir(parsed_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(parsed_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        profile = FundProfile(**data)
                        profiles.append(profile)
                except Exception as e:
                    logger.error(f"Failed to load or parse JSON profile '{file_path}': {str(e)}")
        
        logger.info(f"Successfully loaded {len(profiles)} fund profiles from '{parsed_dir}'")
        return profiles

    def embed_and_load(self, profiles: List[FundProfile], force_refresh: bool = False) -> bool:
        """
        Processes each FundProfile into semantic chunks and inserts them into ChromaDB.
        Performs incremental update checks using content hashes, or forces a refresh if force_refresh=True.
        """
        if not profiles:
            logger.warning("No profiles provided to load.")
            return False

        total_chunks_loaded = 0

        for profile in profiles:
            fund_name = profile.fund_name
            logger.info(f"Processing scheme: '{fund_name}'")

            # Calculate deterministic content hash
            new_hash = profile.calculate_hash()

            if not force_refresh:
                active_hash = self.get_active_hash(fund_name)
                if active_hash == new_hash:
                    logger.info(f"[No Change] Scheme '{fund_name}' is already up-to-date in database (hash: {new_hash}). Skipping re-embedding.")
                    continue
                else:
                    logger.info(f"[Change Detected] Hash changed for '{fund_name}' (old: {active_hash}, new: {new_hash}). Refreshing database entry.")

            # 1. Generate Semantic Chunks
            chunks = self.chunker.chunk(profile)
            if not chunks:
                logger.warning(f"No chunks generated for: '{fund_name}'")
                continue

            # 2. De-duplicate: Remove any existing chunks in ChromaDB for this specific fund_name
            try:
                # Perform metadata-based deletion to prevent duplicates
                self.collection.delete(where={"fund_name": fund_name})
                logger.info(f"De-duplicated: Deleted existing vectors for '{fund_name}'")
            except Exception as e:
                logger.warning(f"Could not check/delete old vectors for '{fund_name}': {str(e)}")

            # 3. Prepare Batch Lists for Insertion
            documents = []
            metadatas = []
            ids = []

            for idx, chunk in enumerate(chunks):
                documents.append(chunk.content)
                metadatas.append(chunk.metadata)
                
                # Create a unique, deterministic ID for each chunk
                sanitized_name = "".join(c if c.isalnum() else "_" for c in fund_name)
                chunk_id = f"{sanitized_name}_{chunk.metadata['data_type']}_{idx}"
                ids.append(chunk_id)

            # 4. Insert Chunks into ChromaDB
            try:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info(f"Loaded {len(chunks)} semantic chunks for '{fund_name}' into database.")
                total_chunks_loaded += len(chunks)
            except Exception as e:
                logger.error(f"Failed to load chunks for '{fund_name}' into ChromaDB: {str(e)}")
                return False

        logger.info(f"Embedding & Loading Complete. Total chunks in database: {total_chunks_loaded}")
        return True

if __name__ == "__main__":
    loader = VectorStoreLoader()
    profiles = loader.load_profiles_from_dir()
    if profiles:
        loader.embed_and_load(profiles)
    else:
        logger.error("No profiles found to embed and load. Please run 'run_ingest.py' first to scrape and parse data.")
