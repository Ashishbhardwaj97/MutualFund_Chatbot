import re
import os
import json
import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger("QueryIntentClassifier")

# Hard-coded regex patterns indicating ADVISORY intent
ADVISORY_PATTERNS = [
    r"\bshould\s+i\b",
    r"\b(buy|sell|sells|selling|sold)\b",
    r"\b(recommend|recommendation|recommendations|advice|advise|advising|adviser|advisor|advisers|advisors|advisory|suggest|suggestion|suggestions|opinion|opinions)\b",
    r"\b(projection|projections|prediction|predictions|predict|predicting|forecast|forecasts|forecasting|future\s+growth|growth\s+prediction|predict\s+growth)\b",
    r"\b(highest|better|best|greatest|top)\s+(performance|returns?|profit|gain|gains|yield|yields)\b",
    r"\btop\s+performing\b",
    r"\bwhich\s+.*\b(best|better|highest|safe|safer)\b",
    r"\bis\s+.*\b(good|safe|safer|better|wise|profitable|a\s+buy|a\s+sell)\b",
    r"\b(good|safe|safer|better|wise|best|great|top)\s+choice\b",
    r"\b(double|triple|multiply)\b"
]

# Keywords indicating comparison/opinion if no factual parameter is present
COMPARISON_KEYWORDS = ["compare", "comparison", "vs", "versus", "better", "best", "comparison of"]

# Factual parameter keywords
FACTUAL_KEYWORDS = [
    "expense", "ratio", "exit", "load", "minimum", "sip", "investment", "amount",
    "lock-in", "lock in", "riskometer", "risk", "benchmark", "index", "nav",
    "aum", "size", "manager", "run by", "experience", "tenure", "managed",
    "objective", "aim", "goal", "description", "details"
]

class QueryIntentClassifier:
    """
    High-speed classifier that inspects user queries for advisory/comparison intent.
    Maintains a strict zero-tolerance policy for investment opinions, comparisons,
    or buy/sell advice.
    """
    def __init__(self):
        # Compile advisory patterns for high-speed regex matching
        self.advisory_regexes = [re.compile(pattern, re.IGNORECASE) for pattern in ADVISORY_PATTERNS]
        self.comparison_words = COMPARISON_KEYWORDS
        self.factual_words = FACTUAL_KEYWORDS

    def clean_query(self, query: str) -> str:
        """
        Normalizes query string for classification.
        """
        if not query:
            return ""
        q = query.lower().strip()
        q = re.sub(r"[^\w\s&]", " ", q)
        return re.sub(r"\s+", " ", q).strip()

    def classify(self, query: str) -> Dict[str, Any]:
        """
        Classifies incoming queries into either 'FACTUAL' or 'ADVISORY'.
        Returns a dictionary containing the intent and execution latency.
        """
        start_time = time.perf_counter()
        normalized_q = self.clean_query(query)

        if not normalized_q:
            latency = (time.perf_counter() - start_time) * 1000.0
            return {"intent": "FACTUAL", "latency_ms": latency}

        # 1. Step 1: Check for hard-blocked advisory patterns (Regex checks)
        for regex in self.advisory_regexes:
            if regex.search(normalized_q):
                latency = (time.perf_counter() - start_time) * 1000.0
                logger.info(f"Advisory pattern matched in query: '{query}'. Classification: ADVISORY.")
                return {"intent": "ADVISORY", "latency_ms": latency}

        # 2. Step 2: Check for general comparison/opinion keywords
        has_comparison = False
        tokens = normalized_q.split()
        for word in self.comparison_words:
            if word in tokens or word in normalized_q:
                has_comparison = True
                break

        if has_comparison:
            # Check if a factual parameter keyword is present to allow parameter comparison
            has_factual_param = False
            for param in self.factual_words:
                if param in tokens or param in normalized_q:
                    has_factual_param = True
                    break
            
            if not has_factual_param:
                latency = (time.perf_counter() - start_time) * 1000.0
                logger.info(f"General comparison query without factual parameters: '{query}'. Classification: ADVISORY.")
                return {"intent": "ADVISORY", "latency_ms": latency}

        latency = (time.perf_counter() - start_time) * 1000.0
        logger.info(f"Query classified as FACTUAL: '{query}'. Latency: {latency:.4f}ms.")
        return {"intent": "FACTUAL", "latency_ms": latency}


class RefusalHandler:
    """
    Standardized handler to read refusal disclaimers and educational resources,
    and build polite refusal payloads.
    """
    def __init__(self, config_path: str = None):
        if not config_path:
            # Locate default refusal_config.json relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "refusal_config.json")
            
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load refusal configuration from {self.config_path}: {str(e)}")
            # Fallback inline config if file reading fails
            return {
                "refusal_disclaimer": "As an AI FAQ assistant, I am designed to provide only direct, objective, and verifiable facts about mutual funds. I cannot provide investment advice, recommendations, performance opinions, comparisons, or buy/sell suggestions.",
                "educational_resources": [
                    {
                        "name": "AMFI India (Association of Mutual Funds in India)",
                        "url": "https://www.amfiindia.com/"
                    },
                    {
                        "name": "SEBI Investor Education (Securities and Exchange Board of India)",
                        "url": "https://investor.sebi.gov.in/"
                    }
                ]
            }

    def get_refusal_response(self) -> Dict[str, Any]:
        """
        Builds a clean, polite standardized refusal response dictionary.
        """
        return {
            "status": "refused",
            "disclaimer": self.config.get("refusal_disclaimer", ""),
            "educational_resources": self.config.get("educational_resources", [])
        }
