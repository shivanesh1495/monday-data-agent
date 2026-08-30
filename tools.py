import os
import re

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from datetime import date, timedelta

import pandas as pd

CANONICAL_SECTORS = [
    "Mining",
    "Renewables",
    "Railways",
    "Powerline",
    "Construction",
    "Others",
]


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
    "billing_status": ["Billing Status", "Invoice Status", "WO Status (billed)"],
}


def normalize_sector_name(value):
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    mapping = {sector.lower(): sector for sector in CANONICAL_SECTORS}
    mapping["renewable"] = "Renewables"
    return mapping.get(text.lower())


def normalize_client_code(value):
    if pd.isna(value):
        return None

    text = str(value).strip().upper()
    if not text:
        return None

    digits = re.search(r"(\d+)$", text)
    if digits:
        return digits.group(1).zfill(3)

    collapsed = re.sub(r"[^A-Z0-9]", "", text)
    return collapsed or None


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


def average_deal_size(deals_df, sector=None):
    """Return average and coverage details for recorded deal values."""

    df = filter_deals(deals_df, sector=sector)
    value_column = resolve_column(df, DEAL_COLUMN_ALIASES["value"])
    values = pd.to_numeric(df[value_column], errors="coerce")
    usable = values.dropna()
    coverage = float((usable.shape[0] / len(df)) * 100) if len(df) else 0.0

    return {
        "sector": sector or "All sectors",
        "deal_count": int(len(df)),
        "value_non_null_count": int(values.notna().sum()),
        "value_missing_count": int(values.isna().sum()),
        "coverage_pct": coverage,
        "average_deal_value": float(usable.mean()) if not usable.empty else None,
        "median_deal_value": float(usable.median()) if not usable.empty else None,
        "total_recorded_value": float(usable.sum()) if not usable.empty else 0.0,
    }


def closing_cycle_time(deals_df, sector=None):
    """Measure close-time coverage and observed durations for closed deals."""

    df = filter_deals(deals_df, sector=sector)
    status_column = resolve_column(df, DEAL_COLUMN_ALIASES["status"])
    created_column = resolve_column(df, DEAL_COLUMN_ALIASES["created_date"], required=False)
    close_column = resolve_column(df, DEAL_COLUMN_ALIASES["close_date"], required=False)

    status = df[status_column].astype(str).str.strip().str.lower()
    closed_df = df.loc[status.isin(["won", "dead"])].copy()

    created_dates = (
        pd.to_datetime(closed_df[created_column], errors="coerce")
        if created_column
        else pd.Series(pd.NaT, index=closed_df.index)
    )
    close_dates = (
        pd.to_datetime(closed_df[close_column], errors="coerce")
        if close_column
        else pd.Series(pd.NaT, index=closed_df.index)
    )

    days_to_close = (close_dates - created_dates).dt.days
    usable = days_to_close.dropna()
    negative_count = int((usable < 0).sum())
    coverage = float((usable.shape[0] / len(closed_df)) * 100) if len(closed_df) else 0.0

    return {
        "sector": sector or "All sectors",
        "closed_deal_count": int(len(closed_df)),
        "usable_close_time_count": int(usable.shape[0]),
        "missing_close_date_count": int(close_dates.isna().sum()),
        "missing_created_date_count": int(created_dates.isna().sum()),
        "coverage_pct": coverage,
        "average_days_to_close": float(usable.mean()) if not usable.empty else None,
        "median_days_to_close": float(usable.median()) if not usable.empty else None,
        "min_days_to_close": float(usable.min()) if not usable.empty else None,
        "max_days_to_close": float(usable.max()) if not usable.empty else None,
        "negative_duration_count": negative_count,
        "is_reliable": coverage >= 50.0 and negative_count == 0,
    }


def detect_data_entry_errors(deals_df, work_orders_df):
    """Flag rows that look like header leakage or obvious malformed records."""

    deal_sector_column = resolve_column(deals_df, DEAL_COLUMN_ALIASES["sector"], required=False)
    suspect_rows = []

    if deal_sector_column:
        critical_columns = [
            "Client Code",
            resolve_column(deals_df, DEAL_COLUMN_ALIASES["status"], required=False),
            "Closure Probability" if "Closure Probability" in deals_df.columns else None,
            resolve_column(deals_df, DEAL_COLUMN_ALIASES["stage"], required=False),
            "Product deal" if "Product deal" in deals_df.columns else None,
        ]
        critical_columns = [column for column in critical_columns if column]

        header_like_mask = pd.Series(False, index=deals_df.index)
        for column in deals_df.columns:
            header_like_mask = header_like_mask | (
                deals_df[column]
                .astype(str)
                .str.strip()
                .str.lower()
                .eq(column.strip().lower())
            )

        missing_core = deals_df[critical_columns].isna().sum(axis=1) if critical_columns else 0
        suspect_mask = header_like_mask | (missing_core >= max(3, len(critical_columns) - 1))

        suspect_df = deals_df.loc[suspect_mask].copy()
        for _, row in suspect_df.iterrows():
            reason_parts = []
            if (
                pd.notna(row.get(deal_sector_column))
                and str(row.get(deal_sector_column)).strip().lower() == deal_sector_column.strip().lower()
            ):
                reason_parts.append("sector cell contains header text")
            if critical_columns:
                blanks = [column for column in critical_columns if pd.isna(row.get(column))]
                if blanks:
                    reason_parts.append("key deal fields are blank")

            suspect_rows.append(
                {
                    "board": "Deals",
                    "item_name": row.get("item_name"),
                    "client_code": row.get("Client Code"),
                    "sector": row.get(deal_sector_column),
                    "reason": "; ".join(reason_parts) or "looks malformed",
                }
            )

    return {
        "suspect_records": suspect_rows,
        "suspect_record_count": len(suspect_rows),
    }


def cross_board_execution_gaps(deals_df, work_orders_df):
    """Compare open deals and completed work orders by normalized client code."""

    deal_code_column = resolve_column(deals_df, ["Client Code"])
    work_order_code_column = resolve_column(work_orders_df, ["Customer Name Code"])
    deal_status_column = resolve_column(deals_df, DEAL_COLUMN_ALIASES["status"])
    execution_status_column = resolve_column(work_orders_df, ["Execution Status"])

    deals = deals_df.copy()
    work_orders = work_orders_df.copy()
    deals["normalized_client_code"] = deals[deal_code_column].apply(normalize_client_code)
    work_orders["normalized_client_code"] = work_orders[work_order_code_column].apply(normalize_client_code)

    open_deals = deals.loc[
        deals[deal_status_column].astype(str).str.strip().str.lower().eq("open")
    ].copy()

    completed_statuses = {"completed", "executed until current month"}
    completed_work_orders = work_orders.loc[
        work_orders[execution_status_column]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(completed_statuses)
    ].copy()

    completed_codes = set(completed_work_orders["normalized_client_code"].dropna())
    open_codes = set(open_deals["normalized_client_code"].dropna())

    open_without_completed = open_deals.loc[
        ~open_deals["normalized_client_code"].isin(completed_codes)
    ].copy()
    completed_without_open = completed_work_orders.loc[
        ~completed_work_orders["normalized_client_code"].isin(open_codes)
    ].copy()

    return {
        "open_deal_row_count": int(len(open_deals)),
        "completed_work_order_row_count": int(len(completed_work_orders)),
        "open_clients_without_completed_work_order": sorted(
            open_without_completed["normalized_client_code"].dropna().unique().tolist()
        ),
        "completed_work_order_clients_without_open_deal": sorted(
            completed_without_open["normalized_client_code"].dropna().unique().tolist()
        ),
        "open_rows_without_completed_work_order": int(len(open_without_completed)),
        "completed_rows_without_open_deal": int(len(completed_without_open)),
        "open_gap_sample": open_without_completed[
            ["item_name", deal_code_column, resolve_column(deals_df, DEAL_COLUMN_ALIASES["sector"], required=False), "Owner code"]
        ]
        .head(10)
        .rename(
            columns={
                deal_code_column: "client_code",
                resolve_column(deals_df, DEAL_COLUMN_ALIASES["sector"], required=False): "sector",
                "Owner code": "owner_code",
            }
        )
        .to_dict(orient="records"),
        "reverse_gap_sample": completed_without_open[
            ["item_name", work_order_code_column, resolve_column(work_orders_df, WORK_ORDER_COLUMN_ALIASES["sector"], required=False), execution_status_column]
        ]
        .head(10)
        .rename(
            columns={
                work_order_code_column: "customer_name_code",
                resolve_column(work_orders_df, WORK_ORDER_COLUMN_ALIASES["sector"], required=False): "sector",
                execution_status_column: "execution_status",
            }
        )
        .to_dict(orient="records"),
        "completed_statuses_used": sorted(completed_statuses),
    }


def win_rate_by_sector(deals_df, work_orders_df=None):
    """Calculate closed-deal win rate by canonical sector and flag unmapped labels."""

    sector_column = resolve_column(deals_df, DEAL_COLUMN_ALIASES["sector"])
    status_column = resolve_column(deals_df, DEAL_COLUMN_ALIASES["status"])

    deals = deals_df.copy()
    deals["canonical_sector"] = deals[sector_column].apply(normalize_sector_name)
    status = deals[status_column].astype(str).str.strip().str.lower()

    breakdown = []
    for sector in CANONICAL_SECTORS:
        sector_df = deals.loc[deals["canonical_sector"] == sector]
        closed_df = sector_df.loc[status.loc[sector_df.index].isin(["won", "dead"])]
        won_count = int(
            closed_df[status_column].astype(str).str.strip().str.lower().eq("won").sum()
        )
        dead_count = int(
            closed_df[status_column].astype(str).str.strip().str.lower().eq("dead").sum()
        )
        closed_count = won_count + dead_count
        win_rate = (won_count / closed_count * 100.0) if closed_count else None

        breakdown.append(
            {
                "sector": sector,
                "deal_count": int(len(sector_df)),
                "closed_deal_count": int(closed_count),
                "won_deal_count": won_count,
                "dead_deal_count": dead_count,
                "win_rate_pct": float(win_rate) if win_rate is not None else None,
                "low_confidence": closed_count < 10,
            }
        )

    unmapped = deals.loc[deals["canonical_sector"].isna(), sector_column].fillna("<blank>")
    result = {
        "breakdown": breakdown,
        "excluded_unmapped_deal_rows": int(deals["canonical_sector"].isna().sum()),
        "unmapped_sector_values": unmapped.value_counts(dropna=False).to_dict(),
        "deal_distinct_sector_labels": int(deals[sector_column].fillna("<blank>").nunique(dropna=False)),
    }

    if work_orders_df is not None:
        work_sector_column = resolve_column(work_orders_df, WORK_ORDER_COLUMN_ALIASES["sector"], required=False)
        if work_sector_column:
            result["work_order_distinct_sector_labels"] = int(
                work_orders_df[work_sector_column].fillna("<blank>").nunique(dropna=False)
            )

    return result


def active_pipeline_by_owner(deals_df):
    """Rank active pipeline concentration by owner."""

    status_column = resolve_column(deals_df, DEAL_COLUMN_ALIASES["status"])
    owner_column = resolve_column(deals_df, DEAL_COLUMN_ALIASES["owner"])
    value_column = resolve_column(deals_df, DEAL_COLUMN_ALIASES["value"])

    df = deals_df.copy()
    status = df[status_column].astype(str).str.strip().str.lower()
    active_df = df.loc[status.isin(["open", "on hold"])].copy()
    active_df["deal_value"] = pd.to_numeric(active_df[value_column], errors="coerce")

    grouped = (
        active_df.groupby(owner_column, dropna=False)
        .agg(
            active_deal_count=("item_id", "count"),
            active_pipeline_value=("deal_value", "sum"),
            value_non_null_count=("deal_value", lambda series: int(series.notna().sum())),
        )
        .reset_index()
        .sort_values("active_pipeline_value", ascending=False)
    )

    total_active_deals = int(len(active_df))
    total_active_value = float(active_df["deal_value"].fillna(0).sum())
    owners = []
    for _, row in grouped.iterrows():
        deal_share = (row["active_deal_count"] / total_active_deals * 100.0) if total_active_deals else 0.0
        value_share = (row["active_pipeline_value"] / total_active_value * 100.0) if total_active_value else 0.0
        owners.append(
            {
                "owner": row[owner_column] or "<blank>",
                "active_deal_count": int(row["active_deal_count"]),
                "active_pipeline_value": float(row["active_pipeline_value"]),
                "value_non_null_count": int(row["value_non_null_count"]),
                "deal_share_pct": float(deal_share),
                "value_share_pct": float(value_share),
            }
        )

    return {
        "owners": owners,
        "total_active_deals": total_active_deals,
        "total_active_pipeline_value": total_active_value,
    }


def billing_status_missing_fraction(work_orders_df):
    """Measure how many work orders have no billing status recorded."""

    status_column = resolve_column(work_orders_df, WORK_ORDER_COLUMN_ALIASES["billing_status"])
    status = work_orders_df[status_column]
    missing_mask = status.isna() | status.astype(str).str.strip().eq("")
    missing_count = int(missing_mask.sum())
    total_count = int(len(work_orders_df))
    fraction = (missing_count / total_count * 100.0) if total_count else 0.0

    return {
        "status_column": status_column,
        "missing_count": missing_count,
        "total_count": total_count,
        "missing_fraction_pct": float(fraction),
    }


def receivable_anomalies(work_orders_df):
    """Flag unusual receivable values, with negatives highlighted first."""

    receivable_column = resolve_column(work_orders_df, WORK_ORDER_COLUMN_ALIASES["amount_receivable"])
    code_column = resolve_column(work_orders_df, ["Customer Name Code"], required=False)
    values = pd.to_numeric(work_orders_df[receivable_column], errors="coerce")
    negative_df = work_orders_df.loc[values < 0].copy()
    negative_df["receivable_value"] = values.loc[negative_df.index]

    positive_values = values.loc[values >= 0].dropna()
    upper_outlier_threshold = None
    positive_outliers = pd.DataFrame(columns=work_orders_df.columns)

    if not positive_values.empty:
        q1 = positive_values.quantile(0.25)
        q3 = positive_values.quantile(0.75)
        iqr = q3 - q1
        upper_outlier_threshold = float(q3 + (1.5 * iqr))
        positive_outliers = work_orders_df.loc[values > upper_outlier_threshold].copy()
        positive_outliers["receivable_value"] = values.loc[positive_outliers.index]

    return {
        "negative_count": int(len(negative_df)),
        "material_negative_count": int((negative_df["receivable_value"] < -1).sum()) if not negative_df.empty else 0,
        "largest_negative_value": float(negative_df["receivable_value"].min()) if not negative_df.empty else None,
        "negative_records": negative_df[
            ["item_name", code_column, receivable_column, "receivable_value"]
        ]
        .head(10)
        .rename(
            columns={
                code_column: "customer_name_code",
                receivable_column: "raw_receivable_value",
            }
        )
        .to_dict(orient="records"),
        "positive_outlier_threshold": upper_outlier_threshold,
        "positive_outlier_count": int(len(positive_outliers)),
        "positive_outliers": positive_outliers[
            ["item_name", code_column, receivable_column, "receivable_value"]
        ]
        .head(10)
        .rename(
            columns={
                code_column: "customer_name_code",
                receivable_column: "raw_receivable_value",
            }
        )
        .to_dict(orient="records"),
    }
