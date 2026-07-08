from __future__ import annotations

import unittest

from api.ai import ImageGenerationRequest, VideoGenerationRequest


class ApiRequestModelsTest(unittest.TestCase):
    def test_image_generation_defaults_to_url_response_format(self) -> None:
        body = ImageGenerationRequest(prompt="draw a cube")

        self.assertEqual(body.response_format, "url")

    def test_image_generation_preserves_reference_images(self) -> None:
        body = ImageGenerationRequest(
            prompt="edit this",
            images=["data:image/png;base64,aW1hZ2U="],
            image_url="https://example.com/reference.png",
        )

        payload = body.model_dump(mode="python")
        self.assertEqual(payload["images"], ["data:image/png;base64,aW1hZ2U="])
        self.assertEqual(payload["image_url"], "https://example.com/reference.png")

    def test_video_generation_preserves_audio_and_image_fields(self) -> None:
        body = VideoGenerationRequest(
            prompt="animate this",
            audio=True,
            image="https://cdn.oreateai.com/aiimage/reference.png",
            image_url="https://cdn.oreateai.com/aiimage/reference-url.png",
            images=["https://cdn.oreateai.com/aiimage/reference-list.png"],
        )

        payload = body.model_dump(mode="python")
        self.assertTrue(payload["audio"])
        self.assertEqual(payload["image"], "https://cdn.oreateai.com/aiimage/reference.png")
        self.assertEqual(payload["image_url"], "https://cdn.oreateai.com/aiimage/reference-url.png")
        self.assertEqual(payload["images"], ["https://cdn.oreateai.com/aiimage/reference-list.png"])


if __name__ == "__main__":
    unittest.main()
