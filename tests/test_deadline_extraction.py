from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.deadline_application import DeadlineExtractionService
from workinbox.deadline_extractor import ExtractedDeadlineCandidate
from workinbox.models import EmailMessage, ImapFlagsSnapshot


class FakeDeadlineExtractor:
    def __init__(
        self,
        results: dict[str, tuple[ExtractedDeadlineCandidate, ...]] | None = None,
        errors: dict[str, Exception] | None = None,
    ) -> None:
        self.results = results or {}
        self.errors = errors or {}
        self.message_ids: list[str] = []

    def extract(self, message: EmailMessage) -> tuple[ExtractedDeadlineCandidate, ...]:
        self.message_ids.append(message.message_id)
        error = self.errors.get(message.message_id)
        if error is not None:
            raise error
        return self.results.get(message.message_id, ())


class FakeImapClient:
    def __init__(self, flags_by_uid: dict[int, tuple[str, ...]]) -> None:
        self.flags_by_uid = flags_by_uid

    def inspect_flags(
        self,
        uid: int,
        *,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        return ImapFlagsSnapshot(
            "INBOX",
            expected_uidvalidity or 10,
            uid,
            self.flags_by_uid.get(uid, ()),
        )


class DeadlineExtractionServiceTest(unittest.TestCase):
    def make_config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )

    def seed(
        self,
        database: EmailDatabase,
        message_id: str,
        uid: int,
        body: str = "締切があります。",
    ) -> None:
        database.synchronize(
            [
                EmailMessage(
                    message_id,
                    "sender@example.com",
                    "me@example.com",
                    "締切のお知らせ",
                    "2026-08-10T10:00:00+09:00",
                    body,
                    mailbox="INBOX",
                    uidvalidity=10,
                    uid=uid,
                )
            ]
        )

    def test_extracts_only_deadline_without_done_tag_and_saves_multiple_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed(database, "<target@example>", 1)
            self.seed(database, "<done@example>", 2)
            self.seed(database, "<review@example>", 3)

            extractor = FakeDeadlineExtractor(
                {
                    "<target@example>": (
                        ExtractedDeadlineCandidate(
                            "エントリー締切",
                            "2026-08-20",
                            "エントリー締切：8月20日",
                            False,
                        ),
                        ExtractedDeadlineCandidate(
                            "論文投稿締切",
                            None,
                            "投稿期限は別紙参照",
                            True,
                        ),
                    )
                }
            )
            imap = FakeImapClient(
                {
                    1: ("\\Flagged", "wib-deadline"),
                    2: ("\\Flagged", "wib-deadline", "wib-deadline-done"),
                    3: ("\\Flagged", "wib-review"),
                }
            )
            service = DeadlineExtractionService(
                self.make_config(path),
                database=database,
                imap_client=imap,
                extractor=extractor,
            )

            result = service.extract_pending()

            self.assertEqual(result.checked, 3)
            self.assertEqual(result.eligible, 1)
            self.assertEqual(result.extracted_messages, 1)
            self.assertEqual(result.candidates_added, 2)
            self.assertEqual(result.errors, ())
            self.assertEqual(extractor.message_ids, ["<target@example>"])
            candidates = database.deadline_candidates("<target@example>")
            self.assertEqual([item.title for item in candidates], ["エントリー締切", "論文投稿締切"])
            self.assertIsNone(candidates[1].due_at)
            self.assertTrue(candidates[1].needs_review)

    def test_zero_candidate_result_is_marked_extracted_and_not_repeated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed(database, "<zero@example>", 1)
            extractor = FakeDeadlineExtractor()
            service = DeadlineExtractionService(
                self.make_config(path),
                database=database,
                imap_client=FakeImapClient({1: ("wib-deadline",)}),
                extractor=extractor,
            )

            first = service.extract_pending()
            second = service.extract_pending()

            self.assertEqual(first.eligible, 1)
            self.assertEqual(first.extracted_messages, 1)
            self.assertEqual(first.candidates_added, 0)
            self.assertEqual(second.eligible, 0)
            self.assertEqual(extractor.message_ids, ["<zero@example>"])
            with sqlite3.connect(path) as connection:
                row = connection.execute(
                    "SELECT candidate_count FROM deadline_extractions WHERE source_message_id = ?",
                    ("<zero@example>",),
                ).fetchone()
            self.assertEqual(row, (0,))

    def test_failed_extraction_is_not_marked_complete_and_can_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            database = EmailDatabase(path)
            database.initialize()
            self.seed(database, "<retry@example>", 1)
            extractor = FakeDeadlineExtractor(
                errors={"<retry@example>": RuntimeError("temporary AI failure")}
            )
            service = DeadlineExtractionService(
                self.make_config(path),
                database=database,
                imap_client=FakeImapClient({1: ("wib-deadline",)}),
                extractor=extractor,
            )

            first = service.extract_pending()
            self.assertEqual(first.eligible, 1)
            self.assertEqual(first.extracted_messages, 0)
            self.assertEqual(len(first.errors), 1)

            extractor.errors.clear()
            extractor.results["<retry@example>"] = (
                ExtractedDeadlineCandidate(
                    "提出締切",
                    "2026-08-20",
                    "8月20日まで",
                    False,
                ),
            )
            second = service.extract_pending()

            self.assertEqual(second.eligible, 1)
            self.assertEqual(second.extracted_messages, 1)
            self.assertEqual(second.candidates_added, 1)
            self.assertEqual(
                extractor.message_ids,
                ["<retry@example>", "<retry@example>"],
            )


if __name__ == "__main__":
    unittest.main()
