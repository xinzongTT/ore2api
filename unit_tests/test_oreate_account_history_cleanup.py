from __future__ import annotations

import unittest
from copy import deepcopy
from typing import Any

from services.account_service import AccountService


class MemoryStorage:
    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self.accounts = deepcopy(accounts)

    def load_accounts(self) -> list[dict[str, Any]]:
        return deepcopy(self.accounts)

    def save_accounts(self, accounts: list[dict[str, Any]]) -> None:
        self.accounts = deepcopy(accounts)

    def load_auth_keys(self) -> list[dict[str, Any]]:
        return []

    def save_auth_keys(self, auth_keys: list[dict[str, Any]]) -> None:
        pass

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy"}


class OreateAccountHistoryCleanupTests(unittest.TestCase):
    def test_marking_oreate_account_normal_clears_stale_openai_refresh_error(self) -> None:
        storage = MemoryStorage([
            {
                "access_token": "oreate-token",
                "source_type": "oreateai",
                "status": "正常",
                "quota": 100,
                "invalid_count": 1,
                "last_invalid_at": "2026-07-08T04:42:24+00:00",
                "last_refresh_error": "token invalidated (/backend-api/me)",
                "last_refresh_error_at": "2026-07-08T04:42:24+00:00",
            }
        ])
        service = AccountService(storage)

        service.update_account("oreate-token", {"status": "正常"})

        saved = storage.accounts[0]
        self.assertEqual(saved["status"], "正常")
        self.assertEqual(saved["invalid_count"], 0)
        self.assertIsNone(saved["last_invalid_at"])
        self.assertIsNone(saved["last_refresh_error"])
        self.assertIsNone(saved["last_refresh_error_at"])


if __name__ == "__main__":
    unittest.main()
