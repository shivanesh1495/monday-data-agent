import os
import unittest
from unittest.mock import Mock

import requests

from monday_client import MondayClient


class MondayClientTests(unittest.TestCase):
    def setUp(self):
        os.environ["MONDAY_API_TOKEN"] = "test-token"

    def test_wraps_timeout_as_runtime_error(self):
        session = Mock()
        session.post.side_effect = requests.Timeout("timed out")
        client = MondayClient(session=session)

        with self.assertRaisesRegex(RuntimeError, "Timed out while querying monday.com"):
            client._request("query { boards { id } }")

    def test_formats_graphql_errors(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "errors": [
                {
                    "message": "Invalid board",
                    "path": ["boards", 0],
                    "extensions": {"code": "BoardNotFound"},
                }
            ]
        }
        session = Mock()
        session.post.return_value = response
        client = MondayClient(session=session)

        with self.assertRaisesRegex(RuntimeError, "Invalid board"):
            client._request("query { boards { id } }")

    def test_returns_data_payload(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": {"boards": []}}
        session = Mock()
        session.post.return_value = response
        client = MondayClient(session=session)

        result = client._request("query { boards { id } }")

        self.assertEqual(result, {"boards": []})


if __name__ == "__main__":
    unittest.main()
