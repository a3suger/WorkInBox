from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.dashboard import DashboardService


class FakeRecordStore:
    def initialize(self) -> None:
        pass

    def list(self):
        return [object(), object(), object()]


class FakeImap:
    searches: list[tuple[str, ...]] = []

    def __init__(self, *args: object) -> None:
        pass

    def __enter__(self) -> "FakeImap":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def login(self, username: str, password: str):
        return "OK", [b""]

    def select(self, mailbox: str, readonly: bool = False):
        self.readonly = readonly
        return "OK", [b""]

    def search(self, charset, *criteria: str):
        FakeImap.searches.append(criteria)
        mapping = {
            ("UNSEEN", "UNFLAGGED"): b"1 2 3 4",
            ("FLAGGED", "KEYWORD", "wib-answer"): b"10 11",
            ("FLAGGED", "KEYWORD", "wib-review"): b"12",
            ("FLAGGED", "KEYWORD", "wib-watch"): b"13 14 15",
            ("FLAGGED", "KEYWORD", "wib-deadline", "UNKEYWORD", "wib-deadline-done"): b"20",
            ("FLAGGED", "KEYWORD", "wib-schedule", "UNKEYWORD", "wib-schedule-done"): b"21 22",
            ("FLAGGED", "KEYWORD", "wib-pending"): b"23",
            ("FLAGGED", "KEYWORD", "wib-waiting-reply"): b"24 25",
            ("FLAGGED", "KEYWORD", "wib-waiting-action"): b"26",
            ("FLAGGED", "KEYWORD", "wib-action-ready"): b"27 28",
        }
        if criteria[:2] == ("SEEN", "UNFLAGGED"):
            return "OK", [b"5 6"]
        return "OK", [mapping.get(criteria, b"")]


class DashboardServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeImap.searches = []

    def config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )

    @patch("workinbox.dashboard.imaplib.IMAP4_SSL", FakeImap)
    def test_snapshot_counts_unattended_and_workflow_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = DashboardService(
                self.config(Path(directory) / "workinbox.db"),
                record_store=FakeRecordStore(),
            ).snapshot()

        self.assertEqual(snapshot.unattended_unread, 4)
        self.assertEqual(snapshot.unattended_read, 2)
        self.assertEqual(snapshot.normal_total, 6)
        self.assertEqual(snapshot.deadline, 1)
        self.assertEqual(snapshot.schedule, 2)
        self.assertEqual(snapshot.pending, 1)
        self.assertEqual(snapshot.waiting_total, 5)
        self.assertEqual(snapshot.records, 3)

    @patch("workinbox.dashboard.imaplib.IMAP4_SSL", FakeImap)
    def test_read_unattended_search_excludes_all_wib_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            DashboardService(
                self.config(Path(directory) / "workinbox.db"),
                record_store=FakeRecordStore(),
            ).snapshot()

        read_search = next(criteria for criteria in FakeImap.searches if criteria[:2] == ("SEEN", "UNFLAGGED"))
        self.assertIn("wib-answer", read_search)
        self.assertIn("wib-deadline", read_search)
        self.assertIn("wib-action-ready", read_search)
        self.assertIn("wib-bulk", read_search)
        self.assertIn("wib-batch", read_search)


if __name__ == "__main__":
    unittest.main()
