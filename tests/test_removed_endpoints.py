import os
import unittest

os.environ.setdefault("CHATGPT2API_AUTH_KEY", "test-admin-key")

from fastapi.testclient import TestClient

from api import create_app


class RemovedEndpointsTest(unittest.TestCase):
    def test_removed_openai_document_endpoints_return_410(self):
        client = TestClient(create_app(), raise_server_exceptions=False)
        headers = {"Authorization": "Bearer test-admin-key"}

        for path in (
            "/v1/editable-file-tasks",
            "/v1/ppt/generations",
            "/v1/psd/generations",
        ):
            with self.subTest(path=path):
                response = client.post(path, json={}, headers=headers)
                self.assertEqual(response.status_code, 410)
                self.assertEqual(response.json()["error"]["type"], "gone")


if __name__ == "__main__":
    unittest.main()
