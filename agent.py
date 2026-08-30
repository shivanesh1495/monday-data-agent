import json
import os
import re

from groq import Groq

from tools import (
    cross_reference_deal_to_execution,
    filter_deals,
    pipeline_summary,
    work_order_financials,
)

KNOWN_SECTORS = [
    "Mining",
    "Renewables",
    "Railways",
    "Powerline",
    "Construction",
    "Others",
]

SYSTEM_PROMPT = """
You are the Skylark Drones Business Intelligence Agent.

Your job is to answer founder-level business questions using live,
normalized monday.com data from the Work Order and Deal Funnel boards.

IMPORTANT RULES:

1. Never invent business numbers.

2. Never calculate business metrics yourself when a Python tool
   can perform the calculation. Use the appropriate tool.

3. Ask a clarifying question BEFORE calling a tool when any of
   these is materially ambiguous:
   - time window
   - sector
   - metric

4. Examples of ambiguity:
   - "How is the pipeline?" -> ask which time period or clarify
     that the user means the current/all available pipeline.
   - "How are we doing in energy?" -> ask which sector if
     "energy" could refer to multiple sectors.
   - "What is our revenue?" -> ask whether the user means
     deal value, billed value, collected amount, or receivables.

5. If the user clearly specifies the required dimension,
   do not ask an unnecessary clarification question.

6. Always surface data-quality caveats in the final answer.

7. Specifically mention:
   - important excluded records
   - missing fields that affected the calculation
   - imputed values, if any
   - whether a metric is based on incomplete data

8. Never silently treat missing values as zero unless the
   tool explicitly defines that behavior.

9. Distinguish:
   - deal value
   - active pipeline
   - billed value
   - collected amount
   - amount receivable
   - work-order value

10. Do not claim that a deal and work order are the same record
    unless a reliable identifier supports that relationship.

11. When comparing Deals and Work Orders by sector, clearly
    describe it as a sector-level comparison unless a direct
    record-level relationship exists.

12. Give concise founder-friendly answers:
    - headline
    - key numbers
    - interpretation
    - data-quality caveats

13. If the requested information cannot be supported by the
    available monday.com data, say so clearly.

Do not expose internal tool names or implementation details
unless the user asks about the architecture.
"""


def detect_sector(question):
    """
    Detect an exact known sector from the user question.
    Returns None if no unambiguous sector is present.
    """

    sectors = detect_sectors(question)
    return sectors[0] if len(sectors) == 1 else None


def detect_sectors(question):
    """Return every known sector mentioned in a message, in canonical form."""

    question_lower = question.lower()
    aliases = {"Renewables": ["renewables", "renewable"]}
    detected = []
    for sector in KNOWN_SECTORS:
        names = aliases.get(sector, [sector.lower()])
        if any(re.search(rf"\b{re.escape(name)}\b", question_lower) for name in names):
            detected.append(sector)
    return detected


def detect_time_window(question):
    """Extract a supported conversational time-window label, if present."""

    question_lower = question.lower().replace("-", " ")
    patterns = {
        "last_month": r"\blast\s+month\b|\bprevious\s+month\b",
        "this_month": r"\bthis\s+month\b|\bcurrent\s+month\b",
        "last_quarter": r"\blast\s+quarter\b|\bprevious\s+quarter\b",
        "this_quarter": r"\bthis\s+quarter\b|\bcurrent\s+quarter\b",
        "this_year": r"\bthis\s+year\b|\bcurrent\s+year\b",
        "last_year": r"\blast\s+year\b|\bprevious\s+year\b",
    }

    for label, pattern in patterns.items():
        if re.search(pattern, question_lower):
            return label

    return None


def is_cross_reference_question(question):
    q = question.lower()

    comparison_words = ["compare", "comparison", "versus", "vs", "against"]
    deal_words = ["deal", "pipeline"]
    execution_words = ["work order", "work-order", "execution"]

    has_comparison = any(word in q for word in comparison_words)
    has_deal = any(word in q for word in deal_words)
    has_execution = any(word in q for word in execution_words)

    return has_comparison and has_deal and has_execution


def is_metric_ambiguity(question):
    question_lower = question.lower()
    return "revenue" in question_lower and not any(
        term in question_lower
        for term in ["deal value", "billed", "collected", "receivable"]
    )


def format_cross_reference_result(payloads, time_window=None):
    """Format deterministic cross-reference results without inventing values."""

    lines = ["Sector comparison"]
    if time_window:
        lines.append(
            f"Requested time window: {time_window.replace('_', ' ')}. "
            "Historical time filtering is not available in the current board tools, "
            "so the figures below reflect the current normalized board state."
        )

    for payload in payloads:
        result = payload["result"]
        sector = result["sector"]
        pipeline = result["pipeline"]
        execution = result["execution"]
        lines.extend(
            [
                "",
                f"{sector}",
                f"- Deal pipeline: {pipeline['total_deal_value']:,.2f} ({pipeline['deal_count']} deals)",
                f"- Work-order execution: {execution['total_order_value']:,.2f} ({execution['work_order_count']} work orders)",
            ]
        )

    lines.extend(
        [
            "",
            "Data quality: missing values were not imputed; see the underlying board fields for any incomplete records.",
            "This is a sector-level comparison, not a direct one-to-one deal-to-work-order match.",
        ]
    )
    return "\n".join(lines)


def detect_direct_business_question(question):
    """Return a deterministic BI instruction for common direct questions."""
    q = question.lower()
    if is_cross_reference_question(question):
        return None

    if re.search(r"\bcompare\b|\bcomparison\b|\bversus\b|\bvs\b|\bagainst\b", q):
        return None

    sector = detect_sector(question)

    pipeline_keywords = [
        "deal pipeline",
        "pipeline",
        "deal value",
        "deal volume",
        "deal summary",
    ]
    execution_keywords = [
        "work order",
        "work-order",
        "work order execution",
        "execution value",
        "work order value",
    ]

    if any(keyword in q for keyword in execution_keywords):
        return {"kind": "work_order", "sector": sector}

    if any(keyword in q for keyword in pipeline_keywords):
        return {"kind": "pipeline", "sector": sector}

    return None


def format_direct_business_result(kind, sector, summary, time_window=None):
    """Render a concise deterministic result for a single-sector BI question."""
    time_window_note = ""
    if time_window:
        time_window_note = (
            f"Requested time window: {time_window.replace('_', ' ')}. "
            "Historical time filtering is not available in the current board tools, "
            "so the figures below reflect the current normalized board state.\n"
        )

    if kind == "pipeline":
        data = summary["result"]
        return (
            f"{sector or 'All sectors'} deal pipeline\n"
            f"{time_window_note}"
            f"- Deals: {data['deal_count']}\n"
            f"- Total deal value: {data['total_deal_value']:,.2f}\n"
            f"- Open deals: {data['open_deals']}\n"
            f"- Won value: {data['won_value']:,.2f}\n"
            f"- On-hold value: {data['on_hold_value']:,.2f}\n"
            f"- Dead value: {data['dead_value']:,.2f}\n"
            "Data quality: missing values were not imputed; incomplete board fields may affect totals."
        )

    data = summary["result"]
    return (
        f"{sector or 'All sectors'} work-order execution\n"
        f"{time_window_note}"
        f"- Work orders: {data['work_order_count']}\n"
        f"- Total order value: {data['total_order_value']:,.2f}\n"
        f"- Billed value: {data['billed_value']:,.2f}\n"
        f"- Collected amount: {data['collected_amount']:,.2f}\n"
        f"- Amount to be billed: {data['amount_to_be_billed']:,.2f}\n"
        f"- Amount receivable: {data['amount_receivable']:,.2f}\n"
        "Data quality: missing values were not imputed; incomplete board fields may affect totals."
    )


def compact_quality_summary(summary):
    """
    Reduce quality information size for Groq context.
    Only include row count and fields with missing values.
    """
    if not summary:
        return {}

    missing = summary.get("missing_values", {})

    important = {
        column: count
        for column, count in missing.items()
        if count > 0
    }

    return {
        "row_count": summary.get("row_count"),
        "important_missing_fields": important
    }


def create_agent(
    deals_df,
    work_orders_df,
    work_order_quality=None,
    deal_quality=None,
):
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing")

    client = Groq(api_key=api_key)

    quality_context = {
        "work_orders": compact_quality_summary(work_order_quality),
        "deals": compact_quality_summary(deal_quality),
    }

    def tool_filter_deals(sector=None, status=None, stage=None, owner=None):
        result = filter_deals(
            deals_df,
            sector=sector,
            status=status,
            stage=stage,
            owner=owner,
        )

        return {
            "row_count": len(result),
            "columns": list(result.columns),
            "sample": result.head(10).to_dict(orient="records"),
            "quality": quality_context["deals"],
        }

    def tool_pipeline_summary(sector=None):
        result = pipeline_summary(deals_df, sector=sector)
        return {"result": result, "quality": quality_context["deals"]}

    def tool_work_order_financials(sector=None):
        result = work_order_financials(work_orders_df, sector=sector)
        return {"result": result, "quality": quality_context["work_orders"]}

    def tool_cross_reference(sector=None, time_window=None):
        result = cross_reference_deal_to_execution(
            deals_df,
            work_orders_df,
            sector=sector,
            time_window=time_window,
        )
        return {
            "result": result,
            "quality": {
                "deals": quality_context["deals"],
                "work_orders": quality_context["work_orders"],
            },
        }

    functions = {
        "filter_deals": tool_filter_deals,
        "pipeline_summary": tool_pipeline_summary,
        "work_order_financials": tool_work_order_financials,
        "cross_reference_deal_to_execution": tool_cross_reference,
    }

    tools = [
        {
            "type": "function",
            "function": {
                "name": "filter_deals",
                "description": (
                    "Filter deals by sector, deal status, deal stage, or owner."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sector": {"type": "string", "description": "Sector/service filter."},
                        "status": {"type": "string", "description": "Deal status filter."},
                        "stage": {"type": "string", "description": "Deal stage filter."},
                        "owner": {"type": "string", "description": "Owner code filter."},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "pipeline_summary",
                "description": (
                    "Calculate deal count, deal value, open, won, dead and on-hold deal counts. "
                    "Can optionally be restricted to a sector."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"sector": {"type": "string", "description": "Optional sector."}},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "work_order_financials",
                "description": (
                    "Calculate work-order count, order value, billed value, collected amount, "
                    "amount to be billed and receivables."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"sector": {"type": "string", "description": "Optional sector."}},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "cross_reference_deal_to_execution",
                "description": (
                    "Compare deal pipeline and work-order execution for ONE SPECIFIC SECTOR. "
                    "The sector argument is mandatory."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sector": {
                            "type": "string",
                            "description": (
                                "Required sector name, such as Mining, Renewables, Railways, "
                                "Powerline, Construction, or Others."
                            ),
                        },
                        "time_window": {
                            "type": "string",
                            "description": "Requested period label, such as last_month."
                        },
                    },
                    "required": ["sector"],
                },
            },
        },
    ]

    def empty_conversation_state():
        return {
            "task": None,
            "sectors": [],
            "comparison": None,
            "metric": None,
            "time_window": None,
            "awaiting": None,
            "last_completed_task": None,
        }

    conversation_state = empty_conversation_state()

    def reset_active_task():
        completed = conversation_state.get("last_completed_task")
        conversation_state.clear()
        conversation_state.update(empty_conversation_state())
        conversation_state["last_completed_task"] = completed

    def remember_active_context(sectors=None, time_window=None):
        for sector in sectors or []:
            if sector not in conversation_state["sectors"]:
                conversation_state["sectors"].append(sector)

        if time_window:
            conversation_state["time_window"] = time_window
            conversation_state["awaiting"] = None

    def start_cross_reference_task(sectors=None, time_window=None):
        reset_active_task()
        conversation_state["task"] = "cross_reference"
        conversation_state["comparison"] = "deal pipeline vs work-order execution"
        conversation_state["metric"] = conversation_state["comparison"]
        remember_active_context(sectors=sectors, time_window=time_window)

    def start_direct_task(kind, sectors=None, time_window=None):
        reset_active_task()
        conversation_state["task"] = kind
        conversation_state["metric"] = kind
        remember_active_context(sectors=sectors, time_window=time_window)

    def finish_active_task():
        conversation_state["last_completed_task"] = {
            "task": conversation_state["task"],
            "sectors": list(conversation_state["sectors"]),
            "comparison": conversation_state["comparison"],
            "metric": conversation_state["metric"],
            "time_window": conversation_state["time_window"],
        }
        reset_active_task()

    def run_cross_reference_task():
        payloads = [
            tool_cross_reference(
                sector=sector,
                time_window=conversation_state["time_window"],
            )
            for sector in conversation_state["sectors"]
        ]
        answer = format_cross_reference_result(
            payloads,
            conversation_state["time_window"],
        )
        finish_active_task()
        return answer

    def run_direct_task():
        sector = conversation_state["sectors"][0] if conversation_state["sectors"] else None

        if conversation_state["task"] == "pipeline":
            summary = tool_pipeline_summary(sector=sector)
        else:
            summary = tool_work_order_financials(sector=sector)

        answer = format_direct_business_result(
            conversation_state["task"],
            sector,
            summary,
            time_window=conversation_state["time_window"],
        )
        finish_active_task()
        return answer

    def ask(question):
        question_lower = question.lower()
        current_sectors = detect_sectors(question)
        time_window = detect_time_window(question)

        direct_question = detect_direct_business_question(question)
        if direct_question:
            start_direct_task(
                direct_question["kind"],
                sectors=current_sectors,
                time_window=time_window,
            )

        if is_cross_reference_question(question):
            start_cross_reference_task(
                sectors=current_sectors,
                time_window=time_window,
            )
        elif conversation_state["task"] in {"pipeline", "work_order", "cross_reference"}:
            remember_active_context(
                sectors=current_sectors,
                time_window=time_window,
            )

        if is_metric_ambiguity(question):
            conversation_state["awaiting"] = "metric"
            return (
                "Which metric do you mean: deal value, billed, collected, "
                "or receivable?"
            )

        if conversation_state["task"] in {"pipeline", "work_order"}:
            if not conversation_state["sectors"]:
                conversation_state["awaiting"] = "sector"
                return (
                    "Which sector should I use? Available sectors are: Mining, Renewables, "
                    "Railways, Powerline, Construction, and Others."
                )

            conversation_state["awaiting"] = None
            return run_direct_task()

        if conversation_state["task"] == "cross_reference":
            if re.search(r"\ball\s+sectors?\b", question_lower):
                conversation_state["awaiting"] = "sector"
                return (
                    "I can compare sectors individually. Which sectors would you like me "
                    "to compare? Available sectors are: Mining, Renewables, Railways, "
                    "Powerline, Construction, and Others."
                )

            if not conversation_state["sectors"] and not current_sectors:
                conversation_state["awaiting"] = "sector"
                return (
                    "Which sector should I compare? Available sectors are: Mining, Renewables, "
                    "Railways, Powerline, Construction, and Others."
                )

            if len(conversation_state["sectors"]) > 1 and not conversation_state["time_window"]:
                conversation_state["awaiting"] = None
                return run_cross_reference_task()

            if len(conversation_state["sectors"]) == 1 and not conversation_state["time_window"]:
                conversation_state["awaiting"] = "time_window"
                return "What time period should I use?"

            if conversation_state["awaiting"] == "time_window" and not conversation_state["time_window"]:
                return "What time period should I use?"

            conversation_state["awaiting"] = None
            return run_cross_reference_task()

        tool_choice = "auto"

        context_lines = []
        if conversation_state["task"]:
            context_lines.append(f"Active task: {conversation_state['task']}")
        if conversation_state["sectors"]:
            context_lines.append(
                "Remembered sectors: " + ", ".join(conversation_state["sectors"])
            )
        if conversation_state["time_window"]:
            context_lines.append(
                "Remembered time window: "
                + conversation_state["time_window"].replace("_", " ")
            )
        if conversation_state["awaiting"]:
            context_lines.append(
                f"Outstanding clarification: {conversation_state['awaiting']}"
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        if context_lines:
            messages.append(
                {
                    "role": "system",
                    "content": "Conversation context:\n" + "\n".join(context_lines),
                }
            )

        messages.append({"role": "user", "content": question})

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=0,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content

        messages.append(message)

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            if name not in functions:
                raise ValueError(f"Unknown tool requested: {name}")

            result = functions[name](**arguments)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": json.dumps(result, default=str),
                }
            )

        try:
            final_response = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=messages,
                temperature=0,
            )

            final_message = final_response.choices[0].message
            content = final_message.content

            if content is not None and content.strip():
                return content
        except Exception:
            pass

        if messages and messages[-1].get("role") == "tool":
            tool_payload = json.loads(messages[-1]["content"])
            result = tool_payload.get("result", tool_payload)
            sector = result.get("sector", "All sectors")
            pipeline = result.get("pipeline", {})
            execution = result.get("execution", {})
            comparison = result.get("comparison", {})

            return (
                f"{sector} sector comparison: "
                f"deal pipeline value is {pipeline.get('total_deal_value', 0):,.2f}, "
                f"while work-order value is {execution.get('total_order_value', 0):,.2f}. "
                f"This is a sector-level comparison, not a direct one-to-one deal-to-work-order match. "
                f"Current counts are {comparison.get('pipeline_deal_count', 0)} deals versus "
                f"{comparison.get('work_order_count', 0)} work orders. "
                "Data quality caveats still apply because missing values were not imputed."
            )

        return "I could not produce a reliable answer from the available business data."

    return ask
