from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.application import WorkTagService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage, ImapFlagsSnapshot
from workinbox.work_tags import WORK_TAGS, definitions_for_flags, require_work_tag


class FakeTagImapClient:
    def __init__(self) -> None:
        self.flags_by_uid: dict[int, tuple[str, ...]] = {
            1: ("\\Seen", "\\Flagged", "wib-important", "wib-deadline", "$label1")
        }
        self.write_calls: list[tuple[int, str, bool, int | None]] = []

    def inspect_flags(
        self,
        uid: int,
        *,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        if expected_uidvalidity != 10:
            raise RuntimeError("unexpected UIDVALIDITY")
        return ImapFlagsSnapshot("INBOX", 10, uid, self.flags_by_uid[uid])

    def set_keyword(
        self,
        uid: int,
        keyword: str,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        self.write_calls.append((uid, keyword, enabled, expected_uidvalidity))
        flags = list(self.flags_by_uid.get(uid, ()))
        if enabled and keyword not in flags:
            flags.append(keyword)
        if not enabled:
            flags = [flag for flag in flags if flag != keyword]
        self.flags_by_uid[uid] = tuple(flags)
        return ImapFlagsSnapshot("INBOX", 10, uid, tuple(flags))


class WorkTagServiceTest(unittest.TestCase):
    def _config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )

    def _seed(self, database: EmailDatabase) -> None:
        database.initialize()
        database.synchronize(
            [
                EmailMessage(
                    "<mail@example>",
                    "sender@example.com",
                    None,
                    "Subject",
                    None,
                    None,
                    mailbox="INBOX",
                    uidvalidity=10,
                    uid=1,
                )
            ]
        )

    def test_canonical_tag_set_contains_twelve_keys(self) -> None:
        self.assertEqual(len(WORK_TAGS), 12)
        self.assertEqual(WORK_TAGS[0].key, "wib-important")
        self.assertEqual(WORK_TAGS[-1].key, "wib-batch")

    def test_definitions_for_flags_ignores_non_workinbox_flags(self) -> None:
        tags = definitions_for_flags(
            ("\\Seen", "$label1", "wib-deadline", "wib-answer", "OtherTag")
        )
        self.assertEqual([tag.key for tag in tags], ["wib-deadline", "wib-answer"])

    def test_read_for_emails_returns_live_imap_tags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            self._seed(database)
            imap = FakeTagImapClient()
            service = WorkTagService(
                self._config(path), database=database, imap_client=imap
            )

            views = service.read_for_emails(database.list_tracked_emails(active=True))

            self.assertEqual(len(views), 1)
            self.assertIsNone(views[0].error)
            self.assertEqual(
                [tag.key for tag in views[0].tags],
                ["wib-important", "wib-deadline"],
            )

    def test_set_tag_writes_only_requested_keyword_with_saved_uidvalidity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            self._seed(database)
            imap = FakeTagImapClient()
            service = WorkTagService(
                self._config(path), database=database, imap_client=imap
            )

            service.set_tag("<mail@example>", "wib-answer", enabled=True)

            self.assertEqual(imap.write_calls, [(1, "wib-answer", True, 10)])

    def test_set_tag_rejects_unknown_workinbox_key_before_imap_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            self._seed(database)
            imap = FakeTagImapClient()
            service = WorkTagService(
                self._config(path), database=database, imap_client=imap
            )

            with self.assertRaisesRegex(ValueError, "Unknown WorkInBox tag"):
                service.set_tag("<mail@example>", "not-a-wib-tag", enabled=True)

            self.assertEqual(imap.write_calls, [])

    def test_require_work_tag_returns_canonical_definition(self) -> None:
        self.assertEqual(require_work_tag("wib-review").label, "読む・検討")


if __name__ == "__main__":
    unittest.main()
