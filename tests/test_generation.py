import pytest
import os
from unittest.mock import patch, MagicMock
from src.generation.validator import OutputValidator
from src.generation.generator import FactualGenerator

# -----------------------------------------------------------------------------
# OutputValidator Tests
# -----------------------------------------------------------------------------

def test_validator_sentence_counting_basic():
    """
    Asserts sentence counting matches normal outputs.
    """
    validator = OutputValidator()
    
    # 1 sentence
    assert validator.count_sentences("This is one sentence.") == 1
    # 2 sentences
    assert validator.count_sentences("First sentence. Second sentence.") == 2
    # 3 sentences
    assert validator.count_sentences("First. Second? Third!") == 3
    # 0 sentences
    assert validator.count_sentences("") == 0
    assert validator.count_sentences("   ") == 0

def test_validator_sentence_counting_decimals_and_abbreviations():
    """
    Asserts decimals (e.g. 1.25%) and common abbreviations (e.g. Mr., Rs.) 
    do not distort sentence counts.
    """
    validator = OutputValidator()
    
    # Decimals and abbreviations inside 2 sentences
    text = "The fund NAV is Rs. 42.50. It is managed by Mr. S. Naren."
    # Rs. 42.50 has a dot after Rs, a dot in 42.50, S. has a dot, Naren has a dot.
    # Total sentences should be evaluated as 2!
    assert validator.count_sentences(text) == 2

    # Decimals and URL inside 3 sentences
    text2 = "The exit load is 1.25% if redeemed within 1 year. For details, view https://groww.in/mutual-funds/icici-pru. Last updated from sources: 2026-06-02"
    assert validator.count_sentences(text2) == 3

def test_validator_citation_extraction():
    """
    Asserts citation extraction finds correct Groww mutual fund URLs.
    """
    validator = OutputValidator()
    
    text = "Find details at https://groww.in/mutual-funds/icici-prudential-large-cap-fund-direct-growth."
    urls = validator.extract_citations(text)
    assert len(urls) == 1
    assert urls[0] == "https://groww.in/mutual-funds/icici-prudential-large-cap-fund-direct-growth"

    # Multi URLs
    text2 = "Check https://groww.in/mutual-funds/fund-a and https://groww.in/mutual-funds/fund-b"
    assert len(validator.extract_citations(text2)) == 2

    # Non Groww URL
    text3 = "Check https://google.com"
    assert len(validator.extract_citations(text3)) == 0

def test_validator_compliance_failures():
    """
    Asserts that the validator correctly flags sentence-limit breaches, citation mismatches,
    missing footers, and advisory keywords.
    """
    target_url = "https://groww.in/mutual-funds/icici-pru-liquid"
    last_scraped_date = "2026-06-02"
    validator = OutputValidator(target_url=target_url, last_scraped_date=last_scraped_date)

    # 1. Valid compliant response
    valid_text = "The fund is managed by Sharmila D'Silva. For metrics, visit: https://groww.in/mutual-funds/icici-pru-liquid\nLast updated from sources: 2026-06-02"
    is_valid, errors = validator.validate(valid_text)
    assert is_valid is True
    assert len(errors) == 0

    # 2. Too long (>3 sentences)
    too_long = "One. Two. Three. Four. For metrics, visit: https://groww.in/mutual-funds/icici-pru-liquid\nLast updated from sources: 2026-06-02"
    is_valid, errors = validator.validate(too_long)
    assert is_valid is False
    assert any("Sentence count exceeds limit" in err for err in errors)

    # 3. Citation mismatch
    wrong_citation = "The fund is managed by Sharmila D'Silva. For metrics, visit: https://groww.in/mutual-funds/wrong-fund\nLast updated from sources: 2026-06-02"
    is_valid, errors = validator.validate(wrong_citation)
    assert is_valid is False
    assert any("Citation URL mismatch" in err for err in errors)

    # 4. Footer missing/incorrect date
    wrong_footer = "The fund is managed by Sharmila. Visit: https://groww.in/mutual-funds/icici-pru-liquid\nLast updated from sources: 2026-05-15"
    is_valid, errors = validator.validate(wrong_footer)
    assert is_valid is False
    assert any("Footer date mismatch" in err for err in errors)

    # 5. Advisory words present
    advisory_text = "You should buy this fund immediately. Visit: https://groww.in/mutual-funds/icici-pru-liquid\nLast updated from sources: 2026-06-02"
    is_valid, errors = validator.validate(advisory_text)
    assert is_valid is False
    assert any("Advisory/opinionated language detected" in err for err in errors)


# -----------------------------------------------------------------------------
# FactualGenerator Tests
# -----------------------------------------------------------------------------

def test_generator_offline_mock_mode():
    """
    Asserts FactualGenerator functions properly in Offline Mock Mode when
    GROQ_API_KEY is not set or mock flag is active.
    """
    # Remove key temporarily if it exists to verify default mock fallback
    with patch.dict(os.environ, {}, clear=True):
        generator = FactualGenerator()
        
        context = [{
            "content": "The exit load of ICICI Liquid Fund is 0.0070% if redeemed within 1 day, and 0% thereafter. It is managed by Sharmila D'Silva.",
            "metadata": {
                "fund_name": "ICICI Prudential Liquid Fund Direct Plan Growth",
                "source_url": "https://groww.in/mutual-funds/icici-prudential-liquid-fund-direct-plan-growth",
                "last_scraped_date": "2026-06-02"
            }
        }]
        
        # 1. Query for Exit Load
        res = generator.generate("What is the exit load of the Liquid Fund?", context)
        assert "exit load" in res.lower()
        assert "https://groww.in/mutual-funds/icici-prudential-liquid-fund-direct-plan-growth" in res
        assert "Last updated from sources: 2026-06-02" in res
        
        # 2. Query for Manager
        res2 = generator.generate("Who is the manager?", context)
        assert "manager" in res2.lower() or "managed" in res2.lower()
        assert "Last updated from sources: 2026-06-02" in res2

def test_generator_validation_success_on_first_attempt():
    """
    Asserts that if Groq API outputs a fully compliant response, it returns immediately.
    """
    generator = FactualGenerator()
    context = [{
        "content": "The fund is run by Nikhil Kabra.",
        "metadata": {
            "source_url": "https://groww.in/mutual-funds/large-cap",
            "last_scraped_date": "2026-06-02"
        }
    }]
    
    mock_api_response = "The fund is run by Nikhil Kabra. For verified details, view: https://groww.in/mutual-funds/large-cap"
    
    with patch.dict(os.environ, {"GROQ_API_KEY": "mock-key"}):
        with patch.object(generator, "_call_groq_api", return_value=mock_api_response) as mock_call:
            res = generator.generate("Who is the manager?", context)
            assert mock_call.call_count == 1
            assert "Nikhil Kabra" in res
            assert "Last updated from sources: 2026-06-02" in res

def test_generator_validation_retry_and_recovery():
    """
    Asserts that generator executes retries if intermediate responses fail validation.
    """
    generator = FactualGenerator()
    context = [{
        "content": "The exit load is 1%.",
        "metadata": {
            "source_url": "https://groww.in/mutual-funds/flexicap",
            "last_scraped_date": "2026-06-02"
        }
    }]
    
    # Attempt 1: Too long (4 sentences)
    # Attempt 2: Compliant
    responses = [
        "First sentence. Second. Third. Fourth. View: https://groww.in/mutual-funds/flexicap",
        "The exit load is 1%. For verified metrics, view: https://groww.in/mutual-funds/flexicap"
    ]
    
    with patch.dict(os.environ, {"GROQ_API_KEY": "mock-key"}):
        with patch.object(generator, "_call_groq_api", side_effect=responses) as mock_call:
            res = generator.generate("What is the exit load?", context)
            assert mock_call.call_count == 2
            assert "1%" in res
            assert "Last updated from sources: 2026-06-02" in res

def test_generator_retry_exhaustion_fallback():
    """
    Asserts that if all 3 attempts fail validation, it returns the pre-configured safe static fallback.
    """
    generator = FactualGenerator()
    context = [{
        "content": "The exit load is 1%.",
        "metadata": {
            "source_url": "https://groww.in/mutual-funds/flexicap",
            "last_scraped_date": "2026-06-02"
        }
    }]
    
    # 3 responses that all violate constraints (e.g. by containing advisory text)
    responses = [
        "You should buy this fund. View: https://groww.in/mutual-funds/flexicap",
        "I recommend this scheme highly. View: https://groww.in/mutual-funds/flexicap",
        "This is the best investment opinion. View: https://groww.in/mutual-funds/flexicap"
    ]
    
    with patch.dict(os.environ, {"GROQ_API_KEY": "mock-key"}):
        with patch.object(generator, "_call_groq_api", side_effect=responses) as mock_call:
            res = generator.generate("What is the exit load?", context)
            assert mock_call.call_count == 3
            assert "unable to format a compliant response" in res
            assert "https://groww.in/mutual-funds/flexicap" in res
            assert "Last updated from sources: 2026-06-02" in res
