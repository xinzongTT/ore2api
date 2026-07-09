from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import ai, image_tasks


class ApiImageEditRoutesTest(unittest.TestCase):
    def test_openai_image_edits_accepts_json_reference_image(self) -> None:
        app = FastAPI()
        app.include_router(ai.create_router())

        with (
            patch("api.ai.require_identity", return_value={"id": "admin", "role": "admin"}),
            patch("api.ai.check_request", return_value=None),
            patch("services.log_service.log_service.add"),
            patch(
                "services.oreate_backend_api.image_generation",
                return_value={"created": 1, "data": [{"url": "https://cdn.oreateai.com/aiimage/edit.png"}]},
            ) as image_generation,
        ):
            response = TestClient(app).post(
                "/v1/images/edits",
                headers={"Authorization": "Bearer test"},
                json={
                    "prompt": "edit this",
                    "image": "data:image/png;base64,aW1hZ2U=",
                    "aspect_ratio": "16:9",
                    "resolution": "4K",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["url"], "https://cdn.oreateai.com/aiimage/edit.png")
        image_generation.assert_called_once()
        self.assertEqual(image_generation.call_args.kwargs["response_format"], "url")
        self.assertEqual(image_generation.call_args.kwargs["images"][0], (b"image", "image_url.png", "image/png"))
        self.assertEqual(image_generation.call_args.kwargs["aspect_ratio"], "16:9")
        self.assertEqual(image_generation.call_args.kwargs["resolution"], "4K")

    def test_image_task_edits_accepts_multipart_reference_image(self) -> None:
        app = FastAPI()
        app.include_router(image_tasks.create_router())

        with (
            patch("api.image_tasks.require_identity", return_value={"id": "admin", "role": "admin"}),
            patch("api.image_tasks.check_request", return_value=None),
            patch.object(
                image_tasks.image_task_service,
                "submit_edit",
                return_value={"id": "task-1", "status": "queued"},
            ) as submit_edit,
        ):
            response = TestClient(app).post(
                "/api/image-tasks/edits",
                headers={"Authorization": "Bearer test"},
                data={
                    "client_task_id": "task-1",
                    "prompt": "edit this",
                    "model": "gpt-image-2",
                    "aspect_ratio": "9:16",
                    "resolution": "2K",
                },
                files={"image": ("reference.png", b"image-bytes", "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        submit_edit.assert_called_once()
        self.assertEqual(submit_edit.call_args.kwargs["client_task_id"], "task-1")
        self.assertEqual(submit_edit.call_args.kwargs["images"], [(b"image-bytes", "reference.png", "image/png")])
        self.assertEqual(submit_edit.call_args.kwargs["aspect_ratio"], "9:16")
        self.assertEqual(submit_edit.call_args.kwargs["resolution"], "2K")


if __name__ == "__main__":
    unittest.main()
