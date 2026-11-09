"""Write compact, submission-ready company research reports."""

from datetime import datetime
from pathlib import Path
import re


_REPORT_SECTIONS = (
    "Executive Summary",
    "Recent Performance",
    "Financial Fundamentals",
    "Management Outlook",
    "Catalysts",
    "Risks",
    "Forward-Looking Trajectory",
    "Bull Case",
    "Base Case",
    "Bear Case",
    "Integrated Conclusion",
    "Data Limitations",
    "Sources",
)

_ALIASES = {
    "Executive Summary": ("Executive Summary", "执行摘要", "一、执行摘要"),
    "Recent Performance": ("Recent Performance", "近期表现", "最近表现"),
    "Financial Fundamentals": ("Financial Fundamentals", "Financial Fundamentals", "基本面"),
    "Management Outlook": ("Management Outlook", "管理层展望", "管理层观点"),
    "Catalysts": ("Catalysts", "催化剂", "上行催化剂"),
    "Risks": ("Risks", "风险", "下行风险"),
    "Forward-Looking Trajectory": (
        "Forward-Looking Trajectory",
        "前瞻走势",
        "前瞻性趋势",
    ),
    "Bull Case": ("Bull Case", "多头情景", "看多情景"),
    "Base Case": ("Base Case", "基准情景", "中性情景"),
    "Bear Case": ("Bear Case", "空头情景", "看空情景"),
    "Integrated Conclusion": ("Integrated Conclusion", "综合结论", "投资结论"),
    "Data Limitations": ("Data Limitations", "数据限制", "数据局限"),
    "Sources": ("Sources", "来源", "数据来源"),
}

# This keeps the markdown body within a practical ten-page submission budget
# while leaving room for headings, tables, and rendered line wrapping.
_SECTION_BUDGETS = {
    "Executive Summary": 2800,
    "Recent Performance": 2800,
    "Financial Fundamentals": 5200,
    "Management Outlook": 2800,
    "Catalysts": 2200,
    "Risks": 2800,
    "Forward-Looking Trajectory": 2600,
    "Bull Case": 1800,
    "Base Case": 1800,
    "Bear Case": 1800,
    "Integrated Conclusion": 3200,
    "Data Limitations": 1800,
    "Sources": 1800,
}


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def _extract_section(text: str, aliases: tuple[str, ...]) -> str:
    """Extract one markdown section from English or common Chinese headings."""
    if not text:
        return ""
    normalized_aliases = {
        re.sub(r"[\s:：]+$", "", alias).casefold() for alias in aliases
    }
    lines = text.splitlines()
    matches: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^\s*(#{1,6})\s*(.*?)\s*$", line)
        if not match:
            continue
        heading = re.sub(r"^\d+[.)、:：-]?\s*", "", match.group(2))
        heading = re.sub(r"[\s:：]+$", "", heading).casefold()
        if heading in normalized_aliases:
            matches.append((index, len(match.group(1))))
    if not matches:
        return ""
    start_line, heading_level = matches[-1]
    start_line += 1
    end_line = len(lines)
    for index in range(start_line, len(lines)):
        next_heading = re.match(r"^\s*(#{1,6})\s+\S", lines[index])
        if next_heading and len(next_heading.group(1)) <= heading_level:
            end_line = index
            break
    return "\n".join(lines[start_line:end_line]).strip()


def _first_nonempty(*values: str) -> str:
    return next((value.strip() for value in values if value and value.strip()), "")


def _trim(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    boundary = text.rfind("\n", 0, limit)
    if boundary < limit // 2:
        boundary = text.rfind(" ", 0, limit)
    boundary = boundary if boundary > 0 else limit
    return text[:boundary].rstrip() + "\n\n[Section shortened for the submission report.]"


def _portfolio_decision(final_state: dict) -> str:
    risk = final_state.get("risk_debate_state") or {}
    return _first_nonempty(
        _text(risk.get("judge_decision")),
        _text((final_state.get("investment_debate_state") or {}).get("judge_decision")),
    )


def _build_submission_sections(final_state: dict) -> dict[str, str]:
    fundamentals = _text(final_state.get("fundamentals_report"))
    market = _text(final_state.get("market_report"))
    transcript = _text(final_state.get("transcript_report"))
    manager = _text((final_state.get("investment_debate_state") or {}).get("judge_decision"))
    portfolio = _portfolio_decision(final_state)
    bull = _text((final_state.get("investment_debate_state") or {}).get("bull_history"))
    bear = _text((final_state.get("investment_debate_state") or {}).get("bear_history"))

    sections = {}
    for name in _REPORT_SECTIONS:
        sections[name] = _first_nonempty(
            _extract_section(fundamentals, _ALIASES[name]),
            _extract_section(transcript, _ALIASES[name]),
        )

    sections["Executive Summary"] = _first_nonempty(
        sections["Executive Summary"], _extract_section(portfolio, _ALIASES["Executive Summary"]),
        _extract_section(manager, _ALIASES["Executive Summary"]),
    )
    sections["Recent Performance"] = _first_nonempty(
        sections["Recent Performance"], _extract_section(market, _ALIASES["Recent Performance"]),
        market,
    )
    sections["Financial Fundamentals"] = _first_nonempty(
        sections["Financial Fundamentals"], fundamentals,
    )
    sections["Management Outlook"] = _first_nonempty(
        sections["Management Outlook"], transcript,
    )
    sections["Integrated Conclusion"] = _first_nonempty(
        sections["Integrated Conclusion"], portfolio, manager,
    )
    sections["Bull Case"] = _first_nonempty(sections["Bull Case"], bull)
    sections["Bear Case"] = _first_nonempty(sections["Bear Case"], bear)

    sections["Data Limitations"] = _first_nonempty(
        sections["Data Limitations"],
        "The report uses point-in-time data available by the analysis date. "
        "Missing or unavailable sources are not replaced with invented content.",
    )
    sections["Sources"] = _first_nonempty(
        sections["Sources"],
        "Sources are the Yahoo Finance market/fundamental tools, Seeking Alpha "
        "supplementary data when ticker validation succeeds, SEC EDGAR filings "
        "(10-K/10-Q), and Alpha Vantage earnings-call transcript records when available.",
    )
    return sections


def _write_agent_files(final_state: dict, save_path: Path) -> None:
    """Keep per-agent files available without inserting their full text in the deliverable."""
    analysts_dir = save_path / "1_analysts"
    analyst_values = (
        ("market.md", final_state.get("market_report")),
        ("sentiment.md", final_state.get("sentiment_report")),
        ("news.md", final_state.get("news_report")),
        ("fundamentals.md", final_state.get("fundamentals_report")),
    )
    for filename, value in analyst_values:
        if value:
            analysts_dir.mkdir(exist_ok=True)
            (analysts_dir / filename).write_text(_text(value), encoding="utf-8")

    debate = final_state.get("investment_debate_state") or {}
    research_dir = save_path / "2_research"
    for filename, value in (
        ("bull.md", debate.get("bull_history")),
        ("bear.md", debate.get("bear_history")),
        ("manager.md", debate.get("judge_decision")),
    ):
        if value:
            research_dir.mkdir(exist_ok=True)
            (research_dir / filename).write_text(_text(value), encoding="utf-8")

    if final_state.get("trader_investment_plan"):
        directory = save_path / "3_trading"
        directory.mkdir(exist_ok=True)
        (directory / "trader.md").write_text(
            _text(final_state["trader_investment_plan"]), encoding="utf-8"
        )

    risk = final_state.get("risk_debate_state") or {}
    risk_dir = save_path / "4_risk"
    for filename, key in (
        ("aggressive.md", "aggressive_history"),
        ("conservative.md", "conservative_history"),
        ("neutral.md", "neutral_history"),
        ("decision.md", "judge_decision"),
    ):
        if risk.get(key):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / filename).write_text(_text(risk[key]), encoding="utf-8")

    portfolio = risk.get("judge_decision")
    if portfolio:
        directory = save_path / "5_portfolio"
        directory.mkdir(exist_ok=True)
        (directory / "decision.md").write_text(_text(portfolio), encoding="utf-8")


def write_report_tree(final_state: dict, ticker: str, save_path) -> Path:
    """Write agent artifacts and a compact company report to ``save_path``."""
    save_path = Path(save_path)
    save_path.mkdir(parents=True, exist_ok=True)
    _write_agent_files(final_state, save_path)

    sections = _build_submission_sections(final_state)
    body = []
    for name in _REPORT_SECTIONS:
        body.append(f"## {name}\n\n{_trim(sections[name], _SECTION_BUDGETS[name])}")
    header = (
        f"# Trading Analysis Report: {ticker}\n\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    output = save_path / "complete_report.md"
    output.write_text(header + "\n\n".join(body), encoding="utf-8")
    return output
