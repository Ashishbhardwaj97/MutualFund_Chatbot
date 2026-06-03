import time
import pytest
from src.guardrails.classifier import QueryIntentClassifier, RefusalHandler

def test_guardrails_factual_queries():
    """
    Asserts that purely factual queries (asking for parameters, objectives, managers, sizes)
    are classified as FACTUAL.
    """
    classifier = QueryIntentClassifier()
    
    factual_cases = [
        "exit load of liquid fund",
        "who is the manager of flexicap",
        "what is the blue chip fund size",
        "multicap expense ratio",
        "what is the investment objective of retirement fund pure equity plan",
        "tell me the nav details of silver etf fof",
        "what is the minimum sip amount of commodities fund",
        "who manages the largecap fund and what is their tenure",
        # Factual comparison of a specific metric is ALLOWED as factual
        "compare the expense ratio of flexicap and multicap funds",
        "compare minimum sip of liquid fund vs commodities fund"
    ]
    
    for case in factual_cases:
        res = classifier.classify(case)
        assert res["intent"] == "FACTUAL", f"Expected FACTUAL for query '{case}', got {res['intent']}"

def test_guardrails_advisory_queries():
    """
    Asserts that investment advice, opinions, projections, general comparisons,
    or buy/sell suggestions are classified as ADVISORY.
    """
    classifier = QueryIntentClassifier()
    
    advisory_cases = [
        "Is Bluechip Fund a buy?",
        "Which fund is better between large cap and multicap?",
        "should I invest in largecap?",
        "give me a recommendation on retirement fund",
        "buy or sell icici commodities fund",
        "which fund is best?",
        "future growth forecast of largecap fund",
        "compare flexicap and multicap funds", # General comparison with no specific parameter
        "which is the safe choice for investment",
        "top performing fund this year",
        "highest returns of icici mutual funds",
        "is largecap a safe choice?",
        "give your suggestion about balanced advantage fund",
        "should i buy or sell commodities fund"
    ]
    
    for case in advisory_cases:
        res = classifier.classify(case)
        assert res["intent"] == "ADVISORY", f"Expected ADVISORY for query '{case}', got {res['intent']}"

def test_refusal_payload_structure():
    """
    Verifies that the RefusalHandler loads correctly and produces the correct
    payload containing disclaimers and SEBI/AMFI educational resource links.
    """
    handler = RefusalHandler()
    payload = handler.get_refusal_response()
    
    assert payload["status"] == "refused"
    assert "As an AI FAQ assistant" in payload["disclaimer"]
    
    resources = payload["educational_resources"]
    assert len(resources) >= 2
    
    # Check that URLs and names exist and are correct
    resource_names = [res["name"] for res in resources]
    resource_urls = [res["url"] for res in resources]
    
    assert any("AMFI" in name for name in resource_names)
    assert any("SEBI" in name for name in resource_names)
    assert "https://www.amfiindia.com/" in resource_urls
    assert "https://investor.sebi.gov.in/" in resource_urls

def test_classification_latency_budget():
    """
    Asserts that the intent classifier responds in sub-millisecond execution speeds,
    well within the 200ms latency budget constraints.
    """
    classifier = QueryIntentClassifier()
    query = "Is Bluechip Fund a buy?"
    
    # Execute and check latency
    res = classifier.classify(query)
    assert res["latency_ms"] < 200.0, f"Latency of {res['latency_ms']}ms exceeded 200ms limit!"
    
    # Run multiple times to verify average latency
    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        _ = classifier.classify(query)
        latencies.append((time.perf_counter() - start) * 1000.0)
        
    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 5.0, f"Average latency of {avg_latency:.4f}ms is surprisingly high (expected < 5ms)"
    print(f"\nAverage Intent Classifier Latency over 100 runs: {avg_latency:.4f} ms")
