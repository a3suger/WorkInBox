from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workinbox.advertising_senders import AdvertisingSenderStore, normalize_sender


class AdvertisingSenderTest(unittest.TestCase):
    def test_store_normalizes_deduplicates_tracks_and_deletes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = AdvertisingSenderStore(Path(directory) / "workinbox.db")
            store.initialize()
            first = store.add("News Letter <NEWS@Example.COM>")
            second = store.add("news@example.com")
            store.record_match("NEWS@example.com")
            self.assertEqual(first.address, "news@example.com")
            self.assertEqual(second.display_name, "News Letter")
            self.assertEqual(len(store.list()), 1)
            self.assertEqual(store.get("news@example.com").match_count, 1)
            self.assertTrue(store.delete("NEWS@example.com"))
            self.assertFalse(store.contains("news@example.com"))

    def test_invalid_sender_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "有効な送信者"):
            normalize_sender("not-an-address")

if __name__ == "__main__":
    unittest.main()
