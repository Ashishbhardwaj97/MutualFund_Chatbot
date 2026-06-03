import os
import shutil
import pytest
import chromadb
from src.ingestion.parser import FundProfile, FundManager, SemanticChunker
from src.ingestion.embedder import VectorStoreLoader

# Define absolute paths for test sandbox directories
TEST_DB_PATH = "data/test_vectordb"

@pytest.fixture(scope="function")
def test_db_cleaner():
    """
    Fixture to ensure a clean, isolated database path for vector testing.
    """
    if os.path.exists(TEST_DB_PATH):
        try:
            shutil.rmtree(TEST_DB_PATH)
        except Exception:
            pass
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            shutil.rmtree(TEST_DB_PATH)
        except Exception:
            pass

def test_deterministic_hashing():
    """
    Test that FundProfile produces deterministic content hashes and is immune to last_scraped_date changes.
    """
    profile1 = FundProfile(
        fund_name="Test Hybrid Fund",
        source_url="https://groww.in/test-hybrid",
        nav=50.25,
        fund_size=100.0,
        expense_ratio=0.5,
        exit_load="0.5% within 1 month",
        min_sip=500.0,
        lock_in="No Lock-in",
        riskometer="High",
        benchmark="Nifty 500",
        managers=[FundManager(name="John Doe", experience="10Y", tenure="5Y")],
        objective="Factual Growth",
        last_scraped_date="2026-06-01"
    )
    
    profile2 = FundProfile(
        fund_name="Test Hybrid Fund",
        source_url="https://groww.in/test-hybrid",
        nav=50.25,
        fund_size=100.0,
        expense_ratio=0.5,
        exit_load="0.5% within 1 month",
        min_sip=500.0,
        lock_in="No Lock-in",
        riskometer="High",
        benchmark="Nifty 500",
        managers=[FundManager(name="John Doe", experience="10Y", tenure="5Y")],
        objective="Factual Growth",
        last_scraped_date="2026-06-02" # Different date
    )
    
    # Assert that despite different scraped dates, the content hash remains identical
    hash1 = profile1.calculate_hash()
    hash2 = profile2.calculate_hash()
    assert hash1 == hash2
    
    # Assert that changing a core metric changes the hash
    profile2.nav = 50.30
    assert profile1.calculate_hash() != profile2.calculate_hash()
    
    # Assert that changing a manager changes the hash
    profile2.nav = 50.25
    profile2.managers = [FundManager(name="Jane Smith", experience="8Y", tenure="2Y")]
    assert profile1.calculate_hash() != profile2.calculate_hash()

from unittest.mock import patch

@patch("chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction")
def test_active_hash_retrieval_and_incremental_flow(mock_emb_class, test_db_cleaner):
    """
    Test that VectorStoreLoader correctly populates, retrieves, and updates active hashes incrementally.
    """
    class MockEmbeddingFunction:
        def __call__(self, input: list) -> list:
            return [[0.1] * 384 for _ in input]
            
    mock_emb_class.return_value = MockEmbeddingFunction()
    
    loader = VectorStoreLoader(db_path=TEST_DB_PATH, collection_name="test_mutual_funds")
    
    profile = FundProfile(
        fund_name="ICICI Test Liquid Fund",
        source_url="https://groww.in/icici-test-liquid",
        nav=10.0,
        fund_size=500.0,
        expense_ratio=0.15,
        exit_load="Nil",
        min_sip=100.0,
        lock_in="No Lock-in",
        riskometer="Low",
        benchmark="Liquid Index",
        managers=[FundManager(name="Rahul Smith", experience="12Y", tenure="4Y")],
        objective="Liquidity",
        last_scraped_date="2026-06-01"
    )
    
    # Initially, database should not contain any hash for this fund
    assert loader.get_active_hash("ICICI Test Liquid Fund") is None
    
    # 1. Embed and load the first time (should add chunks and set the hash)
    success = loader.embed_and_load([profile])
    assert success
    
    first_hash = profile.calculate_hash()
    stored_hash = loader.get_active_hash("ICICI Test Liquid Fund")
    assert stored_hash == first_hash
    
    # Track delete calls using a wrapper function
    delete_called = False
    original_delete = loader.collection.delete
    
    def mock_delete(*args, **kwargs):
        nonlocal delete_called
        delete_called = True
        return original_delete(*args, **kwargs)
        
    # Bypass Pydantic's frozen attribute mechanism
    object.__setattr__(loader.collection, "delete", mock_delete)

    # 2. Re-ingest same content (should skip embedding using incremental hash matching)
    skip_success = loader.embed_and_load([profile])
    assert skip_success
    assert not delete_called, "Deletion should not be triggered when hashes are identical."
    
    # 3. Modify NAV and re-ingest (should detect hash change, delete, and re-embed)
    profile.nav = 10.50
    second_hash = profile.calculate_hash()
    assert first_hash != second_hash
    
    # Reset tracking variable
    delete_called = False
    
    update_success = loader.embed_and_load([profile])
    assert update_success
    assert delete_called, "Deletion must be triggered when a content change is detected."
    
    # Retrieve refreshed hash and verify
    assert loader.get_active_hash("ICICI Test Liquid Fund") == second_hash
