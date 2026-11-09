from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_sec_filings_tool,
    get_sec_filing_content_tool,
    get_sec_filing_evidence_tool,
    get_sec_filing_sections_tool,
    get_earnings_call_transcript_tool,
    get_instrument_context_from_state,
    get_language_instruction,
)


def create_fundamentals_analyst(llm):
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_fundamentals,
            get_balance_sheet,
            get_cashflow,
            get_income_statement,
            get_sec_filings_tool,
            get_sec_filing_content_tool,
            get_sec_filing_evidence_tool,
            get_sec_filing_sections_tool,
            get_earnings_call_transcript_tool,
        ]

        system_message = (
            "You are an equity research analyst producing a company detail report, not only a trade signal. Analyze the company's recent performance, financial fundamentals, management outlook, catalysts, risks, and forward-looking trajectory using the available evidence."
            + " Structure the final report with exactly these Markdown headings: Executive Summary, Recent Performance, Financial Fundamentals, Management Outlook, Catalysts, Risks, Forward-Looking Trajectory, Bull Case, Base Case, Bear Case, Data Limitations, and Sources."
            + " Distinguish reported financial facts from third-party Seeking Alpha metrics, grades, and analyst opinions. Treat Seeking Alpha as supplementary evidence, cite its source and date, and do not present its ratings as company disclosures. If sources disagree, describe the disagreement instead of inventing a reconciliation."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements. Use `get_sec_filings_tool` to list point-in-time SEC filings, `get_sec_filing_sections_tool` to extract labelled sections from a selected 10-K or 10-Q, and `get_sec_filing_evidence_tool` to inspect a selected filing as traceable evidence. Prefer 10-K Business, Risk Factors, MD&A, Liquidity and Capital Resources, and Financial Statements sections over a truncated filing prefix. Use `get_earnings_call_transcript_tool` for a specific fiscal quarter in YYYYQn format; distinguish management remarks and analyst Q&A from SEC filings and do not present transcript sentiment as a reported company fact. Do not use filings published after today's analysis date. Do not use transcript records published after today's analysis date when a publication date is available. Every material claim must identify source, filing/publication date, report period, and whether it is a reported fact, third-party opinion, management forecast, or your inference. If a required source is unavailable, state that explicitly under Data Limitations and do not invent a replacement."
            + get_language_instruction(),
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}."
                    " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}\n"
                    "{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
