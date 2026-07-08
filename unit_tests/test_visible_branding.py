from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api import create_app


class VisibleBrandingTest(unittest.TestCase):
    def test_health_dashboard_uses_oreate2api_branding(self) -> None:
        response = TestClient(create_app()).get("/health")

        self.assertEqual(200, response.status_code)
        self.assertIn("oreate2api", response.text)
        self.assertNotIn("chatgpt2api", response.text.lower())


if __name__ == "__main__":
    unittest.main()
