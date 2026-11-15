"""Упавший ролик должен сам вернуться в работу при следующем запуске по расписанию,
но не больше MAX_ATTEMPTS раз, чтобы сломанная тема не запирала очередь."""

import argparse
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from factory import __main__ as cli
from factory import config, store


def run_once() -> int:
    return cli.cmd_run(argparse.Namespace(limit=1, dry_run=True, upload=False))


class RetryTest(unittest.TestCase):
    def setUp(self):
        # cmd_run держит своё соединение до выхода процесса, а Windows не удаляет открытый файл.
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)  # чтобы sync_topics не подхватил настоящий topics.txt
        self.addCleanup(os.chdir, self.cwd)
        patcher = mock.patch.object(config, "DATA_DIR", Path(self.tmp.name) / "data")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.db = store.connect()
        self.addCleanup(self.db.close)
        self.first = store.add(self.db, "first")
        self.second = store.add(self.db, "second")

    def status(self, video_id):
        return store.get(self.db, video_id)["status"]

    def test_failed_video_is_retried_on_next_run(self):
        with mock.patch.object(cli, "render", side_effect=RuntimeError("сеть")):
            self.assertEqual(run_once(), 1)
        self.assertEqual(self.status(self.first), "failed")

        rendered = []

        def record_and_fail(row, dry_run):
            rendered.append(row["id"])
            raise RuntimeError("снова")

        with mock.patch.object(cli, "render", side_effect=record_and_fail):
            run_once()
        self.assertEqual(rendered, [self.first], "второй запуск должен повторить упавший ролик")

    def test_broken_topic_stops_blocking_queue_after_max_attempts(self):
        seen = []

        def always_fail_first(row, dry_run):
            seen.append(row["id"])
            raise RuntimeError("тема сломана")

        with mock.patch.object(cli, "render", side_effect=always_fail_first):
            for _ in range(store.MAX_ATTEMPTS + 1):
                run_once()
        self.assertEqual(seen, [self.first] * store.MAX_ATTEMPTS + [self.second])
        self.assertEqual(self.status(self.first), "failed")

    def test_killed_build_still_counts_as_an_attempt(self):
        # Railway убивает контейнер (таймаут, память): исключения нет, процесс просто исчезает.
        class Killed(BaseException):
            pass

        seen = []

        def killed(row, dry_run):
            seen.append(row["id"])
            raise Killed

        with mock.patch.object(cli, "render", side_effect=killed):
            for _ in range(store.MAX_ATTEMPTS + 1):
                with self.assertRaises(Killed):
                    run_once()
        self.assertEqual(seen, [self.first] * store.MAX_ATTEMPTS + [self.second],
                         "ролик, который каждый раз убивают, не должен запускаться бесконечно")

        cli.cmd_retry(argparse.Namespace())
        self.assertEqual(store.get(self.db, self.first)["attempts"], 0, "retry должен вернуть и убитый ролик")

    def test_successful_build_is_not_retried(self):
        with mock.patch.object(cli, "render", return_value=(mock.Mock(model_dump_json=lambda: "{}"), Path("x.mp4"))), \
                mock.patch.object(cli.media, "duration", return_value=1.0):
            run_once()
        self.assertEqual(self.status(self.first), "rendered")
        self.assertEqual([r["id"] for r in store.runnable(self.db)], [self.second])

    def test_manual_retry_resets_attempts(self):
        with mock.patch.object(cli, "render", side_effect=RuntimeError("x")):
            for _ in range(store.MAX_ATTEMPTS):
                run_once()
        cli.cmd_retry(argparse.Namespace())
        row = store.get(self.db, self.first)
        self.assertEqual((row["status"], row["attempts"]), ("queued", 0))

    def test_old_database_without_attempts_column_is_migrated(self):
        self.db.close()
        path = config.DATA_DIR / "queue.db"
        path.unlink()
        old = sqlite3.connect(path)
        old.execute("CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, "
                    "status TEXT NOT NULL DEFAULT 'queued', script_json TEXT, video_path TEXT, youtube_id TEXT, "
                    "error TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        old.execute("INSERT INTO videos (topic, status) VALUES ('legacy', 'failed')")
        old.commit()
        old.close()
        self.db = store.connect()
        self.assertEqual(store.get(self.db, 1)["attempts"], 0)
        self.assertEqual([r["topic"] for r in store.runnable(self.db, 1)], ["legacy"])


if __name__ == "__main__":
    unittest.main()
