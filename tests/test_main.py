from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from workinbox.application import SyncMode, SyncResult
from workinbox.config import AppConfig, DatabaseConfig, ImapConfig
from workinbox.main import synchronize


class FakeSynchronizationService:
    modes: list[SyncMode] = []

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def synchronize(self, mode: SyncMode) -> SyncResult:
        self.modes.append(mode)
        return SyncResult(
            mode=mode,
            checked=4,
            flagged=3,
            added=1,
            reactivated=1,
            inactivated=2,
            errors=(),
        )


class MainSynchronizeTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeSynchronizationService.modes = []
        self.config = AppConfig(
            ImapConfig("imap.example", 993, "user", "pass", "INBOX", 7),
            DatabaseConfig(Path("workinbox.db")),
        )

    def test_normal_sync_uses_normal_mode(self) -> None:
        with (
            patch("workinbox.main.load_config", return_value=self.config),
            patch(
                "workinbox.main.SynchronizationService",
                FakeSynchronizationService,
            ),
        ):
            self.assertEqual(synchronize("ignored.yaml"), (3, 1, 2))
        self.assertEqual(FakeSynchronizationService.modes, [SyncMode.NORMAL])

    def test_full_recheck_uses_full_recheck_mode(self) -> None:
        with (
            patch("workinbox.main.load_config", return_value=self.config),
            patch(
                "workinbox.main.SynchronizationService",
                FakeSynchronizationService,
            ),
        ):
            self.assertEqual(
                synchronize("ignored.yaml", full_recheck=True),
                (3, 1, 2),
            )
        self.assertEqual(
            FakeSynchronizationService.modes,
            [SyncMode.FULL_RECHECK],
        )


if __name__ == "__main__":
    unittest.main()
