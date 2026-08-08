from __future__ import annotations

import argparse
import imaplib
import sys
from pathlib import Path

from .config import load_config
from .imap_client import ImapClient


def inspect_flags(config_path: str | Path, uid: int) -> int:
    config = load_config(config_path)
    snapshot = ImapClient(config.imap).inspect_flags(uid)

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
        description="Read IMAP FLAGS for one message without modifying the mailbox"
    )
    parser.add_argument("--config", default="config.yaml", help="YAML configuration path")
    parser.add_argument("--uid", type=int, required=True, help="IMAP UID to inspect")
    args = parser.parse_args()

    if args.uid < 1:
        parser.error("--uid must be at least 1")

    try:
        return inspect_flags(args.config, args.uid)
    except (OSError, ValueError, RuntimeError, imaplib.IMAP4.error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(cli())
