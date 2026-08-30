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

    question_lower = question.lower()
    matches = []

    for sector in KNOWN_SECTORS:
        if re.search(rf"\b{re.escape(sector.lower())}\b", question_lower):
            matches.append(sector)

    if len(matches) == 1:
        return matches[0]

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

    def tool_cross_reference(sector=None):
        result = cross_reference_deal_to_execution(
            deals_df,
            work_orders_df,
            sector=sector,
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
                        }
                    },
                    "required": ["sector"],
                },
            },
        },
    ]

    def ask(question):
        cross_reference = is_cross_reference_question(question)
        sector = detect_sector(question)

        if cross_reference and not sector:
            return (
                "Which sector should I compare? Available sectors are: Mining, Renewables, "
                "Railways, Powerline, Construction, and Others."
            )

        if cross_reference and sector:
            tool_choice = {
                "type": "function",
                "function": {"name": "cross_reference_deal_to_execution"},
            }
        else:
            tool_choice = "auto"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

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

            if name == "cross_reference_deal_to_execution":
                detected_sector = detect_sector(question)
                if detected_sector:
                    arguments["sector"] = detected_sector
                if not arguments.get("sector"):
                    raise ValueError("Cross-board comparison requires a sector.")

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

        final_response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            tool_choice="none",
            temperature=0,
        )

        final_message = final_response.choices[0].message
        content = final_message.content

        if content is not None and content.strip():
            return content

        if messages and messages[-1].get("role") == "tool":
            tool_payload = json.loads(messages[-1]["content"])
            result = tool_payload.get("result", tool_payload)
            sector = result.get("sector", "All sectors")
            pipeline = result.get("pipeline", {})
            execution = result.get("execution", {})
            comparison = result.get("comparison", {})

            return (
                f"{sector} sector comparison: "
                f"deal pipeline value is {pipeline.get('total_pipeline_value', 0):,.2f}, "
                f"while work-order value is {execution.get('total_order_value', 0):,.2f}. "
                f"This is a sector-level comparison, not a direct one-to-one deal-to-work-order match. "
                f"Current counts are {comparison.get('pipeline_deal_count', 0)} deals versus "
                f"{comparison.get('work_order_count', 0)} work orders. "
                "Data quality caveats still apply because missing values were not imputed."
            )

        return "I could not produce a reliable answer from the available business data."

    return ask
