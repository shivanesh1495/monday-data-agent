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

st.markdown(
    """
    <style>
        :root {
            --bg: #030b14;
            --bg-2: #071a2d;
            --panel: rgba(12, 20, 30, 0.82);
            --panel-strong: rgba(17, 27, 39, 0.94);
            --soft: rgba(121, 140, 160, 0.18);
            --line: rgba(148, 163, 184, 0.22);
            --text: #edf2f8;
            --muted: #a7b7c9;
            --accent: #8bd3ff;
            --accent-strong: #55c6ff;
            --shadow: 0 16px 34px rgba(0, 0, 0, 0.28);
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
            background: radial-gradient(circle at top, #091d2e 0%, var(--bg) 38%, #020911 100%);
            color: var(--text);
        }

        .stApp {
            padding-top: 1rem;
        }

        h1 {
            font-size: 3.35rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.065em;
            line-height: 0.9 !important;
            margin: 0 0 0.4rem 0 !important;
        }

        h3 {
            font-size: 1.05rem !important;
            font-weight: 600 !important;
            color: var(--text) !important;
            margin: 0 !important;
        }

        .stCaptionContainer {
            color: var(--muted) !important;
            font-size: 1.22rem !important;
            margin-bottom: 1rem !important;
        }

        .block-container {
            max-width: 1180px;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
        }

        .summary-card,
        .summary-box {
            background: linear-gradient(180deg, rgba(18, 29, 40, 0.9), rgba(10, 16, 24, 0.88));
            border: 1px solid var(--line);
            border-radius: 20px;
            box-shadow: var(--shadow);
            padding: 1rem 1.1rem 0.9rem 1.1rem;
            backdrop-filter: blur(10px);
        }

        .summary-card {
            margin-top: 0.35rem;
            margin-bottom: 1rem;
        }

        .summary-card .stButton > button {
            width: 100%;
            background: linear-gradient(180deg, rgba(23, 35, 46, 0.96), rgba(12, 21, 30, 0.98));
            border: 1px solid rgba(148, 163, 184, 0.26);
            color: var(--text);
            border-radius: 14px;
            height: 3rem;
            font-size: 1.04rem;
            font-weight: 600;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 10px 18px rgba(0,0,0,0.18);
        }

        .summary-card .stButton > button:hover {
            border-color: rgba(139, 211, 255, 0.7);
            box-shadow: 0 0 0 1px rgba(139, 211, 255, 0.18), 0 10px 20px rgba(85, 198, 255, 0.08);
        }

        .summary-card .stDownloadButton > button {
            background: rgba(14, 25, 35, 0.8);
            border: 1px solid rgba(139, 211, 255, 0.35);
            color: var(--text);
            border-radius: 12px;
            height: 2.5rem;
            margin-top: 0.7rem;
            font-weight: 600;
        }

        .stChatInput {
            position: sticky;
            bottom: 0.7rem;
            z-index: 10;
            background: rgba(4, 10, 16, 0.7);
            backdrop-filter: blur(10px);
            padding: 0.35rem 0.2rem 0.2rem 0.2rem;
            border-radius: 18px;
        }

        .stChatInput > div {
            background: rgba(12, 20, 29, 0.92);
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.22);
            box-shadow: 0 10px 20px rgba(0,0,0,0.18);
        }

        .stChatInput textarea {
            background: transparent !important;
            color: var(--text) !important;
            font-size: 1rem;
        }

        .stChatInput button {
            background: linear-gradient(180deg, var(--accent), var(--accent-strong));
            color: #051722;
            border: none;
            border-radius: 12px;
            font-weight: 700;
            box-shadow: 0 8px 18px rgba(85, 198, 255, 0.18);
        }

        .stMarkdown {
            color: var(--text);
        }

        .stAlert {
            background: rgba(14, 20, 28, 0.82);
            border: 1px solid var(--line);
            color: var(--text);
        }

        .stDialog {
            background: rgba(4, 11, 22, 0.92);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Header
# -----------------------------

st.title("Skylark Business Intelligence Agent")

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
# Leadership Summary
# -----------------------------

st.markdown('<div class="summary-card">', unsafe_allow_html=True)

st.subheader("Leadership Summary", divider=False)

if "leadership_summary_markdown" not in st.session_state:
    st.session_state.leadership_summary_markdown = ""

if st.button("Generate Leadership Summary", use_container_width=True):
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

    st.session_state.leadership_summary_markdown = markdown

if st.session_state.leadership_summary_markdown:
    st.markdown(st.session_state.leadership_summary_markdown)
    st.download_button(
        label="Download Markdown",
        data=st.session_state.leadership_summary_markdown,
        file_name="leadership_summary.md",
        mime="text/markdown",
        use_container_width=True,
    )

st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<hr style='border: 1px solid rgba(151,170,188,0.25); margin: 1.2rem 0 1.4rem 0;' />", unsafe_allow_html=True)

# -----------------------------
# Chat history
# -----------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

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
