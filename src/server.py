import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
from dotenv import load_dotenv
load_dotenv()
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.guardrails.classifier import QueryIntentClassifier, RefusalHandler
from src.retrieval.query_analyzer import SCHEME_REGISTRY
from src.retrieval.hybrid_search import HybridSearcher
from src.generation.generator import FactualGenerator
from src.utils.scrubber import DataScrubber

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Server")

app = FastAPI(title="GrowwFAQ API Server", description="Backend for GrowwFAQ Facts-Only Mutual Fund Q&A Assistant")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG Pipeline components
classifier = QueryIntentClassifier()
refusal_handler = RefusalHandler()
searcher = HybridSearcher()
generator = FactualGenerator()
scrubber = DataScrubber()

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    status: str  # "success", "refused", "ambiguous", "error"
    intent: str  # "FACTUAL" or "ADVISORY"
    answer: Optional[str] = None
    disclaimer: Optional[str] = None
    educational_resources: Optional[List[Dict[str, str]]] = None
    matches: List[str] = []
    citations: List[Dict[str, Any]] = []

@app.get("/", response_class=HTMLResponse)
def read_index():
    """
    Serves the premium React SPA frontend.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(current_dir, "frontend", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/api/schemes")
def get_schemes():
    """
    Returns the list of 10 eligible mutual fund schemes from the registry.
    Queries ChromaDB to retrieve their actual last synced date if available.
    """
    schemes_data = []
    try:
        collection = searcher.collection
    except Exception as e:
        logger.error(f"Failed to access vector collection: {str(e)}")
        collection = None

    for scheme in SCHEME_REGISTRY.keys():
        last_scraped = "1 day ago"
        if collection:
            try:
                # Retrieve exactly one chunk to extract its metadata
                results = collection.get(where={"fund_name": scheme}, limit=1, include=["metadatas"])
                if results and results.get("metadatas") and len(results["metadatas"]) > 0:
                    last_scraped = results["metadatas"][0].get("last_scraped_date", last_scraped)
            except Exception as e:
                logger.warning(f"Failed to get metadata for {scheme}: {str(e)}")

        schemes_data.append({
            "fund_name": scheme,
            "last_scraped_date": last_scraped
        })

    return {"schemes": schemes_data}

@app.post("/api/query", response_model=QueryResponse)
def handle_query(payload: QueryRequest):
    """
    Routs incoming query:
    1. Runs Intent Classifier to catch advisory/non-compliant prompts.
    2. Runs Hybrid Searcher to extract target funds and retrieve source contexts.
    3. Runs Factual Generator to compile facts-only compliant responses.
    """
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Scrub query to guarantee zero sensitive data logging or processing
    query = scrubber.scrub(query)
    logger.info(f"Received query: '{query}'")

    # Step 1: Safety & Compliance Check (Intent Classifier)
    intent_res = classifier.classify(query)
    intent = intent_res.get("intent", "FACTUAL")

    if intent == "ADVISORY":
        logger.info(f"Query classified as ADVISORY. Triggering refusal.")
        refusal = refusal_handler.get_refusal_response()
        return QueryResponse(
            status="refused",
            intent="ADVISORY",
            disclaimer=refusal["disclaimer"],
            educational_resources=refusal["educational_resources"]
        )

    # Step 2: RAG Retrieval (Hybrid Search Layer)
    try:
        retrieval_res = searcher.retrieve(query)
    except Exception as e:
        logger.error(f"Retrieval error: {str(e)}")
        return QueryResponse(
            status="error",
            intent="FACTUAL",
            answer="A database error occurred while searching for matching mutual funds."
        )

    status = retrieval_res.get("status")
    matches = retrieval_res.get("matches", [])
    context_chunks = retrieval_res.get("context", [])

    if status == "ambiguous":
        logger.info("Retrieval returned ambiguous status (no matching fund).")
        return QueryResponse(
            status="ambiguous",
            intent="FACTUAL",
            answer="I couldn't identify the mutual fund scheme in your query. Please ask a factual question about one of the eligible schemes in the sidebar."
        )

    # Step 3: Response Generation (facts-only with validators)
    try:
        answer = generator.generate(query, context_chunks)
    except Exception as e:
        logger.error(f"Generation error: {str(e)}")
        return QueryResponse(
            status="error",
            intent="FACTUAL",
            answer="An error occurred while compiling the facts-only response. Please check your query or try again."
        )

    # Compile citation cards metadata for the frontend
    citations = []
    seen_urls = set()
    for chunk in context_chunks:
        meta = chunk.get("metadata", {})
        url = meta.get("source_url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            citations.append({
                "fund_name": meta.get("fund_name"),
                "source_url": url,
                "last_scraped_date": meta.get("last_scraped_date")
            })

    # Return success payload
    return QueryResponse(
        status="success",
        intent="FACTUAL",
        answer=answer,
        matches=matches,
        citations=citations[:1]  # The generator uses exactly one citation URL
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
