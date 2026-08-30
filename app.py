import os
import streamlit as st

from monday_client import MondayClient

from normalize import (
    normalize_work_orders,
    normalize_deals,
    build_quality_summary
)

from agent import create_agent

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
