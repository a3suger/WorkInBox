from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AdvertisingSender:
    address: str
    display_name: str | None
    created_at: str
    last_matched_at: str | None
    match_count: int


def normalize_sender(value: str) -> tuple[str | None, str]:
    name, address = parseaddr(value or "")
    normalized = address.strip().lower()
    if not normalized or "@" not in normalized or any(char.isspace() for char in normalized):
        raise ValueError("有効な送信者メールアドレスを入力してください")
    return (name.strip() or None), normalized


class AdvertisingSenderStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS advertising_senders (
                    address TEXT PRIMARY KEY,
                    display_name TEXT,
                    created_at TEXT NOT NULL,
                    last_matched_at TEXT,
                    match_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def add(self, value: str, *, display_name: str | None = None) -> AdvertisingSender:
        parsed_name, address = normalize_sender(value)
        name = (display_name or parsed_name or "").strip() or None
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO advertising_senders (address, display_name, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    display_name = COALESCE(excluded.display_name, advertising_senders.display_name)
                """,
                (address, name, now),
            )
        result = self.get(address)
        if result is None:
            raise RuntimeError("広告送信者を保存できませんでした")
        return result

    def get(self, value: str) -> AdvertisingSender | None:
        _, address = normalize_sender(value)
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT address, display_name, created_at, last_matched_at, match_count
                FROM advertising_senders WHERE address = ?
                """,
                (address,),
            ).fetchone()
        return self._from_row(row)

    def contains(self, value: str) -> bool:
        return self.get(value) is not None

    def list(self) -> list[AdvertisingSender]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                """
                SELECT address, display_name, created_at, last_matched_at, match_count
                FROM advertising_senders ORDER BY address
                """
            ).fetchall()
        return [item for row in rows if (item := self._from_row(row)) is not None]

    def delete(self, value: str) -> bool:
        _, address = normalize_sender(value)
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                "DELETE FROM advertising_senders WHERE address = ?", (address,)
            )
            return cursor.rowcount == 1

    def record_match(self, value: str) -> None:
        _, address = normalize_sender(value)
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                UPDATE advertising_senders
                SET last_matched_at = ?, match_count = match_count + 1
                WHERE address = ?
                """,
                (now, address),
            )

    @staticmethod
    def _from_row(row) -> AdvertisingSender | None:
        if row is None:
            return None
        return AdvertisingSender(
            address=str(row[0]),
            display_name=str(row[1]) if row[1] is not None else None,
            created_at=str(row[2]),
            last_matched_at=str(row[3]) if row[3] is not None else None,
            match_count=int(row[4]),
        )
