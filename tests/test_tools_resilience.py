import unittest

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


if __name__ == "__main__":
    unittest.main()
