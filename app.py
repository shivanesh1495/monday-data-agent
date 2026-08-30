import os
import streamlit as st

from monday_client import MondayClient
from normalize import (
    build_quality_summary,
    normalize_deals,
    normalize_work_orders,
)

st.title("Monday BI Agent")

try:
    client = MondayClient()

    work_order_id = os.getenv("WORK_ORDER_BOARD_ID")
    deal_id = os.getenv("DEAL_FUNNEL_BOARD_ID")

    work_orders = client.board_to_dataframe(work_order_id)
    deals = client.board_to_dataframe(deal_id)

    work_orders = normalize_work_orders(work_orders)
    deals = normalize_deals(deals)

    st.success("Successfully connected to monday.com")

    st.subheader("Work Orders")
    st.write(work_orders.shape)
    st.dataframe(work_orders.head(10))

    st.subheader("Deals")
    st.write(deals.shape)
    st.dataframe(deals.head(10))

    st.subheader("Work Order Data Quality")
    st.json(build_quality_summary(work_orders))

    st.subheader("Deal Data Quality")
    st.json(build_quality_summary(deals))

except Exception as e:
    st.error("Unable to load monday.com data")
    st.exception(e)
