from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from typing import TextIO


_LOGGER = logging.getLogger(__name__)


class SyncProcessManager:
    """Run WorkInBox synchronization outside the web-server process."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self._lock = Lock()
        self._process: subprocess.Popen[str] | None = None
        self._started_at: datetime | None = None

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

    @property
    def started_at(self) -> datetime | None:
        with self._lock:
            if not self._is_running_unlocked():
                return None
            return self._started_at

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

            _LOGGER.info("Starting synchronization process: %s", " ".join(command))
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._started_at = datetime.now().astimezone()
            _LOGGER.info("Synchronization process started: pid=%d", self._process.pid)

            if self._process.stdout is not None:
                Thread(
                    target=self._forward_output,
                    args=(self._process.pid, self._process.stdout),
                    daemon=True,
                    name=f"workinbox-sync-log-{self._process.pid}",
                ).start()
            return True

    def _is_running_unlocked(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    @staticmethod
    def _forward_output(pid: int, stream: TextIO) -> None:
        try:
            for line in stream:
                text = line.rstrip("\r\n")
                if text:
                    _LOGGER.info("sync[%d] %s", pid, text)
        finally:
            stream.close()
            _LOGGER.info("Synchronization process output closed: pid=%d", pid)
