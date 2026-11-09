"""Unit tests for the RapidAPI Seeking Alpha fundamental context."""

from unittest.mock import patch

from tradingagents.dataflows import seeking_alpha


def test_metrics_and_grades_use_documented_paths_and_slugs(monkeypatch):
    monkeypatch.setenv("SEEKING_ALPHA_API_KEY", "test-key")
    calls = []

    def fake_request(path, params=None):
        calls.append((path, params))
        if path == "/search":
            return {
                "search_result": {
                    "symbols": [
                        {"id": 1150, "type": "symbol", "slug": "nvda"},
                    ]
                }
            }
        return {"path": path}

    with patch.object(seeking_alpha, "_request", side_effect=fake_request):
        seeking_alpha.get_seeking_alpha_metrics("NVDA")
        seeking_alpha.get_seeking_alpha_metrics_grades("NVDA")

    assert calls[1][0] == "/metrics"
    assert calls[2][0] == "/metrics-grades"
    assert calls[1][1]["slugs"]
    assert calls[2][1]["slugs"] == calls[1][1]["slugs"]
    assert calls[1][1]["sa_id"] == "1150"


def test_search_resolves_exact_symbol_and_rejects_other_listing(monkeypatch):
    monkeypatch.delenv("SEEKING_ALPHA_SA_ID", raising=False)
    seeking_alpha.resolve_seeking_alpha_id.cache_clear()
    result = {
        "search_result": {
            "symbols": [
                {"id": 1150, "type": "symbol", "slug": "nvda", "content": "NVIDIA Corporation"},
                {"id": 764532, "type": "symbol", "slug": "nvda:ca", "content": "NVIDIA Corporation"},
            ]
        }
    }
    with patch.object(seeking_alpha, "_request", return_value=result) as request:
        assert seeking_alpha.resolve_seeking_alpha_id("NVDA") == "1150"

    request.assert_called_once_with("/search", {"query": "NVDA", "limit": "20"})


def test_analyst_recommendation_uses_documented_path(monkeypatch):
    monkeypatch.setenv("SEEKING_ALPHA_API_KEY", "test-key")
    with patch.object(seeking_alpha, "_request", return_value={"rating": "buy"}) as request:
        result = seeking_alpha.get_seeking_alpha_analyst_recommendation("NVDA")

    request.assert_called_once_with("/analyst-recommendation", {"sa_id": "1150"})
    assert result["rating"] == "buy"


def test_report_contains_all_three_sections(monkeypatch):
    monkeypatch.setenv("SEEKING_ALPHA_API_KEY", "test-key")
    with patch.object(seeking_alpha, "_request", return_value={"ok": True}):
        report = seeking_alpha.get_seeking_alpha_fundamentals("NVDA", "2026-09-11")

    assert "## Seeking Alpha Metrics" in report
    assert "## Seeking Alpha Metrics Grades" in report
    assert "## Seeking Alpha Analyst Recommendation" in report
    assert "Ticker: NVDA" in report


def test_missing_key_is_reported_without_crashing_report(monkeypatch):
    monkeypatch.delenv("SEEKING_ALPHA_API_KEY", raising=False)
    report = seeking_alpha.get_seeking_alpha_fundamentals("NVDA", "2026-09-11")

    assert "SEEKING_ALPHA_API_KEY is not configured" in report