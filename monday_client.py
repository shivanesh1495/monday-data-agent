import os

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.monday.com/v2"


class MondayClient:

    def __init__(self):
        self.token = os.getenv("MONDAY_API_TOKEN")

        if not self.token:
            raise ValueError("MONDAY_API_TOKEN is missing")

        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
        }

    def _request(self, query):
        response = requests.post(
            API_URL,
            headers=self.headers,
            json={"query": query},
            timeout=30,
        )

        response.raise_for_status()

        result = response.json()

        if "errors" in result:
            raise RuntimeError(result["errors"])

        return result["data"]

    def get_board_columns(self, board_id):
        query = f"""
        query {{
            boards(ids: [{board_id}]) {{
                id
                name
                columns {{
                    id
                    title
                    type
                }}
            }}
        }}
        """

        data = self._request(query)

        if not data["boards"]:
            raise ValueError(f"Board {board_id} not found")

        return data["boards"][0]

    def get_board_items(self, board_id):
        all_items = []

        query = f"""
        query {{
            boards(ids: [{board_id}]) {{
                id
                name
                columns {{
                    id
                    title
                    type
                }}
                items_page(limit: 500) {{
                    cursor
                    items {{
                        id
                        name
                        column_values {{
                            id
                            text
                            value
                        }}
                    }}
                }}
            }}
        }}
        """

        data = self._request(query)

        if not data["boards"]:
            raise ValueError(f"Board {board_id} not found")

        board = data["boards"][0]
        all_items.extend(board["items_page"]["items"])

        cursor = board["items_page"]["cursor"]

        while cursor:
            next_query = f"""
            query {{
                next_items_page(cursor: "{cursor}") {{
                    cursor
                    items {{
                        id
                        name
                        column_values {{
                            id
                            text
                            value
                        }}
                    }}
                }}
            }}
            """

            data = self._request(next_query)
            page = data["next_items_page"]

            all_items.extend(page["items"])
            cursor = page["cursor"]

        return {
            "board_id": board["id"],
            "board_name": board["name"],
            "columns": board["columns"],
            "items": all_items,
        }

    def board_to_dataframe(self, board_id):
        board = self.get_board_items(board_id)

        columns = {column["id"]: column["title"] for column in board["columns"]}

        rows = []

        for item in board["items"]:
            row = {"item_id": item["id"], "item_name": item["name"]}

            for column in item["column_values"]:
                column_name = columns.get(column["id"], column["id"])
                row[column_name] = column["text"]

            rows.append(row)

        return pd.DataFrame(rows)
