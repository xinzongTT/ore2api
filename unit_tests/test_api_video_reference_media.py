from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import ai


class ApiVideoReferenceMediaTest(unittest.TestCase):
    def test_video_generation_accepts_image_url_alias(self) -> None:
        app = FastAPI()
        app.include_router(ai.create_router())

        with (
            patch("api.ai.require_identity", return_value={"id": "admin", "role": "admin"}),
            patch("api.ai.check_request", return_value=None),
            patch("services.log_service.log_service.add"),
            patch(
                "api.ai._oreate_api.video_generation",
                return_value={"created": 1, "data": [{"url": "https://cdn.oreateai.com/aivideo/demo.mp4"}]},
            ) as video_generation,
        ):
            response = TestClient(app).post(
                "/v1/video/generations",
                headers={"Authorization": "Bearer test"},
                json={"prompt": "animate this", "image_url": "data:image/png;base64,aW1hZ2U="},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["url"], "https://cdn.oreateai.com/aivideo/demo.mp4")
        self.assertEqual(video_generation.call_args.kwargs["image"], "data:image/png;base64,aW1hZ2U=")

    def test_video_generation_accepts_first_images_item(self) -> None:
        app = FastAPI()
        app.include_router(ai.create_router())

        with (
            patch("api.ai.require_identity", return_value={"id": "admin", "role": "admin"}),
            patch("api.ai.check_request", return_value=None),
            patch("services.log_service.log_service.add"),
            patch(
                "api.ai._oreate_api.video_generation",
                return_value={"created": 1, "data": [{"url": "https://cdn.oreateai.com/aivideo/demo.mp4"}]},
            ) as video_generation,
        ):
            response = TestClient(app).post(
                "/v1/video/generations",
                headers={"Authorization": "Bearer test"},
                json={
                    "prompt": "animate this",
                    "images": [
                        "data:image/png;base64,aW1hZ2U=",
                        "data:image/png;base64,b3RoZXI=",
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(video_generation.call_args.kwargs["image"], "data:image/png;base64,aW1hZ2U=")


if __name__ == "__main__":
    unittest.main()
