from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.config import AppConfig, DatabaseConfig, IdentityConfig, ImapConfig
from workinbox.models import EmailMessage, ImapFlagsSnapshot
from workinbox.triage_store import TriageRelationStore
from workinbox.triagebox import TriageFetchResult, TriageHeaders, TriageMessage, TriageService


class FakeFocusImapClient:
    def __init__(self, messages: list[TriageMessage]) -> None:
        self.messages = {item.email.message_id: item for item in messages}
        self.unread_ids = [item.email.message_id for item in messages]
        self.find_calls: list[str] = []

    def add(self, item: TriageMessage) -> None:
        self.messages[item.email.message_id] = item
        self.unread_ids.append(item.email.message_id)

    def fetch_unread(self, checkpoint=None) -> TriageFetchResult:
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
        self.find_calls.append(message_id)
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
        return ImapFlagsSnapshot("INBOX", expected_uidvalidity or 10, uid, tuple(flags))

    def _by_uid(self, uid: int) -> TriageMessage:
        return next(item for item in self.messages.values() if item.email.uid == uid)


def message(
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
        email,
        TriageHeaders(
            from_address=sender,
            message_id=message_id,
            in_reply_to=in_reply_to,
            references=references,
            origin_message_id=origin,
        ),
        flags,
    )


class DedicatedWorkflowFocusTest(unittest.TestCase):
    def config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
            identity=IdentityConfig(
                mailbox_address="me@example.com",
                self_addresses=(),
            ),
        )

    def test_focus_table_migrates_and_updates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TriageRelationStore(Path(directory) / "workinbox.db")
            store.initialize()

            self.assertIsNone(store.current_focus_for("<m1@example>"))
            store.ensure_workflow_focus("<m1@example>")
            self.assertEqual(store.current_focus_for("<m1@example>"), "<m1@example>")

            store.set_current_focus("<m1@example>", "<m4@example>")
            self.assertEqual(store.current_focus_for("<m1@example>"), "<m4@example>")
            self.assertEqual(store.workflow_origin_for_focus("<m4@example>"), "<m1@example>")

    def test_support_reply_does_not_move_focus_but_standard_reply_does(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            origin = message(
                "<m1@example>",
                "sender@example.com",
                1,
                flags=("\\Flagged", "wib-schedule", "wib-requested"),
            )
            request = message(
                "<m2@example>",
                "me@example.com",
                2,
                origin="<m1@example>",
            )
            support_reply = message(
                "<m3@example>",
                "supporter@example.com",
                3,
                in_reply_to=("<m2@example>",),
                references=("<m2@example>",),
            )
            imap = FakeFocusImapClient([origin, request, support_reply])
            service = TriageService(self.config(path), imap)

            first = service.run()
            store = TriageRelationStore(path)

            self.assertEqual(first.waiting_action_replies, 1)
            self.assertEqual(store.current_focus_for("<m1@example>"), "<m1@example>")
            self.assertNotEqual(store.current_focus_for("<m1@example>"), "<m3@example>")

            standard_reply = message(
                "<m4@example>",
                "sender@example.com",
                4,
                in_reply_to=("<m1@example>",),
                references=("<m1@example>",),
            )
            imap.add(standard_reply)

            second = service.run()

            self.assertEqual(second.scanned, 1)
            self.assertEqual(store.current_focus_for("<m1@example>"), "<m4@example>")
            self.assertIn("\\Flagged", imap.messages["<m4@example>"].flags)
            self.assertIn("\\Flagged", imap.messages["<m1@example>"].flags)

    def test_unknown_long_thread_searches_only_nearest_reply_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            reply = message(
                "<reply@example>",
                "sender@example.com",
                10,
                in_reply_to=("<nearest@example>",),
                references=(
                    "<oldest@example>",
                    "<older@example>",
                    "<nearest@example>",
                ),
            )
            imap = FakeFocusImapClient([reply])

            result = TriageService(self.config(path), imap).run()

            self.assertEqual(result.errors, ())
            self.assertEqual(imap.find_calls, ["<nearest@example>"])

    def test_progress_reports_relation_check_before_message_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            reply = message(
                "<reply@example>",
                "sender@example.com",
                10,
                in_reply_to=("<nearest@example>",),
            )
            imap = FakeFocusImapClient([reply])
            events: list[dict[str, object]] = []

            TriageService(
                self.config(path), imap, progress_callback=events.append
            ).run()

            self.assertTrue(
                any(
                    event.get("phase") == "triage-relations"
                    and event.get("current") == 1
                    and event.get("total") == 1
                    for event in events
                )
            )


if __name__ == "__main__":
    unittest.main()
