from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.application import WorkTagService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage, ImapFlagsSnapshot, TrackingStatus


class FakeImapClient:
    def __init__(self, flags: tuple[str, ...]) -> None:
        self.flags = list(flags)
        self.keyword_updates: list[tuple[tuple[str, ...], bool]] = []
        self.flagged_updates: list[bool] = []

    def inspect_flags(self, uid: int, *, expected_uidvalidity: int | None = None):
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, tuple(self.flags))

    def set_keywords(
        self,
        uid: int,
        keywords,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ):
        keys = tuple(keywords)
        self.keyword_updates.append((keys, enabled))
        if enabled:
            for key in keys:
                if key not in self.flags:
                    self.flags.append(key)
        else:
            self.flags = [flag for flag in self.flags if flag not in keys]
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, tuple(self.flags))

    def set_keyword(
        self,
        uid: int,
        keyword: str,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ):
        return self.set_keywords(
            uid,
            (keyword,),
            enabled=enabled,
            expected_uidvalidity=expected_uidvalidity,
        )

    def set_flagged(
        self,
        uid: int,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ):
        self.flagged_updates.append(enabled)
        if enabled:
            if "\\Flagged" not in self.flags:
                self.flags.append("\\Flagged")
        else:
            self.flags = [flag for flag in self.flags if flag != "\\Flagged"]
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, tuple(self.flags))


class PendingResolutionTest(unittest.TestCase):
    def make_service(self, path: Path, flags: tuple[str, ...]):
        config = AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )
        database = EmailDatabase(path)
        database.initialize()
        database.synchronize(
            [
                EmailMessage(
                    "<pending@example>",
                    "sender@example.com",
                    "me@example.com",
                    "Pending",
                    None,
                    "Body",
                    mailbox="INBOX",
                    uidvalidity=10,
                    uid=4,
                )
            ]
        )
        imap = FakeImapClient(flags)
        return WorkTagService(config, database=database, imap_client=imap), database, imap

    def test_normal_resolutions_are_answer_review_and_watch(self) -> None:
        for resolution, expected in (
            ("answer", "wib-answer"),
            ("review", "wib-review"),
            ("watch", "wib-watch"),
        ):
            with self.subTest(resolution=resolution), tempfile.TemporaryDirectory() as directory:
                service, _database, imap = self.make_service(
                    Path(directory) / "workinbox.db",
                    ("\\Flagged", "wib-pending", "wib-deadline"),
                )
                service.resolve_pending("<pending@example>", resolution)

                self.assertIn(expected, imap.flags)
                self.assertNotIn("wib-pending", imap.flags)
                self.assertIn("wib-deadline", imap.flags)
                self.assertIn("\\Flagged", imap.flags)
                self.assertEqual(imap.flagged_updates, [])

    def test_dedicated_workflow_resolutions_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service, _database, _imap = self.make_service(
                Path(directory) / "workinbox.db",
                ("\\Flagged", "wib-pending"),
            )
            for resolution in ("deadline", "schedule", "deadline_schedule"):
                with self.subTest(resolution=resolution):
                    with self.assertRaises(ValueError):
                        service.resolve_pending("<pending@example>", resolution)

    def test_none_moves_mail_to_bulk_and_unstars(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service, database, imap = self.make_service(
                Path(directory) / "workinbox.db",
                ("\\Flagged", "wib-pending"),
            )
            service.resolve_pending("<pending@example>", "none")

            self.assertIn("wib-bulk", imap.flags)
            self.assertNotIn("wib-pending", imap.flags)
            self.assertNotIn("\\Flagged", imap.flags)
            self.assertEqual(imap.flagged_updates, [False])
            tracked = database.list_tracked_emails(active=False)
            self.assertEqual(len(tracked), 1)
            self.assertEqual(tracked[0].tracking_status, TrackingStatus.INACTIVE_UNSTARRED)


if __name__ == "__main__":
    unittest.main()
