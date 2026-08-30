import os

from tools import (
    get_billing_summary,
    get_deal_summary,
    get_execution_status,
    get_pipeline_by_sector,
    get_revenue_by_sector,
    get_work_order_summary,
)


def _llm_explain(question, summary):
    question_lower = (question or "").lower()
    summary_text = ""

    if "mining" in question_lower:
        sector_name = "Mining"
        pipeline = summary.get("sector_summary", {})
        sector_value = pipeline.get(sector_name, 0)
        summary_text = (
            f"The Mining pipeline is currently valued at {sector_value:.2f}. "
            "This is the value of open deal coverage in the Mining segment."
        )

    elif "billing" in question_lower:
        billing = summary.get("billing_counts", {})
        total = summary.get("estimated_revenue_total", 0)
        summary_text = (
            f"Billing is tracking as: {billing}. "
            f"Current revenue estimate for the board is {total:.2f}."
        )

    elif "execution" in question_lower or "status" in question_lower:
        execution = summary.get("execution_status", {})
        summary_text = (
            f"Execution status across the work orders is: {execution}. "
            "This helps identify where delivery risk may be concentrated."
        )

    elif "revenue" in question_lower:
        revenue = summary.get("sector_summary", {})
        top_sector = max(revenue.items(), key=lambda item: item[1], default=("Unknown", 0))
        summary_text = (
            f"The largest revenue contributor is {top_sector[0]} at {top_sector[1]:.2f}. "
            "This indicates where the current delivery mix is concentrated."
        )

    else:
        total_pipeline = summary.get("total_pipeline_value", 0)
        deal_count = summary.get("deal_count", 0)
        summary_text = (
            f"The current funnel contains {deal_count} deals and a total pipeline value of {total_pipeline:.2f}. "
            "This is the base for evaluating growth, risk, and execution readiness."
        )

    return summary_text


def run_agent(question):
    question = question or ""

    work_orders, deals = None, None

    try:
        from tools import _get_board_data

        work_orders, deals = _get_board_data()
    except Exception:
        work_orders, deals = None, None

    if deals is None:
        return "I couldn't load monday.com board data. Check the API token and board IDs in the environment."

    summary = get_deal_summary(deals)
    pipeline_by_sector = get_pipeline_by_sector(deals)
    revenue_by_sector = get_revenue_by_sector(work_orders) if work_orders is not None else {}
    work_summary = get_work_order_summary(work_orders) if work_orders is not None else {}
    execution_status = get_execution_status(work_orders) if work_orders is not None else {}
    billing_summary = get_billing_summary(work_orders) if work_orders is not None else {}

    summary["sector_summary"] = pipeline_by_sector
    summary["revenue_by_sector"] = revenue_by_sector
    summary["work_order_summary"] = work_summary
    summary["execution_status"] = execution_status
    summary["billing_counts"] = billing_summary.get("billing_counts", {})
    summary["estimated_revenue_total"] = billing_summary.get("estimated_revenue_total", 0)

    if "mining" in question.lower():
        mining_value = pipeline_by_sector.get("Mining", 0)
        mining_revenue = revenue_by_sector.get("Mining", 0)
        response = (
            f"Mining pipeline outlook: current deal coverage is {mining_value:.2f}, with "
            f"delivery revenue exposure of {mining_revenue:.2f}. "
            f"{_llm_explain(question, summary)}"
        )
        return response

    if "billing" in question.lower():
        response = (
            "Billing view: "
            f"{billing_summary.get('billing_counts', {})}. "
            f"Current estimated revenue total is {billing_summary.get('estimated_revenue_total', 0):.2f}. "
            f"{_llm_explain(question, summary)}"
        )
        return response

    if "execution" in question.lower() or "status" in question.lower():
        response = (
            "Execution status: "
            f"{execution_status}. "
            f"{_llm_explain(question, summary)}"
        )
        return response

    response = (
        f"Here is the current business snapshot: {summary}. "
        f"{_llm_explain(question, summary)}"
    )
    return response
