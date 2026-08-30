import json
import os
import re

from groq import Groq

from tools import (
    active_pipeline_by_owner,
    average_deal_size,
    billing_status_missing_fraction,
    closing_cycle_time,
    cross_board_execution_gaps,
    cross_reference_deal_to_execution,
    detect_data_entry_errors,
    filter_deals,
    pipeline_summary,
    receivable_anomalies,
    win_rate_by_sector,
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

METRIC_DEFINITIONS = {
    "win_rate": {
        "aliases": ["win rate", "conversion", "conversion rate", "close rate"],
        "domain": "pipeline",
        "label": "Win rate",
        "format": "percent",
    },
    "total_deal_value": {
        "aliases": ["deal value", "pipeline value", "deal pipeline", "pipeline"],
        "domain": "pipeline",
        "label": "Total deal value",
        "format": "money",
    },
    "active_pipeline_value": {
        "aliases": ["active pipeline", "open pipeline", "pipeline health"],
        "domain": "pipeline",
        "label": "Active pipeline value",
        "format": "money",
    },
    "won_value": {
        "aliases": ["won value", "won deals", "booked deals"],
        "domain": "pipeline",
        "label": "Won value",
        "format": "money",
    },
    "dead_value": {
        "aliases": ["dead value", "lost deals", "dropped deals"],
        "domain": "pipeline",
        "label": "Dead value",
        "format": "money",
    },
    "on_hold_value": {
        "aliases": ["on hold", "on-hold"],
        "domain": "pipeline",
        "label": "On-hold value",
        "format": "money",
    },
    "total_order_value": {
        "aliases": ["order book", "work order value", "execution value", "total order value"],
        "domain": "work_order",
        "label": "Total order value",
        "format": "money",
    },
    "billed_value": {
        "aliases": ["billed", "billing", "billed value", "invoiced"],
        "domain": "work_order",
        "label": "Billed value",
        "format": "money",
    },
    "collected_amount": {
        "aliases": ["collected", "collections", "cash collected", "receipts"],
        "domain": "work_order",
        "label": "Collected amount",
        "format": "money",
    },
    "amount_receivable": {
        "aliases": ["receivable", "receivables", "outstanding"],
        "domain": "work_order",
        "label": "Amount receivable",
        "format": "money",
    },
    "amount_to_be_billed": {
        "aliases": ["to be billed", "unbilled", "pending billing"],
        "domain": "work_order",
        "label": "Amount to be billed",
        "format": "money",
    },
    "work_order_count": {
        "aliases": ["work order count", "work orders", "execution count"],
        "domain": "work_order",
        "label": "Work orders",
        "format": "count",
    },
}

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


def detect_metric(question):
    """Extract a known metric from the user question."""

    question_lower = question.lower()
    for metric, config in METRIC_DEFINITIONS.items():
        if any(alias in question_lower for alias in config["aliases"]):
            return metric

    return None


def metric_definition(metric):
    return METRIC_DEFINITIONS.get(metric)


def is_all_sectors_question(question):
    return bool(re.search(r"\ball\s+sectors?\b", question.lower()))


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


def is_sector_metric_comparison_question(question):
    q = question.lower()
    has_comparison = bool(re.search(r"\bcompare\b|\bcomparison\b|\bversus\b|\bvs\b|\bagainst\b", q))
    return has_comparison and len(detect_sectors(question)) >= 2 and not is_cross_reference_question(question)


def format_metric_value(value, kind):
    if kind == "percent":
        return f"{value:.1f}%"
    if kind == "count":
        return str(int(value))
    return f"{value:,.2f}"


def metric_value_from_summary(metric, summary):
    data = summary["result"]

    if metric == "win_rate":
        deal_count = data.get("deal_count", 0)
        won_deals = data.get("won_deals", 0)
        return ((won_deals / deal_count) * 100) if deal_count else 0.0

    return float(data.get(metric, 0))


def format_time_filter_note(time_filter):
    if not time_filter or not time_filter.get("requested_time_window"):
        return None

    requested = time_filter["requested_time_window"].replace("_", " ")
    if not time_filter.get("time_window_applied"):
        return f"Requested time window: {requested}. The current tool could not apply a historical filter."

    basis = ", ".join(time_filter.get("date_basis", [])) or "available date fields"
    start = time_filter.get("window_start")
    end = time_filter.get("window_end")
    missing_rows = time_filter.get("excluded_missing_date_rows", 0)

    note = f"Requested time window: {requested} ({start} to {end}) using {basis}."
    if missing_rows:
        note += f" {missing_rows} rows without a usable date were excluded from the historical filter."
    return note


def format_cross_reference_result(payloads, time_window=None):
    """Format deterministic cross-reference results without inventing values."""

    lines = ["Sector comparison"]
    if payloads:
        time_filter_note = format_time_filter_note(payloads[0]["result"].get("time_filter"))
        if time_filter_note:
            lines.append(time_filter_note)

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


def format_sector_metric_comparison(payloads, metric, domain, time_window=None):
    definition = metric_definition(metric)
    label = definition["label"] if definition else metric.replace("_", " ").title()
    value_kind = definition["format"] if definition else "money"
    lines = [f"Sector comparison - {label}"]

    if payloads:
        time_filter_note = format_time_filter_note(payloads[0]["summary"]["result"].get("time_filter"))
        if time_filter_note:
            lines.append(time_filter_note)

    scored = []
    for payload in payloads:
        sector = payload["sector"]
        summary = payload["summary"]
        value = metric_value_from_summary(metric, summary)
        scored.append((sector, value))
        lines.append(f"- {sector}: {format_metric_value(value, value_kind)}")

    if len(scored) >= 2:
        leader, leader_value = max(scored, key=lambda item: item[1])
        trailer, trailer_value = min(scored, key=lambda item: item[1])
        delta = leader_value - trailer_value
        lines.extend(
            [
                "",
                f"Interpretation: {leader} leads on {label.lower()} by {format_metric_value(delta, value_kind)} versus {trailer}.",
                (
                    "Data quality: missing values were not imputed; incomplete board fields may affect this "
                    f"{domain.replace('_', '-')} comparison."
                ),
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

    sector = None if is_all_sectors_question(question) else detect_sector(question)
    metric = detect_metric(question)

    pipeline_keywords = [
        "deal pipeline",
        "pipeline",
        "deal value",
        "deal volume",
        "deal summary",
        "win rate",
        "won deals",
        "open deals",
        "on hold",
    ]
    execution_keywords = [
        "work order",
        "work-order",
        "work order execution",
        "execution value",
        "work order value",
        "collections",
        "collected",
        "billing",
        "billed",
        "receivable",
        "order book",
    ]

    if metric:
        return {"kind": metric_definition(metric)["domain"], "sector": sector, "metric": metric}

    if any(keyword in q for keyword in execution_keywords):
        return {"kind": "work_order", "sector": sector, "metric": None}

    if any(keyword in q for keyword in pipeline_keywords):
        return {"kind": "pipeline", "sector": sector, "metric": None}

    return None


def is_overview_question(question):
    q = question.lower()
    overview_terms = [
        "how are we doing",
        "performance",
        "overview",
        "health",
        "operational",
        "operations",
        "summary",
        "leadership update",
    ]
    return any(term in q for term in overview_terms) and not is_cross_reference_question(question)


def format_direct_business_result(kind, sector, summary, time_window=None, metric=None):
    """Render a concise deterministic result for a single-sector BI question."""
    time_window_note = format_time_filter_note(summary["result"].get("time_filter"))
    time_window_line = f"{time_window_note}\n" if time_window_note else ""

    if metric:
        definition = metric_definition(metric)
        value = metric_value_from_summary(metric, summary)
        focus_line = (
            f"- {definition['label']}: {format_metric_value(value, definition['format'])}\n"
            if definition
            else ""
        )
    else:
        focus_line = ""

    if kind == "pipeline":
        data = summary["result"]
        return (
            f"{sector or 'All sectors'} deal pipeline\n"
            f"{time_window_line}"
            f"{focus_line}"
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
        f"{time_window_line}"
        f"{focus_line}"
        f"- Work orders: {data['work_order_count']}\n"
        f"- Total order value: {data['total_order_value']:,.2f}\n"
        f"- Billed value: {data['billed_value']:,.2f}\n"
        f"- Collected amount: {data['collected_amount']:,.2f}\n"
        f"- Amount to be billed: {data['amount_to_be_billed']:,.2f}\n"
        f"- Amount receivable: {data['amount_receivable']:,.2f}\n"
        "Data quality: missing values were not imputed; incomplete board fields may affect totals."
    )


def format_overview_result(sector, pipeline_summary, work_order_summary):
    pipeline = pipeline_summary["result"]
    work_orders = work_order_summary["result"]
    lines = [f"{sector or 'All sectors'} business overview"]

    pipeline_note = format_time_filter_note(pipeline.get("time_filter"))
    if pipeline_note:
        lines.append(pipeline_note)

    lines.extend(
        [
            f"- Deal pipeline value: {pipeline['total_deal_value']:,.2f}",
            f"- Active pipeline value: {pipeline['active_pipeline_value']:,.2f}",
            f"- Won value: {pipeline['won_value']:,.2f}",
            f"- Work-order value: {work_orders['total_order_value']:,.2f}",
            f"- Billed value: {work_orders['billed_value']:,.2f}",
            f"- Collected amount: {work_orders['collected_amount']:,.2f}",
            (
                "Interpretation: this combines commercial momentum and execution progress in one sector-level view."
            ),
            "Data quality: missing values were not imputed; incomplete board fields may affect totals.",
        ]
    )
    return "\n".join(lines)


def format_average_deal_size_result(result):
    if not result["deal_count"]:
        return "No deals matched that request."

    average = result["average_deal_value"]
    if average is None:
        return (
            f"{result['sector']} average deal size\n"
            "- No recorded deal values were available for the matching deals.\n"
            "Data quality: I cannot calculate a grounded average without populated deal values."
        )

    return (
        f"{result['sector']} average deal size\n"
        f"- Average deal value: {average:,.2f}\n"
        f"- Median deal value: {result['median_deal_value']:,.2f}\n"
        f"- Sample used: {result['value_non_null_count']} of {result['deal_count']} deals "
        f"({result['coverage_pct']:.1f}% coverage)\n"
        "Data quality: missing deal values were not imputed, so treat this as a directional average."
    )


def format_closing_cycle_time_result(result):
    if not result["closed_deal_count"]:
        return "No closed deals matched that request."

    if not result["usable_close_time_count"]:
        return (
            "Deal close time is not reliably tracked in the current board.\n"
            f"- Closed deals: {result['closed_deal_count']}\n"
            "- Deals with both Created Date and Close Date (A): 0\n"
            "Data quality: there is not enough recorded close-date history to calculate a grounded cycle time."
        )

    reliability_line = (
        "Data quality: this field is not reliable enough for a business-wide typical close-time answer."
        if not result["is_reliable"]
        else "Data quality: this estimate is based only on rows with both Created Date and Close Date (A)."
    )

    anomaly_line = ""
    if result["negative_duration_count"]:
        anomaly_line = (
            f"\n- Negative durations found: {result['negative_duration_count']}"
        )

    return (
        "Deal close time coverage\n"
        f"- Closed deals: {result['closed_deal_count']}\n"
        f"- Deals with both Created Date and Close Date (A): {result['usable_close_time_count']} "
        f"({result['coverage_pct']:.1f}% coverage)\n"
        f"- Observed median days to close: {result['median_days_to_close']:.1f}\n"
        f"- Observed average days to close: {result['average_days_to_close']:.1f}"
        f"{anomaly_line}\n"
        f"{reliability_line}"
    )


def format_data_entry_errors_result(result):
    if not result["suspect_record_count"]:
        return "I did not find any obvious header-leak or malformed records."

    lines = [
        f"I found {result['suspect_record_count']} records that look like data-entry errors:",
    ]

    for row in result["suspect_records"][:10]:
        lines.append(
            f"- {row['item_name']}: {row['reason']}."
        )

    lines.append("These look safer to exclude from analysis than to treat as real business records.")
    return "\n".join(lines)


def format_cross_board_execution_gaps_result(result):
    open_clients = result["open_clients_without_completed_work_order"]
    reverse_clients = result["completed_work_order_clients_without_open_deal"]

    lines = [
        "Cross-board deal/work-order join",
        (
            f"- Open deals without a completed work order yet: {len(open_clients)} clients "
            f"({result['open_rows_without_completed_work_order']} open-deal rows)"
        ),
        (
            f"- Completed work orders without an open deal: {len(reverse_clients)} clients "
            f"({result['completed_rows_without_open_deal']} completed work-order rows)"
        ),
    ]

    if open_clients:
        lines.append("- Open-deal gap sample: " + ", ".join(open_clients[:10]))
    if reverse_clients:
        lines.append("- Reverse-gap sample: " + ", ".join(reverse_clients[:10]))

    statuses = ", ".join(result["completed_statuses_used"])
    lines.append(
        f"Matching note: I normalized deal client codes like COMPANY123 against work-order codes like "
        f"WOCOMPANY_123, and treated these execution statuses as completed: {statuses}."
    )
    return "\n".join(lines)


def format_win_rate_by_sector_result(result):
    lines = ["Win rate by sector (closed deals only)"]

    for row in result["breakdown"]:
        if row["closed_deal_count"] == 0:
            continue
        suffix = " [low confidence: small sample]" if row["low_confidence"] else ""
        lines.append(
            f"- {row['sector']}: {row['win_rate_pct']:.1f}% "
            f"({row['won_deal_count']} won / {row['dead_deal_count']} dead; {row['closed_deal_count']} closed){suffix}"
        )

    lines.append("")
    lines.append(
        f"Confidence flags: I excluded {result['excluded_unmapped_deal_rows']} deal rows with non-canonical sector labels from the sector table."
    )

    if result.get("unmapped_sector_values"):
        labels = ", ".join(
            f"{label} ({count})" for label, count in list(result["unmapped_sector_values"].items())[:10]
        )
        lines.append(f"- Unmapped deal-sector labels: {labels}")

    if result.get("work_order_distinct_sector_labels") is not None:
        if result["deal_distinct_sector_labels"] != result["work_order_distinct_sector_labels"]:
            lines.append(
                f"- Sector taxonomy mismatch: deals board has {result['deal_distinct_sector_labels']} distinct labels, "
                f"while work orders have {result['work_order_distinct_sector_labels']}."
            )
        else:
            lines.append(
                f"- Sector taxonomy note: both boards show {result['deal_distinct_sector_labels']} distinct labels here, "
                "but some deal rows still fall outside the canonical sector list."
            )

    lines.append("- Small-sample sectors should be treated as directional.")
    return "\n".join(lines)


def format_active_pipeline_by_owner_result(result):
    owners = result["owners"]
    if not owners:
        return "There are no active open or on-hold deals right now."

    top_owner = owners[0]
    lines = [
        f"Active pipeline is concentrated with {top_owner['owner']}.",
        (
            f"- {top_owner['owner']}: {top_owner['active_deal_count']} active deals, "
            f"{top_owner['active_pipeline_value']:,.2f} in active value "
            f"({top_owner['deal_share_pct']:.1f}% of active deals, {top_owner['value_share_pct']:.1f}% of active value)"
        ),
    ]

    for row in owners[1:4]:
        lines.append(
            f"- {row['owner']}: {row['active_deal_count']} deals, {row['active_pipeline_value']:,.2f}"
        )

    lines.append("Data quality: active pipeline value uses recorded deal values only; missing values were not imputed.")
    return "\n".join(lines)


def format_billing_status_missing_fraction_result(result):
    return (
        f"Billing status coverage\n"
        f"- Missing billing status: {result['missing_count']} of {result['total_count']} work orders "
        f"({result['missing_fraction_pct']:.1f}%)\n"
        "Data quality: billing-status-based analysis is weak until this field is filled more consistently."
    )


def format_receivable_anomalies_result(result):
    if not result["negative_count"] and not result["positive_outlier_count"]:
        return "I did not find any obvious receivable anomalies."

    lines = ["Receivable anomalies worth a second look"]

    if result["negative_count"]:
        lines.append(
            f"- Negative receivables: {result['negative_count']} records"
        )
        if result["largest_negative_value"] is not None:
            lines.append(
                f"- Largest negative receivable: {result['largest_negative_value']:,.2f}"
            )
        sample = result["negative_records"][:5]
        if sample:
            lines.append(
                "- Negative sample: "
                + ", ".join(
                    f"{row['customer_name_code']} ({row['receivable_value']:,.2f})"
                    for row in sample
                )
            )

    if result["positive_outlier_count"]:
        lines.append(
            f"- High receivable outliers above {result['positive_outlier_threshold']:,.2f}: {result['positive_outlier_count']} records"
        )

    lines.append("I flagged these separately instead of silently blending them into average receivable analysis.")
    return "\n".join(lines)


def detect_grounded_question(question):
    q = question.lower()

    if "win rate" in q and (
        "by sector" in q
        or "across sectors" in q
        or "break down" in q
        or "breakdown" in q
    ):
        return {"kind": "win_rate_by_sector"}

    if re.search(r"\baverage\b.*\bdeal size\b|\bavg\b.*\bdeal size\b|\baverage\b.*\bdeal value\b", q):
        return {"kind": "average_deal_size", "sector": detect_sector(question)}

    if re.search(r"\bhow long\b.*\bclose a deal\b|\btime to close\b|\bdays to close\b|\bsales cycle\b", q):
        return {"kind": "closing_cycle_time", "sector": detect_sector(question)}

    if re.search(r"\bdata entry errors?\b|\blook like data entry\b|\bsuspicious records?\b|\bmalformed records?\b", q):
        return {"kind": "data_entry_errors"}

    if "open deal" in q and "work order" in q:
        return {"kind": "cross_board_execution_gaps"}

    if "billing status" in q and re.search(r"\bfraction\b|\bpercent\b|\bpercentage\b|\bhow many\b|\bmissing\b|\bno\b", q):
        return {"kind": "billing_status_missing_fraction"}

    if "receivable" in q and re.search(r"\bunusual\b|\banomal|\bnegative\b|\bsecond look\b", q):
        return {"kind": "receivable_anomalies"}

    if "active pipeline" in q and re.search(r"\bbd\/kam\b|\bowner\b|\bcarrying\b", q):
        return {"kind": "active_pipeline_by_owner"}

    return None


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
    conversation_state=None,
    data_context=None,
):
    api_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=api_key) if api_key else None

    quality_context = {
        "work_orders": compact_quality_summary(work_order_quality),
        "deals": compact_quality_summary(deal_quality),
    }

    def current_deals_df():
        if data_context and data_context.get("deals_df") is not None:
            return data_context["deals_df"]
        return deals_df

    def current_work_orders_df():
        if data_context and data_context.get("work_orders_df") is not None:
            return data_context["work_orders_df"]
        return work_orders_df

    def current_quality_context():
        if not data_context:
            return quality_context
        return {
            "work_orders": compact_quality_summary(
                data_context.get("work_order_quality", work_order_quality)
            ),
            "deals": compact_quality_summary(
                data_context.get("deal_quality", deal_quality)
            ),
        }

    def tool_filter_deals(sector=None, status=None, stage=None, owner=None):
        result = filter_deals(
            current_deals_df(),
            sector=sector,
            status=status,
            stage=stage,
            owner=owner,
        )

        return {
            "row_count": len(result),
            "columns": list(result.columns),
            "sample": result.head(10).to_dict(orient="records"),
            "quality": current_quality_context()["deals"],
        }

    def tool_pipeline_summary(sector=None, time_window=None):
        result = pipeline_summary(
            current_deals_df(),
            sector=sector,
            time_window=time_window or conversation_state.get("time_window"),
        )
        return {"result": result, "quality": current_quality_context()["deals"]}

    def tool_work_order_financials(sector=None, time_window=None):
        result = work_order_financials(
            current_work_orders_df(),
            sector=sector,
            time_window=time_window or conversation_state.get("time_window"),
        )
        return {"result": result, "quality": current_quality_context()["work_orders"]}

    def tool_cross_reference(sector=None, time_window=None):
        result = cross_reference_deal_to_execution(
            current_deals_df(),
            current_work_orders_df(),
            sector=sector,
            time_window=time_window,
        )
        return {
            "result": result,
            "quality": {
                "deals": current_quality_context()["deals"],
                "work_orders": current_quality_context()["work_orders"],
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
                    "Can optionally be restricted to a sector and a supported historical time window."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sector": {"type": "string", "description": "Optional sector."},
                        "time_window": {
                            "type": "string",
                            "description": "Optional period label such as last_month or this_quarter.",
                        },
                    },
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
                    "amount to be billed and receivables. Can optionally be restricted to a sector and time window."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sector": {"type": "string", "description": "Optional sector."},
                        "time_window": {
                            "type": "string",
                            "description": "Optional period label such as last_month or this_quarter.",
                        },
                    },
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
            "domain": None,
            "sectors": [],
            "comparison": None,
            "metric": None,
            "time_window": None,
            "awaiting": None,
            "last_completed_task": None,
        }

    if conversation_state is None:
        conversation_state = empty_conversation_state()
    else:
        defaults = empty_conversation_state()
        for key, value in defaults.items():
            if key not in conversation_state:
                conversation_state[key] = value.copy() if isinstance(value, list) else value
        conversation_state["sectors"] = list(conversation_state.get("sectors") or [])

    def reset_active_task():
        completed = conversation_state.get("last_completed_task")
        conversation_state.clear()
        conversation_state.update(empty_conversation_state())
        conversation_state["last_completed_task"] = completed

    def remember_active_context(sectors=None, time_window=None, metric=None):
        for sector in sectors or []:
            if sector not in conversation_state["sectors"]:
                conversation_state["sectors"].append(sector)

        if time_window:
            conversation_state["time_window"] = time_window
            conversation_state["awaiting"] = None

        if metric and not conversation_state["metric"]:
            conversation_state["metric"] = metric

    def start_cross_reference_task(sectors=None, time_window=None):
        reset_active_task()
        conversation_state["task"] = "cross_reference"
        conversation_state["domain"] = "cross_reference"
        conversation_state["comparison"] = "deal pipeline vs work-order execution"
        conversation_state["metric"] = conversation_state["comparison"]
        remember_active_context(sectors=sectors, time_window=time_window)

    def start_direct_task(kind, sectors=None, time_window=None, metric=None):
        reset_active_task()
        conversation_state["task"] = kind
        conversation_state["domain"] = kind
        conversation_state["metric"] = kind
        if metric:
            conversation_state["metric"] = metric
        remember_active_context(sectors=sectors, time_window=time_window, metric=metric)

    def start_sector_comparison_task(domain, metric=None, sectors=None, time_window=None):
        reset_active_task()
        conversation_state["task"] = "sector_comparison"
        conversation_state["domain"] = domain
        conversation_state["comparison"] = "sector versus sector"
        conversation_state["metric"] = metric
        remember_active_context(sectors=sectors, time_window=time_window, metric=metric)

    def start_overview_task(sectors=None, time_window=None):
        reset_active_task()
        conversation_state["task"] = "overview"
        conversation_state["domain"] = "overview"
        conversation_state["metric"] = "overview"
        remember_active_context(sectors=sectors, time_window=time_window)

    def finish_active_task():
        conversation_state["last_completed_task"] = {
            "task": conversation_state["task"],
            "domain": conversation_state["domain"],
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
            metric=conversation_state["metric"] if conversation_state["metric"] != conversation_state["task"] else None,
        )
        finish_active_task()
        return answer

    def run_sector_comparison_task():
        payloads = []
        for sector in conversation_state["sectors"]:
            if conversation_state["domain"] == "pipeline":
                summary = tool_pipeline_summary(sector=sector)
            else:
                summary = tool_work_order_financials(sector=sector)
            payloads.append({"sector": sector, "summary": summary})

        answer = format_sector_metric_comparison(
            payloads,
            conversation_state["metric"],
            conversation_state["domain"],
            time_window=conversation_state["time_window"],
        )
        finish_active_task()
        return answer

    def run_overview_task():
        sector = conversation_state["sectors"][0] if conversation_state["sectors"] else None
        pipeline = tool_pipeline_summary(sector=sector)
        work_orders = tool_work_order_financials(sector=sector)
        answer = format_overview_result(sector, pipeline, work_orders)
        finish_active_task()
        return answer

    def run_grounded_question(question_type):
        kind = question_type["kind"]

        if kind == "average_deal_size":
            result = average_deal_size(
                current_deals_df(),
                sector=question_type.get("sector"),
            )
            return format_average_deal_size_result(result)

        if kind == "closing_cycle_time":
            result = closing_cycle_time(
                current_deals_df(),
                sector=question_type.get("sector"),
            )
            return format_closing_cycle_time_result(result)

        if kind == "data_entry_errors":
            result = detect_data_entry_errors(
                current_deals_df(),
                current_work_orders_df(),
            )
            return format_data_entry_errors_result(result)

        if kind == "cross_board_execution_gaps":
            result = cross_board_execution_gaps(
                current_deals_df(),
                current_work_orders_df(),
            )
            return format_cross_board_execution_gaps_result(result)

        if kind == "win_rate_by_sector":
            result = win_rate_by_sector(
                current_deals_df(),
                current_work_orders_df(),
            )
            return format_win_rate_by_sector_result(result)

        if kind == "active_pipeline_by_owner":
            result = active_pipeline_by_owner(current_deals_df())
            return format_active_pipeline_by_owner_result(result)

        if kind == "billing_status_missing_fraction":
            result = billing_status_missing_fraction(current_work_orders_df())
            return format_billing_status_missing_fraction_result(result)

        if kind == "receivable_anomalies":
            result = receivable_anomalies(current_work_orders_df())
            return format_receivable_anomalies_result(result)

        return None

    def ask(question):
        question_lower = question.lower()
        current_sectors = detect_sectors(question)
        time_window = detect_time_window(question)
        metric = detect_metric(question)
        grounded_question = detect_grounded_question(question)

        if grounded_question:
            answer = run_grounded_question(grounded_question)
            if answer:
                finish_active_task()
                return answer

        direct_question = detect_direct_business_question(question)
        if is_sector_metric_comparison_question(question):
            domain = metric_definition(metric)["domain"] if metric else None
            start_sector_comparison_task(
                domain=domain,
                metric=metric,
                sectors=current_sectors,
                time_window=time_window,
            )
        elif is_overview_question(question):
            start_overview_task(
                sectors=current_sectors,
                time_window=time_window,
            )
        elif direct_question:
            start_direct_task(
                direct_question["kind"],
                sectors=current_sectors,
                time_window=time_window,
                metric=direct_question.get("metric"),
            )

        if direct_question:
            pass

        if is_cross_reference_question(question):
            start_cross_reference_task(
                sectors=current_sectors,
                time_window=time_window,
            )
        elif conversation_state["task"] in {"pipeline", "work_order", "cross_reference", "sector_comparison", "overview"}:
            remember_active_context(
                sectors=current_sectors,
                time_window=time_window,
                metric=metric,
            )

        if is_metric_ambiguity(question):
            conversation_state["awaiting"] = "metric"
            return (
                "Which metric do you mean: deal value, billed, collected, "
                "or receivable?"
            )

        if conversation_state["task"] in {"pipeline", "work_order"}:
            if not conversation_state["sectors"] and not is_all_sectors_question(question):
                conversation_state["awaiting"] = "sector"
                return (
                    "Which sector should I use? Available sectors are: Mining, Renewables, "
                    "Railways, Powerline, Construction, and Others."
                )

            conversation_state["awaiting"] = None
            return run_direct_task()

        if conversation_state["task"] == "overview":
            if not conversation_state["sectors"] and not is_all_sectors_question(question):
                conversation_state["awaiting"] = "sector"
                return (
                    "Which sector should I summarize? Available sectors are: Mining, Renewables, "
                    "Railways, Powerline, Construction, and Others."
                )

            conversation_state["awaiting"] = None
            return run_overview_task()

        if conversation_state["task"] == "sector_comparison":
            if not conversation_state["metric"]:
                conversation_state["awaiting"] = "metric"
                return (
                    "Which metric should I compare: pipeline, win rate, billed, collected, "
                    "receivable, or work-order value?"
                )

            if len(conversation_state["sectors"]) < 2:
                conversation_state["awaiting"] = "sector"
                return (
                    "Which sectors should I compare? Available sectors are: Mining, Renewables, "
                    "Railways, Powerline, Construction, and Others."
                )

            conversation_state["awaiting"] = None
            return run_sector_comparison_task()

        if conversation_state["task"] == "cross_reference":
            if is_all_sectors_question(question):
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

        if client is None:
            return (
                "I can still answer the structured monday.com questions that are wired to deterministic tools, "
                "but the Groq fallback is not configured for broader open-ended analysis right now."
            )

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
        if conversation_state["domain"]:
            context_lines.append(f"Remembered domain: {conversation_state['domain']}")
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
