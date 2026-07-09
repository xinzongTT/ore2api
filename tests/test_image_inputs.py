import unittest

from api.image_inputs import _should_skip_ssl_verify_for_url


class ImageInputSslVerifyTest(unittest.TestCase):
    def test_oreate_cdn_image_urls_skip_ssl_verification(self):
        self.assertTrue(_should_skip_ssl_verify_for_url("https://cdn.oreateai.com/gpt-image/example.png"))


if __name__ == "__main__":
    unittest.main()
