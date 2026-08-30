import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import pandas as pd
from dateutil import parser


def clean_text(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def fuzzy_date(value):
    if pd.isna(value) or value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    try:
        return parser.parse(value, fuzzy=True, dayfirst=False).date()
    except Exception:
        return None


def normalize_dates(df, date_columns):
    df = df.copy()

    for column in date_columns:
        if column not in df.columns:
            continue

        df[column] = df[column].apply(fuzzy_date)

    return df


def normalize_work_orders(df):
    df = df.copy()

    for column in df.columns:
        if df[column].dtype == "object":
            df[column] = df[column].apply(clean_text)

    if "Billing Status" in df.columns:
        df["Billing Status"] = df["Billing Status"].replace({"BIlled": "Billed"})

    date_columns = [
        "Data Delivery Date",
        "Date of PO/LOI",
        "Probable Start Date",
        "Probable End Date",
        "Last invoice date",
        "Collection Date",
    ]

    df = normalize_dates(df, date_columns)

    return df


def normalize_deals(df):
    df = df.copy()

    for column in df.columns:
        if df[column].dtype == "object":
            df[column] = df[column].apply(clean_text)

    header_artifacts = {
        "Deal Status": "Deal Status",
        "Closure Probability": "Closure Probability",
        "Deal Stage": "Deal Stage",
        "Product deal": "Product deal",
    }

    for column, bad_value in header_artifacts.items():
        if column in df.columns:
            df.loc[df[column] == bad_value, column] = None

    date_columns = [
        "Close Date (A)",
        "Tentative Close Date",
        "Created Date",
    ]

    df = normalize_dates(df, date_columns)

    return df


def build_quality_summary(df):
    missing = {}

    for column in df.columns:
        count = int(df[column].isna().sum())
        if count > 0:
            missing[column] = count

    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "missing_values": missing,
    }
