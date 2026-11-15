"""Ролик не должен обещать ссылку в описании, если ссылки там не будет (PRODUCT_URL не задан)."""

import unittest
from unittest import mock

from factory import config, script


class CallToActionTest(unittest.TestCase):
    def test_no_link_promised_without_product_url(self):
        with mock.patch.object(config, "PRODUCT_URL", ""):
            prompt = script.system_prompt()
        self.assertNotIn("link in the description", prompt)
        self.assertIn("Do not mention a link", prompt)

    def test_link_promised_when_product_url_is_set(self):
        with mock.patch.object(config, "PRODUCT_URL", "https://example.com/template"):
            prompt = script.system_prompt()
        self.assertIn("link in the description", prompt)

    def test_channel_name_is_substituted(self):
        with mock.patch.object(config, "CHANNEL_NAME", "Test Channel"):
            self.assertIn('"Test Channel"', script.system_prompt())


if __name__ == "__main__":
    unittest.main()
