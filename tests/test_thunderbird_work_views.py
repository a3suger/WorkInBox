from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "thunderbird" / "workinbox-extension"


class ThunderbirdWorkViewContractTest(unittest.TestCase):
    def test_unattended_view_is_starless_and_not_bulk(self) -> None:
        implementation = (
            EXTENSION / "experiments" / "mail_views" / "implementation.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Ci.nsMsgSearchAttrib.MsgStatus", implementation)
        self.assertIn("Ci.nsMsgSearchOp.Isnt", implementation)
        self.assertIn("Ci.nsMsgMessageFlags.Marked", implementation)
        self.assertIn('["wib-bulk", "wib-batch"]', implementation)
        self.assertIn("Ci.nsMsgSearchAttrib.Keywords", implementation)
        self.assertIn("Ci.nsMsgSearchOp.DoesntContain", implementation)
        self.assertIn('const VIEW_NAME = "WIB 未着眼";', implementation)
        self.assertIn(
            "threePaneWindow.gViewWrapper.setMailView(VIEW_NAME, null, true)",
            implementation,
        )
        self.assertIn(
            "threePaneWindow.gViewWrapper.setMailView(0, null, true)",
            implementation,
        )
        self.assertNotIn("setMailView(-1", implementation)

    def test_background_routes_unattended_and_normal_views_separately(self) -> None:
        background = (EXTENSION / "background.js").read_text(encoding="utf-8")

        self.assertIn('"unattended-unread": { label: "未着眼・未読", unattended: true, unread: true }', background)
        self.assertIn('"unattended-read": { label: "未着眼・既読", unattended: true, unread: false }', background)
        self.assertIn("messenger.mailViews.ensureUnattendedView(mailTab.id)", background)
        self.assertIn("unread: true", background)
        self.assertIn("messenger.mailViews.resetView(mailTab.id)", background)
        self.assertIn("flagged: true", background)
        self.assertIn('[view.tagKey]: true', background)
        self.assertIn('watch: { tagKey: "wib-watch", label: "注目" }', background)

    def test_web_dashboard_bridge_opens_work_views(self) -> None:
        bridge = (EXTENSION / "workinbox_bridge.js").read_text(encoding="utf-8")

        self.assertIn("[data-wib-open-work-view]", bridge)
        self.assertIn('type: "workinbox-open-work-view"', bridge)
        self.assertIn(
            'new URL("/api/thunderbird/imap-target", window.location.href)',
            bridge,
        )
        self.assertIn("button.title = message", bridge)
        self.assertIn("}, 10000);", bridge)

    def test_manifest_registers_mail_views_experiment(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        experiment = manifest["experiment_apis"]["mailViews"]

        self.assertEqual(experiment["schema"], "experiments/mail_views/schema.json")
        self.assertEqual(
            experiment["parent"]["script"],
            "experiments/mail_views/implementation.js",
        )

    def test_popup_uses_current_work_view_names(self) -> None:
        popup = (EXTENSION / "popup.html").read_text(encoding="utf-8")

        for label in ("未着眼・未読", "未着眼・既読", "返信必要", "見る・検討", "注目"):
            self.assertIn(label, popup)
        self.assertNotIn("Quick Filter PoC", popup)
        self.assertNotIn("回答必要", popup)
        self.assertNotIn("読む・検討", popup)


if __name__ == "__main__":
    unittest.main()
