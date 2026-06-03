import pytest
from src.ingestion.parser import ResilientParser, SemanticChunker, FundProfile, FundManager

# Mock HTML containing Next.js __NEXT_DATA__ script block
MOCK_NEXT_DATA_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Mock Mutual Fund Page</title>
</head>
<body>
    <h1>ICICI Prudential Liquid Fund Direct Plan Growth</h1>
    <script id="__NEXT_DATA__" type="application/json">
    {
        "props": {
            "pageProps": {
                "initialState": {
                    "fundDetail": {
                        "schemeName": "ICICI Prudential Liquid Fund Direct Growth",
                        "navValue": 345.67,
                        "fundSize": 14500.5,
                        "expenseRatio": "0.25%",
                        "exitLoad": {
                            "description": "0.1% if redeemed within 7 days"
                        },
                        "minSipAmount": 100,
                        "lockIn": "No Lock-in",
                        "riskCategory": "Low",
                        "benchmarkName": "NIFTY Liquid Index",
                        "investmentObjective": "To generate reasonable returns with high liquidity.",
                        "fundManagerDetails": [
                            {
                                "name": "Mr. Rahul Goswami",
                                "experience": "18 Years",
                                "tenure": "8 Years"
                            },
                            {
                                "name": "Mr. Rohan Maru",
                                "experience": "12 Years",
                                "tenure": "5 Years"
                            }
                        ]
                    }
                }
            }
        }
    }
    </script>
</body>
</html>
"""

# Mock HTML with no __NEXT_DATA__ (forcing BeautifulSoup fallback)
MOCK_FALLBACK_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>ICICI Prudential Value Discovery Fund Direct Growth Latest NAV</title>
</head>
<body>
    <h1>ICICI Prudential Value Discovery Fund Direct Growth</h1>
    <div>
        <div class="label">NAV</div>
        <div class="val">Rs. 245.50</div>
    </div>
    <div>
        <div class="label">Fund Size</div>
        <div class="val">Rs. 12,345.50 Cr</div>
    </div>
    <div>
        <div class="label">Expense Ratio</div>
        <div class="val">1.25%</div>
    </div>
    <div>
        <div class="label">Exit Load</div>
        <div class="val">1% if redeemed within 1 year</div>
    </div>
    <div>
        <div class="label">Minimum SIP</div>
        <div class="val">Rs. 500</div>
    </div>
    <div>
        <div class="label">Riskometer</div>
        <div class="val">Very High</div>
    </div>
    <div>
        <div class="label">Benchmark Index</div>
        <div class="val">NIFTY 500 TRI</div>
    </div>
    <h2>Investment Objective</h2>
    <p>To generate long term capital appreciation by investing in value stocks.</p>
    <h2>Fund Manager</h2>
    <p>Mr. Sankaran Naren</p>
</body>
</html>
"""

def test_next_data_parsing():
    """
    Test that the parser successfully extracts data from Next.js __NEXT_DATA__ block recursively.
    """
    parser = ResilientParser(source_url="https://groww.in/mock-fund")
    profile = parser.parse(MOCK_NEXT_DATA_HTML)
    
    assert profile.fund_name == "ICICI Prudential Liquid Fund Direct Growth"
    assert profile.nav == 345.67
    assert profile.fund_size == 14500.5
    assert profile.expense_ratio == 0.25
    assert profile.exit_load == "0.1% if redeemed within 7 days"
    assert profile.min_sip == 100.0
    assert profile.lock_in == "No Lock-in"
    assert profile.riskometer == "Low"
    assert profile.benchmark == "NIFTY Liquid Index"
    assert profile.objective == "To generate reasonable returns with high liquidity."
    
    assert len(profile.managers) == 2
    assert profile.managers[0].name == "Mr. Rahul Goswami"
    assert profile.managers[0].experience == "18 Years"
    assert profile.managers[0].tenure == "8 Years"

def test_fallback_parsing():
    """
    Test that the BeautifulSoup semantic fallback parser extracts core values when __NEXT_DATA__ is missing.
    """
    parser = ResilientParser(source_url="https://groww.in/fallback-fund")
    profile = parser.parse(MOCK_FALLBACK_HTML)
    
    assert "Value Discovery" in profile.fund_name
    assert profile.nav == 245.50
    assert profile.fund_size == 12345.5
    assert profile.expense_ratio == 1.25
    assert "1%" in profile.exit_load
    assert profile.min_sip == 500.0
    assert profile.riskometer == "Very High"
    assert profile.benchmark == "NIFTY 500 TRI"
    assert "value stocks" in profile.objective
    
    # Check that managers fallback extracted at least one name
    assert len(profile.managers) >= 1
    assert profile.managers[0].name == "Mr. Sankaran Naren"

# Mock HTML containing Next.js __NEXT_DATA__ with live Groww keys structure
MOCK_LIVE_GROWW_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Mock Live Mutual Fund Page</title>
</head>
<body>
    <h1>ICICI Prudential Liquid Fund Direct Plan Growth</h1>
    <script id="__NEXT_DATA__" type="application/json">
    {
        "props": {
            "pageProps": {
                "mfServerSideData": {
                    "scheme_name": "ICICI Prudential Liquid Fund Direct Plan Growth",
                    "nav": 412.3956,
                    "aum_amount": 8900.25,
                    "expense_ratio": 0.2,
                    "exit_load": "Exit load of 0.0070% if redeemed within 1 day...",
                    "min_sip_investment": 99,
                    "lock_in": {
                        "years": null,
                        "months": null,
                        "days": null
                    },
                    "nfo_risk": "Low",
                    "benchmark_name": "CRISIL Liquid Debt A-I Index",
                    "description": "The scheme seeks reasonable returns, commensurate with low risk levels while providing a high level of liquidity.",
                    "fund_manager_details": [
                        {
                            "person_name": "Sharmila D'Silva",
                            "experience": "She joined ICICI Prudential AMC Limited in September 2016.",
                            "date_from": "2022-06-30T18:30:00.000Z"
                        },
                        {
                            "person_name": "Darshil Dedhia",
                            "experience": "He has been working with ICICI Prudential Mutual Fund since 2013.",
                            "date_from": "2023-06-11T18:30:00.000Z"
                        }
                    ]
                }
            }
        }
    }
    </script>
</body>
</html>
"""

def test_live_groww_parsing():
    """
    Test that the parser successfully extracts data from Next.js payload with live Groww key conventions.
    """
    parser = ResilientParser(source_url="https://groww.in/live-fund")
    profile = parser.parse(MOCK_LIVE_GROWW_HTML)
    
    assert profile.fund_name == "ICICI Prudential Liquid Fund Direct Plan Growth"
    assert profile.nav == 412.3956
    assert profile.fund_size == 8900.25
    assert profile.expense_ratio == 0.2
    assert "0.0070%" in profile.exit_load
    assert profile.min_sip == 99.0
    assert profile.lock_in == "No Lock-in"
    assert profile.riskometer == "Low"
    assert profile.benchmark == "CRISIL Liquid Debt A-I Index"
    assert "reasonable returns" in profile.objective
    
    assert len(profile.managers) == 2
    assert profile.managers[0].name == "Sharmila D'Silva"
    assert "September 2016" in profile.managers[0].experience
    assert profile.managers[0].tenure == "Since June 2022"
    
    assert profile.managers[1].name == "Darshil Dedhia"
    assert "since 2013" in profile.managers[1].experience
    assert profile.managers[1].tenure == "Since June 2023"

# Mock HTML containing Next.js __NEXT_DATA__ with locked-in details
MOCK_LOCKED_IN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Mock Locked Mutual Fund Page</title>
</head>
<body>
    <h1>ICICI Prudential ELSS Tax Saver Direct Plan Growth</h1>
    <script id="__NEXT_DATA__" type="application/json">
    {
        "props": {
            "pageProps": {
                "mfServerSideData": {
                    "scheme_name": "ICICI Prudential ELSS Tax Saver Direct Plan Growth",
                    "lock_in": {
                        "years": 3,
                        "months": 0,
                        "days": 0
                    }
                }
            }
        }
    }
    </script>
</body>
</html>
"""

def test_locked_in_parsing():
    """
    Test that dictionary-based lock-in values are properly parsed and formatted.
    """
    parser = ResilientParser(source_url="https://groww.in/locked-fund")
    profile = parser.parse(MOCK_LOCKED_IN_HTML)
    
    assert profile.lock_in == "3 Year(s)"


def test_semantic_chunking():
    """
    Test that the SemanticChunker partitions the FundProfile into distinct semantic categories.
    """
    profile = FundProfile(
        fund_name="Test Fund",
        source_url="https://groww.in/test-fund",
        nav=100.0,
        fund_size=1250.0,
        expense_ratio=1.0,
        exit_load="No load",
        min_sip=500.0,
        lock_in="No Lock-in",
        riskometer="High",
        benchmark="Nifty 50",
        managers=[FundManager(name="Manager A", experience="10 yrs", tenure="3 yrs")],
        objective="To beat the market."
    )
    
    chunker = SemanticChunker()
    chunks = chunker.chunk(profile)
    
    assert len(chunks) == 3
    
    # Verify metadata categories
    categories = [c.metadata["data_type"] for c in chunks]
    assert "structure_numerical" in categories
    assert "text_description" in categories
    assert "fund_management" in categories
    
    # Assert tag structures
    for chunk in chunks:
        assert chunk.metadata["fund_name"] == "Test Fund"
        assert chunk.metadata["source_url"] == "https://groww.in/test-fund"
        assert "last_scraped_date" in chunk.metadata
