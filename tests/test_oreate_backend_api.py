import unittest

from services.oreate_backend_api import _run_generation_stream, _should_skip_ssl_verify_for_reference_url


class OreateReferenceSslVerifyTest(unittest.TestCase):
    def test_oreate_cdn_reference_urls_skip_ssl_verification(self):
        self.assertTrue(_should_skip_ssl_verify_for_reference_url("https://cdn.oreateai.com/gpt-image/example.png"))


class OreateStreamParsingTest(unittest.TestCase):
    def test_video_stream_stops_after_first_media_url_even_without_end_event(self):
        class CreateChatResponse:
            status_code = 200
            text = "{}"

            def raise_for_status(self):
                return None

            def json(self):
                return {"data": {"chatId": "chat-smoke"}}

        class StreamResponse:
            status_code = 200
            text = ""

            def iter_lines(self):
                yield 'data: {"content":"https://cdn.oreateai.com/aivideo/smoke.mp4"}'
                raise AssertionError("stream reader continued after receiving video URL")

        class Session:
            def __init__(self):
                self.calls = 0

            def post(self, *args, **kwargs):
                self.calls += 1
                return CreateChatResponse() if self.calls == 1 else StreamResponse()

        result = _run_generation_stream(
            Session(),
            "aiVideo",
            "smoke",
            "videoConfig",
            {"modelName": "Seedance 2.0 Fast"},
        )

        self.assertEqual(result["urls"], ["https://cdn.oreateai.com/aivideo/smoke.mp4"])


if __name__ == "__main__":
    unittest.main()
