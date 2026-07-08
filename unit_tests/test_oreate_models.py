from __future__ import annotations

import unittest

from services.oreate_backend_api import list_models


class OreateModelsTest(unittest.TestCase):
    def test_removed_chat_models_are_not_exposed(self) -> None:
        payload = list_models()
        model_ids = {str(item.get("id") or "") for item in payload["data"]}

        self.assertNotIn("oreate-chat", model_ids)
        self.assertIn("gpt-image-2", model_ids)
        self.assertIn("seedance-2.0-fast", model_ids)


if __name__ == "__main__":
    unittest.main()
