import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
import re
import math
import logging
from typing import List, Dict, Any, Optional, Tuple

import chromadb
from chromadb.utils import embedding_functions

from src.retrieval.query_analyzer import QueryAnalyzer

logger = logging.getLogger("HybridSearcher")

def tokenize(text: str) -> List[str]:
    """
    Standard text tokenizer: lowercases, removes non-alphanumeric chars,
    and returns a list of individual word tokens.
    """
    if not text:
        return []
    text = text.lower().strip()
    # Replace non-alphanumeric characters with spaces
    cleaned = re.sub(r"[^\w\s&]", " ", text)
    tokens = cleaned.split()
    return tokens

class LocalBM25:
    """
    A lightweight, pure-Python, zero-dependency implementation of the
    standard BM25 Okapi text relevance ranking algorithm.
    """
    def __init__(self, corpus: List[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avg_doc_len = 0.0
        
        self.doc_lengths: List[int] = []
        self.doc_term_frequencies: List[Dict[str, int]] = []
        self.doc_frequencies: Dict[str, int] = {}
        
        # Tokenize corpus and calculate stats
        total_len = 0
        for doc in corpus:
            tokens = tokenize(doc)
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            total_len += doc_len
            
            # Count local term frequencies
            tf: Dict[str, int] = {}
            unique_terms = set(tokens)
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self.doc_term_frequencies.append(tf)
            
            # Count document frequencies (how many docs have term)
            for term in unique_terms:
                self.doc_frequencies[term] = self.doc_frequencies.get(term, 0) + 1
                
        if self.corpus_size > 0:
            self.avg_doc_len = total_len / self.corpus_size

    def get_idf(self, term: str) -> float:
        """
        Calculates Inverse Document Frequency (IDF) with standard smooth log.
        """
        df = self.doc_frequencies.get(term, 0)
        # Smooth Okapi BM25 IDF
        return math.log(1.0 + (self.corpus_size - df + 0.5) / (df + 0.5))

    def get_scores(self, query: str) -> List[float]:
        """
        Scores all corpus documents against a user query string.
        """
        query_tokens = tokenize(query)
        scores: List[float] = []
        
        for i in range(self.corpus_size):
            score = 0.0
            doc_len = self.doc_lengths[i]
            tf_dict = self.doc_term_frequencies[i]
            
            for term in query_tokens:
                if term in tf_dict:
                    tf = tf_dict[term]
                    idf = self.get_idf(term)
                    
                    # BM25 Formula numerator and denominator
                    numerator = tf * (self.k1 + 1.0)
                    denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_doc_len if self.avg_doc_len > 0 else 1.0)))
                    
                    score += idf * (numerator / denominator)
                    
            scores.append(score)
            
        return scores


# Intent based keyword categories
INTENT_KEYWORDS: Dict[str, List[str]] = {
    "structure_numerical": [
        "expense", "ratio", "exit", "load", "minimum", "sip", 
        "lock-in", "lock in", "riskometer", "benchmark", "nav", 
        "aum", "size", "cr", "charges", "fees", "cost", "risk", "benchmark index"
    ],
    "fund_management": [
        "manager", "run by", "experience", "tenure", "managed by", 
        "names", "sharmila", "darshil", "nikhil", "goswami", "naren", "kabra", 
        "manager's", "managers", "team"
    ],
    "text_description": [
        "objective", "aim", "goal", "invests in", "strategy", 
        "purpose", "description", "details"
    ]
}


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


class HybridSearcher:
    """
    RAG Retrieval layer executing Query Analysis, Strict Metadata Filtering,
    Dense Vector Search, Sparse BM25 Search, RRF Rank Merging, and Intent-Based Boosting.
    """
    def __init__(self, db_path: str = "data/vectordb", collection_name: str = "mutual_funds"):
        self.analyzer = QueryAnalyzer()
        self.db_path = db_path
        self.collection_name = collection_name
        
        # Connect to persistent ChromaDB client
        logger.info(f"Connecting to persistent ChromaDB client at: {self.db_path}")
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        # Configure matching embedding function
        try:
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="BAAI/bge-small-en-v1.5"
            )
        except Exception as e:
            logger.warning(
                f"Could not load SentenceTransformer embedding function offline: {str(e)}. "
                "Falling back to deterministic OfflineMockEmbeddingFunction."
            )
            self.embedding_function = OfflineMockEmbeddingFunction()
        
        # Access the collection
        self.collection = self.client.get_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function
        )

    def _determine_intent(self, query: str) -> Optional[str]:
        """
        Scans query tokens to determine dominant information category intent.
        """
        tokens = tokenize(query)
        match_counts = {cat: 0 for cat in INTENT_KEYWORDS}
        
        for token in tokens:
            for cat, keywords in INTENT_KEYWORDS.items():
                if token in keywords:
                    match_counts[cat] += 1
                    
        # Find maximum matched category if any
        max_cat = max(match_counts, key=match_counts.get)
        if match_counts[max_cat] > 0:
            return max_cat
        return None

    def search_fund(self, query: str, fund_name: str) -> List[Dict[str, Any]]:
        """
        Executes strict metadata filtered hybrid search for a single, specific mutual fund.
        """
        logger.info(f"Executing isolated hybrid search within scheme '{fund_name}' for query '{query}'")
        
        # 1. Retrieve ALL chunks associated with this fund to enforce candidate boundaries
        try:
            get_results = self.collection.get(
                where={"fund_name": fund_name},
                include=["documents", "metadatas"]
            )
        except Exception as e:
            logger.error(f"Error querying ChromaDB metadata for '{fund_name}': {str(e)}")
            return []
            
        if not get_results or not get_results.get("documents"):
            logger.warning(f"No document chunks found in database for scheme '{fund_name}'")
            return []
            
        candidate_docs: List[str] = get_results["documents"]
        candidate_metadatas: List[Dict[str, Any]] = get_results["metadatas"]
        candidate_ids: List[str] = get_results["ids"]
        
        # 2. Dense Vector Search Scoring/Ranking
        # Query semantic vectors within the metadata scope to assign dense scores/ranks
        try:
            dense_query = self.collection.query(
                query_texts=[query],
                n_results=len(candidate_docs),
                where={"fund_name": fund_name},
                include=["distances"]
            )
        except Exception as e:
            logger.error(f"Error generating dense vectors or querying: {str(e)}")
            # Fallback: assign rank based on alphabetical IDs to keep system running
            dense_query = {"ids": [candidate_ids], "distances": [[0.5] * len(candidate_ids)]}
            
        # Map dense IDs to ranks (smaller distance = higher rank)
        dense_rankings: Dict[str, int] = {}
        if dense_query and dense_query.get("ids") and len(dense_query["ids"]) > 0:
            ordered_ids = dense_query["ids"][0]
            for rank, chunk_id in enumerate(ordered_ids):
                dense_rankings[chunk_id] = rank + 1  # 1-indexed rank
                
        # 3. Sparse BM25 Scoring/Ranking
        bm25_model = LocalBM25(candidate_docs)
        bm25_scores = bm25_model.get_scores(query)
        
        # Sort indices based on BM25 scores (higher score = higher rank)
        sparse_pairs = list(zip(candidate_ids, bm25_scores))
        sparse_pairs.sort(key=lambda x: x[1], reverse=True)
        
        sparse_rankings: Dict[str, int] = {}
        for rank, (chunk_id, _) in enumerate(sparse_pairs):
            sparse_rankings[chunk_id] = rank + 1  # 1-indexed rank
            
        # 4. RRF Rank Merging
        # Merge rankings using the standard reciprocal rank fusion algorithm
        rrf_constant = 60.0
        final_chunks: List[Dict[str, Any]] = []
        
        # Determine intent category to apply booster rewards
        intent = self._determine_intent(query)
        logger.info(f"Detected intent category for query '{query}': {intent}")
        
        for idx, chunk_id in enumerate(candidate_ids):
            dense_rank = dense_rankings.get(chunk_id, len(candidate_docs))
            sparse_rank = sparse_rankings.get(chunk_id, len(candidate_docs))
            
            # RRF calculation
            rrf_score = (1.0 / (rrf_constant + dense_rank)) + (1.0 / (rrf_constant + sparse_rank))
            
            metadata = candidate_metadatas[idx]
            
            # 5. Intent-Based Boosting
            # If the user query is looking for this exact type of content, apply a deterministic +1.0 boost
            is_boosted = False
            if intent and metadata.get("data_type") == intent:
                rrf_score += 1.0
                is_boosted = True
                
            final_chunks.append({
                "id": chunk_id,
                "content": candidate_docs[idx],
                "metadata": metadata,
                "rrf_score": rrf_score,
                "is_boosted": is_boosted
            })
            
        # Sort by RRF score descending
        final_chunks.sort(key=lambda x: x["rrf_score"], reverse=True)
        return final_chunks

    def retrieve(self, query: str) -> Dict[str, Any]:
        """
        Orchestrates full retrieval flow: parses entity tags, resolves edge cases,
        executes strict hybrid queries, and returns ordered context blocks.
        """
        # Clean and extract schemes
        extracted_schemes = self.analyzer.extract_entities(query)
        
        # Edge Case 1: Lacking scheme entity entirely
        if not extracted_schemes:
            logger.warning(f"No fund entities extracted for query: '{query}'")
            return {
                "status": "ambiguous",
                "matches": [],
                "context": []
            }
            
        # Edge Case 2: Factual multi-entity retrieval (e.g. comparing two funds side-by-side)
        if len(extracted_schemes) > 1:
            logger.info(f"Multi-entity retrieval triggered for schemes: {extracted_schemes}")
            combined_context = []
            for scheme in extracted_schemes:
                scheme_context = self.search_fund(query, scheme)
                # Keep top 2 chunks of each scheme to prevent context cluttering
                combined_context.extend(scheme_context[:2])
                
            return {
                "status": "multi_entity",
                "matches": extracted_schemes,
                "context": combined_context
            }
            
        # Standard Single-Scheme Retrieval Case
        target_scheme = extracted_schemes[0]
        context = self.search_fund(query, target_scheme)
        
        return {
            "status": "success",
            "matches": [target_scheme],
            "context": context
        }
