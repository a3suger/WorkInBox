from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.config import load_config


class ConfigTest(unittest.TestCase):
    def test_loads_new_mail_lookback_days_and_ai_defaults(self) -> None:
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
            self.assertEqual(config.imap.timeout_seconds, 30.0)
            self.assertEqual(config.ai.url, "http://127.0.0.1:11434")
            self.assertEqual(config.ai.model, "qwen2.5:7b")
            self.assertEqual(config.ai.body_max_chars, 4000)
            self.assertEqual(config.ai.timeout_seconds, 120.0)
            self.assertEqual(config.ai.keep_alive, "30m")
            self.assertEqual(config.ai.max_workers, 1)
            self.assertIsNone(config.identity)
            self.assertIsNone(config.ai.identity)
            self.assertEqual(config.schedule_support.supporters, ())

    def test_loads_identity_and_normalizes_all_addresses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                """imap:
  host: imap.example
  username: user
  password: pass
  new_mail_lookback_days: 7
identity:
  mailbox_address: Main@Example.COM
  self_addresses:
    - main@example.com
    - Alias@Example.com
    - external@example.net
  name: Example User
database:
  path: workinbox.db
""",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertIsNotNone(config.identity)
            assert config.identity is not None
            self.assertEqual(config.identity.name, "Example User")
            self.assertEqual(
                config.identity.all_addresses,
                ("main@example.com", "alias@example.com", "external@example.net"),
            )
            self.assertIs(config.ai.identity, config.identity)

    def test_loads_schedule_supporters_from_from_style_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                """imap:
  host: imap.example
  username: user
  password: pass
  new_mail_lookback_days: 7
schedule_support:
  supporters:
    - "山田 太郎 <yamada@example.com>"
    - "sato@example.com"
database:
  path: workinbox.db
""",
                encoding="utf-8",
            )
            config = load_config(path)
            supporters = config.schedule_support.supporters
            self.assertEqual(len(supporters), 2)
            self.assertEqual(supporters[0].label, "山田 太郎 <yamada@example.com>")
            self.assertEqual(supporters[0].name, "山田 太郎")
            self.assertEqual(supporters[0].address, "yamada@example.com")
            self.assertEqual(supporters[1].label, "sato@example.com")
            self.assertIsNone(supporters[1].name)
            self.assertEqual(supporters[1].address, "sato@example.com")

    def test_schedule_supporter_requires_email_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                """imap:
  host: imap.example
  username: user
  password: pass
  new_mail_lookback_days: 7
schedule_support:
  supporters:
    - "山田 太郎"
database:
  path: workinbox.db
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "schedule_support.supporters"):
                load_config(path)

    def test_loads_ai_overrides(self) -> None:
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
ai:
  url: http://localhost:11434
  model: qwen2.5:7b
  body_max_chars: 2500
  timeout_seconds: 45
  keep_alive: 10m
  max_workers: 3
""",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.ai.body_max_chars, 2500)
            self.assertEqual(config.ai.timeout_seconds, 45.0)
            self.assertEqual(config.ai.keep_alive, "10m")
            self.assertEqual(config.ai.max_workers, 3)

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

    def test_imap_timeout_must_be_positive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                """imap:
  host: imap.example
  username: user
  password: pass
  new_mail_lookback_days: 7
  timeout_seconds: 0
database:
  path: workinbox.db
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "imap.timeout_seconds"):
                load_config(path)

    def test_ai_body_max_chars_must_be_positive(self) -> None:
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
ai:
  body_max_chars: 0
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "ai.body_max_chars"):
                load_config(path)

    def test_ai_max_workers_is_limited(self) -> None:
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
ai:
  max_workers: 5
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "ai.max_workers"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
