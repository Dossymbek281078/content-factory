"""Сценарий не должен утверждать о продукте то, чего код не делает или что никто не проверял
(сверка ролика 3: «numbers never invented», «verified report», «posts itself»)."""

import unittest
from unittest import mock

from factory import config, script
from factory.models import Scene, VideoScript


def video(narration: str, description: str = "How to build it.") -> VideoScript:
    return VideoScript(title="Feedback reports", description=description, tags=["ai"], thumbnail_text="AUTO",
                       scenes=[Scene(narration=narration, visual_prompt="desk")])


class ClaimsGateTest(unittest.TestCase):
    def test_overclaims_are_caught(self):
        for line in ("The numbers are never invented by the model.", "You get a verified, cited report.", "It becomes a verified, cited feedback report.",
                     "It posts itself to Slack every Monday.", "Accuracy is guaranteed.",
                     "It is 100% accurate.", "Zero hallucinations.", "It never misses a lead.",
                     "Leads get routed in seconds.", "The CRM stays clean."):
            with self.subTest(line=line):
                self.assertTrue(script.overclaims(video(line)))

    def test_build_steps_pass(self):
        for line in ("Verify the webhook signature before parsing.", "Schedule the script with a cron job.",
                     "Here is how to post the summary to Slack.", "Check each quote against the transcript.",
                     "This step takes a few seconds per ticket in our design."):
            with self.subTest(line=line):
                self.assertEqual(script.overclaims(video(line)), [])

    def test_check_promises_rejects_overclaim_before_scenes(self):
        with mock.patch.object(config, "PRODUCT_URL", ""):
            with self.assertRaises(RuntimeError) as caught:
                script.check_promises(video("You get a verified, cited report."))
        self.assertIn("verified", str(caught.exception))

    def test_prompt_forbids_claims_about_results(self):
        self.assertIn("Do not claim results", script.system_prompt())

    def test_mock_script_passes(self):
        self.assertEqual(script.overclaims(script.mock_script("x")), [])


if __name__ == "__main__":
    unittest.main()
