from __future__ import annotations

import unittest
from unittest.mock import patch

from services.model_catalog_service import get_model_catalog


class ModelCatalogOreateOnlyTest(unittest.TestCase):
    def test_catalog_does_not_expose_removed_chat_models_and_includes_video_models(self) -> None:
        with (
            patch("services.model_catalog_service.config.get", return_value={}),
            patch("services.model_catalog_service.account_service.list_accounts", return_value=[]),
        ):
            catalog = get_model_catalog()

        self.assertEqual(catalog["chat_models"], [])
        self.assertIn("gpt-image-2", catalog["image_models"])
        self.assertIn("seedance-2.0-fast", catalog["all_models"])
        self.assertNotIn("oreate-chat", catalog["all_models"])

    def test_catalog_keeps_all_oreate_media_models_when_accounts_are_available(self) -> None:
        with (
            patch("services.model_catalog_service.config.get", return_value={}),
            patch(
                "services.model_catalog_service.account_service.list_accounts",
                return_value=[{"status": "正常", "source_type": "oreateai", "quota": 25}],
            ),
        ):
            catalog = get_model_catalog()

        self.assertIn("gpt-image-2", catalog["image_models"])
        self.assertIn("nano-banana-2", catalog["image_models"])
        self.assertIn("seedream", catalog["image_models"])
        self.assertIn("kling-image", catalog["image_models"])
        self.assertIn("seedance-2.0-fast", catalog["video_models"])
        self.assertIn("seedance-2.0-fast", catalog["all_models"])


if __name__ == "__main__":
    unittest.main()
