from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.image_task_service import ImageTaskService


class ImageTaskReferenceMediaTest(unittest.TestCase):
    def test_submit_generation_keeps_reference_images_in_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ImageTaskService(Path(temp_dir) / "image_tasks.json")
            reference_images = [(b"image-bytes", "reference.png", "image/png")]

            with patch.object(service, "_submit", return_value={"id": "task-1"}) as submit:
                service.submit_generation(
                    {"id": "admin"},
                    client_task_id="task-1",
                    prompt="edit this",
                    model="gpt-image-2",
                    images=reference_images,
                )

        payload = submit.call_args.kwargs["payload"]
        self.assertEqual(payload["images"], reference_images)


if __name__ == "__main__":
    unittest.main()
