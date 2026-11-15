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


def video(narration: str, description: str = "How it works.") -> script.VideoScript:
    return script.VideoScript(title="Meeting notes to tasks", description=description, tags=["ai"],
                              thumbnail_text="AUTO", scenes=[script.Scene(narration=narration, visual_prompt="desk")])


class StaleScriptTest(unittest.TestCase):
    """Сценарий из кэша мог быть написан до правила «без ссылки» — загрузка должна его поймать."""

    def test_finds_promise_in_narration(self):
        found = script.promised_links(video("Grab the template from the link in the description."))
        self.assertTrue(found)

    def test_finds_promise_in_description(self):
        self.assertTrue(script.promised_links(video("Done.", description="Download the code below.")))

    def test_plain_script_passes(self):
        self.assertEqual(script.promised_links(video("Now every meeting ends with a task list.")), [])

    def test_ordinary_automation_steps_pass(self):
        for line in ("Link the Slack node to Gmail.", "Use an HTTP node to download the PDF.",
                     "Extract all links from the page.", "Zapier links your apps.",
                     "Download the attachment, then comment the code.", "Copy the workflow ID from the URL.",
                     "Now get the workflow running on a schedule."):
            with self.subTest(line=line):
                self.assertEqual(script.promised_links(video(line)), [])

    def test_varied_promises_are_caught(self):
        for line in ("Grab the free template.", "Get my workflow and try it.", "It's in the video description.",
                     "Check the description box.", "Details down below.", "See below for the setup.",
                     "It's in the show notes.", "Find it in the pinned comment.", "Link in bio.",
                     "The template is free.", "Comment TEMPLATE and I'll send it.", "The link is below.",
                     "Everything is under the video.", "Download my blueprint."):
            with self.subTest(line=line):
                self.assertTrue(script.promised_links(video(line)))

    def test_tags_and_thumbnail_are_scanned(self):
        v = video("Done.")
        v.thumbnail_text = "FREE TEMPLATE BELOW"
        self.assertTrue(script.promised_links(v))

    def test_upload_refuses_stale_promise_without_product_url(self):
        from factory import __main__ as cli
        row = {"id": 7, "video_path": "final.mp4",
               "script_json": video("Check the link in the description.").model_dump_json()}
        with mock.patch.object(config, "PRODUCT_URL", ""), \
                mock.patch("factory.youtube.upload_private") as sent:
            with self.assertRaises(RuntimeError):
                cli.upload(None, row)
        sent.assert_not_called()


if __name__ == "__main__":
    unittest.main()
