import json
from unittest.mock import Mock, patch

import pytest

from tradingagents.dataflows import sec_edgar


@pytest.fixture(autouse=True)
def clear_sec_cache(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Course Student student@example.com")
    sec_edgar._ticker_map.cache_clear()
    yield
    sec_edgar._ticker_map.cache_clear()


def test_get_sec_filings_filters_by_analysis_date_and_form():
    ticker_response = Mock()
    ticker_response.json.return_value = {
        "0": {"ticker": "NVDA", "cik_str": 1045810}
    }
    ticker_response.raise_for_status.return_value = None

    submissions_response = Mock()
    submissions_response.json.return_value = {
        "cik": "0001045810",
        "filings": {
            "recent": {
                "accessionNumber": ["0001-1", "0002-2", "0003-3"],
                "filingDate": ["2026-01-10", "2026-09-01", "2026-10-01"],
                "reportDate": ["2025-12-31", "2026-06-30", "2026-09-30"],
                "form": ["10-K", "10-Q", "8-K"],
                "primaryDocument": ["annual.htm", "quarterly.htm", "current.htm"],
            }
        },
    }
    submissions_response.raise_for_status.return_value = None

    with patch.object(
        sec_edgar.requests,
        "get",
        side_effect=[ticker_response, submissions_response],
    ):
        result = json.loads(sec_edgar.get_sec_filings("NVDA", "2026-09-15"))

    assert [item["form"] for item in result["filings"]] == ["10-K", "10-Q"]
    assert result["filings"][1]["url"].endswith("/00022/quarterly.htm")


def test_sec_user_agent_is_required(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT")
    with pytest.raises(sec_edgar.SecEdgarNotConfiguredError):
        sec_edgar.resolve_cik("NVDA")


def test_filing_content_is_normalized_and_truncated():
    response = Mock()
    response.text = (
        "<html><head><style>ignore this</style></head><body>"
        "<h1>Item 1</h1><p>Revenue increased.</p>"
        "<script>ignore this too</script><p>Cash flow improved.</p>"
        "</body></html>"
    )
    response.raise_for_status.return_value = None

    with patch.object(sec_edgar.requests, "get", return_value=response):
        result = sec_edgar.get_sec_filing_content(
            "https://www.sec.gov/Archives/edgar/data/1/filing.htm"
        )

    assert "Item 1" in result
    assert "Revenue increased." in result
    assert "ignore this" not in result


def test_filing_content_ignores_inline_xbrl_hidden_metadata():
    html = (
        '<div style="display:none"><ix:header><ix:hidden>'
        "<ix:nonNumeric>hidden fact</ix:nonNumeric>"
        "</ix:hidden></ix:header></div>"
        "<div><h1>Item 1. Business</h1><p>NVIDIA develops accelerated computing.</p></div>"
    )
    response = Mock()
    response.text = html
    response.raise_for_status.return_value = None

    with patch.object(sec_edgar.requests, "get", return_value=response):
        result = sec_edgar.get_sec_filing_content(
            "https://www.sec.gov/Archives/edgar/data/1/filing.htm"
        )

    assert "hidden fact" not in result
    assert "Item 1. Business" in result
    assert "NVIDIA develops accelerated computing." in result


def test_filing_content_rejects_non_sec_url():
    with pytest.raises(ValueError, match="SEC filing URL"):
        sec_edgar.get_sec_filing_content("https://example.com/filing.htm")


def test_sec_filing_evidence_preserves_provenance():
    response = Mock()
    response.text = "<html><body><p>Revenue increased.</p></body></html>"
    response.raise_for_status.return_value = None
    filing = {
        "form": "10-Q",
        "filing_date": "2026-09-01",
        "report_date": "2026-06-30",
        "url": "https://www.sec.gov/Archives/edgar/data/1/q.htm",
    }

    with patch.object(sec_edgar.requests, "get", return_value=response):
        result = json.loads(sec_edgar.get_sec_filing_evidence("NVDA", filing))

    record = result["evidence"][0]
    assert record["source"] == "SEC EDGAR"
    assert record["claim_type"] == "reported_fact"
    assert record["published_at"] == "2026-09-01"
    assert record["report_period"] == "2026-06-30"
    assert record["url"] == filing["url"]


def test_filing_sections_skip_table_of_contents_and_extract_later_sections():
    html = (
        "<html><body>"
        "<p>ITEM 1. BUSINESS</p><p>Table of contents only.</p>"
        "<p>ITEM 1A. RISK FACTORS</p><p>TOC risk.</p>"
        "<div><h1>ITEM 1. BUSINESS</h1><p>Actual business section.</p>"
        "<h1>ITEM 1A. RISK FACTORS</h1><p>Actual risk section.</p>"
        "<h1>ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS</h1>"
        "<p>Actual MD&amp;A section.</p></div>"
        "</body></html>"
    )
    response = Mock()
    response.text = html
    response.raise_for_status.return_value = None

    with patch.object(sec_edgar.requests, "get", return_value=response):
        result = json.loads(
            sec_edgar.get_sec_filing_sections(
                "https://www.sec.gov/Archives/edgar/data/1/filing.htm",
                "10-K",
            )
        )

    assert result["available_sections"] == ["Business", "Risk Factors", "MD&A"]
    assert "Actual business section." in result["sections"]["Business"]
    assert "Table of contents only." not in result["sections"]["Business"]
    assert "Actual risk section." in result["sections"]["Risk Factors"]
    assert "Actual MD&A section." in result["sections"]["MD&A"]


def test_filing_sections_rejects_unsupported_form():
    with pytest.raises(ValueError, match="10-K.*10-Q"):
        sec_edgar.get_sec_filing_sections(
            "https://www.sec.gov/Archives/edgar/data/1/filing.htm",
            "8-K",
        )
