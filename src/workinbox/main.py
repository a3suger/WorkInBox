from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

from .config import load_config
from .database import EmailDatabase
from .imap_client import ImapClient


def synchronize(config_path: str | Path) -> tuple[int, int, int]:
    config = load_config(config_path)
    logging.info("Connecting IMAP server")
    messages = ImapClient(config.imap).fetch_flagged()
    logging.info("Found %d flagged messages", len(messages))

    database = EmailDatabase(config.database.path)
    database.initialize()
    added, removed = database.synchronize(messages)
    logging.info("Added %d messages", added)
    logging.info("Removed %d messages", removed)
    logging.info("Synchronization completed")
    return len(messages), added, removed


def cli() -> int:
    parser = argparse.ArgumentParser(description="Synchronize flagged IMAP mail")
    parser.add_argument("--config", default="config.yaml", help="YAML configuration path")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        synchronize(args.config)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        logging.error("Synchronization failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(cli())
