import json
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.sec_edgar import (
    get_sec_filing_content,
    get_sec_filing_evidence,
    get_sec_filings,
    get_sec_filing_sections,
)


@tool
def get_sec_filings_tool(
    ticker: Annotated[str, "US stock ticker or SEC CIK"],
    analysis_date: Annotated[str, "Cutoff date in yyyy-mm-dd format"],
) -> str:
    """List SEC 10-K, 10-Q, and 8-K filings available by the cutoff date."""
    try:
        return get_sec_filings(ticker, analysis_date)
    except LookupError as exc:
        return json.dumps(
            {
                "source": "SEC EDGAR",
                "available": False,
                "ticker": ticker,
                "analysis_date": analysis_date,
                "reason": str(exc),
                "data_limitations": (
                    "SEC EDGAR ticker mapping is limited to SEC-registered "
                    "issuers and does not cover every exchange listing. "
                    "Use another fundamentals source for this instrument."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )


@tool
def get_sec_filing_content_tool(
    url: Annotated[str, "SEC Archives URL returned by get_sec_filings_tool"],
) -> str:
    """Retrieve the content of one SEC filing selected from the filing list."""
    return get_sec_filing_content(url)


@tool
def get_sec_filing_sections_tool(
    url: Annotated[str, "SEC Archives URL returned by get_sec_filings_tool"],
    form: Annotated[str, "SEC form: 10-K or 10-Q"],
) -> str:
    """Extract labelled sections from a 10-K or 10-Q filing."""
    return get_sec_filing_sections(url, form)


@tool
def get_sec_filing_evidence_tool(
    ticker: Annotated[str, "US stock ticker"],
    filing_json: Annotated[str, "One filing object copied from get_sec_filings_tool JSON"],
) -> str:
    """Retrieve one filing as a traceable evidence record."""
    import json

    filing = json.loads(filing_json)
    if not isinstance(filing, dict):
        raise ValueError("filing_json must decode to one filing object")
    return get_sec_filing_evidence(ticker, filing)
