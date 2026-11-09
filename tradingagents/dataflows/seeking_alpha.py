"""Seeking Alpha data fetched through the RapidAPI subscription."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_HOST = "seeking-alpha-api.p.rapidapi.com"
DEFAULT_METRIC_SLUGS = (
    "fnma,cnlc,cgm,cintr,cxahy,cdesp,chmc,cpags,cmfc,clmb,cgbdc,cezpw,"
    "cblbd,cstne,crdmc,cfro,ctnk,cbap,cparr,chtgc,casc,cvygr,cvtgn,"
    "ccnc,chiti,ckof,ctimb,cssrey,cvtsi,ccx,cexpe,cdnow,cslvm,cviv,carco"
)


def _request(path: str, params: dict[str, str] | None = None) -> dict:
    api_key = os.getenv("SEEKING_ALPHA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("SEEKING_ALPHA_API_KEY is not configured")
    host = os.getenv("SEEKING_ALPHA_API_HOST", DEFAULT_HOST).strip()
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"https://{host}{path}{query}",
        headers={
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": host,
            "Content-Type": "application/json",
        },
        method="GET",
    )
    with urlopen(request, timeout=30) as response:
        value = json.loads(response.read().decode("utf-8"))
    return value if isinstance(value, dict) else {"data": value}


@lru_cache(maxsize=128)
def resolve_seeking_alpha_id(ticker: str) -> str:
    """Resolve an exact Seeking Alpha symbol match through the Search API."""
    configured_id = os.getenv("SEEKING_ALPHA_SA_ID", "").strip()
    if configured_id:
        return configured_id

    normalized = ticker.strip().upper()
    result = _request("/search", {"query": ticker, "limit": "20"})
    symbols = result.get("search_result", {}).get("symbols", [])
    for symbol in symbols:
        if (
            isinstance(symbol, dict)
            and symbol.get("type") == "symbol"
            and str(symbol.get("slug", "")).upper() == normalized
            and symbol.get("id") is not None
        ):
            return str(symbol["id"])

    raise LookupError(
        f"No exact Seeking Alpha symbol match for {ticker!r}; "
        "refusing to select a different exchange listing"
    )


def _params(ticker: str) -> dict[str, str]:
    params = {
        "slugs": os.getenv("SEEKING_ALPHA_METRIC_SLUGS", DEFAULT_METRIC_SLUGS),
    }
    params["sa_id"] = resolve_seeking_alpha_id(ticker)
    return params


def get_seeking_alpha_metrics(ticker: str | None = None) -> dict:
    """Fetch the Metrics endpoint shown in the RapidAPI snippet."""
    return _request("/metrics", _params(ticker or ""))


def get_seeking_alpha_metrics_grades(ticker: str | None = None) -> dict:
    """Fetch the Metrics Grades endpoint shown in the RapidAPI snippet."""
    return _request("/metrics-grades", _params(ticker or ""))


def get_seeking_alpha_analyst_recommendation(ticker: str | None = None) -> dict:
    """Fetch Analyst Recommendation, optionally scoped by RapidAPI ``sa_id``."""
    sa_id = resolve_seeking_alpha_id(ticker or "")
    return _request("/analyst-recommendation", {"sa_id": sa_id} if sa_id else None)


def get_seeking_alpha_fundamentals(ticker: str, curr_date: str | None = None) -> str:
    """Return the three responses as labelled fundamental-analysis context."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    sections: list[str] = []
    for title, fetch in (
        ("Metrics", get_seeking_alpha_metrics),
        ("Metrics Grades", get_seeking_alpha_metrics_grades),
        ("Analyst Recommendation", get_seeking_alpha_analyst_recommendation),
    ):
        try:
            data = fetch(ticker)
        except Exception as exc:  # noqa: BLE001 - report optional-source failure
            data = {"unavailable": str(exc)}
        sections.extend(
            [
                f"## Seeking Alpha {title}",
                f"Ticker: {ticker}",
                f"Analysis date: {curr_date or 'not specified'}",
                f"Retrieved at: {retrieved_at}",
                json.dumps(data, ensure_ascii=False, indent=2),
                "",
            ]
        )
    return "\n".join(sections).rstrip()