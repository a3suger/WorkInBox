from __future__ import annotations

import logging
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from typing import TextIO

from .sync_progress import PROGRESS_MARKER


_LOGGER = logging.getLogger(__name__)


class SyncProcessManager:
    """Run WorkInBox synchronization outside the web-server process."""

    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self._lock = Lock()
        self._process: subprocess.Popen[str] | None = None
        self._started_at: datetime | None = None
        self._progress: dict[str, object] | None = None

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

    @property
    def progress(self) -> dict[str, object] | None:
        with self._lock:
            return dict(self._progress) if self._progress is not None else None

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
                "--emit-progress",
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
            self._progress = {
                "phase": "starting",
                "label": "同期プロセスを開始しています",
                "current": 0,
                "total": None,
                "errors": 0,
            }
            _LOGGER.info("Synchronization process started: pid=%d", self._process.pid)

            if self._process.stdout is not None:
                Thread(
                    target=self._forward_output,
                    args=(self._process.pid, self._process.stdout),
                    daemon=True,
                    name=f"workinbox-sync-log-{self._process.pid}",
                ).start()
            return True

    def stop(self, *, timeout_seconds: float = 5.0) -> None:
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None:
                return
            pid = process.pid
            _LOGGER.info("Stopping synchronization process: pid=%d", pid)
            process.terminate()

        try:
            process.wait(timeout=timeout_seconds)
            _LOGGER.info("Synchronization process stopped: pid=%d", pid)
        except subprocess.TimeoutExpired:
            _LOGGER.warning(
                "Synchronization process did not stop after %.1fs; killing pid=%d",
                timeout_seconds,
                pid,
            )
            process.kill()
            process.wait()
            _LOGGER.info("Synchronization process killed: pid=%d", pid)

    def _is_running_unlocked(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    def _forward_output(self, pid: int, stream: TextIO) -> None:
        try:
            for line in stream:
                text = line.rstrip("\r\n")
                if text.startswith(PROGRESS_MARKER):
                    try:
                        event = json.loads(text[len(PROGRESS_MARKER):])
                    except (json.JSONDecodeError, TypeError):
                        _LOGGER.warning("Invalid synchronization progress: %s", text)
                    else:
                        if isinstance(event, dict):
                            with self._lock:
                                self._progress = event
                        continue
                if text:
                    _LOGGER.info("sync[%d] %s", pid, text)
        finally:
            stream.close()
            _LOGGER.info("Synchronization process output closed: pid=%d", pid)
