from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage

from tradingagents.agents.analysts.fundamentals_analyst import (
    create_fundamentals_analyst,
)


def test_fundamentals_analyst_exposes_course_data_tools_and_constraints():
    bound_chain = MagicMock()
    response = MagicMock(
        tool_calls=[],
        content="## Executive Summary\nEvidence-based report.",
    )
    bound_chain.return_value = response
    llm = MagicMock()
    llm.bind_tools.return_value = bound_chain

    analyst = create_fundamentals_analyst(llm)
    result = analyst(
        {
            "company_of_interest": "NVDA",
            "trade_date": "2026-10-18",
            "messages": [HumanMessage(content="Analyze NVDA.")],
        }
    )

    llm.bind_tools.assert_called_once()
    tools = llm.bind_tools.call_args.args[0]
    tool_names = {tool.name for tool in tools}
    assert {
        "get_fundamentals",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
        "get_sec_filings_tool",
        "get_sec_filing_content_tool",
        "get_sec_filing_evidence_tool",
        "get_earnings_call_transcript_tool",
        "get_sec_filing_sections_tool",
    } <= tool_names

    prompt = bound_chain.call_args.args[0]
    rendered = "\n".join(message.content for message in prompt.messages)
    assert "2026-10-18" in rendered
    assert "Do not use filings published after today's analysis date" in rendered
    assert "Data Limitations" in rendered
    assert "Forward-Looking Trajectory" in rendered
    assert "get_earnings_call_transcript_tool" in rendered
    assert result["fundamentals_report"].startswith("## Executive Summary")


def test_fundamentals_analyst_returns_empty_report_while_tool_call_is_pending():
    bound_chain = MagicMock()
    bound_chain.return_value = MagicMock(
        tool_calls=[{"name": "get_sec_filings_tool"}],
        content="",
    )
    llm = MagicMock()
    llm.bind_tools.return_value = bound_chain

    result = create_fundamentals_analyst(llm)(
        {
            "company_of_interest": "NVDA",
            "trade_date": "2026-10-18",
            "messages": [HumanMessage(content="Analyze NVDA.")],
        }
    )

    assert result["fundamentals_report"] == ""
    assert result["messages"][0].tool_calls
