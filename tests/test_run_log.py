"""Полный лог прогона пишется в файл на томе: Railway отдаёт по развёртыванию только последние
50 строк, и 15.11 причина «Deployment crashed» так и потерялась."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from factory import config, runlog

ROOT = Path(__file__).resolve().parent.parent


class RunLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "data"
        patcher = mock.patch.object(config, "DATA_DIR", self.data)
        patcher.start()
        self.addCleanup(patcher.stop)

    def logs(self):
        return sorted((self.data / "logs").glob("run-*.log"))

    def call(self, fn):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = runlog.run_logged(fn, None)
        return code, out.getvalue(), err.getvalue()

    def test_stdout_stderr_and_exit_code_go_to_file_and_console(self):
        def fn(_):
            print("сцена 1/3")
            print("ОШИБКА загрузки: 403", file=sys.stderr)
            return 1

        code, out, err = self.call(fn)
        self.assertEqual(code, 1)
        self.assertIn("сцена 1/3", out)  # в railway logs строки остаются
        self.assertIn("403", err)
        [log] = self.logs()
        text = log.read_text(encoding="utf-8")
        for line in ("сцена 1/3", "ОШИБКА загрузки: 403", "код выхода 1"):
            self.assertIn(line, text)

    def test_unhandled_exception_traceback_is_kept(self):
        def fn(_):
            raise ValueError("ffmpeg упал")

        code, _, err = self.call(fn)
        self.assertEqual(code, 1)
        self.assertIn("Traceback", err)
        text = self.logs()[0].read_text(encoding="utf-8")
        self.assertIn("Traceback", text)
        self.assertIn("ValueError: ffmpeg упал", text)
        self.assertIn("код выхода 1", text)

    def test_streams_are_restored(self):
        before = sys.stdout, sys.stderr
        self.call(lambda _: 0)
        self.assertEqual((sys.stdout, sys.stderr), before)

    def test_next_run_prints_tail_of_previous_log(self):
        # Том читается только из работающего контейнера, а cron-служба между прогонами стоит:
        # хвост прошлого лога должен попасть в railway logs следующего прогона.
        logs = self.data / "logs"
        logs.mkdir(parents=True)
        lines = [f"строка {i}" for i in range(40)] + ["MemoryError: ffmpeg"]
        (logs / "run-20260101T000000Z.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
        _, out, _ = self.call(lambda _: 0)
        self.assertIn("run-20260101T000000Z.log", out)
        self.assertIn("MemoryError: ffmpeg", out)
        self.assertNotIn("строка 5\n", out)  # только хвост, не весь файл

    def test_log_dir_failure_does_not_stop_the_run(self):
        # Том полон или без прав: ролик важнее лога.
        with mock.patch.object(runlog, "_open_log", side_effect=OSError("No space left on device")):
            code, out, err = self.call(lambda _: print("сцена 1/1") or 0)
        self.assertEqual(code, 0)
        self.assertIn("сцена 1/1", out)
        self.assertIn("No space left on device", err)

    def test_log_write_failure_mid_run_does_not_stop_the_run(self):
        class Full(io.StringIO):
            def write(self, text):
                raise OSError("No space left on device")

        with mock.patch.object(runlog, "_open_log", return_value=Full()):
            code, out, _ = self.call(lambda _: print("сцена 1/1") or 0)
        self.assertEqual(code, 0)
        self.assertIn("сцена 1/1", out)

    def test_old_logs_are_pruned(self):
        logs = self.data / "logs"
        logs.mkdir(parents=True)
        for i in range(runlog.KEEP + 5):
            (logs / f"run-20260101T0000{i:02}Z.log").write_text("x", encoding="utf-8")
        self.call(lambda _: 0)
        self.assertEqual(len(self.logs()), runlog.KEEP)
        self.assertFalse((logs / "run-20260101T000000Z.log").exists())  # старейший удалён


class RunCommandWritesLogTest(unittest.TestCase):
    def test_scheduled_run_with_empty_queue_leaves_a_log(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            env = {**os.environ, "DATA_DIR": str(Path(tmp) / "data"), "PYTHONPATH": str(ROOT),
                   "PYTHONIOENCODING": "utf-8"}
            env.pop("RAILWAY_PROJECT_ID", None)
            proc = subprocess.run([sys.executable, "-m", "factory", "run", "--limit", "1"],
                                  cwd=tmp, env=env, capture_output=True, timeout=60)
            self.assertEqual(proc.returncode, 2, proc.stderr.decode("utf-8", "replace"))
            [log] = (Path(tmp) / "data" / "logs").glob("run-*.log")
            text = log.read_text(encoding="utf-8")
            self.assertIn("очередь пуста", text)
            self.assertIn("код выхода 2", text)


if __name__ == "__main__":
    unittest.main()
