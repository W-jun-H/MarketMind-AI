import json
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.alpha_vantage_transcript import (
    get_earnings_call_transcript,
)


@tool
def get_earnings_call_transcript_tool(
    ticker: Annotated[str, "US stock ticker"],
    quarter: Annotated[str, "Fiscal quarter in YYYYQ1, YYYYQ2, YYYYQ3, or YYYYQ4 format"],
    curr_date: Annotated[str, "Analysis cutoff date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve a traceable Alpha Vantage earnings-call transcript."""
    try:
        return get_earnings_call_transcript(ticker, quarter, curr_date)
    except LookupError as exc:
        return json.dumps(
            {
                "source": "Alpha Vantage",
                "evidence_type": "earnings_call_transcript",
                "available": False,
                "ticker": ticker,
                "report_period": quarter,
                "analysis_date": curr_date or "not specified",
                "reason": str(exc),
                "data_limitations": (
                    "No transcript was published or available for the requested "
                    "ticker and fiscal quarter. Do not infer transcript content."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
