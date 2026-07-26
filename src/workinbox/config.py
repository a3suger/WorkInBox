from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    path: Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    imap: ImapConfig
    database: DatabaseConfig


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as stream:
        raw: dict[str, Any] = yaml.safe_load(stream) or {}

    try:
        imap_raw = raw["imap"]
        database_raw = raw["database"]
        imap = ImapConfig(
            host=str(imap_raw["host"]),
            port=int(imap_raw.get("port", 993)),
            username=str(imap_raw["username"]),
            password=str(imap_raw["password"]),
            mailbox=str(imap_raw.get("mailbox", "INBOX")),
        )
        database_path = Path(str(database_raw["path"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid configuration: {exc}") from exc

    if not database_path.is_absolute():
        database_path = config_path.parent / database_path
    return AppConfig(imap=imap, database=DatabaseConfig(database_path))
