"""SEC EDGAR filing metadata and document retrieval."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

from .errors import VendorNotConfiguredError
from .evidence import EvidenceRecord, format_evidence, sec_filing_evidence

SEC_BASE_URL = "https://data.sec.gov"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives"
REQUEST_TIMEOUT = 30
DEFAULT_FORMS = ("10-K", "10-Q", "8-K")
DEFAULT_CONTENT_CHAR_LIMIT = 24000
DEFAULT_SECTION_CHAR_LIMIT = 12000

_SECTION_PATTERNS = {
    "Business": r"ITEM\s+1\.?\s+BUSINESS\b",
    "Risk Factors": r"ITEM\s+1A\.?\s+RISK\s+FACTORS\b",
    "MD&A": r"ITEM\s+(?:2|7)\.?\s+MANAGEMENT['’]S\s+DISCUSSION\s+AND\s+ANALYSIS\b",
    "Liquidity and Capital Resources": (
        r"LIQUIDITY\s+AND\s+CAPITAL\s+RESOURCES\b"
    ),
    "Financial Statements": (
        r"ITEM\s+(?:8|1)\.?\s+FINANCIAL\s+STATEMENTS\b"
    ),
}
_SECTION_BOUNDARIES = {
    "Business": ("Risk Factors",),
    "Risk Factors": ("MD&A",),
    "MD&A": ("Financial Statements",),
    "Liquidity and Capital Resources": ("Financial Statements",),
    "Financial Statements": (),
}


class SecEdgarNotConfiguredError(VendorNotConfiguredError):
    """Raised when SEC requests cannot identify the client."""


def _user_agent() -> str:
    value = os.getenv("SEC_USER_AGENT", "").strip()
    if not value:
        raise SecEdgarNotConfiguredError(
            "SEC_USER_AGENT must be configured, for example "
            "'Student Name student@example.com'."
        )
    return value


def _get_json(url: str) -> dict:
    response = requests.get(
        url,
        headers={"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise ValueError(f"SEC returned an unexpected response for {url}")
    return value


@lru_cache(maxsize=1)
def _ticker_map() -> dict[str, str]:
    data = _get_json("https://www.sec.gov/files/company_tickers.json")
    result = {}
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker", "")).strip().upper()
        cik = entry.get("cik_str")
        if ticker and cik is not None:
            result[ticker] = str(cik).zfill(10)
    return result


def resolve_cik(ticker: str) -> str:
    """Resolve a US ticker to its SEC CIK."""
    normalized = ticker.strip().upper()
    if normalized.isdigit():
        return normalized.zfill(10)
    try:
        return _ticker_map()[normalized]
    except KeyError as exc:
        raise LookupError(f"SEC EDGAR has no ticker mapping for {ticker!r}") from exc


def _parse_analysis_date(analysis_date: str | None) -> date | None:
    if not analysis_date:
        return None
    try:
        return date.fromisoformat(analysis_date)
    except ValueError as exc:
        raise ValueError(
            f"analysis_date must use yyyy-mm-dd format, got {analysis_date!r}"
        ) from exc


def _filing_records(submissions: dict, analysis_date: date | None, forms: set[str]) -> list[dict]:
    recent = submissions.get("filings", {}).get("recent", {})
    records = []
    fields = ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument")
    for row in zip(*(recent.get(field, []) for field in fields)):
        accession, filing_date, report_date, form, primary_document = row
        if form not in forms:
            continue
        filed = date.fromisoformat(filing_date)
        if analysis_date and filed > analysis_date:
            continue
        accession_path = accession.replace("-", "")
        records.append(
            {
                "accession_number": accession,
                "filing_date": filing_date,
                "report_date": report_date,
                "form": form,
                "primary_document": primary_document,
                "url": urljoin(
                    SEC_ARCHIVES_URL + "/",
                    f"edgar/data/{int(submissions['cik'] or 0)}/{accession_path}/{primary_document}",
                ),
            }
        )
    return records


def get_sec_filings(
    ticker: str,
    analysis_date: str | None = None,
    forms: tuple[str, ...] = DEFAULT_FORMS,
    limit: int = 12,
) -> str:
    """Return point-in-time SEC filing metadata formatted for an LLM."""
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    cutoff = _parse_analysis_date(analysis_date)
    cik = resolve_cik(ticker)
    submissions = _get_json(f"{SEC_BASE_URL}/submissions/CIK{cik}.json")
    records = _filing_records(submissions, cutoff, set(forms))[:limit]
    payload = {
        "ticker": ticker,
        "cik": cik,
        "analysis_date": analysis_date or "not specified",
        "forms": list(forms),
        "filings": records,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def get_sec_filing_content(url: str) -> str:
    """Retrieve and normalize one SEC filing after the LLM selects its URL."""
    return _get_filing_text(url, DEFAULT_CONTENT_CHAR_LIMIT)


def get_sec_filing_sections(
    url: str,
    form: str,
    section_char_limit: int = DEFAULT_SECTION_CHAR_LIMIT,
) -> str:
    """Extract labelled 10-K/10-Q sections without treating a prefix as complete."""
    if form not in {"10-K", "10-Q"}:
        raise ValueError("form must be either '10-K' or '10-Q'")
    if section_char_limit <= 0:
        raise ValueError("section_char_limit must be greater than zero")

    text = _get_filing_text(url, None)
    sections = {}
    for name, pattern in _SECTION_PATTERNS.items():
        matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
        if not matches:
            continue
        start = matches[-1].start()
        following = [
            match.start()
            for boundary_name in _SECTION_BOUNDARIES[name]
            for match in re.finditer(
                _SECTION_PATTERNS[boundary_name], text, flags=re.IGNORECASE
            )
            if match.start() > start
        ]
        end = min(following) if following else len(text)
        section = text[start:end].strip()
        if len(section) > section_char_limit:
            section = (
                section[:section_char_limit].rsplit(" ", 1)[0]
                + "\n\n[SEC section truncated at the configured character limit.]"
            )
        sections[name] = section

    return json.dumps(
        {
            "source": "SEC EDGAR",
            "form": form,
            "url": url,
            "sections": sections,
            "available_sections": list(sections),
        },
        ensure_ascii=False,
        indent=2,
    )


def get_sec_filing_evidence(
    ticker: str,
    filing: dict,
    retrieved_at: str | None = None,
) -> str:
    """Retrieve one filing and return it as a provenance-preserving record."""
    content = get_sec_filing_content(str(filing.get("url", "")))
    record: EvidenceRecord = sec_filing_evidence(
        ticker=ticker,
        filing=filing,
        content=content,
        retrieved_at=retrieved_at,
    )
    return format_evidence([record])


def _get_filing_text(url: str, max_chars: int | None) -> str:
    if not url.startswith(SEC_ARCHIVES_URL + "/"):
        raise ValueError("SEC filing URL must point to www.sec.gov/Archives")
    response = requests.get(
        url,
        headers={"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    text = _html_to_text(response.text, max_chars)
    return text


class _FilingTextParser(HTMLParser):
    """Extract readable filing text while ignoring non-document HTML."""

    _IGNORED_TAGS = {
        "script",
        "style",
        "svg",
        "noscript",
        "ix:header",
        "ix:hidden",
    }
    _BLOCK_TAGS = {
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "p",
        "tr",
        "td",
        "th",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self._IGNORED_TAGS:
            self._ignored_stack.append(tag)
        elif self._is_hidden(attrs):
            self._ignored_stack.append(tag)
        elif not self._ignored_stack and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._ignored_stack and tag == self._ignored_stack[-1]:
            self._ignored_stack.pop()
        elif self._ignored_stack:
            return
        elif tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._ignored_stack:
            self.parts.append(data)

    @staticmethod
    def _is_hidden(attrs) -> bool:
        attributes = {name.lower(): (value or "").lower() for name, value in attrs}
        style = attributes.get("style", "").replace(" ", "")
        return (
            "hidden" in attributes
            or attributes.get("aria-hidden") == "true"
            or "display:none" in style
            or "visibility:hidden" in style
        )


def _html_to_text(html: str, max_chars: int | None) -> str:
    if max_chars is not None and max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")
    parser = _FilingTextParser()
    parser.feed(html)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    text = "\n".join(line for line in lines if line)
    if max_chars is None or len(text) <= max_chars:
        return text
    return (
        text[:max_chars].rsplit(" ", 1)[0]
        + "\n\n[SEC filing content truncated at the configured character limit.]"
    )
