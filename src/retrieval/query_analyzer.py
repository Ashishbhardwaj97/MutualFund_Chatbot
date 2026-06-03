import re
import logging
from typing import List, Dict, Set

logger = logging.getLogger("QueryAnalyzer")

# Comprehensive mapping of canonical database fund_name strings to key colloquial terms.
# Contains all possible direct/indirect naming variations to ensure 100% precision.
SCHEME_REGISTRY: Dict[str, List[str]] = {
    "ICICI Prudential Large Cap Fund Direct Growth": [
        "large cap", "largecap", "bluechip", "blue chip", "large-cap", "icici prudential large cap"
    ],
    "ICICI Prudential Commodities Fund Direct Growth": [
        "commodities", "commodity", "metals", "metal", "icici prudential commodities"
    ],
    "ICICI Prudential Equity & Debt Fund Direct Growth": [
        "balanced", "balanced advantage", "balanced-advantage", "equity & debt", "equity and debt", 
        "equity & debt fund", "hybrid", "icici prudential balanced"
    ],
    "ICICI Prudential Liquid Fund Direct Plan Growth": [
        "liquid", "liquid fund", "icici prudential liquid"
    ],
    "ICICI Prudential Flexicap Fund Direct Growth": [
        "flexicap", "flexi cap", "flexi-cap", "icici prudential flexicap"
    ],
    "ICICI Prudential Value Direct Growth": [
        "value", "value discovery", "value fund", "icici prudential value"
    ],
    "ICICI Prudential Retirement Fund Pure Equity Plan Direct Growth": [
        "retirement", "pure equity plan", "retirement fund", "icici prudential retirement"
    ],
    "ICICI Prudential Multicap Fund Direct Plan Growth": [
        "multicap", "multi cap", "multi-cap", "icici prudential multicap"
    ],
    "ICICI Prudential Silver ETF FoF Direct Growth": [
        "silver", "silver etf", "silver fof", "silver fund", "icici prudential silver"
    ],
    "ICICI Prudential Smallcap Fund Direct Plan Growth": [
        "smallcap", "small cap", "small-cap", "icici prudential smallcap"
    ]
}

class QueryAnalyzer:
    """
    Parses user queries to extract matching mutual fund schemes.
    Resolves colloquial scheme abbreviations and full names to database keys.
    """
    def __init__(self):
        self.registry = SCHEME_REGISTRY

    def clean_query(self, query: str) -> str:
        """
        Normalizes the user query: lowercases, removes excess whitespace, and cleans punctuation.
        """
        if not query:
            return ""
        # Lowercase and clean
        q = query.lower().strip()
        # Remove common punctuation except ampersands (used in 'equity & debt')
        q = re.sub(r"[^\w\s&]", " ", q)
        # Collapse multiple spaces
        q = re.sub(r"\s+", " ", q).strip()
        return q

    def extract_entities(self, query: str) -> List[str]:
        """
        Analyzes the query and extracts canonical fund names.
        Returns a list of matching canonical fund names.
        """
        normalized_q = self.clean_query(query)
        if not normalized_q:
            return []

        matched_schemes: Set[str] = set()

        for canonical_name, aliases in self.registry.items():
            # Check canonical name directly (lowercased)
            canonical_lower = canonical_name.lower()
            # Normalize 'equity & debt' to 'equity and debt' to cover both
            canonical_normalized = canonical_lower.replace("&", "and")

            # Check if canonical name is mentioned in the query
            if canonical_lower in normalized_q or canonical_normalized in normalized_q:
                matched_schemes.add(canonical_name)
                continue

            # Check aliases
            for alias in aliases:
                # Use word-boundary or substring checks depending on length and uniqueness
                pattern = rf"\b{re.escape(alias)}\b"
                if re.search(pattern, normalized_q):
                    matched_schemes.add(canonical_name)
                    break

        result = list(matched_schemes)
        logger.info(f"Extracted entities for query '{query}': {result}")
        return result
