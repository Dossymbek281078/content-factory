import os
import sys
import unittest
from unittest import mock

from factory import __main__ as cli
from factory import config


class ProjectGuardTest(unittest.TestCase):
    """Вторая служба Railway на том же репозитории не должна платить за сцены."""

    def run_cli(self, argv, env):
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(sys, "argv", ["factory", *argv]), \
             mock.patch.object(cli, "cmd_run", return_value=0) as run, \
             mock.patch.object(cli, "cmd_upload", return_value=0) as upload:
            code = cli.main()
        return code, run, upload

    def test_foreign_project_skips_run_and_exits_zero(self):
        code, run, _ = self.run_cli(["run", "--limit", "1", "--upload"], {"RAILWAY_PROJECT_ID": "other-project"})
        self.assertEqual(code, 0)  # 0, чтобы restart ON_FAILURE не запускал снова
        run.assert_not_called()

    def test_foreign_project_skips_upload(self):
        code, run, upload = self.run_cli(["upload", "3"], {"RAILWAY_PROJECT_ID": "other-project"})
        self.assertEqual(code, 0)
        upload.assert_not_called()
        run.assert_not_called()

    def test_foreign_project_touches_nothing_paid(self):
        """Сквозной: настоящий cmd_run, подменены только платные вызовы и база."""
        paid = [mock.patch.object(cli.media, "voice"), mock.patch.object(cli.media, "visual"),
                mock.patch.object(cli, "generate_script"), mock.patch.object(cli.store, "connect")]
        mocks = [p.start() for p in paid]
        self.addCleanup(mock.patch.stopall)
        with mock.patch.dict(os.environ, {"RAILWAY_PROJECT_ID": "other-project"}), \
             mock.patch.object(sys, "argv", ["factory", "run", "--limit", "1", "--upload"]):
            self.assertEqual(cli.main(), 0)
        for m in mocks:
            m.assert_not_called()

    def test_empty_project_id_is_local(self):
        _, run, _ = self.run_cli(["run"], {"RAILWAY_PROJECT_ID": ""})
        run.assert_called_once()

    def test_foreign_project_still_lists(self):
        with mock.patch.dict(os.environ, {"RAILWAY_PROJECT_ID": "other-project"}), \
             mock.patch.object(sys, "argv", ["factory", "list"]), \
             mock.patch.object(cli, "cmd_list", return_value=0) as listing:
            cli.main()
        listing.assert_called_once()

    def test_home_project_runs(self):
        _, run, _ = self.run_cli(["run"], {"RAILWAY_PROJECT_ID": config.HOME_RAILWAY_PROJECT_ID})
        run.assert_called_once()

    def test_outside_railway_runs(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RAILWAY_PROJECT_ID", None)
            with mock.patch.object(sys, "argv", ["factory", "run", "--dry-run"]), \
                 mock.patch.object(cli, "cmd_run", return_value=0) as run:
                cli.main()
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
