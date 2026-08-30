import os

import pandas as pd

from monday_client import MondayClient
from normalize import normalize_deals, normalize_work_orders


def _numeric(value):
    if pd.isna(value):
        return 0.0

    if isinstance(value, str):
        value = value.strip().replace(",", "").replace("₹", "").replace("$", "")
        if not value:
            return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _get_board_data():
    client = MondayClient()

    work_orders = client.board_to_dataframe(os.getenv("WORK_ORDER_BOARD_ID"))
    deals = client.board_to_dataframe(os.getenv("DEAL_FUNNEL_BOARD_ID"))

    work_orders = normalize_work_orders(work_orders)
    deals = normalize_deals(deals)

    return work_orders, deals


def get_deal_summary(deals=None):
    if deals is None:
        _, deals = _get_board_data()

    deals = deals.copy()
    deals["Masked Deal value"] = pd.to_numeric(
        deals["Masked Deal value"].apply(_numeric), errors="coerce"
    )

    status_summary = deals["Deal Status"].fillna("Unknown").astype(str).str.strip()
    status_counts = status_summary.value_counts().to_dict()

    sector_summary = deals.groupby("Sector/service", dropna=False)["Masked Deal value"].sum().to_dict()
    stage_summary = deals["Deal Stage"].fillna("Unknown").astype(str).str.strip().value_counts().to_dict()

    total_pipeline = float(deals["Masked Deal value"].sum())
    open_value = float(
        deals.loc[deals["Deal Status"].fillna("").str.lower().eq("open"), "Masked Deal value"].sum()
    )

    return {
        "deal_count": int(len(deals)),
        "total_pipeline_value": round(total_pipeline, 2),
        "open_pipeline_value": round(open_value, 2),
        "status_counts": status_counts,
        "sector_summary": {k: round(v, 2) for k, v in sector_summary.items()},
        "stage_summary": stage_summary,
    }


def get_pipeline_by_sector(deals=None):
    if deals is None:
        _, deals = _get_board_data()

    deals = deals.copy()
    deals["Masked Deal value"] = pd.to_numeric(
        deals["Masked Deal value"].apply(_numeric), errors="coerce"
    )

    return {
        sector: round(float(total), 2)
        for sector, total in deals.groupby("Sector/service", dropna=False)["Masked Deal value"].sum().items()
    }


def get_revenue_by_sector(work_orders=None):
    if work_orders is None:
        work_orders, _ = _get_board_data()

    work_orders = work_orders.copy()

    amount_columns = [
        column for column in work_orders.columns
        if "Amount in Rupees" in column and "Masked" in column
    ]

    if not amount_columns:
        return {}

    total_col = amount_columns[0]
    work_orders[total_col] = pd.to_numeric(work_orders[total_col].apply(_numeric), errors="coerce")

    return {
        sector: round(float(total), 2)
        for sector, total in work_orders.groupby("Sector", dropna=False)[total_col].sum().items()
    }


def get_deal_stage_summary(deals=None):
    if deals is None:
        _, deals = _get_board_data()

    deals = deals.copy()
    return {
        str(stage): int(count)
        for stage, count in deals["Deal Stage"].fillna("Unknown").astype(str).str.strip().value_counts().items()
    }


def get_work_order_summary(work_orders=None):
    if work_orders is None:
        work_orders, _ = _get_board_data()

    work_orders = work_orders.copy()

    execution_counts = work_orders["Execution Status"].fillna("Unknown").astype(str).str.strip().value_counts().to_dict()

    revenue_columns = [
        column for column in work_orders.columns
        if "Amount in Rupees" in column and "Masked" in column
    ]
    total_revenue = 0.0
    if revenue_columns:
        work_orders[revenue_columns[0]] = pd.to_numeric(
            work_orders[revenue_columns[0]].apply(_numeric), errors="coerce"
        )
        total_revenue = float(work_orders[revenue_columns[0]].sum())

    return {
        "work_order_count": int(len(work_orders)),
        "execution_status": execution_counts,
        "total_revenue": round(total_revenue, 2),
    }


def get_execution_status(work_orders=None):
    if work_orders is None:
        work_orders, _ = _get_board_data()

    work_orders = work_orders.copy()
    return {
        str(status): int(count)
        for status, count in work_orders["Execution Status"].fillna("Unknown").astype(str).str.strip().value_counts().items()
    }


def get_billing_summary(work_orders=None):
    if work_orders is None:
        work_orders, _ = _get_board_data()

    work_orders = work_orders.copy()
    billing_status = work_orders["Billing Status"].fillna("Unknown").astype(str).str.strip().value_counts().to_dict()

    revenue_columns = [
        column for column in work_orders.columns
        if "Amount in Rupees" in column and "Masked" in column
    ]
    billed_total = 0.0
    if revenue_columns:
        work_orders[revenue_columns[0]] = pd.to_numeric(
            work_orders[revenue_columns[0]].apply(_numeric), errors="coerce"
        )
        billed_total = float(work_orders[revenue_columns[0]].sum())

    return {
        "billing_counts": billing_status,
        "estimated_revenue_total": round(billed_total, 2),
    }


def get_tools():
    return [
        get_deal_summary,
        get_pipeline_by_sector,
        get_revenue_by_sector,
        get_deal_stage_summary,
        get_work_order_summary,
        get_execution_status,
        get_billing_summary,
    ]
