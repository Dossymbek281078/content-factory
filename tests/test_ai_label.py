"""Описание ролика на YouTube всегда несёт текстовую пометку ИИ: флаг containsSyntheticMedia
зрителю в описании не виден, а у ролика 5 пометки в тексте не было."""

import unittest
from unittest import mock

from factory import config, youtube
from factory.models import Scene, VideoScript

SCRIPT = VideoScript(title="Invoices to Postgres", description="A design walkthrough.", tags=["ai"],
                     thumbnail_text="PDF TO SQL", scenes=[Scene(narration="Done.", visual_prompt="desk")])


class AiLabelTest(unittest.TestCase):
    def test_label_added_without_product_url(self):
        with mock.patch.object(config, "PRODUCT_URL", ""):
            text = youtube.build_description(SCRIPT)
        self.assertTrue(text.startswith("A design walkthrough."))
        self.assertTrue(text.endswith(youtube.AI_LABEL))

    def test_label_added_with_product_url(self):
        with mock.patch.object(config, "PRODUCT_URL", "https://example.test/p"):
            text = youtube.build_description(SCRIPT)
        self.assertTrue(text.startswith("Template and code: https://example.test/p"))
        self.assertTrue(text.endswith(youtube.AI_LABEL))

    def test_label_not_doubled(self):
        script = SCRIPT.model_copy(update={"description": "Walkthrough.\n\n" + youtube.AI_LABEL})
        with mock.patch.object(config, "PRODUCT_URL", ""):
            text = youtube.build_description(script)
        self.assertEqual(text.count(youtube.AI_LABEL), 1)


if __name__ == "__main__":
    unittest.main()
