from __future__ import annotations

import io
import logging
import unittest
from unittest.mock import Mock, patch

from workinbox.sync_process import SyncProcessManager


class SyncProcessManagerTest(unittest.TestCase):
    @patch("workinbox.sync_process.Thread")
    @patch("workinbox.sync_process.subprocess.Popen")
    def test_start_runs_workinbox_sync_in_child_process(
        self, popen: Mock, thread: Mock
    ) -> None:
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        process.stdout = io.StringIO("")
        popen.return_value = process
        manager = SyncProcessManager("test-config.yaml")

        started = manager.start()

        self.assertTrue(started)
        command = popen.call_args.args[0]
        self.assertEqual(command[-3:], ["--config", "test-config.yaml", "--emit-progress"])
        self.assertIn("workinbox.main", command)
        self.assertEqual(popen.call_args.kwargs["stdout"], __import__("subprocess").PIPE)
        self.assertEqual(popen.call_args.kwargs["stderr"], __import__("subprocess").STDOUT)
        self.assertTrue(popen.call_args.kwargs["text"])
        thread.return_value.start.assert_called_once_with()
        self.assertTrue(manager.is_running)
        self.assertEqual(manager.pid, 1234)
        self.assertIsNotNone(manager.started_at)

    @patch("workinbox.sync_process.Thread")
    @patch("workinbox.sync_process.subprocess.Popen")
    def test_start_rejects_second_sync_while_running(
        self, popen: Mock, thread: Mock
    ) -> None:
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        process.stdout = io.StringIO("")
        popen.return_value = process
        manager = SyncProcessManager("test-config.yaml")

        self.assertTrue(manager.start())
        self.assertFalse(manager.start(full_recheck=True))
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(thread.call_count, 1)

    @patch("workinbox.sync_process.Thread")
    @patch("workinbox.sync_process.subprocess.Popen")
    def test_full_recheck_adds_cli_flag(self, popen: Mock, thread: Mock) -> None:
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        process.stdout = io.StringIO("")
        popen.return_value = process
        manager = SyncProcessManager("test-config.yaml")

        self.assertTrue(manager.start(full_recheck=True))

        command = popen.call_args.args[0]
        self.assertEqual(command[-1], "--full-recheck")
        self.assertIn("--emit-progress", command)

    def test_forward_output_routes_child_lines_through_logging(self) -> None:
        stream = io.StringIO("first line\nsecond line\n")

        with self.assertLogs("workinbox.sync_process", level=logging.INFO) as captured:
            SyncProcessManager("test-config.yaml")._forward_output(4321, stream)

        self.assertIn("sync[4321] first line", captured.output[0])
        self.assertIn("sync[4321] second line", captured.output[1])
        self.assertIn("output closed: pid=4321", captured.output[2])

    def test_forward_output_captures_structured_progress(self) -> None:
        manager = SyncProcessManager("test-config.yaml")
        stream = io.StringIO(
            'WORKINBOX_PROGRESS {"phase":"triage","label":"TriageBox","current":3,"total":8,"errors":0}\n'
        )

        manager._forward_output(4321, stream)

        self.assertEqual(manager.progress["phase"], "triage")
        self.assertEqual(manager.progress["current"], 3)
        self.assertEqual(manager.progress["total"], 8)


if __name__ == "__main__":
    unittest.main()
