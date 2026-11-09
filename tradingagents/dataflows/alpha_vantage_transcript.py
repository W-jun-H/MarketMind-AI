"""Alpha Vantage earnings-call transcript retrieval."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from .alpha_vantage_common import _make_api_request

_QUARTER_PATTERN = re.compile(r"^\d{4}Q[1-4]$")


def get_earnings_call_transcript(
    ticker: str,
    quarter: str,
    curr_date: str | None = None,
) -> str:
    """Return a provenance-labelled transcript for one fiscal quarter.

    Alpha Vantage identifies transcript records by ticker and ``YYYYQn``
    quarter. The response is kept as structured JSON so speaker turns and
    sentiment are not flattened before the analyst receives them.
    """
    normalized_ticker = ticker.strip().upper()
    normalized_quarter = quarter.strip().upper()
    if not normalized_ticker:
        raise ValueError("ticker must not be empty")
    if not _QUARTER_PATTERN.fullmatch(normalized_quarter):
        raise ValueError("quarter must use YYYYQ1, YYYYQ2, YYYYQ3, or YYYYQ4 format")

    raw = _make_api_request(
        "EARNINGS_CALL_TRANSCRIPT",
        {"symbol": normalized_ticker, "quarter": normalized_quarter},
    )
    if not isinstance(raw, str):
        raise ValueError("Alpha Vantage returned an unexpected transcript response")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Alpha Vantage returned non-JSON transcript data") from exc
    if not isinstance(payload, dict):
        raise ValueError("Alpha Vantage returned an unexpected transcript payload")

    returned_symbol = str(payload.get("symbol", "")).strip().upper()
    returned_quarter = str(payload.get("quarter", "")).strip().upper()
    if returned_symbol != normalized_ticker or returned_quarter != normalized_quarter:
        raise ValueError(
            "Alpha Vantage transcript identity mismatch: "
            f"requested {normalized_ticker} {normalized_quarter}, "
            f"received {returned_symbol or 'unknown'} {returned_quarter or 'unknown'}"
        )

    transcript = payload.get("transcript")
    if not isinstance(transcript, list) or not transcript:
        raise LookupError(
            f"Alpha Vantage has no earnings-call transcript for "
            f"{normalized_ticker} {normalized_quarter}"
        )

    return json.dumps(
        {
            "source": "Alpha Vantage",
            "evidence_type": "earnings_call_transcript",
            "ticker": normalized_ticker,
            "published_at": None,
            "report_period": normalized_quarter,
            "analysis_date": curr_date or "not specified",
            "claim_type": "management_remarks_and_analyst_qa",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "source_url": "https://www.alphavantage.co/documentation/",
            "transcript": transcript,
        },
        ensure_ascii=False,
        indent=2,
    )
