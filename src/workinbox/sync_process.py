from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from threading import Lock


class SyncProcessManager:
    """Run WorkInBox synchronization outside the web-server process."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self._lock = Lock()
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running_unlocked()

    @property
    def pid(self) -> int | None:
        with self._lock:
            if not self._is_running_unlocked() or self._process is None:
                return None
            return self._process.pid

    def start(self, *, full_recheck: bool = False) -> bool:
        with self._lock:
            if self._is_running_unlocked():
                return False

            command = [
                sys.executable,
                "-m",
                "workinbox.main",
                "--config",
                str(self.config_path),
            ]
            if full_recheck:
                command.append("--full-recheck")

            logging.info("Starting synchronization process: %s", " ".join(command))
            self._process = subprocess.Popen(command)
            logging.info("Synchronization process started: pid=%d", self._process.pid)
            return True

    def _is_running_unlocked(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None
