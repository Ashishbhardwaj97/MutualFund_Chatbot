import pytest
from src.retrieval.query_analyzer import QueryAnalyzer
from src.retrieval.hybrid_search import LocalBM25, HybridSearcher, tokenize

def test_query_analyzer_basic():
    """
    Asserts that colloquial scheme names map with 100% precision to the correct canonical fund name.
    """
    analyzer = QueryAnalyzer()
    
    # Test cases mapping input queries to expected canonical names
    cases = [
        ("exit load of liquid fund", "ICICI Prudential Liquid Fund Direct Plan Growth"),
        ("who is the manager of flexicap", "ICICI Prudential Flexicap Fund Direct Growth"),
        ("what is the blue chip fund size", "ICICI Prudential Large Cap Fund Direct Growth"),
        ("tell me about the value discovery fund", "ICICI Prudential Value Direct Growth"),
        ("what is the benchmark of retirement fund pure equity plan", "ICICI Prudential Retirement Fund Pure Equity Plan Direct Growth"),
        ("multicap expense ratio", "ICICI Prudential Multicap Fund Direct Plan Growth"),
        ("silver etf fof details", "ICICI Prudential Silver ETF FoF Direct Growth"),
        ("icici commodities fund minimum investment", "ICICI Prudential Commodities Fund Direct Growth"),
        ("smallcap nav details", "ICICI Prudential Smallcap Fund Direct Plan Growth")
    ]
    
    for query, expected_canonical in cases:
        matches = analyzer.extract_entities(query)
        assert len(matches) == 1, f"Expected exactly one match for: '{query}', got {matches}"
        assert matches[0] == expected_canonical, f"Expected '{expected_canonical}' for '{query}', got '{matches[0]}'"

def test_query_analyzer_multi_entity():
    """
    Asserts that queries mentioning multiple schemes are mapped to both canonical names correctly.
    """
    analyzer = QueryAnalyzer()
    query = "compare the expense ratio of flexicap and multicap funds"
    matches = analyzer.extract_entities(query)
    
    assert len(matches) == 2
    assert "ICICI Prudential Flexicap Fund Direct Growth" in matches
    assert "ICICI Prudential Multicap Fund Direct Plan Growth" in matches

def test_query_analyzer_empty_ambiguous():
    """
    Asserts that queries with no scheme mentions return empty results.
    """
    analyzer = QueryAnalyzer()
    assert analyzer.extract_entities("what is mutual fund?") == []
    assert analyzer.extract_entities("what is the minimum sip amount?") == []

def test_local_bm25():
    """
    Verifies that the custom zero-dependency LocalBM25 class ranks documents with keyword precision.
    """
    corpus = [
        "The exit load of this scheme is 0.007% if redeemed within 1 day, and 0% thereafter.",
        "The fund is managed by Sharmila D'Silva and Darshil Dedhia who have extensive industry experience.",
        "The investment objective of the fund is to generate reasonable returns with high levels of liquidity."
    ]
    
    bm25 = LocalBM25(corpus)
    
    # 1. Query "exit load" should score the first document the highest
    exit_scores = bm25.get_scores("exit load")
    assert exit_scores[0] > exit_scores[1]
    assert exit_scores[0] > exit_scores[2]
    
    # 2. Query "managed by sharmila" should score the second document the highest
    mgr_scores = bm25.get_scores("managed by sharmila")
    assert mgr_scores[1] > mgr_scores[0]
    assert mgr_scores[1] > mgr_scores[2]
    
    # 3. Query "investment objective" should score the third document the highest
    obj_scores = bm25.get_scores("investment objective")
    assert obj_scores[2] > obj_scores[0]
    assert obj_scores[2] > obj_scores[1]

def test_hybrid_searcher_success_flow():
    """
    Tests the fully integrated HybridSearcher using the active persistent ChromaDB.
    Verifies strict metadata filtering (zero fund bleed) and dynamic intent-based boosting.
    """
    searcher = HybridSearcher(db_path="data/vectordb", collection_name="mutual_funds")
    
    # Test case: exit load of liquid fund
    query = "What is the exit load of the Liquid Fund?"
    res = searcher.retrieve(query)
    
    assert res["status"] == "success"
    assert len(res["matches"]) == 1
    assert res["matches"][0] == "ICICI Prudential Liquid Fund Direct Plan Growth"
    
    context = res["context"]
    assert len(context) > 0
    
    # Assert Strict Isolation (Zero Fund Bleed verification)
    # Every returned chunk must belong to the ICICI Prudential Liquid Fund
    for chunk in context:
        assert chunk["metadata"]["fund_name"] == "ICICI Prudential Liquid Fund Direct Plan Growth"
        assert chunk["metadata"]["source_url"] == "https://groww.in/mutual-funds/icici-prudential-liquid-fund-direct-plan-growth"
        
    # Assert Intent-Based Boosting
    # Query mentions "exit load", which matches "structure_numerical" keywords.
    # Therefore, the numerical chunk must be ranked first (Rank 1).
    first_chunk = context[0]
    assert first_chunk["metadata"]["data_type"] == "structure_numerical"
    assert first_chunk["is_boosted"] is True

def test_hybrid_searcher_manager_boosting():
    """
    Verifies that fund manager queries correctly determine intent and boost the management details chunk.
    """
    searcher = HybridSearcher(db_path="data/vectordb", collection_name="mutual_funds")
    
    # Test case: who is the manager of large cap
    query = "Who is the manager of the Large Cap Fund?"
    res = searcher.retrieve(query)
    
    assert res["status"] == "success"
    assert res["matches"][0] == "ICICI Prudential Large Cap Fund Direct Growth"
    
    context = res["context"]
    assert len(context) > 0
    
    # First chunk should be boosted and contain fund manager information
    first_chunk = context[0]
    assert first_chunk["metadata"]["data_type"] == "fund_management"
    assert first_chunk["is_boosted"] is True
    assert "Manager" in first_chunk["content"] or "team" in first_chunk["content"].lower()

def test_hybrid_searcher_multi_entity():
    """
    Verifies retrieval for multi-fund queries, checking that chunks from both funds are gathered.
    """
    searcher = HybridSearcher(db_path="data/vectordb", collection_name="mutual_funds")
    
    query = "what is the minimum sip of multicap and silver fund?"
    res = searcher.retrieve(query)
    
    assert res["status"] == "multi_entity"
    assert len(res["matches"]) == 2
    assert "ICICI Prudential Multicap Fund Direct Plan Growth" in res["matches"]
    assert "ICICI Prudential Silver ETF FoF Direct Growth" in res["matches"]
    
    context = res["context"]
    assert len(context) > 0
    
    # Chunks should be retrieved from both schemes
    matched_names = {chunk["metadata"]["fund_name"] for chunk in context}
    assert "ICICI Prudential Multicap Fund Direct Plan Growth" in matched_names
    assert "ICICI Prudential Silver ETF FoF Direct Growth" in matched_names

def test_hybrid_searcher_ambiguous():
    """
    Verifies that queries mentioning no funds are flagged as ambiguous to prevent multi-fund bleeding.
    """
    searcher = HybridSearcher(db_path="data/vectordb", collection_name="mutual_funds")
    
    query = "what is the exit load?"
    res = searcher.retrieve(query)
    
    assert res["status"] == "ambiguous"
    assert res["matches"] == []
    assert res["context"] == []
