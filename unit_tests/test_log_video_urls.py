from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from services.log_service import LoggedCall


class LoggedCallVideoUrlsTest(unittest.TestCase):
    def test_video_generation_result_urls_are_logged(self) -> None:
        captured: list[dict[str, object]] = []
        call = LoggedCall(
            {"id": "admin", "name": "管理员", "role": "admin"},
            "/v1/video/generations",
            "seedance-2.0-fast",
            "文生视频",
            request_text="城市夜景延时摄影",
        )

        async def run_call() -> object:
            return await call.run(
                lambda: {
                    "created": 1,
                    "data": [{"url": "https://cdn.oreateai.com/aivideo/sample.mp4"}],
                }
            )

        with patch("services.log_service.log_service.add") as add:
            result = asyncio.run(run_call())
            captured.extend(args[2] for args, _kwargs in add.call_args_list)

        self.assertEqual(result["data"][0]["url"], "https://cdn.oreateai.com/aivideo/sample.mp4")
        self.assertTrue(captured)
        self.assertIn("https://cdn.oreateai.com/aivideo/sample.mp4", captured[-1]["urls"])


if __name__ == "__main__":
    unittest.main()
