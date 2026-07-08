from __future__ import annotations

import unittest
from copy import deepcopy
from typing import Any
from unittest.mock import patch

from services.account_service import AccountService
from services.storage.base import StorageBackend


class MemoryStorage(StorageBackend):
    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self.accounts = deepcopy(accounts)
        self.auth_keys: list[dict[str, Any]] = []

    def load_accounts(self) -> list[dict[str, Any]]:
        return deepcopy(self.accounts)

    def save_accounts(self, accounts: list[dict[str, Any]]) -> None:
        self.accounts = deepcopy(accounts)

    def load_auth_keys(self) -> list[dict[str, Any]]:
        return deepcopy(self.auth_keys)

    def save_auth_keys(self, auth_keys: list[dict[str, Any]]) -> None:
        self.auth_keys = deepcopy(auth_keys)

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy"}

    def get_backend_info(self) -> dict[str, Any]:
        return {"type": "memory"}


class OreateAccountRefreshTest(unittest.TestCase):
    def test_oreate_account_refresh_uses_oreate_probe_not_openai_backend(self) -> None:
        storage = MemoryStorage(
            [
                {
                    "access_token": "oreate-cookie-token",
                    "source_type": "oreateai",
                    "status": "异常",
                    "cookies": {"ouss": "session-cookie"},
                    "quota": 0,
                }
            ]
        )
        service = AccountService(storage)

        class OpenAIShouldNotBeUsed:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                raise AssertionError("OpenAI backend should not be used for oreateai accounts")

        with (
            patch("services.openai_backend_api.OpenAIBackendAPI", OpenAIShouldNotBeUsed),
            patch(
                "services.oreate_backend_api.fetch_account_remote_info",
                return_value={"status": "正常", "quota": 123, "image_quota_unknown": False},
                create=True,
            ),
        ):
            refreshed = service.fetch_remote_info("oreate-cookie-token", "refresh_accounts")

        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed["status"], "正常")
        self.assertEqual(refreshed["quota"], 123)
        self.assertEqual(storage.accounts[0]["status"], "正常")


if __name__ == "__main__":
    unittest.main()
