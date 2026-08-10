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
class IdentityConfig:
    mailbox_address: str
    self_addresses: tuple[str, ...