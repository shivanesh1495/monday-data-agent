import os
import streamlit as st

from monday_client import MondayClient
from normalize import normalize_deals, normalize_work_orders
from tools import (
    cross_reference_deal_to_execution,
    filter_deals,
    pipeline_summary,
    work_order_financials,
)

st.title("Monday BI Agent - Tool Test")

client = MondayClient()

work_order_id = os.getenv("WORK_ORDER_BOARD_ID")
deal_id = os.getenv("DEAL_FUNNEL_BOARD_ID")

work_orders = client.board_to_dataframe(work_order_id)
deals = client.board_to_dataframe(deal_id)

work_orders = normalize_work_orders(work_orders)
deals = normalize_deals(deals)

st.header("1. Filter Deals")
mining_deals = filter_deals(deals, sector="Mining")
st.write("Mining deals:", len(mining_deals))

st.header("2. Pipeline Summary")
pipeline = pipeline_summary(deals, sector="Mining")
st.json(pipeline)

st.header("3. Work Order Financials")
financials = work_order_financials(work_orders, sector="Mining")
st.json(financials)

st.header("4. Cross Reference")
comparison = cross_reference_deal_to_execution(deals, work_orders, sector="Mining")
st.json(comparison)
