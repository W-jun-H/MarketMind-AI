"""Common evidence records passed between data sources and research agents."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceRecord:
    """A traceable fact, opinion, or forecast returned by a data source."""

    source: str
    evidence_type: str
    ticker: str
    published_at: str | None
    report_period: str | None
    claim_type: str
    content: str
    url: str | None = None
    retrieved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def format_evidence(records: list[EvidenceRecord]) -> str:
    """Serialize evidence records for an LLM while preserving provenance."""
    return json.dumps(
        {"evidence": [record.to_dict() for record in records]},
        ensure_ascii=False,
        indent=2,
    )


def sec_filing_evidence(
    ticker: str,
    filing: dict[str, Any],
    content: str,
    retrieved_at: str | None = None,
) -> EvidenceRecord:
    """Build a point-in-time evidence record from one SEC filing."""
    form = str(filing.get("form", "SEC filing"))
    return EvidenceRecord(
        source="SEC EDGAR",
        evidence_type=form,
        ticker=ticker,
        published_at=filing.get("filing_date"),
        report_period=filing.get("report_date"),
        claim_type="reported_fact",
        content=content,
        url=filing.get("url"),
        retrieved_at=retrieved_at,
    )
