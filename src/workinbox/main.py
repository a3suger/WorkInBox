from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

from .application import SyncMode, SyncResult, SynchronizationService
from .config import load_config


def synchronize(
    config_path: str | Path,
    *,
    full_recheck: bool = False,
) -> tuple[int, int, int]:
    config = load_config(config_path)
    service = SynchronizationService(config)
    mode = SyncMode.FULL_RECHECK if full_recheck else SyncMode.NORMAL

    logging.info("Connecting IMAP server")
    result = service.synchronize(mode)
    _log_result(result)
    return result.flagged, result.added, result.inactivated


def _log_result(result: SyncResult) -> None:
    if result.mode == SyncMode.NORMAL:
        logging.info("TriageBox scanned %d unread messages", result.triage_scanned)
        logging.info(
            "TriageBox marked %d support requests waiting for action",
            result.triage_support_requests,
        )
        logging.info(
            "TriageBox resolved %d waiting-action replies",
            result.triage_waiting_action_replies,
        )
    logging.info("Checked %d existing messages", result.checked)
    logging.info("Found %d flagged messages", result.flagged)
    logging.info("Added %d messages", result.added)
    logging.info("Reactivated %d messages", result.reactivated)
    logging.info("Inactivated %d messages", result.inactivated)
    if result.mode == SyncMode.NORMAL:
        logging.info("AI-classified %d messages", result.ai_classified)
    for error in result.triage_errors:
        logging.warning("Unable to triage %s: %s", error.message_id, error.message)
    for error in result.errors:
        logging.warning("Unable to check %s: %s", error.message_id, error.message)
    for error in result.ai_errors:
        logging.warning("Unable to AI-classify %s: %s", error.message_id, error.message)
    logging.info("Synchronization completed")


def cli() -> int:
    parser = argparse.ArgumentParser(description="Synchronize flagged IMAP mail")
    parser.add_argument("--config", default="config.yaml", help="YAML configuration path")
    parser.add_argument(
        "--full-recheck",
        action="store_true",
        help="Recheck inactive messages as well as active messages",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        synchronize(args.config, full_recheck=args.full_recheck)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        logging.error("Synchronization failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(cli())
