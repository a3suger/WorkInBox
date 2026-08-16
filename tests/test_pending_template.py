from __future__ import annotations

import unittest

from workinbox.web import _TEMPLATES


class PendingTemplateTest(unittest.TestCase):
    def test_pending_ui_exposes_only_normal_workflow_choices(self) -> None:
        source, _, _ = _TEMPLATES.env.loader.get_source(_TEMPLATES.env, "pending.html")

        for resolution, label in (
            ("answer", "返信必要"),
            ("review", "見る・検討"),
            ("watch", "注目"),
            ("none", "何もしなくてよい"),
        ):
            self.assertIn(f"resolution={resolution}", source)
            self.assertIn(label, source)

        self.assertNotIn("resolution=deadline", source)
        self.assertNotIn("resolution=schedule", source)
        self.assertNotIn("締切＋スケジュール", source)


if __name__ == "__main__":
    unittest.main()
