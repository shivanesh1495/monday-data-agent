import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import pandas as pd


def resolve_column(df, candidates, required=True):
    """Return the first available column from a list of aliases."""

    for candidate in candidates:
        if candidate in df.columns:
            return candidate

    if required:
        available = ", ".join(df.columns)
        names = ", ".join(candidates)
        raise KeyError(f"None of the expected columns were found: {names}. Available: {available}")

    return None


DEAL_COLUMN_ALIASES = {
    "sector": ["Sector/service", "Sector", "Sector Service"],
    "status": ["Deal Status", "Status"],
    "stage": ["Deal Stage", "Stage"],
    "owner": ["Owner code", "Owner", "Owner Code"],
    "value": ["Masked Deal value", "Deal Value", "Deal value"],
    "close_date": ["Close Date (A)", "Close Date"],
    "tentative_close_date": ["Tentative Close Date", "Tentative close date"],
    "created_date": ["Created Date", "Created date"],
}

WORK_ORDER_COLUMN_ALIASES = {
    "sector": ["Sector", "Sector/service", "Sector Service"],
    "total_order_value": [
        "Amount in Rupees (Excl of GST) (Masked)",
        "Order Value",
        "Amount in Rupees (Excl. of GST) (Masked)",
    ],
    "billed_value": [
        "Billed Value in Rupees (Excl of GST.) (Masked)",
        "Billed Value in Rupees (Excl of GST) (Masked)",
        "Billed",
    ],
    "collected_amount": [
        "Collected Amount in Rupees (Incl of GST.) (Masked)",
        "Collected Amount in Rupees (Incl. GST.) (Masked)",
        "Collected",
    ],
    "amount_to_be_billed": [
        "Amount to be billed in Rs. (Exl. of GST) (Masked)",
        "Amount to be billed in Rs. (Exl. of GST.) (Masked)",
        "Amount To Be Billed",
    ],
    "amount_receivable": [
        "Amount Receivable (Masked)",
        "Receivable",
        "Amount Receivable",
    ],
}


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
    sector_column = resolve_column(df, DEAL_COLUMN_ALIASES["sector"], required=False)
    status_column = resolve_column(df, DEAL_COLUMN_ALIASES["status"], required=False)
    stage_column = resolve_column(df, DEAL_COLUMN_ALIASES["stage"], required=False)
    owner_column = resolve_column(df, DEAL_COLUMN_ALIASES["owner"], required=False)

    if sector and sector_column:
        df = df[
            df[sector_column]
            .astype(str)
            .str.strip()
            .str.lower()
            == sector.strip().lower()
        ]

    if status and status_column:
        df = df[
            df[status_column]
            .astype(str)
            .str.strip()
            .str.lower()
            == status.strip().lower()
        ]

    if stage and stage_column:
        df = df[
            df[stage_column]
            .astype(str)
            .str.strip()
            .str.lower()
            == stage.strip().lower()
        ]

    if owner and owner_column:
        df = df[
            df[owner_column]
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

    value_column = resolve_column(df, DEAL_COLUMN_ALIASES["value"])
    status_column = resolve_column(df, DEAL_COLUMN_ALIASES["status"])
    value = pd.to_numeric(df[value_column], errors="coerce")
    status = df[status_column].astype(str).str.strip().str.lower()

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
    sector_column = resolve_column(df, WORK_ORDER_COLUMN_ALIASES["sector"], required=False)

    if sector and sector_column:
        df = df[
            df[sector_column]
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

    resolved = {}
    for field in [
        "total_order_value",
        "billed_value",
        "collected_amount",
        "amount_to_be_billed",
        "amount_receivable",
    ]:
        resolved[field] = resolve_column(df, WORK_ORDER_COLUMN_ALIASES[field])

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
    time_window=None,
):
    """
    Compare deal pipeline and work-order execution
    for a sector.
    """

    deal_data = pipeline_summary(deals_df, sector=sector)
    work_data = work_order_financials(work_orders_df, sector=sector)

    return {
        "sector": sector or "All sectors",
        "requested_time_window": time_window,
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
