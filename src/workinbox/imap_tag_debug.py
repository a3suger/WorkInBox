from __future__ import annotations

import argparse
import imaplib
import sys
from pathlib import Path

from .config import load_config
from .imap_client import ImapClient


TEST_KEYWORD = "wib-deadline"


def set_deadline_tag(config_path: str | Path, uid: int, *, enabled: bool) -> int:
    config = load_config(config_path)
    snapshot = ImapClient(config.imap).set_keyword(uid, TEST_KEYWORD, enabled=enabled)

    action = "added" if enabled else "removed"
    print(f"{TEST_KEYWORD}: {action}")
    print(f"Mailbox: {snapshot.mailbox}")
    print(f"UIDVALIDITY: {snapshot.uidvalidity}")
    print(f"UID: {snapshot.uid}")
    print("FLAGS:")
    if snapshot.flags:
        for flag in snapshot.flags:
            print(f"  {flag}")
    else:
        print("  (none)")
    return 0


def cli() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Add or remove the WorkInBox test keyword wib-deadline for one IMAP UID"
        )
    )
    parser.add_argument("action", choices=("add", "remove"))
    parser.add_argument("--config", default="config.yaml", help="YAML configuration path")
    parser.add_argument("--uid", type=int, required=True, help="IMAP UID to modify")
    args = parser.parse_args()

    if args.uid < 1:
        parser.error("--uid must be at least 1")

    try:
        return set_deadline_tag(args.config, args.uid, enabled=args.action == "add")
    except (OSError, ValueError, RuntimeError, imaplib.IMAP4.error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(cli())
