from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class ImapConfig:
    host: str
    port: int
    username: str
    password: str
    mailbox: str = "INBOX"
    new_mail_lookback_days: int = 1


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    path: Path


@dataclass(frozen=True, slots=True)
class AiConfig:
    url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b"
    body_max_chars: int = 4000
    timeout_seconds: float = 120.0
    keep_alive: str = "30m"
    max_workers: int = 1


@dataclass(frozen=True, slots=True)
class AppConfig:
    imap: ImapConfig
    database: DatabaseConfig
    ai: AiConfig = field(default_factory=AiConfig)


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as stream:
        raw: dict[str, Any] = yaml.safe_load(stream) or {}

    try:
        imap_raw = raw["imap"]
        database_raw = raw["database"]
        new_mail_lookback_days = int(imap_raw["new_mail_lookback_days"])
        if new_mail_lookback_days < 1:
            raise ValueError("new_mail_lookback_days must be at least 1")
        imap = ImapConfig(
            host=str(imap_raw["host"]),
            port=int(imap_raw.get("port", 993)),
            username=str(imap_raw["username"]),
            password=str(imap_raw["password"]),
            mailbox=str(imap_raw.get("mailbox", "INBOX")),
            new_mail_lookback_days=new_mail_lookback_days,
        )
        database_path = Path(str(database_raw["path"]))

        ai_raw = raw.get("ai", {}) or {}
        body_max_chars = int(ai_raw.get("body_max_chars", 4000))
        timeout_seconds = float(ai_raw.get("timeout_seconds", 120.0))
        max_workers = int(ai_raw.get("max_workers", 1))
        if body_max_chars < 1:
            raise ValueError("ai.body_max_chars must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("ai.timeout_seconds must be greater than 0")
        if max_workers < 1 or max_workers > 4:
            raise ValueError("ai.max_workers must be between 1 and 4")
        ai = AiConfig(
            url=str(ai_raw.get("url", "http://127.0.0.1:11434")),
            model=str(ai_raw.get("model", "qwen2.5:7b")),
            body_max_chars=body_max_chars,
            timeout_seconds=timeout_seconds,
            keep_alive=str(ai_raw.get("keep_alive", "30m")),
            max_workers=max_workers,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid configuration: {exc}") from exc

    if not database_path.is_absolute():
        database_path = config_path.parent / database_path
    return AppConfig(imap=imap, database=DatabaseConfig(database_path), ai=ai)
