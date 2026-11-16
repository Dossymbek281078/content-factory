"""Запуск по расписанию с пустой очередью не должен молча выходить с кодом 0:
16.11 так прошёл день без ролика, и в логах Railway не было ни строки."""

import argparse
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from factory import __main__ as cli
from factory import config, store


class EmptyQueueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)  # без topics.txt
        self.addCleanup(os.chdir, self.cwd)
        patcher = mock.patch.object(config, "DATA_DIR", Path(self.tmp.name) / "data")
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, upload: bool):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.cmd_run(argparse.Namespace(limit=1, dry_run=True, upload=upload))
        return code, err.getvalue()

    def test_empty_queue_fails_loudly(self):
        code, err = self.run_cli(upload=True)
        self.assertNotEqual(code, 0)
        self.assertIn("очередь пуста", err)
        self.assertIn("topics.txt", err)

    def test_done_videos_do_not_count_as_work(self):
        db = store.connect()
        self.addCleanup(db.close)
        vid = store.add(db, "old")
        store.update(db, vid, status="uploaded")
        code, err = self.run_cli(upload=True)
        self.assertNotEqual(code, 0)
        self.assertIn("очередь пуста", err)

    def test_pending_upload_is_work(self):
        db = store.connect()
        self.addCleanup(db.close)
        vid = store.add(db, "old")
        store.update(db, vid, status="rendered")
        with mock.patch.object(cli, "upload"):
            code, err = self.run_cli(upload=True)
        self.assertEqual(code, 0)
        self.assertNotIn("очередь пуста", err)


if __name__ == "__main__":
    unittest.main()
