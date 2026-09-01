from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from starlette.requests import Request

from workinbox.application import DeadlineService
from workinbox.application import TrackingQueryService
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.database import EmailDatabase
from workinbox.models import EmailMessage, TrackingStatus
from workinbox.web import _TEMPLATES, _mid_value, create_app


class WebFoundationTest(unittest.TestCase):
    def test_mid_value_removes_only_surrounding_angle_brackets(self) -> None:
        self.assertEqual(_mid_value(" <message@example.com> "), "message@example.com")
        self.assertEqual(_mid_value("message@example.com"), "message@example.com")

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
            routes: dict[str, set[str]] = {}
            for route in app.routes:
                routes.setdefault(route.path, set()).update(route.methods or ())

        self.assertIn("GET", routes["/"])
        self.assertIn("GET", routes["/active"])
        self.assertIn("GET", routes["/inactive"])
        self.assertIn("GET", routes["/records"])
        self.assertIn("GET", routes["/pending"])
        self.assertIn("GET", routes["/deadlines"])
        self.assertIn("GET", routes["/schedules"])
        self.assertIn("GET", routes["/api/thunderbird/imap-target"])
        self.assertIn("GET", routes["/api/health"])
        self.assertIn("GET", routes["/api/extension/bootstrap"])
        self.assertIn("GET", routes["/api/deadlines/summary"])
        self.assertIn("GET", routes["/deadlines.ics"])
        self.assertIn("PROPFIND", routes["/caldav/deadlines/"])
        self.assertIn("REPORT", routes["/caldav/deadlines/"])
        self.assertIn("PUT", routes["/caldav/deadlines/{resource_name}"])
        self.assertIn("GET", routes["/deadlines/{deadline_id}/source-message"])
        self.assertIn("GET", routes["/deadlines/{deadline_id}"])
        self.assertIn("POST", routes["/deadlines/{deadline_id}"])
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

    def test_extension_bootstrap_exposes_only_safe_connection_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(self._config(Path(directory) / "workinbox.db"))
            route = next(route for route in app.routes if route.path == "/api/extension/bootstrap")
            payload = route.endpoint()

        self.assertEqual(payload["api_version"], 1)
        self.assertEqual(payload["new_mail_lookback_days"], 7)
        self.assertEqual(payload["imap_target"]["mailbox"], "INBOX")
        self.assertNotIn("password", payload["imap_target"])

    def test_health_reports_database_and_latest_synchronization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            EmailDatabase(path).initialize()
            app = create_app(self._config(path))
            route = next(route for route in app.routes if route.path == "/api/health")
            payload = route.endpoint()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database"], "ok")
        self.assertEqual(payload["api_version"], 1)
        self.assertIsNone(payload["last_sync_at"])

    def test_health_is_degraded_when_database_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(self._config(Path(directory) / "missing.db"))
            route = next(route for route in app.routes if route.path == "/api/health")
            payload = route.endpoint()

        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["database"], "unavailable")

    def test_templates_are_loadable(self) -> None:
        for name in (
            "base.html", "dashboard.html", "emails.html", "pending.html", "deadlines.html",
            "schedules.html", "records.html", "deadline_source_message.html",
            "deadline_detail.html",
        ):
            self.assertIsNotNone(_TEMPLATES.get_template(name))

    def test_dashboard_template_contains_required_starting_points(self) -> None:
        source, _, _ = _TEMPLATES.env.loader.get_source(_TEMPLATES.env, "dashboard.html")
        self.assertIn("<h4>未着眼</h4>", source)
        self.assertIn("うち未読", source)
        self.assertIn("/ 既読", source)
        self.assertIn("スターなし AND 一括処理なし", source)
        self.assertNotIn("WIB作業タグなし", source)
        self.assertIn('data-wib-open-work-view="unattended"', source)
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

    def test_deadline_source_page_contains_mail_fallback_and_auto_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            config = self._config(path)
            database = EmailDatabase(path)
            database.initialize()
            database.synchronize([
                EmailMessage(
                    "<source@example>",
                    "sender@example.com",
                    "me@example.com",
                    "Source subject",
                    "2026-08-25T09:00:00+09:00",
                    "Body",
                )
            ])
            service = DeadlineService(config, database=database)
            candidate = service.add_candidate(
                "<source@example>",
                "回答期限",
                due_at="2026-08-30",
            )
            deadline = service.register_candidate(candidate.id)
            app = create_app(config, deadline_service=service)
            route = next(
                route
                for route in app.routes
                if route.path == "/deadlines/{deadline_id}/source-message"
            )
            request = Request({
                "type": "http",
                "method": "GET",
                "scheme": "http",
                "server": ("localhost", 8000),
                "path": f"/deadlines/{deadline.id}/source-message",
                "root_path": "",
                "query_string": b"",
                "headers": [],
            })

            response = route.endpoint(request, deadline.id)
            body = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("回答期限", body)
        self.assertIn("Source subject", body)
        self.assertIn("sender@example.com", body)
        self.assertIn('data-wib-auto-open-message-id="&lt;source@example&gt;"', body)

    def test_deadline_detail_page_contains_edit_form_and_source_mail_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workinbox.db"
            config = self._config(path)
            database = EmailDatabase(path)
            database.initialize()
            database.synchronize([
                EmailMessage(
                    "<source@example>",
                    "sender@example.com",
                    "me@example.com",
                    "Source subject",
                    "2026-08-25T09:00:00+09:00",
                    "Body",
                )
            ])
            service = DeadlineService(config, database=database)
            candidate = service.add_candidate(
                "<source@example>",
                "回答期限",
                due_at="2026-08-30",
            )
            deadline = service.register_candidate(
                candidate.id,
                description="返信内容を確認",
            )
            app = create_app(config, deadline_service=service)
            route = next(
                route
                for route in app.routes
                if route.path == "/deadlines/{deadline_id}" and "GET" in route.methods
            )
            request = Request({
                "type": "http",
                "method": "GET",
                "scheme": "http",
                "server": ("localhost", 8000),
                "path": f"/deadlines/{deadline.id}",
                "root_path": "",
                "query_string": b"",
                "headers": [],
            })

            response = route.endpoint(request, deadline.id)
            body = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("締切の確認・修正", body)
        self.assertIn(f'action="/deadlines/{deadline.id}"', body)
        self.assertIn('name="title" value="回答期限"', body)
        self.assertIn('name="due_at" value="2026-08-30"', body)
        self.assertIn("返信内容を確認", body)
        self.assertIn('data-wib-open-message-id="&lt;source@example&gt;"', body)

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
        self.assertIn("別スレッドの依頼メール", source)
        self.assertIn("元メールを本文内転送", source)
        self.assertIn("X-WorkInBox-Origin-Message-ID", source)
        self.assertIn("schedule_support.supporters", source)
        self.assertIn("対応待ち", source)

    def test_schedule_list_excludes_requested_messages(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "src" / "workinbox" / "web.py"
        ).read_text(encoding="utf-8")

        self.assertIn('or "wib-requested" in keys', source)


if __name__ == "__main__":
    unittest.main()
