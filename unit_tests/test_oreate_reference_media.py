from __future__ import annotations

import unittest
from unittest.mock import patch

from services import oreate_backend_api


class FakeOreateAccountService:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool]] = []

    def get_available_access_token(self, **_kwargs: object) -> str:
        return "oreate-token"

    def get_account(self, access_token: str) -> dict[str, object] | None:
        if access_token != "oreate-token":
            return None
        return {
            "access_token": access_token,
            "source_type": "oreateai",
            "status": "normal",
            "cookies": {"ouss": "session-cookie"},
        }

    def mark_image_result(self, access_token: str, success: bool) -> None:
        self.results.append((access_token, success))


class FakeStreamResponse:
    status_code = 200

    def iter_lines(self):
        yield 'data: {"event":"end","data":{"result":"https://cdn.oreateai.com/aiimage/demo.png"}}'


class FakeSession:
    def __init__(self) -> None:
        self.last_json: dict[str, object] | None = None

    def post(self, _url: str, **kwargs: object) -> FakeStreamResponse:
        self.last_json = kwargs.get("json")  # type: ignore[assignment]
        return FakeStreamResponse()


class OreateReferenceMediaTest(unittest.TestCase):
    def test_generation_stream_sends_reference_attachments(self) -> None:
        session = FakeSession()
        attachments = [
            {
                "bos_url": "oreate/object/path.png",
                "bosUrl": "oreate/object/path.png",
                "doc_title": "reference",
                "doc_type": "png",
                "flag": "upload",
                "type": "file",
                "status": 1,
            }
        ]

        with patch.object(oreate_backend_api, "_create_chat", return_value="chat-1"):
            oreate_backend_api._run_generation_stream(
                session,  # type: ignore[arg-type]
                "aiImage",
                "edit this",
                "imageConfig",
                {"modelName": "Google Nano Banana 2", "ratio": "1:1", "resolution": "1K"},
                attachments=attachments,
            )

        self.assertIsNotNone(session.last_json)
        messages = session.last_json["messages"]  # type: ignore[index]
        self.assertEqual(messages[0]["attachments"], attachments)

    def test_video_generation_uploads_data_url_reference_image(self) -> None:
        fake_accounts = FakeOreateAccountService()
        data_url = "data:image/png;base64,aW1hZ2UtYnl0ZXM="

        with (
            patch.object(oreate_backend_api, "account_service", fake_accounts),
            patch.object(oreate_backend_api, "_make_session", return_value=object()),
            patch.object(oreate_backend_api, "_fetch_video_model_configs", return_value=[]),
            patch.object(
                oreate_backend_api,
                "_upload_oreate_media",
                return_value={"object": "oreate/object/reference.png", "filename": "reference.png", "content_type": "image/png"},
                create=True,
            ) as upload_media,
            patch.object(
                oreate_backend_api,
                "_run_generation_stream",
                return_value={"urls": ["https://cdn.oreateai.com/aivideo/demo.mp4"], "raw": "", "chat_id": "chat-2"},
            ) as run_stream,
        ):
            result = oreate_backend_api.video_generation(
                "animate this",
                image=data_url,
                duration=5,
                resolution="480P",
            )

        self.assertEqual(result["data"][0]["url"], "https://cdn.oreateai.com/aivideo/demo.mp4")
        upload_media.assert_called_once()
        video_config = run_stream.call_args.args[4]
        self.assertEqual(video_config["textOrImage"]["image"], "oreate/object/reference.png")
        self.assertEqual(fake_accounts.results, [("oreate-token", True)])

    def test_video_generation_accepts_image_url_alias(self) -> None:
        fake_accounts = FakeOreateAccountService()
        data_url = "data:image/png;base64,aW1hZ2UtYnl0ZXM="

        with (
            patch.object(oreate_backend_api, "account_service", fake_accounts),
            patch.object(oreate_backend_api, "_make_session", return_value=object()),
            patch.object(oreate_backend_api, "_fetch_video_model_configs", return_value=[]),
            patch.object(
                oreate_backend_api,
                "_upload_oreate_media",
                return_value={"object": "oreate/object/reference.png", "filename": "reference.png", "content_type": "image/png"},
                create=True,
            ) as upload_media,
            patch.object(
                oreate_backend_api,
                "_run_generation_stream",
                return_value={"urls": ["https://cdn.oreateai.com/aivideo/demo.mp4"], "raw": "", "chat_id": "chat-2"},
            ) as run_stream,
        ):
            oreate_backend_api.video_generation(
                "animate this",
                image_url=data_url,
                duration=5,
                resolution="480P",
            )

        upload_media.assert_called_once()
        video_config = run_stream.call_args.args[4]
        self.assertEqual(video_config["textOrImage"]["image"], "oreate/object/reference.png")


if __name__ == "__main__":
    unittest.main()
