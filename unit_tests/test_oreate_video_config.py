from __future__ import annotations

import unittest

from services.oreate_backend_api import _build_video_config, _extract_generation_urls


class OreateVideoConfigTest(unittest.TestCase):
    def test_seedance_fast_uses_real_ai_type_for_480p_5s_no_audio(self) -> None:
        config = _build_video_config(
            model="seedance-2.0-fast",
            size="1024x576",
            duration=5,
            aspect_ratio="16:9",
            resolution="480P",
            audio=False,
        )

        self.assertEqual(
            config,
            {
                "modelName": "Seedance 2.0 Fast",
                "ratio": "16:9",
                "resolution": "480",
                "duration": 5,
                "isAudio": False,
                "aiType": 14072,
                "scene": "text_or_image",
                "textOrImage": {"image": ""},
            },
        )

    def test_video_url_extraction_stops_before_escaped_quote_backslash(self) -> None:
        raw = (
            'data: {"event":"generating","data":{"result":"'
            '<video src=\\"https://cdn.oreateai.com/aivideo/videodownload/3025605224.mp4\\">"}}'
        )

        self.assertEqual(
            _extract_generation_urls(raw, "aiVideo"),
            ["https://cdn.oreateai.com/aivideo/videodownload/3025605224.mp4"],
        )


if __name__ == "__main__":
    unittest.main()
