"""Ролик 5 советовал «Set temperature to zero» и принудительный tool_choice: по документации на
Claude Sonnet 5.5 и Opus 5.5 это 400. И в 5 кадрах из 11 модель картинок нарисовала мусорный текст
на бумаге, экранах и «базе данных». Такой сценарий должен остановиться до платных сцен."""

import unittest
from unittest import mock

from factory import config, script
from factory.models import Scene, VideoScript


def make(narration: str, visual: str = "glowing glass funnel with particles, dark background") -> VideoScript:
    return VideoScript(title="Invoices to Postgres", description="A design walkthrough.", tags=["ai"],
                       thumbnail_text="PDF TO SQL", scenes=[Scene(narration=narration, visual_prompt=visual)])


# Подсказки картинок ролика 5 для кадров с мусорным текстом (1, 2, 4, 5, 6) — дословно, сокращены.
VIDEO5_TEXTY = [
    "a single sheet of paper drifting through soft blue light and dissolving into glowing structured rows of a database grid",
    "Overhead shot of a tidy desk with a stack of assorted blank paper invoices in different shapes and colors beside a laptop",
    "Close-up of a glowing translucent database cylinder made of stacked glass discs",
    "monitor glow reflecting on the hands, out-of-focus abstract colored code shapes on screen",
    "Macro shot of a magnifying glass hovering over a blank paper document with abstract highlighted rectangular regions",
]
# Кадры ролика 5 без текста (3, 7, 8, 10).
VIDEO5_CLEAN = [
    "Clean isometric 3D illustration of four connected modular blocks on a dark matte surface, linked by thin glowing cables",
    "Side view of a sleek abstract mechanical checkpoint gate on a dark conveyor, small glowing cubes passing through",
    "Cinematic close-up of a server rack in a cool-lit data center aisle, rows of small status lights glowing blue",
    "Elegant abstract visualization of glowing particles flowing through a narrow glass funnel into a small brass meter",
]


class ApiFactsGateTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(config, "PRODUCT_URL", "")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_temperature_advice_stops_build(self):
        with self.assertRaisesRegex(RuntimeError, "temperature"):
            script.check_promises(make("Set temperature to zero to reduce variation between runs."))

    def test_forced_tool_choice_stops_build(self):
        for text in ["Set tool choice to force that tool.", "Gets back fields through a forced tool call.",
                     "Use tool_choice any."]:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                script.check_promises(make(text))

    def test_more_wrong_variants_stop_build(self):
        for text in ["Use a temperature of 0.", "Pass tool-choice with the tool name.",
                     "Force the model to call record invoice.", "Lower the temperature for consistency."]:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                script.check_promises(make(text))

    def test_normal_tool_use_passes(self):
        for text in ["Define one tool with strict true and validate the result in code.",
                     "The sensor reports room temperature every minute.",
                     "Leave tool_choice on auto.", "Set tool_choice to none for the summary call.",
                     "The schema forces the team to agree on field names."]:
            with self.subTest(text=text):
                script.check_promises(make(text))

    def test_warning_against_wrong_advice_passes(self):
        """Прогон 17.11 14:01Z упал на верном совете: ведущий как раз предупреждал не принуждать tool choice."""
        for text in ["If you prefer tools, define the tool with strict set to true, but do not force it with "
                     "tool choice, because Opus 5.5, Sonnet 5.5 and Fable 5.2 reject that with a 400 error.",
                     "Don't set temperature on Sonnet 5.5.", "Never use tool_choice any here.",
                     "Avoid forcing the model to call a tool."]:
            with self.subTest(text=text):
                script.check_promises(make(text))

    def test_wrong_advice_after_a_warning_still_stops_build(self):
        for text in ["Do not guess the fields, set tool choice to force that tool.",
                     "Never skip validation; use tool_choice any."]:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                script.check_promises(make(text))

    def test_negated_objects_in_visual_pass(self):
        script.check_promises(make("Parse the reply in code.",
                                   "A brass desk lamp on an empty oak desk, warm light, no text, no screens, no paper"))

    def test_texty_visuals_from_video5_stop_build(self):
        for visual in VIDEO5_TEXTY:
            with self.subTest(visual=visual[:40]), self.assertRaisesRegex(RuntimeError, "мусорный текст"):
                script.check_promises(make("Parse the reply in code.", visual))

    def test_clean_visuals_from_video5_pass(self):
        for visual in VIDEO5_CLEAN:
            with self.subTest(visual=visual[:40]):
                script.check_promises(make("Parse the reply in code.", visual))

    def test_prompt_carries_api_facts(self):
        prompt = script.system_prompt()
        self.assertIn("temperature", prompt)
        self.assertIn("strict: true", prompt)
        self.assertIn("never show paper", prompt)


if __name__ == "__main__":
    unittest.main()
