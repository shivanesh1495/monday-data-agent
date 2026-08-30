import os
import unittest
from unittest.mock import patch

import pandas as pd

from agent import create_agent


class ConversationMemoryTests(unittest.TestCase):
    def setUp(self):
        os.environ["GROQ_API_KEY"] = "test-key"

        deals = pd.DataFrame(
            [
                {"Sector": "Railways", "Deal Value": 1000, "Status": "Open"},
                {"Sector": "Mining", "Deal Value": 2000, "Status": "Won"},
                {"Sector": "Renewables", "Deal Value": 3000, "Status": "Open"},
            ]
        )
        work_orders = pd.DataFrame(
            [
                {"Sector": "Railways", "Order Value": 900, "Billed": 500, "Collected": 400},
                {"Sector": "Mining", "Order Value": 1800, "Billed": 1000, "Collected": 800},
                {"Sector": "Renewables", "Order Value": 2700, "Billed": 1300, "Collected": 1100},
            ]
        )
        self.ask = create_agent(deals, work_orders)

    @patch("agent.cross_reference_deal_to_execution")
    def test_remembers_single_sector_and_time_window(self, mock_tool):
        mock_tool.return_value = {
            "sector": "Railways",
            "pipeline": {"total_deal_value": 1000, "deal_count": 1},
            "execution": {"total_order_value": 900, "work_order_count": 1},
        }

        first = self.ask("Compare deal pipeline with work-order execution.")
        self.assertIn("sector", first.lower())

        second = self.ask("Railways")
        self.assertIn("period", second.lower())

        result = self.ask("Last month")
        self.assertNotIn("Which sector", result)
        self.assertNotIn("What time period", result)

        self.assertEqual(mock_tool.call_count, 1)
        self.assertEqual(mock_tool.call_args.kwargs["sector"], "Railways")
        self.assertEqual(mock_tool.call_args.kwargs["time_window"], "last_month")

    @patch("agent.cross_reference_deal_to_execution")
    def test_multi_sector_compare_executes_without_repeat_clarification(self, mock_tool):
        mock_tool.side_effect = [
            {
                "sector": "Mining",
                "pipeline": {"total_deal_value": 2000, "deal_count": 1},
                "execution": {"total_order_value": 1800, "work_order_count": 1},
            },
            {
                "sector": "Renewables",
                "pipeline": {"total_deal_value": 3000, "deal_count": 1},
                "execution": {"total_order_value": 2700, "work_order_count": 1},
            },
        ]

        self.ask("Compare deal pipeline with work-order execution.")
        result = self.ask("Mining and Renewables")

        self.assertNotIn("Which sector", result)
        self.assertNotIn("What time period", result)
        self.assertEqual(mock_tool.call_count, 2)
        self.assertEqual(
            {call.kwargs["sector"] for call in mock_tool.call_args_list},
            {"Mining", "Renewables"},
        )

    @patch("agent.cross_reference_deal_to_execution")
    def test_new_comparison_does_not_reuse_completed_context(self, mock_tool):
        mock_tool.side_effect = [
            {
                "sector": "Railways",
                "pipeline": {"total_deal_value": 1000, "deal_count": 1},
                "execution": {"total_order_value": 900, "work_order_count": 1},
            },
            {
                "sector": "Powerline",
                "pipeline": {"total_deal_value": 1500, "deal_count": 1},
                "execution": {"total_order_value": 1200, "work_order_count": 1},
            },
        ]

        self.ask("Compare deal pipeline with work-order execution.")
        self.ask("Railways")
        self.ask("Last month")

        self.ask("Compare deal pipeline with work-order execution.")
        follow_up = self.ask("Powerline")
        self.assertIn("period", follow_up.lower())

        result = self.ask("This month")
        self.assertNotIn("Railways", result)
        self.assertEqual(mock_tool.call_count, 2)
        self.assertEqual(mock_tool.call_args_list[1].kwargs["sector"], "Powerline")
        self.assertEqual(mock_tool.call_args_list[1].kwargs["time_window"], "this_month")

    @patch("agent.pipeline_summary")
    def test_direct_pipeline_question_remembers_requested_sector(self, mock_pipeline):
        mock_pipeline.return_value = {
            "deal_count": 1,
            "total_deal_value": 1000,
            "open_deals": 1,
            "won_value": 0,
            "on_hold_value": 0,
            "dead_value": 0,
        }

        first = self.ask("Show me the deal pipeline.")
        self.assertIn("sector", first.lower())

        result = self.ask("Railways")
        self.assertIn("Railways deal pipeline", result)
        self.assertNotIn("Which sector", result)

    @patch("agent.pipeline_summary")
    def test_compares_win_rate_between_sectors(self, mock_pipeline):
        mock_pipeline.side_effect = [
            {
                "deal_count": 10,
                "total_deal_value": 1000,
                "open_deals": 4,
                "won_value": 300,
                "on_hold_value": 100,
                "dead_value": 200,
                "won_deals": 5,
            },
            {
                "deal_count": 8,
                "total_deal_value": 800,
                "open_deals": 3,
                "won_value": 160,
                "on_hold_value": 50,
                "dead_value": 240,
                "won_deals": 2,
            },
        ]

        result = self.ask("Compare win rate between Mining and Renewables.")

        self.assertIn("Sector comparison - Win rate", result)
        self.assertIn("Mining: 50.0%", result)
        self.assertIn("Renewables: 25.0%", result)

    @patch("agent.work_order_financials")
    def test_compares_collections_between_sectors(self, mock_work_orders):
        mock_work_orders.side_effect = [
            {
                "work_order_count": 3,
                "total_order_value": 1000,
                "billed_value": 700,
                "collected_amount": 500,
                "amount_to_be_billed": 200,
                "amount_receivable": 300,
            },
            {
                "work_order_count": 2,
                "total_order_value": 900,
                "billed_value": 600,
                "collected_amount": 450,
                "amount_to_be_billed": 150,
                "amount_receivable": 250,
            },
        ]

        result = self.ask("Compare collections between Railways and Powerline.")

        self.assertIn("Sector comparison - Collected amount", result)
        self.assertIn("Railways: 500.00", result)
        self.assertIn("Powerline: 450.00", result)

    @patch("agent.work_order_financials")
    @patch("agent.pipeline_summary")
    def test_overview_question_routes_to_combined_sector_summary(
        self,
        mock_pipeline,
        mock_work_orders,
    ):
        mock_pipeline.return_value = {
            "deal_count": 2,
            "total_deal_value": 2000,
            "active_pipeline_value": 1200,
            "won_value": 500,
            "dead_value": 300,
            "on_hold_value": 100,
            "open_deals": 1,
            "time_filter": {
                "requested_time_window": "this_quarter",
                "time_window_applied": True,
                "date_basis": ["Close Date (A)"],
                "excluded_missing_date_rows": 0,
                "window_start": "2026-07-01",
                "window_end": "2026-09-30",
            },
        }
        mock_work_orders.return_value = {
            "work_order_count": 2,
            "total_order_value": 1800,
            "billed_value": 900,
            "collected_amount": 700,
            "amount_to_be_billed": 400,
            "amount_receivable": 250,
            "time_filter": {
                "requested_time_window": "this_quarter",
                "time_window_applied": True,
                "date_basis": ["Date of PO/LOI"],
                "excluded_missing_date_rows": 0,
                "window_start": "2026-07-01",
                "window_end": "2026-09-30",
            },
        }

        result = self.ask("How are we doing in Railways this quarter?")

        self.assertIn("Railways business overview", result)
        self.assertIn("2026-07-01 to 2026-09-30", result)
        self.assertIn("Deal pipeline value: 2,000.00", result)
        self.assertIn("Collected amount: 700.00", result)


if __name__ == "__main__":
    unittest.main()
