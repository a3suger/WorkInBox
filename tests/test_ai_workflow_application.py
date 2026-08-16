from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.ai_classifier import AiClassification
from workinbox.application import SynchronizationService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage, ImapFlagsSnapshot, TrackingStatus


class FakeClassifier:
    def classify(self, message: EmailMessage) -> AiClassification:
        return AiClassification(False, False, normal_workflow="none", reason="対応不要")


class FakeImapClient:
    def __init__(self) -> None:
        self.flags = ("\\Flagged",)
        self.keyword_updates: list[tuple[tuple[str, ...], bool]] = []
        self.flagged_updates: list[bool] = []

    def set_keywords(
        self,
        uid: int,
        keywords: tuple[str, ...],
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        keys = tuple(keywords)
        self.keyword_updates.append((keys, enabled))
        current = list(self.flags)
        if enabled:
            current.extend(key for key in keys if key not in current)
        else:
            current = [flag for flag in current if flag not in keys]
        self.flags = tuple(current)
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, self.flags)

    def set_flagged(
        self,
        uid: int,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        self.flagged_updates.append(enabled)
        current = [flag for flag in self.flags if flag != "\\Flagged"]
        if enabled:
            current.append("\\Flagged")
        self.flags = tuple(current)
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, self.flags)


class AiWorkflowApplicationTest(unittest.TestCase):
    def test_nothing_to_do_adds_bulk_unstars_and_inactivates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            database.synchronize(
                [
                    EmailMessage(
                        "<none@example>",
                        "sender@example.com",
                        "me@example.com",
                        "FYI",
                        None,
                        "共有のみです。",
                        mailbox="INBOX",
                        uidvalidity=10,
                        uid=7,
                    )
                ]
            )
            imap = FakeImapClient()
            config = AppConfig(
                ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
                DatabaseConfig(path),
            )
            service = SynchronizationService(
                config,
                database=database,
                imap_client=imap,
                classifier=FakeClassifier(),
            )
            tracked = database.list_tracked_emails(active=True)[0]

            outcome = service._classify_one(tracked)

            self.assertTrue(outcome.classified)
            self.assertEqual(imap.keyword_updates, [(('wib-bulk',), True)])
            self.assertEqual(imap.flagged_updates, [False])
            self.assertNotIn("\\Flagged", imap.flags)
            self.assertIn("wib-bulk", imap.flags)
            self.assertEqual(
                database.list_tracked_emails(active=False)[0].tracking_status,
                TrackingStatus.INACTIVE_UNSTARRED,
            )


if __name__ == "__main__":
    unittest.main()
