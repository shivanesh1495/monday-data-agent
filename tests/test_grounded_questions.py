import os
import unittest

import pandas as pd

from agent import create_agent


class GroundedQuestionTests(unittest.TestCase):
    def setUp(self):
        os.environ["GROQ_API_KEY"] = "test-key"

        self.deals = pd.DataFrame(
            [
                {
                    "item_id": "1",
                    "item_name": "Solar A",
                    "Owner code": "OWNER_001",
                    "Client Code": "COMPANY001",
                    "Deal Status": "Won",
                    "Close Date (A)": "2026-07-01",
                    "Closure Probability": "80",
                    "Masked Deal value": "100",
                    "Tentative Close Date": None,
                    "Deal Stage": "G. Project Won",
                    "Product deal": "Survey",
                    "Sector/service": "Renewables",
                    "Created Date": "2026-06-01",
                },
                {
                    "item_id": "2",
                    "item_name": "Solar B",
                    "Owner code": "OWNER_001",
                    "Client Code": "COMPANY002",
                    "Deal Status": "Dead",
                    "Close Date (A)": None,
                    "Closure Probability": "30",
                    "Masked Deal value": None,
                    "Tentative Close Date": None,
                    "Deal Stage": "L. Project Lost",
                    "Product deal": "Survey",
                    "Sector/service": "Renewables",
                    "Created Date": "2026-06-05",
                },
                {
                    "item_id": "3",
                    "item_name": "Solar C",
                    "Owner code": "OWNER_002",
                    "Client Code": "COMPANY003",
                    "Deal Status": "Open",
                    "Close Date (A)": None,
                    "Closure Probability": "50",
                    "Masked Deal value": "300",
                    "Tentative Close Date": None,
                    "Deal Stage": "E. Proposal/Commercials Sent",
                    "Product deal": "Survey",
                    "Sector/service": "Renewables",
                    "Created Date": "2026-06-10",
                },
                {
                    "item_id": "4",
                    "item_name": "Solar D",
                    "Owner code": "OWNER_002",
                    "Client Code": "COMPANY004",
                    "Deal Status": "Won",
                    "Close Date (A)": None,
                    "Closure Probability": "85",
                    "Masked Deal value": None,
                    "Tentative Close Date": None,
                    "Deal Stage": "G. Project Won",
                    "Product deal": "Survey",
                    "Sector/service": "Renewables",
                    "Created Date": "2026-06-15",
                },
                {
                    "item_id": "5",
                    "item_name": "Mine A",
                    "Owner code": "OWNER_001",
                    "Client Code": "COMPANY005",
                    "Deal Status": "Won",
                    "Close Date (A)": None,
                    "Closure Probability": "90",
                    "Masked Deal value": "500",
                    "Tentative Close Date": None,
                    "Deal Stage": "G. Project Won",
                    "Product deal": "Mapping",
                    "Sector/service": "Mining",
                    "Created Date": "2026-05-01",
                },
                {
                    "item_id": "6",
                    "item_name": "Mine B",
                    "Owner code": "OWNER_001",
                    "Client Code": "COMPANY006",
                    "Deal Status": "Dead",
                    "Close Date (A)": None,
                    "Closure Probability": "20",
                    "Masked Deal value": "400",
                    "Tentative Close Date": None,
                    "Deal Stage": "L. Project Lost",
                    "Product deal": "Mapping",
                    "Sector/service": "Mining",
                    "Created Date": "2026-05-02",
                },
                {
                    "item_id": "7",
                    "item_name": "Mine C",
                    "Owner code": "OWNER_003",
                    "Client Code": "COMPANY007",
                    "Deal Status": "Open",
                    "Close Date (A)": None,
                    "Closure Probability": "60",
                    "Masked Deal value": "700",
                    "Tentative Close Date": None,
                    "Deal Stage": "F. Negotiations",
                    "Product deal": "Mapping",
                    "Sector/service": "Mining",
                    "Created Date": "2026-05-03",
                },
                {
                    "item_id": "8",
                    "item_name": "Rail A",
                    "Owner code": "OWNER_003",
                    "Client Code": "COMPANY008",
                    "Deal Status": "Open",
                    "Close Date (A)": None,
                    "Closure Probability": "65",
                    "Masked Deal value": "800",
                    "Tentative Close Date": None,
                    "Deal Stage": "F. Negotiations",
                    "Product deal": "Inspection",
                    "Sector/service": "Railways",
                    "Created Date": "2026-05-04",
                },
                {
                    "item_id": "9",
                    "item_name": "Rail B",
                    "Owner code": "OWNER_003",
                    "Client Code": "COMPANY009",
                    "Deal Status": "On Hold",
                    "Close Date (A)": None,
                    "Closure Probability": "40",
                    "Masked Deal value": "900",
                    "Tentative Close Date": None,
                    "Deal Stage": "M. Projects On Hold",
                    "Product deal": "Inspection",
                    "Sector/service": "Railways",
                    "Created Date": "2026-05-05",
                },
                {
                    "item_id": "10",
                    "item_name": "Build A",
                    "Owner code": "OWNER_004",
                    "Client Code": "COMPANY010",
                    "Deal Status": "Won",
                    "Close Date (A)": "2026-07-10",
                    "Closure Probability": "95",
                    "Masked Deal value": "200",
                    "Tentative Close Date": None,
                    "Deal Stage": "G. Project Won",
                    "Product deal": "Execution",
                    "Sector/service": "Construction",
                    "Created Date": "2026-07-01",
                },
                {
                    "item_id": "11",
                    "item_name": "Mine D",
                    "Owner code": "OWNER_004",
                    "Client Code": "COMPANY011",
                    "Deal Status": "Dead",
                    "Close Date (A)": "2026-08-01",
                    "Closure Probability": "10",
                    "Masked Deal value": "250",
                    "Tentative Close Date": None,
                    "Deal Stage": "L. Project Lost",
                    "Product deal": "Execution",
                    "Sector/service": "DSP",
                    "Created Date": "2026-08-10",
                },
                {
                    "item_id": "12",
                    "item_name": "Nezuko",
                    "Owner code": "",
                    "Client Code": None,
                    "Deal Status": None,
                    "Close Date (A)": None,
                    "Closure Probability": None,
                    "Masked Deal value": None,
                    "Tentative Close Date": None,
                    "Deal Stage": None,
                    "Product deal": None,
                    "Sector/service": "Sector/service",
                    "Created Date": None,
                },
                {
                    "item_id": "13",
                    "item_name": "Bugs Bunny",
                    "Owner code": "",
                    "Client Code": None,
                    "Deal Status": None,
                    "Close Date (A)": None,
                    "Closure Probability": None,
                    "Masked Deal value": None,
                    "Tentative Close Date": None,
                    "Deal Stage": None,
                    "Product deal": None,
                    "Sector/service": "Sector/service",
                    "Created Date": None,
                },
            ]
        )

        self.work_orders = pd.DataFrame(
            [
                {
                    "item_id": "w1",
                    "item_name": "WO Solar A",
                    "Customer Name Code": "WOCOMPANY_001",
                    "Execution Status": "Completed",
                    "Sector": "Renewables",
                    "Billing Status": None,
                    "Amount Receivable (Masked)": "10",
                },
                {
                    "item_id": "w2",
                    "item_name": "WO Mine A",
                    "Customer Name Code": "WOCOMPANY_005",
                    "Execution Status": "Completed",
                    "Sector": "Mining",
                    "Billing Status": None,
                    "Amount Receivable (Masked)": "-50",
                },
                {
                    "item_id": "w3",
                    "item_name": "WO Extra A",
                    "Customer Name Code": "WOCOMPANY_020",
                    "Execution Status": "Completed",
                    "Sector": "Powerline",
                    "Billing Status": "Billed",
                    "Amount Receivable (Masked)": "1000",
                },
                {
                    "item_id": "w4",
                    "item_name": "WO Extra B",
                    "Customer Name Code": "WOCOMPANY_021",
                    "Execution Status": "Executed until current month",
                    "Sector": "Railways",
                    "Billing Status": None,
                    "Amount Receivable (Masked)": "0",
                },
                {
                    "item_id": "w5",
                    "item_name": "WO Build A",
                    "Customer Name Code": "WOCOMPANY_030",
                    "Execution Status": "Not Started",
                    "Sector": "Construction",
                    "Billing Status": None,
                    "Amount Receivable (Masked)": "20",
                },
                {
                    "item_id": "w6",
                    "item_name": "WO Other A",
                    "Customer Name Code": "WOCOMPANY_040",
                    "Execution Status": "Completed",
                    "Sector": "Others",
                    "Billing Status": None,
                    "Amount Receivable (Masked)": "20000",
                },
            ]
        )

        self.context = {
            "deals_df": self.deals,
            "work_orders_df": self.work_orders,
            "deal_quality": {},
            "work_order_quality": {},
        }
        self.ask = create_agent(
            self.deals,
            self.work_orders,
            conversation_state={},
            data_context=self.context,
        )

    def test_average_deal_size_reports_sample_size_and_coverage(self):
        answer = self.ask("What's our average deal size in Renewables?")

        self.assertIn("Renewables average deal size", answer)
        self.assertIn("Sample used: 2 of 4 deals (50.0% coverage)", answer)
        self.assertIn("directional average", answer)

    def test_close_time_prefers_reliability_caveat_when_coverage_is_low(self):
        answer = self.ask("How long does it typically take us to close a deal?")

        self.assertIn("Closed deals: 7", answer)
        self.assertIn("Deals with both Created Date and Close Date (A): 3", answer)
        self.assertIn("Negative durations found: 1", answer)
        self.assertIn("not reliable enough", answer)

    def test_data_entry_error_question_flags_header_leaks(self):
        answer = self.ask("Are there any records in here that look like data entry errors?")

        self.assertIn("Nezuko", answer)
        self.assertIn("Bugs Bunny", answer)
        self.assertIn("header text", answer)

    def test_cross_board_gap_question_normalizes_client_codes(self):
        answer = self.ask("Which clients have an open deal but no completed work order yet?")

        self.assertIn("Open deals without a completed work order yet: 3 clients", answer)
        self.assertIn("Completed work orders without an open deal: 5 clients", answer)
        self.assertIn("COMPANY123 against work-order codes like WOCOMPANY_123", answer)

    def test_win_rate_by_sector_flags_unmapped_or_small_sample_labels(self):
        answer = self.ask("Break down win rate by sector, and flag anything you're not confident in.")

        self.assertIn("Win rate by sector (closed deals only)", answer)
        self.assertIn("Construction: 100.0% (1 won / 0 dead; 1 closed) [low confidence: small sample]", answer)
        self.assertIn("I excluded 3 deal rows with non-canonical sector labels", answer)
        self.assertIn("Sector taxonomy", answer)

    def test_active_pipeline_question_surfaces_owner_concentration(self):
        answer = self.ask("Which BD/KAM owner is carrying the most of our active pipeline?")

        self.assertIn("Active pipeline is concentrated with OWNER_003", answer)
        self.assertIn("3 active deals", answer)
        self.assertIn("88.9%", answer)

    def test_billing_status_question_computes_fraction(self):
        answer = self.ask("What fraction of our work orders have no billing status recorded?")

        self.assertIn("Missing billing status: 5 of 6 work orders (83.3%)", answer)

    def test_receivable_anomaly_question_flags_negative_values(self):
        answer = self.ask("Any unusual receivable amounts I should know about?")

        self.assertIn("Negative receivables: 1 records", answer)
        self.assertIn("Largest negative receivable: -50.00", answer)

    def test_agent_uses_updated_shared_data_context(self):
        first = self.ask("What's our average deal size in Renewables?")
        self.assertIn("Average deal value: 200.00", first)

        refreshed_deals = self.deals.copy()
        refreshed_deals.loc[refreshed_deals["Sector/service"] == "Renewables", "Masked Deal value"] = "1000"
        self.context["deals_df"] = refreshed_deals

        second = self.ask("What's our average deal size in Renewables?")
        self.assertIn("Average deal value: 1,000.00", second)
        self.assertIn("Sample used: 4 of 4 deals (100.0% coverage)", second)


if __name__ == "__main__":
    unittest.main()
