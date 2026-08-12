from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fastapi.responses import RedirectResponse

from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.web_runtime import create_app


class FakeSyncProcessManager:
    def __init__(self) -> None:
        self.running = False
        self.pid_value: int | None = None
        self.started_at_value: datetime | None = None
        self.starts: list[bool] = []

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def pid(self) -> int | None:
        return self.pid_value if self.running else None

    @property
    def started_at(self) -> datetime | None:
        return self.started_at_value if self.running else None

    def start(self, *, full_recheck: bool = False) -> bool:
        if self.running:
            return False
        self.running = True
        self.pid_value = 4321
        self.started_at_value = datetime(2026, 8, 12, 10, 45).astimezone()
        self.starts.append(full_recheck)
        return True


class WebRuntimeTest(unittest.TestCase):
    def make_config(self, path: Path) -> AppConfig:
        return AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(path),
        )

    def test_sync_status_reports_background_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = FakeSyncProcessManager()
            app = create_app(
                self.make_config(Path(directory) / "workinbox.db"),
                sync_process_manager=manager,
            )
            route = next(route for route in app.routes if route.path == "/api/sync-status")

            idle = route.endpoint()
            self.assertFalse(idle["running"])
            self.assertIsNone(idle["pid"])
            self.assertIsNone(idle["started_at"])
            self.assertEqual(idle["poll_interval_ms"], 2000)
            self.assertIsInstance(idle["current_time"], str)

            manager.start()
            running = route.endpoint()
            self.assertTrue(running["running"])
            self.assertEqual(running["pid"], 4321)
            self.assertEqual(
                running["started_at"],
                manager.started_at.isoformat(timespec="seconds"),
            )
            self.assertEqual(running["poll_interval_ms"], 2000)
            self.assertIsInstance(running["current_time"], str)

    def test_normal_sync_route_starts_process_and_marks_redirect_for_reload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = FakeSyncProcessManager()
            app = create_app(
                self.make_config(Path(directory) / "workinbox.db"),
                sync_process_manager=manager,
            )
            route = next(
                route
                for route in app.routes
                if route.path == "/sync" and "POST" in (route.methods or set())
            )

            response = route.endpoint()

            self.assertIsInstance(response, RedirectResponse)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["location"], "/active?sync_started=1")
            self.assertEqual(manager.starts, [False])

    def test_full_recheck_route_starts_full_recheck_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = FakeSyncProcessManager()
            app = create_app(
                self.make_config(Path(directory) / "workinbox.db"),
                sync_process_manager=manager,
            )
            route = next(
                route
                for route in app.routes
                if route.path == "/full-recheck" and "POST" in (route.methods or set())
            )

            response = route.endpoint()

            self.assertIsInstance(response, RedirectResponse)
            self.assertEqual(response.headers["location"], "/active?sync_started=1")
            self.assertEqual(manager.starts, [True])

    def test_second_sync_request_does_not_start_another_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = FakeSyncProcessManager()
            app = create_app(
                self.make_config(Path(directory) / "workinbox.db"),
                sync_process_manager=manager,
            )
            route = next(
                route
                for route in app.routes
                if route.path == "/sync" and "POST" in (route.methods or set())
            )

            route.endpoint()
            response = route.endpoint()

            self.assertIsInstance(response, RedirectResponse)
            self.assertEqual(manager.starts, [False])


if __name__ == "__main__":
    unittest.main()
