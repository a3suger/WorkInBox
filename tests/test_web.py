from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.application import TrackingQueryService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage, TrackingStatus
from workinbox.web import _TEMPLATES, create_app


class WebFoundationTest(unittest.TestCase):
    def _config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig(
                "imap.example",
                993,
                "user",
                "pass",
                "INBOX",
                new_mail_lookback_days=7,
            ),
            DatabaseConfig(path),
        )

    def test_tracking_query_service_separates_active_and_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            config = self._config(path)
            database = EmailDatabase(path)
            database.initialize()
            database.synchronize([
                EmailMessage(
                    "<active@example>", "active@example.com", None, "Active mail",
                    "Sat, 8 Aug 2026 09:00:00 +0000", None,
                    mailbox="INBOX", uidvalidity=10, uid=1,
                ),
                EmailMessage(
                    "<inactive@example>", "inactive@example.com", None, "Inactive mail",
                    "Fri, 7 Aug 2026 09:00:00 +0000", None,
                    mailbox="INBOX", uidvalidity=10, uid=2,
                ),
            ])
            database.update_tracking_status("<inactive@example>", TrackingStatus.INACTIVE_UNSTARRED)

            service = TrackingQueryService(config, database=database)
            active = service.active_emails()
            inactive = service.inactive_emails()
            self.assertEqual([email.message_id for email in active], ["<active@example>"])
            self.assertEqual([email.message_id for email in inactive], ["<inactive@example>"])
            self.assertEqual(active[0].uid, 1)
            self.assertEqual(active[0].uidvalidity, 10)
            self.assertEqual(active[0].mailbox, "INBOX")

    def test_web_app_has_expected_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(self._config(Path(directory) / "workinbox.db"))
            routes = {route.path: set(route.methods or ()) for route in app.routes}

        self.assertIn("GET", routes["/"])
        self.assertIn("GET", routes["/active"])
        self.assertIn("GET", routes["/inactive"])
        self.assertIn("GET", routes["/records"])
        self.assertIn("GET", routes["/pending"])
        self.assertIn("GET", routes["/deadlines"])
        self.assertIn("GET", routes["/schedules"])
        self.assertIn("GET", routes["/api/thunderbird/imap-target"])
        self.assertIn("GET", routes["/deadlines.ics"])
        self.assertIn("POST", routes["/normal-workflow/complete"])
        self.assertIn("POST", routes["/normal-workflow/record"])
        self.assertIn("POST", routes["/deadlines/add"])
        self.assertIn("POST", routes["/deadlines/no-deadline"])
        self.assertIn("POST", routes["/deadlines/{candidate_id}/register"])
        self.assertIn("POST", routes["/deadlines/{candidate_id}/reject"])
        self.assertIn("POST", routes["/deadlines/{candidate_id}/revise"])
        self.assertIn("POST", routes["/schedules/complete"])
        self.assertIn("POST", routes["/pending/resolve"])
        self.assertIn("POST", routes["/sync"])
        self.assertIn("POST", routes["/full-recheck"])
        self.assertIn("POST", routes["/tags/{key}/{operation}"])

    def test_thunderbird_imap_target_excludes_password(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(self._config(Path(directory) / "workinbox.db"))
            route = next(route for route in app.routes if route.path == "/api/thunderbird/imap-target")
            payload = route.endpoint()

        self.assertEqual(payload, {
            "host": "imap.example",
            "port": 993,
            "username": "user",
            "mailbox": "INBOX",
        })
        self.assertNotIn("password", payload)

    def test_templates_are_loadable(self) -> None:
        for name in (
            "base.html", "dashboard.html", "emails.html", "pending.html", "deadlines.html",
            "schedules.html", "records.html",
        ):
            self.assertIsNotNone(_TEMPLATES.get_template(name))

    def test_dashboard_template_contains_required_starting_points(self) -> None:
        source, _, _ = _TEMPLATES.env.loader.get_source(_TEMPLATES.env, "dashboard.html")
        self.assertIn("未着眼・未読", source)
        self.assertIn("未着眼・既読", source)
        self.assertIn("スターなし AND 未読 AND 一括処理なし", source)
        self.assertIn("スターなし AND 既読 AND 一括処理なし", source)
        self.assertNotIn("WIB作業タグなし", source)
        self.assertIn('data-wib-open-work-view="unattended-unread"', source)
        self.assertIn('data-wib-open-work-view="unattended-read"', source)
        self.assertIn('data-wib-open-work-view="answer"', source)
        self.assertIn('data-wib-open-work-view="review"', source)
        self.assertIn('data-wib-open-work-view="watch"', source)
        self.assertIn('href="/deadlines"', source)
        self.assertIn('href="/schedules"', source)
        self.assertIn('href="/pending"', source)
        self.assertIn('href="/records"', source)

    def test_email_template_contains_normal_completion_controls(self) -> None:
        source, _, _ = _TEMPLATES.env.loader.get_source(_TEMPLATES.env, "emails.html")
        self.assertIn("/normal-workflow/complete", source)
        self.assertIn("/normal-workflow/record", source)
        self.assertIn("通常終了", source)
        self.assertIn("Record に保存して終了", source)
        self.assertIn("wib-answer", source)
        self.assertIn("wib-review", source)
        self.assertIn("wib-watch", source)

    def test_deadline_template_offers_explicit_whole_mail_exit(self) -> None:
        source, _, _ = _TEMPLATES.env.loader.get_source(_TEMPLATES.env, "deadlines.html")
        self.assertIn("AI抽出は完了していますが、締切候補は見つかりませんでした", source)
        self.assertIn("/deadlines/no-deadline", source)
        self.assertIn("このメールには締切なしとして終了", source)
        self.assertIn("未確定の候補をすべて登録しない状態", source)

    def test_schedule_template_contains_support_request_bridge(self) -> None:
        source, _, _ = _TEMPLATES.env.loader.get_source(_TEMPLATES.env, "schedules.html")
        self.assertIn("data-wib-support-request-form", source)
        self.assertNotIn('name="method"', source)
        self.assertNotIn('name="keep_reply_subject"', source)
        self.assertIn('value="schedule_adjustment"', source)
        self.assertIn('value="schedule_entry"', source)
        self.assertIn('<select name="to" required', source)
        self.assertIn("{{ supporter.label }}", source)
        self.assertIn('name="cc" value="{{ self_cc }}"', source)
        self.assertIn("別スレッドの新規メール", source)
        self.assertIn("X-WorkInBox-Origin-Message-ID", source)
        self.assertIn("schedule_support.supporters", source)
        self.assertIn("対応待ち", source)


if __name__ == "__main__":
    unittest.main()
