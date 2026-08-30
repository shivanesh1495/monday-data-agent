import html
import os
import re
from datetime import datetime
from textwrap import dedent

import streamlit as st

from agent import create_agent
from monday_client import MondayClient
from normalize import (
    build_quality_summary,
    normalize_deals,
    normalize_work_orders,
)
from tools import leadership_summary

st.set_page_config(
    page_title="Skylark",
    page_icon="S",
    layout="centered",
)

HISTORY_ICON = """
<svg viewBox="0 0 24 24" aria-hidden="true">
  <path d="M4 12a8 8 0 1 0 2.4-5.7" />
  <path d="M4 4v5h5" />
  <path d="M12 8v4l2.7 2.2" />
</svg>
"""

SPARK_ICON = """
<svg viewBox="0 0 24 24" aria-hidden="true">
  <path d="M8 6l2.2 4.8L15 13l-4.8 2.2L8 20l-2.2-4.8L1 13l4.8-2.2L8 6Z" />
  <path d="M18 5l.9 1.9L21 8l-2.1 1.1L18 11l-.9-1.9L15 8l2.1-1.1L18 5Z" />
</svg>
"""

BAR_ICON = """
<svg viewBox="0 0 24 24" aria-hidden="true">
  <path d="M5 18V9" />
  <path d="M11 18V5" />
  <path d="M17 18v-7" />
  <path d="M4 18h15" />
</svg>
"""

st.markdown(
    dedent(
        """
    <style>
        :root {
            --bg: #05090d;
            --bg-soft: #0b1016;
            --content-width: 44rem;
            --command-width: 34rem;
            --line: rgba(149, 162, 178, 0.20);
            --text: #e7edf3;
            --muted: #7e8a96;
            --muted-strong: #aab6c2;
            --accent: #18d9f7;
            --shadow: 0 18px 44px rgba(0, 0, 0, 0.32);
            --shadow-soft: 0 10px 24px rgba(0, 0, 0, 0.22);
            --shadow-float: 0 18px 46px rgba(0, 0, 0, 0.44);
        }

        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stApp"] {
            background:
                radial-gradient(circle at top, rgba(10, 18, 24, 0.92), transparent 44%),
                linear-gradient(180deg, #0a1016 0%, var(--bg) 28%, #04070b 100%);
            color: var(--text);
            font-family: "Segoe UI", "Trebuchet MS", sans-serif;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {
            display: none !important;
        }

        .stApp {
            padding-top: 0;
        }

        .block-container {
            max-width: var(--content-width);
            padding-top: 0;
            padding-left: 1.1rem;
            padding-right: 1.1rem;
            padding-bottom: 10rem;
        }

        .topbar-shell {
            position: sticky;
            top: 0;
            z-index: 30;
            margin: 0 -1.1rem 1.2rem -1.1rem;
            padding: 0.9rem 1.1rem 0.8rem 1.1rem;
            background: linear-gradient(180deg, rgba(10, 16, 22, 0.97), rgba(10, 16, 22, 0.88));
            border-bottom: 1px solid rgba(142, 153, 168, 0.10);
            backdrop-filter: blur(16px);
        }

        .topbar {
            display: grid;
            grid-template-columns: 44px 1fr 44px;
            align-items: center;
            gap: 0.35rem;
            min-height: 44px;
        }

        .topbar-icon,
        .topbar-button {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            width: 100%;
            color: #cfd7df;
        }

        .topbar-icon svg,
        .state-icon svg,
        .snapshot-head svg {
            width: 24px;
            height: 24px;
            stroke: currentColor;
            stroke-width: 1.8;
            fill: none;
            stroke-linecap: round;
            stroke-linejoin: round;
        }

        .brand {
            text-align: center;
            font-size: 1.9rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            color: var(--accent);
            text-shadow: 0 0 18px rgba(24, 217, 247, 0.18);
        }

        .topbar-button .stButton > button {
            min-width: 32px;
            width: 32px;
            height: 32px;
            padding: 0;
            border: none;
            background: transparent;
            box-shadow: none;
            color: #cfd7df;
            font-size: 1.45rem;
            line-height: 1;
        }

        .topbar-button .stButton {
            margin: 0;
        }

        .topbar-button .stButton > button:hover {
            background: rgba(255, 255, 255, 0.04);
            border: none;
            color: #eef7fb;
        }

        .topbar-button .stButton > button:focus,
        .topbar-button .stButton > button:focus-visible {
            border: none;
            box-shadow: 0 0 0 1px rgba(34, 225, 255, 0.24);
        }

        .assistant-shell,
        .message-card,
        .composer-banner {
            background: linear-gradient(180deg, rgba(18, 24, 31, 0.98), rgba(15, 20, 27, 0.96));
            border: 1px solid rgba(142, 153, 168, 0.18);
            border-radius: 14px;
            box-shadow: var(--shadow-soft);
        }

        .assistant-shell {
            position: relative;
            margin-bottom: 0.95rem;
            padding: 1.35rem 1.35rem 1.25rem 1.35rem;
            overflow: hidden;
        }

        .assistant-shell::before,
        .loading-card::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            background: linear-gradient(180deg, #22e1ff, rgba(34, 225, 255, 0.30));
        }

        .intro-copy {
            font-size: 1.02rem;
            line-height: 1.42;
            color: var(--text);
            margin-bottom: 1.1rem;
        }

        .snapshot-card {
            padding: 1rem 1rem 0.95rem 1rem;
            border-radius: 18px;
            background: linear-gradient(180deg, rgba(31, 37, 45, 0.92), rgba(27, 33, 41, 0.94));
            border: 1px solid rgba(142, 153, 168, 0.12);
        }

        .snapshot-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.9rem;
            color: #d3d9df;
            font-family: Consolas, "Courier New", monospace;
            font-size: 0.78rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
        }

        .snapshot-head svg {
            color: var(--accent);
        }

        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
        }

        .kpi-label {
            color: #cbd4dc;
            font-size: 0.95rem;
            margin-bottom: 0.25rem;
        }

        .kpi-value {
            color: #dff9ff;
            font-size: 1.95rem;
            line-height: 1;
            letter-spacing: -0.04em;
            font-weight: 600;
            margin-bottom: 0.35rem;
        }

        .kpi-note {
            font-size: 0.95rem;
            color: #8feaff;
            font-weight: 600;
        }

        .kpi-note-muted {
            color: #ffb7b0;
        }

        .meta-line {
            margin: 0.35rem 0 1.3rem 0.4rem;
            color: var(--muted);
            font-family: Consolas, "Courier New", monospace;
            letter-spacing: 0.08em;
            font-size: 0.92rem;
        }

        .panel-title {
            color: #d5eff5;
            font-size: 1.15rem;
            line-height: 1.24;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }

        .panel-copy {
            color: #bac4cf;
            line-height: 1.5;
            margin-bottom: 1rem;
        }

        .chart-frame {
            padding: 1rem;
            border-radius: 18px;
            border: 1px solid rgba(142, 153, 168, 0.14);
            background: linear-gradient(180deg, rgba(33, 39, 46, 0.90), rgba(28, 34, 41, 0.92));
        }

        .chart-label {
            color: #9ca8b4;
            font-family: Consolas, "Courier New", monospace;
            font-size: 0.92rem;
            letter-spacing: 0.04em;
            margin-bottom: 0.85rem;
        }

        .mini-chart {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.85rem;
            align-items: end;
            min-height: 210px;
        }

        .bar-group {
            display: flex;
            flex-direction: column;
            gap: 0.55rem;
            height: 100%;
        }

        .bar-shell {
            position: relative;
            height: 138px;
            display: flex;
            align-items: end;
            padding: 0 0.2rem;
        }

        .bar-fill {
            width: 100%;
            border-radius: 8px 8px 2px 2px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        .tone-a,
        .tone-c {
            background: linear-gradient(180deg, rgba(36, 211, 241, 0.90), rgba(36, 211, 241, 0.34));
        }

        .tone-b,
        .tone-d {
            background: linear-gradient(180deg, rgba(160, 152, 209, 0.90), rgba(160, 152, 209, 0.36));
        }

        .bar-label,
        .bar-value {
            color: #dbe4ec;
            font-size: 0.86rem;
        }

        .bar-value {
            color: #aab6c2;
        }

        .empty-chart {
            padding: 2rem 0.5rem 0.25rem 0.5rem;
            color: var(--muted);
            line-height: 1.5;
        }

        .notice-card {
            margin-bottom: 0.9rem;
            padding: 0.95rem 1rem;
            border-radius: 18px;
            border: 1px solid rgba(142, 153, 168, 0.14);
            background: rgba(26, 31, 38, 0.88);
            color: var(--muted-strong);
        }

        .notice-card strong {
            color: var(--text);
        }

        .stButton > button,
        .stDownloadButton > button {
            width: 100%;
            height: 3rem;
            border-radius: 999px;
            border: 1px solid rgba(142, 153, 168, 0.18);
            background: linear-gradient(180deg, rgba(32, 38, 46, 0.96), rgba(23, 28, 35, 0.98));
            color: var(--text);
            font-size: 0.9rem;
            font-weight: 500;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: rgba(34, 225, 255, 0.42);
            color: #ebfbff;
        }

        .summary-shell {
            margin-top: 1rem;
        }

        .message-state {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            margin-bottom: 0.85rem;
            color: #d8dde5;
            font-size: 0.88rem;
        }

        .state-icon {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 18px;
            height: 18px;
            color: #c6adff;
        }

        .report-title {
            font-size: 1.4rem;
            line-height: 1.18;
            font-weight: 700;
            margin-bottom: 0.35rem;
            color: #d7f5ff;
        }

        .report-subcopy {
            color: #bcc7d2;
            line-height: 1.5;
            margin-bottom: 1rem;
        }

        .report-section {
            margin-top: 1rem;
            padding: 0.95rem 1rem;
            border-radius: 18px;
            border: 1px solid rgba(142, 153, 168, 0.14);
            background: rgba(31, 37, 45, 0.76);
        }

        .report-section h4 {
            margin: 0 0 0.8rem 0;
            color: #d9e6f3;
            font-size: 0.98rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            font-family: Consolas, "Courier New", monospace;
            font-weight: 500;
        }

        .report-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.8rem;
        }

        .report-stat {
            padding: 0.75rem 0.8rem;
            border-radius: 14px;
            background: rgba(14, 19, 25, 0.74);
            border: 1px solid rgba(142, 153, 168, 0.10);
        }

        .report-stat span {
            display: block;
            color: #99a6b2;
            font-size: 0.82rem;
            margin-bottom: 0.28rem;
        }

        .report-stat strong {
            color: #edf5fb;
            font-size: 1.02rem;
            font-weight: 600;
        }

        .report-footnote {
            margin-top: 1rem;
            color: #9eb0bf;
            line-height: 1.5;
            font-size: 0.92rem;
        }

        .conversation-turn {
            margin-top: 1.1rem;
        }

        .assistant-turn .message-card,
        .user-turn .message-card {
            position: relative;
            padding: 1.1rem 1.1rem 1rem 1.1rem;
        }

        .assistant-turn .message-card {
            margin-right: 0.85rem;
            overflow: hidden;
        }

        .assistant-turn .message-card::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            background: linear-gradient(180deg, #22e1ff, rgba(34, 225, 255, 0.28));
        }

        .user-turn {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }

        .user-turn .message-card {
            width: min(100%, 28rem);
            background: linear-gradient(180deg, rgba(58, 63, 72, 0.98), rgba(52, 57, 66, 0.98));
            border-color: rgba(164, 173, 185, 0.16);
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.24);
        }

        .message-copy {
            color: #e4ebf2;
            line-height: 1.55;
            font-size: 1rem;
            white-space: pre-wrap;
        }

        .message-body {
            color: #dfe7ef;
            line-height: 1.65;
            font-size: 1rem;
        }

        .message-body > *:first-child {
            margin-top: 0;
        }

        .message-body > *:last-child {
            margin-bottom: 0;
        }

        .message-body p,
        .message-body ul,
        .message-body ol,
        .message-body table,
        .message-body blockquote {
            margin: 0 0 1rem 0;
        }

        .message-body h1,
        .message-body h2,
        .message-body h3,
        .message-body h4 {
            margin: 1.1rem 0 0.6rem 0;
            color: #e9f6fb;
            line-height: 1.25;
        }

        .message-body h1 {
            font-size: 1.35rem;
        }

        .message-body h2 {
            font-size: 1.2rem;
        }

        .message-body h3,
        .message-body h4 {
            font-size: 1.05rem;
        }

        .message-body strong {
            color: #f4fbff;
            font-weight: 700;
        }

        .message-body ul,
        .message-body ol {
            padding-left: 1.2rem;
        }

        .message-body li {
            margin-bottom: 0.35rem;
        }

        .message-body code {
            padding: 0.1rem 0.35rem;
            border-radius: 6px;
            background: rgba(148, 163, 184, 0.12);
            color: #c8f6ff;
            font-family: Consolas, "Courier New", monospace;
            font-size: 0.92em;
        }

        .message-body blockquote {
            padding: 0.8rem 1rem;
            border-left: 3px solid rgba(34, 225, 255, 0.65);
            border-radius: 0 14px 14px 0;
            background: rgba(255, 255, 255, 0.03);
            color: #c9d4de;
        }

        .message-table {
            width: 100%;
            border-collapse: collapse;
            overflow: hidden;
            border-radius: 14px;
            border: 1px solid rgba(142, 153, 168, 0.14);
            background: rgba(255, 255, 255, 0.02);
        }

        .message-table th,
        .message-table td {
            padding: 0.75rem 0.8rem;
            text-align: left;
            vertical-align: top;
            border-bottom: 1px solid rgba(142, 153, 168, 0.10);
        }

        .message-table th {
            color: #dff9ff;
            font-weight: 600;
            background: rgba(34, 225, 255, 0.08);
        }

        .message-table tr:last-child td {
            border-bottom: none;
        }

        .message-meta {
            margin-top: 0.45rem;
            padding-left: 0.35rem;
            color: var(--muted);
            font-family: Consolas, "Courier New", monospace;
            letter-spacing: 0.08em;
            font-size: 0.9rem;
        }

        .message-meta-right {
            padding-left: 0;
            padding-right: 0.35rem;
        }

        .meta-dot {
            opacity: 0.6;
            margin: 0 0.15rem;
        }

        .composer-banner {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            margin-top: 1.1rem;
            margin-bottom: 1.35rem;
            padding: 0.8rem 1rem;
            color: #c9eff9;
            font-family: Consolas, "Courier New", monospace;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            font-size: 0.82rem;
            opacity: 0.92;
        }

        .status-dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: #c7f4ff;
            box-shadow: 0 0 0 5px rgba(24, 217, 247, 0.08);
        }

        [data-testid="stBottom"] {
            background: transparent !important;
            display: flex;
            justify-content: center;
            pointer-events: none;
        }

        [data-testid="stBottom"] > div {
            width: calc(100% - 2.2rem) !important;
            max-width: var(--command-width) !important;
            min-width: 0 !important;
            flex: 0 1 var(--command-width) !important;
            margin: 0 auto;
            padding: 0 0 1.25rem 0;
            background: transparent !important;
        }

        [data-testid="stBottomBlockContainer"] {
            width: 100%;
            max-width: none;
            padding: 0 !important;
            background: transparent !important;
            pointer-events: auto;
        }

        [data-testid="stBottom"] .stElementContainer,
        [data-testid="stBottom"] [data-testid="stVerticalBlock"],
        [data-testid="stBottom"] [data-testid="stVerticalBlockBorderWrapper"] {
            width: 100% !important;
            max-width: none !important;
        }

        .stChatInput {
            position: relative;
            bottom: auto;
            z-index: 35;
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 auto !important;
            padding: 0.28rem;
            border-radius: 16px;
            background: rgba(8, 12, 17, 0.58);
            border: 1px solid rgba(151, 170, 188, 0.14);
            box-shadow:
                var(--shadow-float),
                0 0 24px rgba(24, 217, 247, 0.08);
            backdrop-filter: blur(18px);
        }

        .stChatInput > div {
            min-height: 2.85rem;
            border-radius: 12px;
            border: 1px solid rgba(124, 211, 255, 0.12);
            background:
                radial-gradient(circle at calc(100% - 2rem) 50%, rgba(24, 217, 247, 0.20), transparent 22%),
                linear-gradient(180deg, rgba(16, 21, 28, 0.98), rgba(12, 17, 23, 0.96));
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.04),
                inset 0 -1px 0 rgba(0, 0, 0, 0.30);
        }

        .stChatInput textarea {
            color: var(--text) !important;
            background: transparent !important;
            font-size: 0.95rem;
            line-height: 1.45;
            padding-left: 0.85rem !important;
            padding-right: 0.5rem !important;
        }

        .stChatInput textarea::placeholder {
            color: #768290 !important;
        }

        .stChatInput button {
            border: none !important;
            border-radius: 50% !important;
            background: linear-gradient(180deg, #1be0fb, #09c9ea) !important;
            color: #051117 !important;
            margin-right: 0.5rem !important;
            box-shadow:
                0 9px 20px rgba(24, 217, 247, 0.28),
                0 0 14px rgba(24, 217, 247, 0.20);
            transform: translateY(0);
            align-self: center !important;
        }

        .loading-card {
            position: relative;
            overflow: hidden;
            margin-right: 1.2rem;
            padding-top: 1rem !important;
        }

        .pulse-bar {
            margin-top: 0.35rem;
            height: 3px;
            width: 32%;
            border-radius: 999px;
            background: linear-gradient(90deg, #9cf5ff, #a98ef0);
        }

        @media (max-width: 640px) {
            .block-container {
                padding-left: 0.75rem;
                padding-right: 0.75rem;
                padding-bottom: 9rem;
            }

            .topbar-shell {
                margin-left: -0.75rem;
                margin-right: -0.75rem;
            }

            .assistant-shell,
            .assistant-turn .message-card,
            .user-turn .message-card {
                margin-right: 0;
            }

            [data-testid="stBottom"] > div {
                width: calc(100% - 1.5rem) !important;
                max-width: 100% !important;
                flex-basis: calc(100% - 1.5rem) !important;
                padding: 0 0 0.9rem 0;
            }

            .stChatInput {
                width: 100%;
                padding: 0.28rem;
            }

            .kpi-grid,
            .report-grid,
            .mini-chart {
                grid-template-columns: 1fr;
            }

            .bar-shell {
                height: 110px;
            }
        }
    </style>
    """
    ).strip(),
    unsafe_allow_html=True,
)


def zero_pipeline_summary():
    return {
        "deal_count": 0,
        "total_deal_value": 0.0,
        "active_pipeline_value": 0.0,
        "won_value": 0.0,
        "dead_value": 0.0,
        "on_hold_value": 0.0,
        "open_deals": 0,
        "won_deals": 0,
        "dead_deals": 0,
        "on_hold_deals": 0,
    }


def zero_work_order_summary():
    return {
        "work_order_count": 0,
        "total_order_value": 0.0,
        "billed_value": 0.0,
        "collected_amount": 0.0,
        "amount_to_be_billed": 0.0,
        "amount_receivable": 0.0,
    }


@st.cache_data(ttl=300)
def load_data():
    client = MondayClient()

    work_order_id = os.getenv("WORK_ORDER_BOARD_ID")
    deal_id = os.getenv("DEAL_FUNNEL_BOARD_ID")

    if not work_order_id:
        raise ValueError("WORK_ORDER_BOARD_ID is missing")

    if not deal_id:
        raise ValueError("DEAL_FUNNEL_BOARD_ID is missing")

    work_orders = client.board_to_dataframe(work_order_id)
    deals = client.board_to_dataframe(deal_id)

    work_orders = normalize_work_orders(work_orders)
    deals = normalize_deals(deals)

    work_quality = build_quality_summary(work_orders)
    deal_quality = build_quality_summary(deals)

    return work_orders, deals, work_quality, deal_quality


def build_agent(
    deals_df,
    work_orders_df,
    work_quality,
    deal_quality,
    conversation_state=None,
    data_context=None,
):
    return create_agent(
        deals_df=deals_df,
        work_orders_df=work_orders_df,
        work_order_quality=work_quality,
        deal_quality=deal_quality,
        conversation_state=conversation_state,
        data_context=data_context,
    )


def now_label():
    return datetime.now().strftime("%I:%M %p")


def safe_ratio(numerator, denominator):
    if not denominator:
        return 0.0
    return (numerator / denominator) * 100


def format_money(value):
    if value is None:
        return "--"

    value = float(value)
    magnitude = abs(value)

    if magnitude >= 1_000_000_000:
        return f"Rs.{value / 1_000_000_000:.1f}B"
    if magnitude >= 1_000_000:
        return f"Rs.{value / 1_000_000:.1f}M"
    if magnitude >= 1_000:
        return f"Rs.{value / 1_000:.1f}K"

    return f"Rs.{value:,.0f}"


def format_precise_money(value):
    if value is None:
        return "--"
    return f"Rs.{float(value):,.2f}"


def format_percent(value):
    if value is None:
        return "--"
    return f"{float(value):.1f}%"


def escape_copy(text):
    return html.escape(str(text) if text is not None else "")


def html_block(markup):
    return dedent(markup).strip()


def format_inline_markdown(text):
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped


def split_table_row(line):
    trimmed = line.strip().strip("|")
    return [cell.strip() for cell in trimmed.split("|")]


def is_table_separator(line):
    stripped = line.strip()
    if "|" not in stripped:
        return False
    parts = [part.strip() for part in stripped.strip("|").split("|")]
    if not parts:
        return False
    return all(part and set(part) <= {"-", ":"} for part in parts)


def render_markdown_content(content):
    lines = str(content).replace("\r\n", "\n").split("\n")
    blocks = []
    index = 0

    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = format_inline_markdown(heading_match.group(2).strip())
            blocks.append(f"<h{level}>{text}</h{level}>")
            index += 1
            continue

        if stripped.startswith(">"):
            quote_lines = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(lines[index].strip()[1:].strip())
                index += 1
            quote_html = "<br>".join(format_inline_markdown(part) for part in quote_lines)
            blocks.append(f"<blockquote>{quote_html}</blockquote>")
            continue

        if (
            index + 1 < len(lines)
            and "|" in stripped
            and is_table_separator(lines[index + 1])
        ):
            header_cells = split_table_row(lines[index])
            row_html = []
            index += 2

            while index < len(lines):
                row_line = lines[index].strip()
                if not row_line or "|" not in row_line:
                    break
                row_cells = split_table_row(lines[index])
                row_html.append(
                    "<tr>"
                    + "".join(f"<td>{format_inline_markdown(cell)}</td>" for cell in row_cells)
                    + "</tr>"
                )
                index += 1

            header_html = "".join(
                f"<th>{format_inline_markdown(cell)}</th>" for cell in header_cells
            )
            blocks.append(
                "<table class='message-table'>"
                f"<thead><tr>{header_html}</tr></thead>"
                f"<tbody>{''.join(row_html)}</tbody>"
                "</table>"
            )
            continue

        unordered_match = re.match(r"^[-*]\s+(.*)$", stripped)
        ordered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if unordered_match or ordered_match:
            is_ordered = bool(ordered_match)
            tag = "ol" if is_ordered else "ul"
            items = []

            while index < len(lines):
                current = lines[index].strip()
                pattern = r"^\d+\.\s+(.*)$" if is_ordered else r"^[-*]\s+(.*)$"
                match = re.match(pattern, current)
                if not match:
                    break
                items.append(f"<li>{format_inline_markdown(match.group(1).strip())}</li>")
                index += 1

            blocks.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        paragraph_lines = [stripped]
        index += 1

        while index < len(lines):
            lookahead = lines[index].strip()
            if not lookahead:
                index += 1
                break
            if re.match(r"^(#{1,4})\s+", lookahead):
                break
            if lookahead.startswith(">"):
                break
            if re.match(r"^[-*]\s+", lookahead):
                break
            if re.match(r"^\d+\.\s+", lookahead):
                break
            if (
                index + 1 < len(lines)
                and "|" in lookahead
                and is_table_separator(lines[index + 1])
            ):
                break
            paragraph_lines.append(lookahead)
            index += 1

        paragraph_html = " ".join(format_inline_markdown(part) for part in paragraph_lines)
        blocks.append(f"<p>{paragraph_html}</p>")

    return f"<div class='message-body'>{''.join(blocks)}</div>"


def missing_count(summary_map, *keys):
    for key in keys:
        if key in summary_map:
            return int(summary_map[key])
    return 0


def build_chart_markup(items, live_data):
    if not live_data:
        return (
            "<div class='empty-chart'>"
            "Live monday.com metrics will appear here once the board sync succeeds."
            "</div>"
        )

    max_value = max((item["value"] for item in items), default=0) or 1
    groups = []

    for item in items:
        height = max(18, round((item["value"] / max_value) * 100))
        groups.append(
            (
                "<div class='bar-group'>"
                f"<div class='bar-label'>{escape_copy(item['label'])}</div>"
                "<div class='bar-shell'>"
                f"<div class='bar-fill {escape_copy(item['tone'])}' style='height: {height}%;'></div>"
                "</div>"
                f"<div class='bar-value'>{escape_copy(format_money(item['value']))}</div>"
                "</div>"
            )
        )

    return f"<div class='mini-chart'>{''.join(groups)}</div>"


def report_stat(label, value):
    return (
        "<div class='report-stat'>"
        f"<span>{escape_copy(label)}</span>"
        f"<strong>{escape_copy(value)}</strong>"
        "</div>"
    )


def build_summary_markdown(summary, deals_df, work_orders_df, deal_quality, work_quality):
    pipeline = summary["pipeline"]
    financials = summary["work_orders"]
    deal_missing = deal_quality.get("missing_values", {}) if deal_quality else {}
    work_missing = work_quality.get("missing_values", {}) if work_quality else {}

    return f"""
# Leadership Summary

## Deal Pipeline

- Total deals: {pipeline["deal_count"]}
- Total deal value: {format_precise_money(pipeline["total_deal_value"])}
- Active pipeline value: {format_precise_money(pipeline["active_pipeline_value"])}
- Open deals: {pipeline["open_deals"]}
- Won value: {format_precise_money(pipeline["won_value"])}
- Dead value: {format_precise_money(pipeline["dead_value"])}
- On-hold value: {format_precise_money(pipeline["on_hold_value"])}

## Work Orders

- Work orders: {financials["work_order_count"]}
- Total order value: {format_precise_money(financials["total_order_value"])}
- Billed value: {format_precise_money(financials["billed_value"])}
- Collected amount: {format_precise_money(financials["collected_amount"])}
- Amount to be billed: {format_precise_money(financials["amount_to_be_billed"])}
- Amount receivable: {format_precise_money(financials["amount_receivable"])}

## Data Quality

### Deals
- {len(deals_df)} total records
- Close Date missing in {missing_count(deal_missing, 'Close Date (A)')} records
- Closure Probability missing in {missing_count(deal_missing, 'Closure Probability')} records
- No values were imputed

### Work Orders
- {len(work_orders_df)} total records
- Expected Billing Month missing in {missing_count(work_missing, 'Expected Billing Month')} records
- Actual Collection Month missing in {missing_count(work_missing, 'Actual Collection Month')} records
- Collection Status missing in {missing_count(work_missing, 'Collection status')} records
- Collection Date missing in {missing_count(work_missing, 'Collection Date')} records
- No values were imputed

> On-hold deal value: {format_precise_money(pipeline["on_hold_value"])} based on available deal-value data; missing deal values were not imputed.
""".strip()


def build_summary_html(summary, deals_df, work_orders_df, deal_quality, work_quality):
    pipeline = summary["pipeline"]
    financials = summary["work_orders"]
    deal_missing = deal_quality.get("missing_values", {}) if deal_quality else {}
    work_missing = work_quality.get("missing_values", {}) if work_quality else {}

    pipeline_cards = "".join(
        [
            report_stat("Total Deals", pipeline["deal_count"]),
            report_stat("Total Deal Value", format_precise_money(pipeline["total_deal_value"])),
            report_stat("Active Pipeline", format_precise_money(pipeline["active_pipeline_value"])),
            report_stat("Open Deals", pipeline["open_deals"]),
            report_stat("Won Value", format_precise_money(pipeline["won_value"])),
            report_stat("On-Hold Value", format_precise_money(pipeline["on_hold_value"])),
        ]
    )

    work_cards = "".join(
        [
            report_stat("Work Orders", financials["work_order_count"]),
            report_stat("Total Order Value", format_precise_money(financials["total_order_value"])),
            report_stat("Billed Value", format_precise_money(financials["billed_value"])),
            report_stat("Collected Amount", format_precise_money(financials["collected_amount"])),
            report_stat("To Be Billed", format_precise_money(financials["amount_to_be_billed"])),
            report_stat("Receivable", format_precise_money(financials["amount_receivable"])),
        ]
    )

    quality_cards = "".join(
        [
            report_stat("Deal Rows", len(deals_df)),
            report_stat(
                "Deals Missing Close Date",
                missing_count(deal_missing, "Close Date (A)"),
            ),
            report_stat(
                "Deals Missing Closure Probability",
                missing_count(deal_missing, "Closure Probability"),
            ),
            report_stat("Work Order Rows", len(work_orders_df)),
            report_stat(
                "Missing Expected Billing Month",
                missing_count(work_missing, "Expected Billing Month"),
            ),
            report_stat(
                "Missing Collection Date",
                missing_count(work_missing, "Collection Date"),
            ),
        ]
    )

    return html_block(
        f"""
<div class="assistant-shell summary-shell">
    <div class="message-state">
        <span class="state-icon">{SPARK_ICON}</span>
        <span>Leadership summary ready</span>
    </div>
    <div class="report-title">Executive Leadership Summary</div>
    <div class="report-subcopy">
        A compact view of the live monday.com pipeline, order-book health, and data quality caveats.
    </div>
    <div class="report-section">
        <h4>Deal Pipeline</h4>
        <div class="report-grid">{pipeline_cards}</div>
    </div>
    <div class="report-section">
        <h4>Work Orders</h4>
        <div class="report-grid">{work_cards}</div>
    </div>
    <div class="report-section">
        <h4>Data Quality</h4>
        <div class="report-grid">{quality_cards}</div>
    </div>
    <div class="report-footnote">
        On-hold deal value currently stands at {escape_copy(format_precise_money(pipeline["on_hold_value"]))}.
        Missing deal values were not imputed.
    </div>
</div>
"""
    )


def render_message(role, content, timestamp=None):
    timestamp = timestamp or now_label()
    meta_label = "Skylark" if role == "assistant" else "You"
    role_class = "assistant-turn" if role == "assistant" else "user-turn"
    state_html = ""

    if role == "assistant":
        state_html = (
            "<div class='message-state'>"
            f"<span class='state-icon'>{SPARK_ICON}</span>"
            "<span>AI analysis</span>"
            "</div>"
        )

    body_html = (
        render_markdown_content(content)
        if role == "assistant"
        else f"<div class='message-copy'>{escape_copy(content)}</div>"
    )

    st.html(
        html_block(
            f"""
<div class="conversation-turn {role_class}">
    <div class="message-card">
        {state_html}
        {body_html}
    </div>
    <div class="message-meta{' message-meta-right' if role == 'user' else ''}">
        {escape_copy(meta_label)} <span class="meta-dot">&#8226;</span> {escape_copy(timestamp)}
    </div>
</div>
"""
        )
    )


if "messages" not in st.session_state:
    st.session_state.messages = []

if "leadership_summary_markdown" not in st.session_state:
    st.session_state.leadership_summary_markdown = ""

if "show_summary_panel" not in st.session_state:
    st.session_state.show_summary_panel = False

if "analysis_agent" not in st.session_state:
    st.session_state.analysis_agent = None

if "analysis_context" not in st.session_state:
    st.session_state.analysis_context = {}

if "analysis_conversation_state" not in st.session_state:
    st.session_state.analysis_conversation_state = {}


def reset_chat_state():
    st.session_state.messages = []
    st.session_state.show_summary_panel = False
    st.session_state.analysis_agent = None
    st.session_state.analysis_context = {}
    st.session_state.analysis_conversation_state = {}


live_data = True
data_error = None
agent_error = None
ask = None
summary = {
    "pipeline": zero_pipeline_summary(),
    "work_orders": zero_work_order_summary(),
}

try:
    work_orders, deals, work_quality, deal_quality = load_data()
    summary = leadership_summary(deals, work_orders)
except Exception:
    live_data = False
    data_error = (
        "Live monday.com data is unavailable right now. "
        "The redesign still renders, but KPIs and analysis stay inactive until the sync succeeds."
    )
    work_orders = None
    deals = None
    work_quality = {}
    deal_quality = {}
else:
    try:
        st.session_state.analysis_context = {
            "deals_df": deals,
            "work_orders_df": work_orders,
            "work_order_quality": work_quality,
            "deal_quality": deal_quality,
        }
        st.session_state.analysis_agent = build_agent(
            deals_df=deals,
            work_orders_df=work_orders,
            work_quality=work_quality,
            deal_quality=deal_quality,
            conversation_state=st.session_state.analysis_conversation_state,
            data_context=st.session_state.analysis_context,
        )
        ask = st.session_state.analysis_agent
    except Exception:
        agent_error = (
            "The UI is live, but the analysis agent is not ready yet. "
            "Check the Groq API configuration to reactivate chat answers."
        )


pipeline = summary["pipeline"]
financials = summary["work_orders"]
win_rate = safe_ratio(pipeline["won_deals"], pipeline["deal_count"])
welcome_time = now_label()

chart_items = [
    {"label": "Pipeline", "value": pipeline["active_pipeline_value"], "tone": "tone-a"},
    {"label": "Billed", "value": financials["billed_value"], "tone": "tone-b"},
    {"label": "Collected", "value": financials["collected_amount"], "tone": "tone-c"},
    {"label": "Receivable", "value": financials["amount_receivable"], "tone": "tone-d"},
]

st.markdown("<div class='topbar-shell'>", unsafe_allow_html=True)
topbar_columns = st.columns([1, 4, 1])

with topbar_columns[0]:
    st.empty()

with topbar_columns[1]:
    st.markdown(
        html_block(
            """
<div class="brand">Skylark</div>
"""
        ),
        unsafe_allow_html=True,
    )

with topbar_columns[2]:
    st.markdown("<div class='topbar-button'>", unsafe_allow_html=True)
    new_chat_clicked = st.button("↺", key="new_chat", help="Start a new chat")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

if new_chat_clicked:
    reset_chat_state()
    st.rerun()

welcome_copy = (
    "Welcome back. Here is your Executive Leadership Summary for today."
    if live_data
    else "Welcome back. Skylark is ready when your live monday.com data connection comes online."
)

primary_note = f"Open deals: {pipeline['open_deals']}" if live_data else "Waiting for live sync"
secondary_note = f"Won deals: {pipeline['won_deals']}" if live_data else "Analysis offline"

st.markdown(
    html_block(
        f"""
<div class="assistant-shell">
    <div class="intro-copy">{escape_copy(welcome_copy)}</div>
    <div class="snapshot-card">
        <div class="snapshot-head">
            <span>Global KPI Snapshot</span>
            <span>{BAR_ICON}</span>
        </div>
        <div class="kpi-grid">
            <div>
                <div class="kpi-label">Order Book</div>
                <div class="kpi-value">{escape_copy(format_money(financials["total_order_value"]) if live_data else "--")}</div>
                <div class="kpi-note">{escape_copy(primary_note)}</div>
            </div>
            <div>
                <div class="kpi-label">Pipeline Conv.</div>
                <div class="kpi-value">{escape_copy(format_percent(win_rate) if live_data else "--")}</div>
                <div class="kpi-note kpi-note-muted">{escape_copy(secondary_note)}</div>
            </div>
        </div>
    </div>
</div>
<div class="meta-line">Skylark &#8226; {escape_copy(welcome_time)}</div>
"""
    ),
    unsafe_allow_html=True,
)

if data_error:
    st.markdown(
        f"<div class='notice-card'><strong>Connection notice.</strong> {escape_copy(data_error)}</div>",
        unsafe_allow_html=True,
    )
elif agent_error:
    st.markdown(
        f"<div class='notice-card'><strong>Agent notice.</strong> {escape_copy(agent_error)}</div>",
        unsafe_allow_html=True,
    )

panel_copy = (
    "Booked demand, billing progress, and collections pulled from the live monday.com boards."
    if live_data
    else "The shell is styled and ready. KPI bars will light up once live business data is available."
)

st.markdown(
    html_block(
        f"""
<div class="assistant-shell">
    <div class="message-state">
        <span class="state-icon">{SPARK_ICON}</span>
        <span>Analyzing correlated datasets...</span>
    </div>
    <div class="panel-title">Pipeline, Billing, and Collections Snapshot</div>
    <div class="panel-copy">{escape_copy(panel_copy)}</div>
    <div class="chart-frame">
        <div class="chart-label">Value</div>
        {build_chart_markup(chart_items, live_data)}
    </div>
</div>
"""
    ),
    unsafe_allow_html=True,
)

prompt_to_run = None
summary_warning = None

leadership_summary_clicked = st.button(
    "Leadership Summary",
    use_container_width=True,
)

if leadership_summary_clicked:
    if live_data:
        st.session_state.show_summary_panel = True
        st.session_state.leadership_summary_markdown = build_summary_markdown(
            summary=summary,
            deals_df=deals,
            work_orders_df=work_orders,
            deal_quality=deal_quality,
            work_quality=work_quality,
        )
    else:
        summary_warning = (
            "Live monday.com data is unavailable, so the leadership summary cannot be generated yet."
        )

if summary_warning:
    st.markdown(
        f"<div class='notice-card'><strong>Summary notice.</strong> {escape_copy(summary_warning)}</div>",
        unsafe_allow_html=True,
    )

if st.session_state.show_summary_panel and live_data:
    st.markdown(
        build_summary_html(
            summary=summary,
            deals_df=deals,
            work_orders_df=work_orders,
            deal_quality=deal_quality,
            work_quality=work_quality,
        ),
        unsafe_allow_html=True,
    )
    st.download_button(
        label="Download Markdown",
        data=st.session_state.leadership_summary_markdown,
        file_name="leadership_summary.md",
        mime="text/markdown",
        use_container_width=True,
    )

for message in st.session_state.messages:
    render_message(
        role=message["role"],
        content=message["content"],
        timestamp=message.get("timestamp"),
    )

st.markdown(
    html_block(
        """
<div class="composer-banner">
    <span class="status-dot"></span>
    <span>AI MODE ACTIVE</span>
</div>
"""
    ),
    unsafe_allow_html=True,
)

typed_question = st.chat_input("Ask Skylark...")

if typed_question:
    prompt_to_run = typed_question

if prompt_to_run:
    user_timestamp = now_label()

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt_to_run,
            "timestamp": user_timestamp,
        }
    )
    render_message("user", prompt_to_run, user_timestamp)

    loading_slot = st.empty()
    loading_slot.html(
        html_block(
            f"""
<div class="conversation-turn assistant-turn">
    <div class="message-card loading-card">
        <div class="message-state">
            <span class="state-icon">{SPARK_ICON}</span>
            <span>Analyzing correlated datasets...</span>
        </div>
        <div class="pulse-bar"></div>
    </div>
</div>
"""
        )
    )

    if not live_data:
        answer = (
            "Live monday.com data is unavailable right now, so I cannot run a fresh analysis yet."
        )
    elif ask is None:
        answer = (
            "The Skylark analysis agent is not ready yet. "
            "Check the Groq API configuration and try again."
        )
    else:
        with st.spinner("Analyzing monday.com data..."):
            try:
                answer = ask(prompt_to_run)
            except Exception:
                answer = (
                    "I couldn't complete that analysis. "
                    "Please try again or rephrase the question."
                )

    loading_slot.empty()

    assistant_timestamp = now_label()
    render_message("assistant", answer, assistant_timestamp)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "timestamp": assistant_timestamp,
        }
    )
