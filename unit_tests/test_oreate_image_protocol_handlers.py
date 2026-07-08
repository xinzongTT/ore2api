from __future__ import annotations

import unittest
from unittest.mock import patch

from services.protocol import openai_v1_image_edit, openai_v1_image_generations


class OreateImageProtocolHandlersTest(unittest.TestCase):
    def test_image_generation_handler_delegates_to_oreate_backend(self) -> None:
        with patch(
            "services.protocol.openai_v1_image_generations.oreate_backend_api.image_generation",
            return_value={"created": 1, "data": [{"url": "https://cdn.oreateai.com/aiimage/demo.png"}]},
        ) as image_generation:
            result = openai_v1_image_generations.handle({
                "prompt": "draw a cube",
                "model": "gpt-image-2",
                "n": 1,
                "size": "1024x1024",
                "response_format": "url",
            })

        self.assertEqual(result["data"][0]["url"], "https://cdn.oreateai.com/aiimage/demo.png")
        image_generation.assert_called_once()
        self.assertEqual(image_generation.call_args.kwargs["prompt"], "draw a cube")
        self.assertEqual(image_generation.call_args.kwargs["response_format"], "url")

    def test_image_generation_handler_passes_reference_images(self) -> None:
        with patch(
            "services.protocol.openai_v1_image_generations.oreate_backend_api.image_generation",
            return_value={"created": 1, "data": [{"url": "https://cdn.oreateai.com/aiimage/demo.png"}]},
        ) as image_generation:
            openai_v1_image_generations.handle({
                "prompt": "edit this",
                "images": [(b"image-bytes", "reference.png", "image/png")],
            })

        self.assertEqual(
            image_generation.call_args.kwargs["images"],
            [(b"image-bytes", "reference.png", "image/png")],
        )

    def test_image_edit_handler_delegates_reference_images_to_generation(self) -> None:
        with patch(
            "services.oreate_backend_api.image_generation",
            return_value={"created": 1, "data": [{"url": "https://cdn.oreateai.com/aiimage/edit.png"}]},
        ) as image_generation:
            result = openai_v1_image_edit.handle({
                "prompt": "edit this",
                "model": "gpt-image-2",
                "n": 1,
                "images": [(b"image-bytes", "reference.png", "image/png")],
            })

        self.assertEqual(result["data"][0]["url"], "https://cdn.oreateai.com/aiimage/edit.png")
        image_generation.assert_called_once()
        self.assertEqual(image_generation.call_args.kwargs["prompt"], "edit this")
        self.assertEqual(
            image_generation.call_args.kwargs["images"],
            [(b"image-bytes", "reference.png", "image/png")],
        )


if __name__ == "__main__":
    unittest.main()
