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


if __name__ == "__main__":
    unittest.main()
