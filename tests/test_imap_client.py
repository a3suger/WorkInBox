from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from workinbox.config import ImapConfig
from workinbox.imap_client import ImapClient, _new_mail_since
from workinbox.models import ImapCheckState, ImapReference


RAW_MESSAGE = (
    b"Message-ID: <new@example>\r\n"
    b"From: sender@example.com\r\n"
    b"To: me@example.com\r\n"
    b"Subject: Hello\r\n"
    b"Date: Sat, 8 Aug 2026 09:00:00 +0000\r\n"
    b"\r\n"
    b"Body"
)


class FakeImap:
    last_search_args: tuple[object, ...] | None = None
    last_select_readonly: bool | None = None

    def __init__(self, *args: object) -> None:
        self.fetch_responses: dict[int, tuple[str, list[object]]] = {
            10: ("OK", [(b"1 (UID 10 FLAGS (\\Seen))", b"")]),
            20: ("OK", [None]),
            30: ("NO", []),
            40: ("OK", [(b"4 (UID 40 FLAGS (\\Flagged \\Seen))", b"")]),
            60: (
                "OK",
                [(b"6 (UID 60 FLAGS (\\Seen \\Flagged $label1 WorkInBoxTest))", b"")],
            ),
        }

    def __enter__(self) -> "FakeImap":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        return "OK", [b""]

    def select(self, mailbox: str, readonly: bool = False) -> tuple[str, list[bytes]]:
        FakeImap.last_select_readonly = readonly
        return "OK", [b"6"]

    def response(self, code: str) -> tuple[str, list[bytes]]:
        return "UIDVALIDITY", [b"55"]

    def uid(self, command: str, *args: object) -> tuple[str, list[object]]:
        if command == "search":
            FakeImap.last_search_args = args
            return "OK", [b"40 50"]
        uid = int(args[0])
        query = str(args[1])
        if query == "(UID FLAGS)":
            return self.fetch_responses[uid]
        if uid == 40:
            return "OK", [(b"4 (UID 40 BODY[] {10})", RAW_MESSAGE), b")"]
        if uid == 50:
            return "NO", []
        raise AssertionError((command, args))


class ImapClientTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeImap.last_search_args = None
        FakeImap.last_select_readonly = None
        self.config = ImapConfig(
            "imap.example", 993, "user", "pass", "INBOX", 7
        )

    @patch("workinbox.imap_client.imaplib.IMAP4_SSL", FakeImap)
    @patch("workinbox.imap_client.date")
    def test_synchronize_distinguishes_states_and_limits_new_discovery(
        self, mock_date
    ) -> None:
        mock_date.today.return_value = date(2026, 8, 8)
        existing = [
            ImapReference("<unstarred@example>", "INBOX", 55, 10),
            ImapReference("<missing@example>", "INBOX", 55, 20),
            ImapReference("<error@example>", "INBOX", 55, 30),
            ImapReference("<flagged@example>", "INBOX", 55, 40),
        ]
        checks, messages = ImapClient(self.config).synchronize(existing)

        self.assertEqual(
            [check.state for check in checks],
            [
                ImapCheckState.UNSTARRED,
                ImapCheckState.MISSING,
                ImapCheckState.ERROR,
                ImapCheckState.FLAGGED,
            ],
        )
        self.assertEqual(
            FakeImap.last_search_args,
            (None, "FLAGGED", "SINCE", "02-Aug-2026"),
        )
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_id, "<new@example>")
        self.assertEqual(messages[0].mailbox, "INBOX")
        self.assertEqual(messages[0].uidvalidity, 55)
        self.assertEqual(messages[0].uid, 40)

    @patch("workinbox.imap_client.imaplib.IMAP4_SSL", FakeImap)
    def test_inspect_flags_reads_keywords_without_write_access(self) -> None:
        snapshot = ImapClient(self.config).inspect_flags(60)

        self.assertTrue(FakeImap.last_select_readonly)
        self.assertEqual(snapshot.mailbox, "INBOX")
        self.assertEqual(snapshot.uidvalidity, 55)
        self.assertEqual(snapshot.uid, 60)
        self.assertEqual(
            snapshot.flags,
            ("\\Seen", "\\Flagged", "$label1", "WorkInBoxTest"),
        )

    def test_new_mail_since_counts_today_as_one_calendar_day(self) -> None:
        self.assertEqual(_new_mail_since(date(2026, 8, 8), 1), date(2026, 8, 8))
        self.assertEqual(_new_mail_since(date(2026, 8, 8), 7), date(2026, 8, 2))

    @patch("workinbox.imap_client.imaplib.IMAP4_SSL", FakeImap)
    def test_uidvalidity_change_aborts_before_state_results(self) -> None:
        existing = [ImapReference("<old@example>", "INBOX", 54, 10)]
        with self.assertRaisesRegex(RuntimeError, "UIDVALIDITY changed"):
            ImapClient(self.config).synchronize(existing)


if __name__ == "__main__":
    unittest.main()
