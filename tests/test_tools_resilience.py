import unittest
from datetime import date

import pandas as pd

from tools import filter_deals, pipeline_summary, work_order_financials


class ToolResilienceTests(unittest.TestCase):
    def test_filter_and_pipeline_summary_support_alias_columns(self):
        deals = pd.DataFrame(
            [
                {"Sector": "Railways", "Deal Value": 1000, "Status": "Open"},
                {"Sector": "Railways", "Deal Value": 500, "Status": "Won"},
                {"Sector": "Mining", "Deal Value": 200, "Status": "Dead"},
            ]
        )

        filtered = filter_deals(deals, sector="Railways")
        summary = pipeline_summary(deals, sector="Railways")

        self.assertEqual(len(filtered), 2)
        self.assertEqual(summary["deal_count"], 2)
        self.assertEqual(summary["total_deal_value"], 1500.0)
        self.assertEqual(summary["won_value"], 500.0)

    def test_work_order_financials_support_alias_columns(self):
        work_orders = pd.DataFrame(
            [
                {
                    "Sector": "Powerline",
                    "Order Value": 1000,
                    "Billed": 600,
                    "Collected": 450,
                    "Amount To Be Billed": 200,
                    "Receivable": 150,
                },
                {
                    "Sector": "Powerline",
                    "Order Value": 700,
                    "Billed": 400,
                    "Collected": 300,
                    "Amount To Be Billed": 150,
                    "Receivable": 100,
                },
            ]
        )

        summary = work_order_financials(work_orders, sector="Powerline")

        self.assertEqual(summary["work_order_count"], 2)
        self.assertEqual(summary["total_order_value"], 1700.0)
        self.assertEqual(summary["billed_value"], 1000.0)
        self.assertEqual(summary["collected_amount"], 750.0)
        self.assertEqual(summary["amount_to_be_billed"], 350.0)
        self.assertEqual(summary["amount_receivable"], 250.0)

    def test_pipeline_summary_applies_last_month_filter(self):
        deals = pd.DataFrame(
            [
                {
                    "Sector/service": "Railways",
                    "Masked Deal value": 1000,
                    "Deal Status": "Open",
                    "Close Date (A)": date(2026, 7, 15),
                    "Tentative Close Date": None,
                    "Created Date": date(2026, 7, 1),
                },
                {
                    "Sector/service": "Railways",
                    "Masked Deal value": 3000,
                    "Deal Status": "Won",
                    "Close Date (A)": date(2026, 8, 10),
                    "Tentative Close Date": None,
                    "Created Date": date(2026, 8, 1),
                },
            ]
        )

        summary = pipeline_summary(
            deals,
            sector="Railways",
            time_window="last_month",
            reference_date=date(2026, 8, 30),
        )

        self.assertEqual(summary["deal_count"], 1)
        self.assertEqual(summary["total_deal_value"], 1000.0)
        self.assertTrue(summary["time_filter"]["time_window_applied"])
        self.assertEqual(summary["time_filter"]["window_start"], "2026-07-01")
        self.assertEqual(summary["time_filter"]["window_end"], "2026-07-31")

    def test_work_order_financials_applies_this_quarter_filter(self):
        work_orders = pd.DataFrame(
            [
                {
                    "Sector": "Mining",
                    "Amount in Rupees (Excl of GST) (Masked)": 1000,
                    "Billed Value in Rupees (Excl of GST.) (Masked)": 400,
                    "Collected Amount in Rupees (Incl of GST.) (Masked)": 350,
                    "Amount to be billed in Rs. (Exl. of GST) (Masked)": 600,
                    "Amount Receivable (Masked)": 200,
                    "Date of PO/LOI": date(2026, 8, 10),
                    "Last invoice date": date(2026, 8, 15),
                    "Collection Date": date(2026, 8, 20),
                },
                {
                    "Sector": "Mining",
                    "Amount in Rupees (Excl of GST) (Masked)": 900,
                    "Billed Value in Rupees (Excl of GST.) (Masked)": 300,
                    "Collected Amount in Rupees (Incl of GST.) (Masked)": 250,
                    "Amount to be billed in Rs. (Exl. of GST) (Masked)": 500,
                    "Amount Receivable (Masked)": 150,
                    "Date of PO/LOI": date(2026, 5, 10),
                    "Last invoice date": date(2026, 5, 15),
                    "Collection Date": date(2026, 5, 20),
                },
            ]
        )

        summary = work_order_financials(
            work_orders,
            sector="Mining",
            time_window="this_quarter",
            reference_date=date(2026, 8, 30),
        )

        self.assertEqual(summary["work_order_count"], 1)
        self.assertEqual(summary["total_order_value"], 1000.0)
        self.assertEqual(summary["billed_value"], 400.0)
        self.assertEqual(summary["collected_amount"], 350.0)
        self.assertTrue(summary["time_filter"]["time_window_applied"])
        self.assertEqual(summary["time_filter"]["window_start"], "2026-07-01")
        self.assertEqual(summary["time_filter"]["window_end"], "2026-09-30")


if __name__ == "__main__":
    unittest.main()
