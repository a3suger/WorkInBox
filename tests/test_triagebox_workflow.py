from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.ai_classifier import AiClassification
from workinbox.application import SynchronizationService, WorkTagService
from workinbox.config import AppConfig, DatabaseConfig, IdentityConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage, ImapFlagsSnapshot
from workinbox.triage_store import TriageRelationStore
from workinbox.triagebox import TriageFetchResult, TriageHeaders, TriageMessage, TriageService


class FakeClassifier:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def classify(self, message: EmailMessage) -> AiClassification:
        self.messages.append(message)
        return AiClassification(False, False, False, True, False, "review")


class FakeTriageImapClient:
    def __init__(self, messages: list[TriageMessage]) -> None:
        self.messages = {item.email.message_id: item for item in messages}
        self.unread_ids = [item.email.message_id for item in messages]
        self.keyword_updates: list[tuple[int, str, bool]] = []
        self.flagged_updates: list[tuple[int, bool]] = []
        self.received_references = []
        self.fetch_checkpoints: list[tuple[int, int] | None] = []

    def fetch_unread(self, checkpoint: tuple[int, int] | None = None) -> TriageFetchResult:
        self.fetch_checkpoints.append(checkpoint)
        last_uid = checkpoint[1] if checkpoint and checkpoint[0] == 10 else 0
        selected = [
            self.messages[message_id]
            for message_id in self.unread_ids
            if (self.messages[message_id].email.uid or 0) > last_uid
        ]
        highest = max(
            ((item.email.uid or 0) for item in self.messages.values()),
            default=0,
        )
        return TriageFetchResult(tuple(selected), 10, highest)

    def find_message_by_message_id(self, message_id: str) -> TriageMessage | None:
        return self.messages.get(message_id)

    def set_keyword(
        self,
        uid: int,
        keyword: str,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        item = self._by_uid(uid)
        flags = list(item.flags)
        if enabled and keyword not in flags:
            flags.append(keyword)
        if not enabled:
            flags = [value for value in flags if value != keyword]
        self.messages[item.email.message_id] = TriageMessage(
            item.email, item.headers, tuple(flags)
        )
        self.keyword_updates.append((uid, keyword, enabled))
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, tuple(flags))

    def set_flagged(
        self,
        uid: int,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        item = self._by_uid(uid)
        flags = [value for value in item.flags if value != "\\Flagged"]
        if enabled:
            flags.append("\\Flagged")
        self.messages[item.email.message_id] = TriageMessage(
            item.email, item.headers, tuple(flags)
        )
        self.flagged_updates.append((uid, enabled))
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, tuple(flags))

    def synchronize(self, existing):
        self.received_references = list(existing)
        flagged = [
            item.email
            for item in self.messages.values()
            if "\\Flagged" in item.flags
        ]
        return [], flagged

    def inspect_flags(
        self,
        uid: int,
        *,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        item = self._by_uid(uid)
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, item.flags)

    def set_keywords(
        self,
        uid: int,
        keywords,
        *,
        enabled: bool,
        expected_uidvalidity: int | None = None,
    ) -> ImapFlagsSnapshot:
        snapshot = None
        for keyword in tuple(keywords):
            snapshot = self.set_keyword(
                uid,
                keyword,
                enabled=enabled,
                expected_uidvalidity=expected_uidvalidity,
            )
        assert snapshot is not None
        return snapshot

    def _by_uid(self, uid: int) -> TriageMessage:
        for item in self.messages.values():
            if item.email.uid == uid:
                return item
        raise AssertionError(f"unknown UID {uid}")


def triage_message(
    message_id: str,
    sender: str,
    uid: int,
    *,
    flags: tuple[str, ...] = (),
    origin: str | None = None,
    in_reply_to: tuple[str, ...] = (),
    references: tuple[str, ...] = (),
) -> TriageMessage:
    email = EmailMessage(
        message_id,
        sender,
        "me@example.com",
        None,
        None,
        None,
        mailbox="INBOX",
        uidvalidity=10,
        uid=uid,
    )
    return TriageMessage(
        email=email,
        headers=TriageHeaders(
            from_address=sender,
            message_id=message_id,
            in_reply_to=in_reply_to,
            references=references,
            origin_message_id=origin,
        ),
        flags=flags,
    )


class TriageBoxWorkflowTest(unittest.TestCase):
    def make_config(self, path: Path) -> AppConfig:
        identity = IdentityConfig(
            mailbox_address="me@example.com",
            self_addresses=("alias@example.com",),
        )
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
            identity=identity,
        )

    def test_support_request_copy_marks_origin_requested_and_becomes_waiting_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            config = self.make_config(path)
            origin = triage_message(
                "<origin@example>",
                "sender@example.com",
                1,
                flags=("\\Flagged", "wib-schedule"),
            )
            request = triage_message(
                "<request@example>",
                "me@example.com",
                2,
                origin="<origin@example>",
            )
            imap = FakeTriageImapClient([origin, request])

            result = TriageService(config, imap).run()

            self.assertEqual(result.support_requests, 1)
            self.assertIn("wib-requested", imap.messages["<origin@example>"].flags)
            self.assertIn("wib-waiting-action", imap.messages["<request@example>"].flags)
            self.assertIn("\\Flagged", imap.messages["<request@example>"].flags)
            self.assertEqual(
                TriageRelationStore(path).origin_for("<request@example>"),
                "<origin@example>",
            )
            self.assertEqual(TriageRelationStore(path).checkpoint("INBOX"), (10, 2))

    def test_second_run_only_fetches_after_saved_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            config = self.make_config(path)
            old_message = triage_message("<old@example>", "other@example.com", 5)
            imap = FakeTriageImapClient([old_message])
            service = TriageService(config, imap)

            first = service.run()
            second = service.run()

            self.assertEqual(first.scanned, 1)
            self.assertEqual(second.scanned, 0)
            self.assertEqual(imap.fetch_checkpoints, [None, (10, 5)])

    def test_supporter_reply_moves_focus_from_request_to_reply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            config = self.make_config(path)
            origin = triage_message(
                "<origin@example>",
                "sender@example.com",
                1,
                flags=("\\Flagged", "wib-schedule"),
            )
            request = triage_message(
                "<request@example>",
                "me@example.com",
                2,
                origin="<origin@example>",
            )
            reply = triage_message(
                "<reply@example>",
                "supporter@example.com",
                3,
                in_reply_to=("<request@example>",),
                references=("<origin@example>", "<request@example>"),
            )
            imap = FakeTriageImapClient([origin, request, reply])
            service = TriageService(config, imap)

            result = service.run()

            self.assertEqual(result.support_requests, 1)
            self.assertEqual(result.waiting_action_replies, 1)
            self.assertNotIn("wib-waiting-action", imap.messages["<request@example>"].flags)
            self.assertNotIn("\\Flagged", imap.messages["<request@example>"].flags)
            self.assertIn("wib-schedule", imap.messages["<reply@example>"].flags)
            self.assertIn("\\Flagged", imap.messages["<reply@example>"].flags)
            relations = TriageRelationStore(path)
            self.assertEqual(relations.origin_for("<request@example>"), "<origin@example>")
            self.assertEqual(relations.origin_for("<reply@example>"), "<origin@example>")
            self.assertEqual(
                relations.relation_kind_for("<request@example>"),
                "schedule_support_request_replied",
            )

            repeated = service.run()

            self.assertEqual(repeated.support_requests, 0)
            self.assertEqual(repeated.waiting_action_replies, 0)

    def test_schedule_reply_completion_marks_origin_done_and_unstars_reply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            config = self.make_config(path)
            database = EmailDatabase(path)
            database.initialize()
            origin = triage_message(
                "<origin@example>",
                "sender@example.com",
                1,
                flags=("\\Flagged", "wib-schedule", "wib-requested"),
            )
            reply = triage_message(
                "<reply@example>",
                "supporter@example.com",
                3,
                flags=("\\Flagged", "wib-schedule"),
            )
            database.synchronize([origin.email, reply.email])
            relations = TriageRelationStore(path)
            relations.initialize()
            relations.record(
                "<reply@example>",
                "<origin@example>",
                "schedule_support_reply",
                related_message_id="<request@example>",
            )
            imap = FakeTriageImapClient([origin, reply])
            service = WorkTagService(config, database=database, imap_client=imap)

            service.set_tag("<reply@example>", "wib-schedule-done", enabled=True)

            self.assertIn("wib-schedule-done", imap.messages["<origin@example>"].flags)
            self.assertIn("wib-schedule-done", imap.messages["<reply@example>"].flags)
            self.assertNotIn("\\Flagged", imap.messages["<reply@example>"].flags)

    def test_normal_sync_runs_triage_before_flagged_discovery_and_ai(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            config = self.make_config(path)
            database = EmailDatabase(path)
            database.initialize()
            origin = triage_message(
                "<origin@example>",
                "sender@example.com",
                1,
                flags=("\\Flagged", "wib-schedule"),
            )
            request = triage_message(
                "<request@example>",
                "me@example.com",
                2,
                origin="<origin@example>",
            )
            imap = FakeTriageImapClient([origin, request])
            classifier = FakeClassifier()
            service = SynchronizationService(
                config,
                database=database,
                imap_client=imap,
                classifier=classifier,
            )

            result = service.normal_sync()

            self.assertEqual(result.triage_support_requests, 1)
            self.assertEqual(result.added, 2)
            self.assertEqual(classifier.messages, [])
            self.assertIsNotNone(database.email_message("<request@example>"))


if __name__ == "__main__":
    unittest.main()
