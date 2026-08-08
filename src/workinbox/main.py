from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

from .config import load_config
from .database import EmailDatabase
from .imap_client import ImapClient
from .models import ImapCheckState, TrackingStatus


def synchronize(config_path: str | Path) -> tuple[int, int, int]:
    config = load_config(config_path)
    database = EmailDatabase(config.database.path)
    database.initialize()
    existing = database.active_imap_references(config.imap.mailbox)

    logging.info("Connecting IMAP server")
    checks, messages = ImapClient(config.imap).synchronize(existing)

    inactivated = 0
    for check in checks:
        if check.state == ImapCheckState.ERROR:
            logging.warning(
                "Unable to check %s: %s",
                check.message_id,
                check.error or "unknown IMAP error",
            )
            continue
        target = {
            ImapCheckState.FLAGGED: TrackingStatus.ACTIVE,
            ImapCheckState.UNSTARRED: TrackingStatus.INACTIVE_UNSTARRED,
            ImapCheckState.MISSING: TrackingStatus.INACTIVE_MOVED,
        }[check.state]
        if database.update_tracking_status(check.message_id, target):
            if target != TrackingStatus.ACTIVE:
                inactivated += 1

    logging.info("Found %d flagged messages", len(messages))
    added, reactivated = database.synchronize(messages)
    logging.info("Added %d messages", added)
    logging.info("Reactivated %d messages", reactivated)
    logging.info("Inactivated %d messages", inactivated)
    logging.info("Synchronization completed")
    return len(messages), added, inactivated


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
