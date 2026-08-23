from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.application import WorkTagService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage, ImapFlagsSnapshot
from workinbox.triage_store import TriageRelationStore
from workinbox.work_tags import WORK_TAGS, definitions_for_flags, require_work_tag


class FakeTagImapClient:
    def __init__(self) -> None:
        self.flags_by_uid: dict[int, tuple[str, ...]] = {
            1: ("\\Seen", "\\Flagged", "wib-watch", "wib-deadline", "$label1")
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

    def test_canonical_tag_set_matches_current_design(self) -> None:
        self.assertEqual(len(WORK_TAGS), 13)
        keys = {tag.key for tag in WORK_TAGS}
        self.assertIn("wib-watch", keys)
        self.assertIn("wib-action-ready", keys)
        self.assertIn("wib-bulk", keys)
        self.assertNotIn("wib-important", keys)
        self.assertNotIn("wib-batch", keys)

    def test_definitions_for_flags_ignores_non_workinbox_flags(self) -> None:
        tags = definitions_for_flags(
            ("\\Seen", "$label1", "wib-deadline", "wib-answer", "OtherTag")
        )
        self.assertEqual([tag.key for tag in tags], ["wib-deadline", "wib-answer"])

    def test_legacy_batch_flag_is_read_as_bulk_without_rewriting_mail(self) -> None:
        tags = definitions_for_flags(("wib-batch",))
        self.assertEqual([tag.key for tag in tags], ["wib-bulk"])

    def test_legacy_important_is_not_reinterpreted_as_watch(self) -> None:
        tags = definitions_for_flags(("wib-important",))
        self.assertEqual(tags, ())

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
                ["wib-watch", "wib-deadline"],
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

    def test_setting_dedicated_tag_registers_workflow_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            self._seed(database)
            service = WorkTagService(
                self._config(path), database=database, imap_client=FakeTagImapClient()
            )

            service.set_tag("<mail@example>", "wib-schedule", enabled=True)

            store = TriageRelationStore(path)
            self.assertEqual(
                store.current_focus_for("<mail@example>"), "<mail@example>"
            )

    def test_require_work_tag_returns_canonical_definition(self) -> None:
        self.assertEqual(require_work_tag("wib-answer").label, "返信必要")
        self.assertEqual(require_work_tag("wib-review").label, "見る・検討")
        self.assertEqual(require_work_tag("wib-watch").label, "注目")
        self.assertEqual(require_work_tag("wib-action-ready").label, "対応あり")
        self.assertEqual(require_work_tag("wib-bulk").label, "一括処理")


if __name__ == "__main__":
    unittest.main()
