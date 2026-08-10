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
            database.synchronize(
                [
                    EmailMessage(
                        "<active@example>",
                        "active@example.com",
                        None,
                        "Active mail",
                        "Sat, 8 Aug 2026 09:00:00 +0000",
                        None,
                        mailbox="INBOX",
                        uidvalidity=10,
                        uid=1,
                    ),
                    EmailMessage(
                        "<inactive@example>",
                        "inactive@example.com",
                        None,
                        "Inactive mail",
                        "Fri, 7 Aug 2026 09:00:00 +0000",
                        None,
                        mailbox="INBOX",
                        uidvalidity=10,
                        uid=2,
                    ),
                ]
            )
            database.update_tracking_status(
                "<inactive@example>",
                TrackingStatus.INACTIVE_UNSTARRED,
            )

            service = TrackingQueryService(config, database=database)
            active = service.active_emails()
            inactive = service.inactive_emails()
            self.assertEqual(
                [email.message_id for email in active],
                ["<active@example>"],
            )
            self.assertEqual(
                [email.message_id for email in inactive],
                ["<inactive@example>"],
            )
            self.assertEqual(active[0].uid, 1)
            self.assertEqual(active[0].uidvalidity, 10)
            self.assertEqual(active[0].mailbox, "INBOX")

    def test_web_app_has_expected_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(self._config(Path(directory) / "workinbox.db"))
            routes = {
                route.path: set(route.methods or ())
                for route in app.routes
            }

        self.assertIn("GET", routes["/"])
        self.assertIn("GET", routes["/active"])
        self.assertIn("GET", routes["/inactive"])
        self.assertIn("GET", routes["/pending"])
        self.assertIn("GET", routes["/deadlines"])
        self.assertIn("POST", routes["/pending/resolve"])
        self.assertIn("POST", routes["/sync"])
        self.assertIn("POST", routes["/full-recheck"])
        self.assertIn("POST", routes["/tags/{key}/{operation}"])

    def test_templates_are_loadable(self) -> None:
        self.assertIsNotNone(_TEMPLATES.get_template("base.html"))
        self.assertIsNotNone(_TEMPLATES.get_template("emails.html"))
        self.assertIsNotNone(_TEMPLATES.get_template("pending.html"))
        self.assertIsNotNone(_TEMPLATES.get_template("deadlines.html"))


if __name__ == "__main__":
    unittest.main()
