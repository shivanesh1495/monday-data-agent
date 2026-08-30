import os
import streamlit as st

from monday_client import MondayClient

from normalize import (
    normalize_work_orders,
    normalize_deals,
    build_quality_summary
)

from agent import create_agent
from tools import leadership_summary

st.set_page_config(
    page_title="Skylark BI Agent",
    page_icon="📊",
    layout="centered"
)

# -----------------------------
# Header
# -----------------------------

st.title("Skylark Business Intelligence Agent")

st.caption(
    "Ask questions about deals, pipeline, "
    "work orders and operational performance."
)

# -----------------------------
# Load data
# -----------------------------

@st.cache_data(ttl=300)
def load_data():

    client = MondayClient()

    work_order_id = os.getenv(
        "WORK_ORDER_BOARD_ID"
    )

    deal_id = os.getenv(
        "DEAL_FUNNEL_BOARD_ID"
    )

    if not work_order_id:
        raise ValueError(
            "WORK_ORDER_BOARD_ID is missing"
        )

    if not deal_id:
        raise ValueError(
            "DEAL_FUNNEL_BOARD_ID is missing"
        )

    work_orders = client.board_to_dataframe(
        work_order_id
    )

    deals = client.board_to_dataframe(
        deal_id
    )

    work_orders = normalize_work_orders(
        work_orders
    )

    deals = normalize_deals(
        deals
    )

    work_quality = build_quality_summary(
        work_orders
    )

    deal_quality = build_quality_summary(
        deals
    )

    return (
        work_orders,
        deals,
        work_quality,
        deal_quality
    )

# -----------------------------
# Initialize
# -----------------------------

try:

    (
        work_orders,
        deals,
        work_quality,
        deal_quality
    ) = load_data()

except Exception as e:

    st.error(
        "Unable to load monday.com data."
    )

    st.exception(e)

    st.stop()

# -----------------------------
# Agent
# -----------------------------

@st.cache_resource
def build_agent(
    work_quality,
    deal_quality
):

    return create_agent(
        deals_df=deals,
        work_orders_df=work_orders,
        work_order_quality=work_quality,
        deal_quality=deal_quality
    )

ask = build_agent(
    work_quality,
    deal_quality
)

# -----------------------------
# Chat history
# -----------------------------

if "messages" not in st.session_state:

    st.session_state.messages = []

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )

# -----------------------------
# Leadership Summary
# -----------------------------

st.divider()

st.subheader("Leadership Summary")

if st.button("Generate Leadership Summary"):

    summary = leadership_summary(
        deals,
        work_orders
    )

    pipeline = summary["pipeline"]
    financials = summary["work_orders"]

    deal_missing = build_quality_summary(deals)["missing_values"]
    work_missing = build_quality_summary(work_orders)["missing_values"]

    def missing_count(summary_map, *keys):
        for key in keys:
            if key in summary_map:
                return int(summary_map[key])
        return 0

    markdown = f"""
# Leadership Summary

## Deal Pipeline

- Total deals: {pipeline["deal_count"]}
- Total deal value: ₹{pipeline["total_deal_value"]:,.2f}
- Active pipeline value: ₹{pipeline["active_pipeline_value"]:,.2f}
- Open deals: {pipeline["open_deals"]}
- Won value: ₹{pipeline["won_value"]:,.2f}
- Dead value: ₹{pipeline["dead_value"]:,.2f}
- On-hold value: ₹{pipeline["on_hold_value"]:,.2f}

## Work Orders

- Work orders: {financials["work_order_count"]}
- Total order value: ₹{financials["total_order_value"]:,.2f}
- Billed value: ₹{financials["billed_value"]:,.2f}
- Collected amount: ₹{financials["collected_amount"]:,.2f}
- Amount to be billed: ₹{financials["amount_to_be_billed"]:,.2f}
- Amount receivable: ₹{financials["amount_receivable"]:,.2f}

## Data Quality

### Deals
- {len(deals)} total records
- Close Date missing in {missing_count(deal_missing, 'Close Date (A)')} records
- Closure Probability missing in {missing_count(deal_missing, 'Closure Probability')} records
- No values were imputed

### Work Orders
- {len(work_orders)} total records
- Expected Billing Month missing in {missing_count(work_missing, 'Expected Billing Month')} records
- Actual Collection Month missing in {missing_count(work_missing, 'Actual Collection Month')} records
- Collection Status missing in {missing_count(work_missing, 'Collection status')} records
- Collection Date missing in {missing_count(work_missing, 'Collection Date')} records
- No values were imputed

> On-hold deal value: ₹{pipeline["on_hold_value"]:,.2f} based on available deal-value data; missing deal values were not imputed.
"""

    st.markdown(markdown)

    st.download_button(
        label="Download Markdown",
        data=markdown,
        file_name="leadership_summary.md",
        mime="text/markdown"
    )

# -----------------------------
# Chat input
# -----------------------------

question = st.chat_input(
    "Ask a business question..."
)

if question:

    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):

        st.markdown(question)

    with st.chat_message("assistant"):

        with st.spinner(
            "Analyzing monday.com data..."
        ):

            try:

                answer = ask(question)

            except Exception as e:

                answer = (
                    "I couldn't complete that analysis. "
                    "Please try again or rephrase the question."
                )

                st.error(str(e))

        st.markdown(answer)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })
