"""Сценарий, который обещает ссылку, шаблон или код, собирается только при живой странице
PRODUCT_URL: иначе ролик встаёт уже собранным и оплаченным (так было с роликом 1)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from factory import __main__ as cli
from factory import config, script
from factory.models import Scene, VideoScript

PROMISING = VideoScript(title="Meetings to tasks", description="The code template is linked below.", tags=["ai"],
                        thumbnail_text="AUTO", scenes=[Scene(narration="Done.", visual_prompt="desk")])


class PromiseGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(config, "DATA_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.row = {"id": 3, "topic": "meetings"}
        self.work = Path(self.tmp.name) / "video_0003"

    def render_promising(self, url: str, page_ok: bool):
        with mock.patch.object(config, "PRODUCT_URL", url), \
                mock.patch.object(cli, "generate_script", return_value=PROMISING), \
                mock.patch.object(script, "page_is_live", return_value=page_ok), \
                mock.patch.object(cli.media, "voice") as voice, mock.patch.object(cli.media, "visual") as visual:
            with self.assertRaises(RuntimeError) as caught:
                cli.render(self.row, dry_run=False)
        voice.assert_not_called()
        visual.assert_not_called()
        return caught.exception

    def test_promise_without_product_url_stops_before_paid_scenes(self):
        error = self.render_promising("", page_ok=False)
        self.assertIn("PRODUCT_URL", str(error))
        # Сцен ещё нет — сценарий удаляется, следующая попытка напишет новый.
        self.assertFalse((self.work / "script.json").exists())

    def test_promise_with_dead_page_stops_before_paid_scenes(self):
        self.render_promising("https://example.com/lab/x", page_ok=False)

    def test_cached_script_with_paid_scenes_is_kept(self):
        self.work.mkdir(parents=True)
        (self.work / "script.json").write_text(PROMISING.model_dump_json(), encoding="utf-8")
        (self.work / "scene_00.mp3").write_bytes(b"paid")
        with mock.patch.object(config, "PRODUCT_URL", ""):
            with self.assertRaises(RuntimeError):
                cli.render(self.row, dry_run=False)
        # Озвучка уже оплачена под этот сценарий: новый сценарий разошёлся бы с ней.
        self.assertTrue((self.work / "script.json").exists())

    def test_promise_with_live_page_passes(self):
        with mock.patch.object(config, "PRODUCT_URL", "https://example.com/lab/x"), \
                mock.patch.object(script, "page_is_live", return_value=True):
            script.check_promises(PROMISING)

    def test_plain_script_needs_no_page(self):
        plain = PROMISING.model_copy(update={"description": "How it works."})
        with mock.patch.object(config, "PRODUCT_URL", ""):
            script.check_promises(plain)

    def test_dry_run_mock_script_promises_nothing(self):
        self.assertEqual(script.promised_links(script.mock_script("x")), [])


if __name__ == "__main__":
    unittest.main()
