from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.config import load_config


class ConfigTest(unittest.TestCase):
    def test_loads_new_mail_lookback_days(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                """imap:
  host: imap.example
  username: user
  password: pass
  new_mail_lookback_days: 7
database:
  path: workinbox.db
""",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.imap.new_mail_lookback_days, 7)

    def test_lookback_days_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                """imap:
  host: imap.example
  username: user
  password: pass
database:
  path: workinbox.db
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "new_mail_lookback_days"):
                load_config(path)

    def test_lookback_days_must_be_positive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                """imap:
  host: imap.example
  username: user
  password: pass
  new_mail_lookback_days: 0
database:
  path: workinbox.db
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "at least 1"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
