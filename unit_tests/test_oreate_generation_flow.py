from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import oreate_backend_api


class FakeOreateAccountService:
    def __init__(self) -> None:
        self.available_requests: list[dict[str, object]] = []
        self.results: list[tuple[str, bool]] = []

    def list_accounts(self) -> list[dict[str, object]]:
        return [
            {
                "access_token": "openai-token",
                "source_type": "web",
                "status": "正常",
                "cookies": {"ouss": "wrong-cookie"},
            }
        ]

    def get_available_access_token(self, **kwargs: object) -> str:
        self.available_requests.append(dict(kwargs))
        return "oreate-token"

    def get_account(self, access_token: str) -> dict[str, object] | None:
        if access_token != "oreate-token":
            return None
        return {
            "access_token": access_token,
            "source_type": "oreateai",
            "status": "正常",
            "cookies": {"ouss": "session-cookie"},
        }

    def mark_image_result(self, access_token: str, success: bool) -> None:
        self.results.append((access_token, success))


class OreateGenerationFlowTest(unittest.TestCase):
    def test_image_generation_uses_oreate_account_scheduler_and_marks_success(self) -> None:
        fake_accounts = FakeOreateAccountService()

        with (
            patch.object(oreate_backend_api, "account_service", fake_accounts),
            patch.object(oreate_backend_api, "_make_session", return_value=object()),
            patch.object(
                oreate_backend_api,
                "_run_generation_stream",
                return_value={"urls": ["https://cdn.oreateai.com/aiimage/demo.png"], "raw": "", "chat_id": "chat-1"},
            ),
        ):
            result = oreate_backend_api.image_generation("draw a cube")

        self.assertEqual(result["data"][0]["url"], "https://cdn.oreateai.com/aiimage/demo.png")
        self.assertEqual(fake_accounts.available_requests, [{"source_type": "oreateai"}])
        self.assertEqual(fake_accounts.results, [("oreate-token", True)])

    def test_image_generation_error_raises_http_exception_and_marks_failure(self) -> None:
        fake_accounts = FakeOreateAccountService()

        with (
            patch.object(oreate_backend_api, "account_service", fake_accounts),
            patch.object(oreate_backend_api, "_make_session", return_value=object()),
            patch.object(
                oreate_backend_api,
                "_run_generation_stream",
                return_value={"urls": [], "raw": "", "error": "quota exhausted", "chat_id": "chat-2"},
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                oreate_backend_api.image_generation("draw a cube")

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(fake_accounts.available_requests, [{"source_type": "oreateai"}])
        self.assertEqual(fake_accounts.results, [("oreate-token", False)])


if __name__ == "__main__":
    unittest.main()
