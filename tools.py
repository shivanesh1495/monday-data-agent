import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import pandas as pd


def filter_deals(
    deals_df,
    sector=None,
    status=None,
    stage=None,
    owner=None
):
    """
    Filter deals using optional criteria.
    """

    df = deals_df.copy()

    if sector:
        df = df[
            df["Sector/service"]
            .astype(str)
            .str.strip()
            .str.lower()
            == sector.strip().lower()
        ]

    if status:
        df = df[
            df["Deal Status"]
            .astype(str)
            .str.strip()
            .str.lower()
            == status.strip().lower()
        ]

    if stage:
        df = df[
            df["Deal Stage"]
            .astype(str)
            .str.strip()
            .str.lower()
            == stage.strip().lower()
        ]

    if owner:
        df = df[
            df["Owner code"]
            .astype(str)
            .str.strip()
            .str.lower()
            == owner.strip().lower()
        ]

    return df


def pipeline_summary(deals_df, sector=None):
    """
    Calculate pipeline metrics from the Deals DataFrame.
    """

    df = filter_deals(deals_df, sector=sector)

    if df.empty:
        return {
            "deal_count": 0,
            "total_deal_value": 0,
            "active_pipeline_value": 0,
            "won_value": 0,
            "dead_value": 0,
            "on_hold_value": 0,
            "open_deals": 0,
            "won_deals": 0,
            "dead_deals": 0,
            "on_hold_deals": 0,
        }

    value = pd.to_numeric(df["Masked Deal value"], errors="coerce")

    status = df["Deal Status"].astype(str).str.strip().str.lower()

    open_mask = status == "open"
    won_mask = status == "won"
    dead_mask = status == "dead"
    hold_mask = status == "on hold"

    return {
        "deal_count": len(df),
        "total_deal_value": float(value.fillna(0).sum()),
        "active_pipeline_value": float(
            value[open_mask | hold_mask].fillna(0).sum()
        ),
        "won_value": float(value[won_mask].fillna(0).sum()),
        "dead_value": float(value[dead_mask].fillna(0).sum()),
        "on_hold_value": float(value[hold_mask].fillna(0).sum()),
        "open_deals": int(open_mask.sum()),
        "won_deals": int(won_mask.sum()),
        "dead_deals": int(dead_mask.sum()),
        "on_hold_deals": int(hold_mask.sum()),
    }


def work_order_financials(work_orders_df, sector=None):
    """
    Calculate financial metrics for work orders.
    """

    df = work_orders_df.copy()

    if sector:
        df = df[
            df["Sector"]
            .astype(str)
            .str.strip()
            .str.lower()
            == sector.strip().lower()
        ]

    if df.empty:
        return {
            "work_order_count": 0,
            "total_order_value": 0,
            "billed_value": 0,
            "collected_amount": 0,
            "amount_to_be_billed": 0,
            "amount_receivable": 0,
        }

    def number(column):
        return pd.to_numeric(df[column], errors="coerce").fillna(0)

    amount_value_cols = {
        "total_order_value": "Amount in Rupees (Excl of GST) (Masked)",
        "billed_value": "Billed Value in Rupees (Excl of GST.) (Masked)",
        "collected_amount": "Collected Amount in Rupees (Incl of GST.) (Masked)",
        "amount_to_be_billed": "Amount to be billed in Rs. (Exl. of GST) (Masked)",
        "amount_receivable": "Amount Receivable (Masked)",
    }

    fallback_cols = {
        "collected_amount": [
            "Collected Amount in Rupees (Incl. GST.) (Masked)",
            "Collected Amount in Rupees (Incl of GST.) (Masked)",
        ],
        "billed_value": [
            "Billed Value in Rupees (Excl of GST.) (Masked)",
            "Billed Value in Rupees (Excl of GST) (Masked)",
        ],
        "amount_to_be_billed": [
            "Amount to be billed in Rs. (Exl. of GST) (Masked)",
            "Amount to be billed in Rs. (Exl. of GST.) (Masked)",
        ],
    }

    resolved = {}
    for field, default_col in amount_value_cols.items():
        col_name = default_col
        if default_col not in df.columns:
            candidates = fallback_cols.get(field, [])
            for candidate in candidates:
                if candidate in df.columns:
                    col_name = candidate
                    break
        resolved[field] = col_name

    return {
        "work_order_count": len(df),
        "total_order_value": float(number(resolved["total_order_value"]).sum()),
        "billed_value": float(number(resolved["billed_value"]).sum()),
        "collected_amount": float(number(resolved["collected_amount"]).sum()),
        "amount_to_be_billed": float(number(resolved["amount_to_be_billed"]).sum()),
        "amount_receivable": float(number(resolved["amount_receivable"]).sum()),
    }


def cross_reference_deal_to_execution(
    deals_df,
    work_orders_df,
    sector=None,
):
    """
    Compare deal pipeline and work-order execution
    for a sector.
    """

    deal_data = pipeline_summary(deals_df, sector=sector)
    work_data = work_order_financials(work_orders_df, sector=sector)

    return {
        "sector": sector or "All sectors",
        "pipeline": deal_data,
        "execution": work_data,
        "comparison": {
            "pipeline_deal_count": deal_data["deal_count"],
            "work_order_count": work_data["work_order_count"],
            "pipeline_value": deal_data["total_deal_value"],
            "executed_order_value": work_data["total_order_value"],
        },
    }


def leadership_summary(deals_df, work_orders_df):
    """
    Generate a concise leadership summary using
    deterministic BI calculations.
    """

    pipeline = pipeline_summary(deals_df)
    financials = work_order_financials(work_orders_df)

    return {
        "pipeline": pipeline,
        "work_orders": financials
    }
