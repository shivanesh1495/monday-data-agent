import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from datetime import date, timedelta

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
    "order_date": ["Date of PO/LOI", "Probable Start Date", "Probable End Date"],
    "execution_date": ["Data Delivery Date", "Probable End Date", "Probable Start Date"],
    "invoice_date": ["Last invoice date", "Expected Billing Month", "Actual Billing Month"],
    "collection_date": ["Collection Date", "Actual Collection Month", "Last invoice date"],
}


def current_reference_date():
    return date.today()


def month_range(year, month):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def quarter_range(year, quarter):
    month = ((quarter - 1) * 3) + 1
    start = date(year, month, 1)
    if quarter == 4:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 3, 1) - timedelta(days=1)
    return start, end


def get_time_window_bounds(time_window, reference_date=None):
    if not time_window:
        return None

    reference_date = reference_date or current_reference_date()

    if time_window == "this_month":
        return month_range(reference_date.year, reference_date.month)

    if time_window == "last_month":
        if reference_date.month == 1:
            return month_range(reference_date.year - 1, 12)
        return month_range(reference_date.year, reference_date.month - 1)

    if time_window == "this_quarter":
        quarter = ((reference_date.month - 1) // 3) + 1
        return quarter_range(reference_date.year, quarter)

    if time_window == "last_quarter":
        quarter = ((reference_date.month - 1) // 3) + 1
        if quarter == 1:
            return quarter_range(reference_date.year - 1, 4)
        return quarter_range(reference_date.year, quarter - 1)

    if time_window == "this_year":
        return date(reference_date.year, 1, 1), date(reference_date.year, 12, 31)

    if time_window == "last_year":
        return date(reference_date.year - 1, 1, 1), date(reference_date.year - 1, 12, 31)

    return None


def to_date_series(series):
    timestamps = pd.to_datetime(series, errors="coerce")
    return timestamps.dt.date


def effective_date_series(df, candidate_columns):
    resolved_columns = [column for column in candidate_columns if column in df.columns]
    if not resolved_columns:
        return pd.Series(pd.NaT, index=df.index), []

    combined = pd.Series(pd.NaT, index=df.index, dtype="object")
    for column in resolved_columns:
        parsed = to_date_series(df[column])
        combined = combined.where(combined.notna(), parsed)

    return combined, resolved_columns


def apply_time_window(df, time_window, candidate_columns, reference_date=None):
    if not time_window:
        return df.copy(), {
            "requested_time_window": None,
            "time_window_applied": False,
            "date_basis": [],
            "excluded_missing_date_rows": 0,
            "window_start": None,
            "window_end": None,
        }

    bounds = get_time_window_bounds(time_window, reference_date=reference_date)
    if not bounds:
        return df.copy(), {
            "requested_time_window": time_window,
            "time_window_applied": False,
            "date_basis": [],
            "excluded_missing_date_rows": 0,
            "window_start": None,
            "window_end": None,
        }

    effective_dates, resolved_columns = effective_date_series(df, candidate_columns)
    start, end = bounds
    mask = effective_dates.notna() & effective_dates.apply(lambda value: start <= value <= end)
    filtered = df.loc[mask].copy()
    excluded_missing = int(effective_dates.isna().sum())

    return filtered, {
        "requested_time_window": time_window,
        "time_window_applied": True,
        "date_basis": resolved_columns,
        "excluded_missing_date_rows": excluded_missing,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
    }


def merge_time_filter_metadata(*items):
    applied = any(item.get("time_window_applied") for item in items if item)
    requested = next(
        (item.get("requested_time_window") for item in items if item and item.get("requested_time_window")),
        None,
    )
    basis = []
    excluded = 0
    starts = []
    ends = []

    for item in items:
        if not item:
            continue
        basis.extend(item.get("date_basis", []))
        excluded += int(item.get("excluded_missing_date_rows", 0))
        if item.get("window_start"):
            starts.append(item["window_start"])
        if item.get("window_end"):
            ends.append(item["window_end"])

    deduped_basis = list(dict.fromkeys(basis))
    return {
        "requested_time_window": requested,
        "time_window_applied": applied,
        "date_basis": deduped_basis,
        "excluded_missing_date_rows": excluded,
        "window_start": min(starts) if starts else None,
        "window_end": max(ends) if ends else None,
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


def pipeline_summary(deals_df, sector=None, time_window=None, reference_date=None):
    """
    Calculate pipeline metrics from the Deals DataFrame.
    """

    df = filter_deals(deals_df, sector=sector)
    filtered_df, time_filter = apply_time_window(
        df,
        time_window,
        [
            *DEAL_COLUMN_ALIASES["close_date"],
            *DEAL_COLUMN_ALIASES["tentative_close_date"],
            *DEAL_COLUMN_ALIASES["created_date"],
        ],
        reference_date=reference_date,
    )
    df = filtered_df

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
            "time_filter": time_filter,
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
        "time_filter": time_filter,
    }


def work_order_financials(work_orders_df, sector=None, time_window=None, reference_date=None):
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
            "time_filter": {
                "requested_time_window": time_window,
                "time_window_applied": bool(time_window),
                "date_basis": [],
                "excluded_missing_date_rows": 0,
                "window_start": None,
                "window_end": None,
            },
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

    orders_df, order_time_filter = apply_time_window(
        df,
        time_window,
        WORK_ORDER_COLUMN_ALIASES["order_date"],
        reference_date=reference_date,
    )
    billed_df, billed_time_filter = apply_time_window(
        df,
        time_window,
        WORK_ORDER_COLUMN_ALIASES["invoice_date"],
        reference_date=reference_date,
    )
    collected_df, collected_time_filter = apply_time_window(
        df,
        time_window,
        WORK_ORDER_COLUMN_ALIASES["collection_date"],
        reference_date=reference_date,
    )

    return {
        "work_order_count": len(orders_df),
        "total_order_value": float(pd.to_numeric(orders_df[resolved["total_order_value"]], errors="coerce").fillna(0).sum()),
        "billed_value": float(pd.to_numeric(billed_df[resolved["billed_value"]], errors="coerce").fillna(0).sum()),
        "collected_amount": float(pd.to_numeric(collected_df[resolved["collected_amount"]], errors="coerce").fillna(0).sum()),
        "amount_to_be_billed": float(pd.to_numeric(orders_df[resolved["amount_to_be_billed"]], errors="coerce").fillna(0).sum()),
        "amount_receivable": float(pd.to_numeric(collected_df[resolved["amount_receivable"]], errors="coerce").fillna(0).sum()),
        "time_filter": merge_time_filter_metadata(
            order_time_filter,
            billed_time_filter,
            collected_time_filter,
        ),
    }


def cross_reference_deal_to_execution(
    deals_df,
    work_orders_df,
    sector=None,
    time_window=None,
    reference_date=None,
):
    """
    Compare deal pipeline and work-order execution
    for a sector.
    """

    deal_data = pipeline_summary(
        deals_df,
        sector=sector,
        time_window=time_window,
        reference_date=reference_date,
    )
    work_data = work_order_financials(
        work_orders_df,
        sector=sector,
        time_window=time_window,
        reference_date=reference_date,
    )

    return {
        "sector": sector or "All sectors",
        "requested_time_window": time_window,
        "pipeline": deal_data,
        "execution": work_data,
        "time_filter": merge_time_filter_metadata(
            deal_data.get("time_filter"),
            work_data.get("time_filter"),
        ),
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
