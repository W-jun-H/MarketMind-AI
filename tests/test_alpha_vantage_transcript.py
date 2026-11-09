import json

import pytest

from tradingagents.dataflows import alpha_vantage_transcript as transcript


def _payload(symbol="NVDA", quarter="2025Q2", turns=None):
    return json.dumps(
        {
            "symbol": symbol,
            "quarter": quarter,
            "transcript": turns if turns is not None else [
                {
                    "speaker": "Jensen Huang",
                    "title": "CEO",
                    "content": "Prepared remarks.",
                    "sentiment": "0.7",
                }
            ],
        }
    )


def test_transcript_returns_provenance_and_speaker_turns(monkeypatch):
    calls = []
    monkeypatch.setattr(
        transcript,
        "_make_api_request",
        lambda function, params: calls.append((function, params)) or _payload(),
    )

    result = json.loads(
        transcript.get_earnings_call_transcript("nvda", "2025q2", "2026-11-02")
    )

    assert calls == [
        (
            "EARNINGS_CALL_TRANSCRIPT",
            {"symbol": "NVDA", "quarter": "2025Q2"},
        )
    ]
    assert result["source"] == "Alpha Vantage"
    assert result["evidence_type"] == "earnings_call_transcript"
    assert result["ticker"] == "NVDA"
    assert result["report_period"] == "2025Q2"
    assert result["analysis_date"] == "2026-11-02"
    assert result["transcript"][0]["speaker"] == "Jensen Huang"


@pytest.mark.parametrize("quarter", ["2025", "2025Q5", "Q1", "2025q"])
def test_transcript_rejects_invalid_quarter(monkeypatch, quarter):
    monkeypatch.setattr(
        transcript,
        "_make_api_request",
        lambda *_args, **_kwargs: pytest.fail("request should not be made"),
    )
    with pytest.raises(ValueError, match="quarter"):
        transcript.get_earnings_call_transcript("NVDA", quarter)


def test_transcript_rejects_identity_mismatch(monkeypatch):
    monkeypatch.setattr(
        transcript,
        "_make_api_request",
        lambda *_args, **_kwargs: _payload(symbol="AAPL"),
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        transcript.get_earnings_call_transcript("NVDA", "2025Q2")


def test_transcript_reports_missing_record(monkeypatch):
    monkeypatch.setattr(
        transcript,
        "_make_api_request",
        lambda *_args, **_kwargs: _payload(turns=[]),
    )
    with pytest.raises(LookupError, match="no earnings-call transcript"):
        transcript.get_earnings_call_transcript("NVDA", "2025Q2")
