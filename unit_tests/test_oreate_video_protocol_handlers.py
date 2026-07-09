from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from services.protocol import openai_v1_video_generations


class FakeJsonRequest:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body

    async def json(self) -> dict[str, object]:
        return self.body


class OreateVideoProtocolHandlersTest(unittest.TestCase):
    def test_video_generation_handler_normalizes_legacy_seedance_model(self) -> None:
        with patch(
            "services.protocol.openai_v1_video_generations.video_generation",
            return_value={"created": 1, "data": [{"url": "https://cdn.oreateai.com/aivideo/unit-test-video.mp4"}]},
        ) as video_generation:
            response = asyncio.run(openai_v1_video_generations.handle_video_generations(FakeJsonRequest({
                "prompt": "animate this",
                "model": "seedance-2.0",
            })))

        payload = json.loads(response.body)
        self.assertEqual(payload["data"][0]["url"], "https://cdn.oreateai.com/aivideo/unit-test-video.mp4")
        self.assertEqual(video_generation.call_args.kwargs["model"], "seedance-2.0-fast")


if __name__ == "__main__":
    unittest.main()
