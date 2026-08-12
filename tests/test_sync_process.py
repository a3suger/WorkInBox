from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from workinbox.sync_process import SyncProcessManager


class SyncProcessManagerTest(unittest.TestCase):
    @patch("workinbox.sync_process.subprocess.Popen")
    def test_start_runs_workinbox_sync_in_child_process(self, popen: Mock) -> None:
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        popen.return_value = process
        manager = SyncProcessManager("test-config.yaml")

        started = manager.start()

        self.assertTrue(started)
        command = popen.call_args.args[0]
        self.assertEqual(command[-3:], ["--config", "test-config.yaml"][-3:])
        self.assertIn("workinbox.main", command)
        self.assertTrue(manager.is_running)
        self.assertEqual(manager.pid, 1234)

    @patch("workinbox.sync_process.subprocess.Popen")
    def test_start_rejects_second_sync_while_running(self, popen: Mock) -> None:
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        popen.return_value = process
        manager = SyncProcessManager("test-config.yaml")

        self.assertTrue(manager.start())
        self.assertFalse(manager.start(full_recheck=True))
        self.assertEqual(popen.call_count, 1)

    @patch("workinbox.sync_process.subprocess.Popen")
    def test_full_recheck_adds_cli_flag(self, popen: Mock) -> None:
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        popen.return_value = process
        manager = SyncProcessManager("test-config.yaml")

        self.assertTrue(manager.start(full_recheck=True))

        command = popen.call_args.args[0]
        self.assertEqual(command[-1], "--full-recheck")


if __name__ == "__main__":
    unittest.main()
