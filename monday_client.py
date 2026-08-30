import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

API_URL = "https://api.monday.com/v2"


class MondayClient:

    def __init__(self, timeout=30, session=None):
        self.token = os.getenv("MONDAY_API_TOKEN")

        if not self.token:
            raise ValueError("MONDAY_API_TOKEN is missing")

        self.timeout = timeout
        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
        }
        self.session = session or self._build_session()

    def _build_session(self):
        session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _format_errors(self, errors):
        formatted = []
        for error in errors:
            if isinstance(error, dict):
                message = error.get("message") or str(error)
                path = error.get("path")
                code = error.get("extensions", {}).get("code")
                details = []
                if code:
                    details.append(f"code={code}")
                if path:
                    details.append(f"path={'.'.join(str(part) for part in path)}")
                if details:
                    formatted.append(f"{message} ({', '.join(details)})")
                else:
                    formatted.append(message)
            else:
                formatted.append(str(error))
        return "; ".join(formatted)

    def _request(self, query):
        try:
            response = self.session.post(
                API_URL,
                headers=self.headers,
                json={"query": query},
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise RuntimeError(
                "Timed out while querying monday.com. Please try again."
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Could not reach monday.com: {exc}"
            ) from exc

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body_preview = response.text[:300]
            raise RuntimeError(
                f"monday.com API returned HTTP {response.status_code}: {body_preview}"
            ) from exc

        result = response.json()

        if "errors" in result:
            raise RuntimeError(
                f"monday.com query failed: {self._format_errors(result['errors'])}"
            )

        if "data" not in result:
            raise RuntimeError("monday.com API response did not include a data payload")

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
