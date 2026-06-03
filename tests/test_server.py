import pytest
from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)

def test_root_endpoint():
    """
    Asserts that the root GET request serves the HTML React frontend.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "GrowwFAQ" in response.text
    assert "React" in response.text or "Babel" in response.text

def test_api_schemes_endpoint():
    """
    Asserts that the /api/schemes endpoint returns the list of 10 eligible schemes.
    """
    response = client.get("/api/schemes")
    assert response.status_code == 200
    data = response.json()
    assert "schemes" in data
    schemes = data["schemes"]
    assert len(schemes) == 10
    
    # Assert that some required canonical names are present
    names = [s["fund_name"] for s in schemes]
    assert "ICICI Prudential Large Cap Fund Direct Growth" in names
    assert "ICICI Prudential Liquid Fund Direct Plan Growth" in names
    assert "ICICI Prudential Commodities Fund Direct Growth" in names
    
    # Verify metadata contains scraper date
    for s in schemes:
        assert "fund_name" in s
        assert "last_scraped_date" in s

def test_api_query_advisory_refusal():
    """
    Asserts that a query containing advisory words (e.g. "should I buy")
    instantly triggers the intent classifier safety refusal and returns disclaimers.
    """
    response = client.post("/api/query", json={"query": "Should I invest in the Large Cap fund?"})
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "refused"
    assert data["intent"] == "ADVISORY"
    assert data["answer"] is None
    assert "I cannot provide investment advice" in data["disclaimer"]
    
    # Verify that educational resources contain official links
    resources = data["educational_resources"]
    assert len(resources) >= 2
    resource_names = [r["name"] for r in resources]
    assert any("AMFI" in n for n in resource_names)
    assert any("SEBI" in n for n in resource_names)

def test_api_query_factual_success():
    """
    Asserts that a factual query matching a registered scheme
    successfully performs retrieval, triggers generation, and returns a verified citation card.
    """
    # Using mock generation triggers (or offline mode fallback)
    response = client.post("/api/query", json={"query": "What is the exit load of Liquid Fund?"})
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    assert data["intent"] == "FACTUAL"
    assert data["answer"] is not None
    assert len(data["citations"]) == 1
    
    citation = data["citations"][0]
    assert citation["fund_name"] == "ICICI Prudential Liquid Fund Direct Plan Growth"
    assert "groww.in" in citation["source_url"]
    assert "last_scraped_date" in citation

def test_api_query_ambiguous():
    """
    Asserts that a general factual query without specifying any matching fund
    is caught and returned as ambiguous so the UI can request clarification.
    """
    response = client.post("/api/query", json={"query": "what is the minimum SIP investment?"})
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "ambiguous"
    assert data["intent"] == "FACTUAL"
    assert "I couldn't identify the mutual fund scheme" in data["answer"]
    assert len(data["citations"]) == 0

def test_data_scrubber_direct():
    """
    Directly tests the DataScrubber utility against PAN, Aadhaar, Email, OTP, and Bank Accounts.
    """
    from src.utils.scrubber import DataScrubber
    scrubber = DataScrubber()
    
    # 1. Test PAN
    assert scrubber.scrub("My PAN is ABCDE1234F") == "My PAN is [REDACTED_PAN]"
    # 2. Test Aadhaar
    assert scrubber.scrub("My Aadhaar is 9876 5432 1098") == "My Aadhaar is [REDACTED_AADHAAR]"
    # 3. Test Email
    assert scrubber.scrub("Send details to test@example.com please") == "Send details to [REDACTED_EMAIL] please"
    # 4. Test OTP
    assert scrubber.scrub("My verification OTP code is 123456") == "My verification OTP code is [REDACTED_OTP]"
    # 5. Test Bank Account
    assert scrubber.scrub("Send to account 1234567890123") == "Send to account [REDACTED_ACCOUNT]"

