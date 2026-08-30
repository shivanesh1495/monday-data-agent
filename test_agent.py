import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import agent


class AgentRoutingTests(unittest.TestCase):
    def setUp(self):
        os.environ["GROQ_API_KEY"] = "test-key"
        self.deals = pd.DataFrame(
            [
                {"Sector/service": "Mining", "Masked Deal value": 100, "Deal Status": "Open"},
                {"Sector/service": "Renewables", "Masked Deal value": 250, "Deal Status": "Won"},
            ]
        )
        self.work_orders = pd.DataFrame(
            [
                {
                    "Sector": "Mining",
                    "Amount in Rupees (Excl of GST) (Masked)": 80,
                    "Billed Value in Rupees (Excl of GST.) (Masked)": 40,
                    "Collected Amount in Rupees (Incl of GST.) (Masked)": 20,
                    "Amount to be billed in Rs. (Exl. of GST) (Masked)": 40,
                    "Amount Receivable (Masked)": 20,
                },
                {
                    "Sector": "Renewables",
                    "Amount in Rupees (Excl of GST) (Masked)": 200,
                    "Billed Value in Rupees (Excl of GST.) (Masked)": 100,
                    "Collected Amount in Rupees (Incl of GST.) (Masked)": 50,
                    "Amount to be billed in Rs. (Exl. of GST) (Masked)": 100,
                    "Amount Receivable (Masked)": 50,
                },
            ]
        )

    @patch("agent.Groq")
    def test_direct_pipeline_question_uses_deterministic_tooling(self, mock_groq):
        mock_client = mock_groq.return_value
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None, content="fallback response"))]
        )

        ask = agent.create_agent(self.deals, self.work_orders)
        response = ask("What is the current Mining deal pipeline?")

        self.assertIn("Mining", response)
        self.assertIn("deal pipeline", response.lower())
        self.assertEqual(mock_client.chat.completions.create.call_count, 0)

    @patch("agent.Groq")
    def test_multi_turn_comparison_keeps_sector_and_time_window(self, _mock_groq):
        ask = agent.create_agent(self.deals, self.work_orders)

        first = ask("Compare deal pipeline with work-order execution.")
        second = ask("Mining and Renewables")
        third = ask("Last month")

        self.assertIn("Which sector should I compare", first)
        self.assertIn("What time period should I use?", second)
        self.assertIn("Sector comparison", third)
        self.assertIn("Mining", third)
        self.assertIn("Renewables", third)


if __name__ == "__main__":
    unittest.main()
