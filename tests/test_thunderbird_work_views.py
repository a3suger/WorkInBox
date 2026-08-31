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
            "threePaneWindow.gViewWrapper.setMailView(name, null, true)",
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
        self.assertIn('unattended: { label: "未着眼", unattended: true, unread: false }', background)
        self.assertIn(
            "messenger.mailViews.ensureUnattendedView(mailTab.id, lookbackDays)",
            background,
        )
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
            'new URL("/api/extension/bootstrap", window.location.href)',
            bridge,
        )
        self.assertIn("bootstrap.new_mail_lookback_days", bridge)
        self.assertIn('view.startsWith("unattended")', bridge)
        self.assertIn("button.title = message", bridge)
        self.assertIn("}, 10000);", bridge)

    def test_deadline_source_page_auto_opens_its_message(self) -> None:
        bridge = (EXTENSION / "workinbox_bridge.js").read_text(encoding="utf-8")

        self.assertIn('"[data-wib-auto-open-message-id]"', bridge)
        self.assertIn("void handleOpenMessage(autoOpenMessageButton)", bridge)

    def test_source_message_links_use_mid_with_search_fallback(self) -> None:
        message_link = (
            ROOT / "src" / "workinbox" / "templates" / "_message_link.html"
        ).read_text(encoding="utf-8")
        bridge = (EXTENSION / "workinbox_bridge.js").read_text(encoding="utf-8")

        self.assertIn('href="mid:{{ message_id | mid_value }}"', message_link)
        self.assertIn('data-wib-open-message-id="{{ message_id }}"', message_link)
        self.assertIn("見つからない場合は検索", message_link)
        self.assertIn('querySelectorAll(".wib-message-search-fallback")', bridge)
        self.assertIn("button.hidden = false", bridge)

        for template_name in (
            "deadlines.html",
            "schedules.html",
            "emails.html",
            "pending.html",
            "deadline_detail.html",
            "deadline_source_message.html",
            "records.html",
        ):
            template = (
                ROOT / "src" / "workinbox" / "templates" / template_name
            ).read_text(encoding="utf-8")
            self.assertIn("source_message_link(", template, template_name)

    def test_manifest_registers_mail_views_experiment(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        experiment = manifest["experiment_apis"]["mailViews"]

        self.assertEqual(experiment["schema"], "experiments/mail_views/schema.json")
        self.assertEqual(
            experiment["parent"]["script"],
            "experiments/mail_views/implementation.js",
        )

    def test_message_display_action_completes_normal_workflow_in_one_click(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        background = (EXTENSION / "background.js").read_text(encoding="utf-8")

        self.assertEqual(
            manifest["message_display_action"]["default_title"],
            "WIB: 通常ワークフローを終了",
        )
        self.assertIn("messenger.messageDisplayAction.onClicked", background)
        self.assertIn("messenger.messageDisplay.getDisplayedMessage(tab.id)", background)
        self.assertIn("NORMAL_WORKFLOW_TAGS", background)
        self.assertIn("const bulkTagKey = await resolveBulkTagKey()", background)
        self.assertIn("await addTag(message, bulkTagKey)", background)
        self.assertIn("await messenger.messages.tags.list()", background)
        self.assertIn("await messenger.messages.tags.create(", background)
        self.assertIn('const LEGACY_BULK_TAG = "wib-batch"', background)
        self.assertIn('tag: "一括処理"', background)
        self.assertNotIn("await messenger.messages.get(message.id)", background)
        self.assertIn(
            "await messenger.messages.update(message.id, { flagged: false })",
            background,
        )

    def test_popup_uses_current_work_view_names(self) -> None:
        popup = (EXTENSION / "popup.html").read_text(encoding="utf-8")

        for label in ("未着眼・未読", "未着眼・既読", "返信必要", "見る・検討", "注目"):
            self.assertIn(label, popup)
        self.assertNotIn("Quick Filter PoC", popup)
        self.assertNotIn("回答必要", popup)
        self.assertNotIn("読む・検討", popup)

    def test_extension_dashboard_is_registered_and_opened_in_a_reused_tab(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        popup = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        popup_bridge = (EXTENSION / "popup_bridge.js").read_text(encoding="utf-8")
        background = (EXTENSION / "background.js").read_text(encoding="utf-8")

        self.assertEqual(manifest["version"], "0.3.4")
        self.assertTrue((EXTENSION / "dashboard.html").is_file())
        self.assertTrue((EXTENSION / "dashboard.js").is_file())
        self.assertTrue((EXTENSION / "dashboard.css").is_file())
        self.assertIn('id="open-extension-dashboard"', popup)
        self.assertIn('type: "workinbox-open-dashboard"', popup_bridge)
        self.assertIn('messenger.runtime.getURL("dashboard.html")', background)
        self.assertIn("getExistingDashboardTab()", background)

    def test_extension_dashboard_counts_thunderbird_message_state(self) -> None:
        dashboard = (EXTENSION / "dashboard.html").read_text(encoding="utf-8")
        dashboard_script = (EXTENSION / "dashboard.js").read_text(encoding="utf-8")
        background = (EXTENSION / "background.js").read_text(encoding="utf-8")

        for count_name in (
            "unattendedTotal",
            "unattendedUnread",
            "unattendedRead",
            "answer",
            "review",
            "watch",
            "deadline",
            "schedule",
            "pending",
            "waitingReply",
            "waitingAction",
            "actionReady",
        ):
            self.assertIn(f'data-count="{count_name}"', dashboard)
        self.assertIn('type: "workinbox-dashboard-counts"', dashboard_script)
        self.assertIn("currentConfig.lookbackDays", dashboard_script)
        self.assertIn('fetchJson("/api/health")', dashboard_script)
        self.assertIn('fetchJson("/api/extension/bootstrap")', dashboard_script)
        self.assertIn('id="normal-sync"', dashboard)
        self.assertIn('fetchJson("/api/sync", { method: "POST" })', dashboard_script)
        self.assertIn("!isOnline || syncRunning", dashboard_script)
        self.assertIn("workinboxExtensionDashboardCache", dashboard_script)
        self.assertIn("messenger.messages.query({", background)
        self.assertIn("messenger.messages.continueList(page.id)", background)
        self.assertIn("fromDate: since", background)
        self.assertIn("flagged: false", background)
        self.assertIn('mode: "any"', background)
        self.assertIn("Object.values(DASHBOARD_TAG_COUNTS)", background)
        self.assertIn("tags.has(BULK_TAG) || tags.has(LEGACY_BULK_TAG)", background)
        self.assertIn("received >= since", background)
        self.assertIn('type: "workinbox-dashboard-invalidated"', background)
        self.assertNotIn('tags.has("wib-deadline-done")', background)
        self.assertNotIn('tags.has("wib-schedule-done")', background)

    def test_unattended_dashboard_view_uses_lookback_days(self) -> None:
        dashboard_script = (EXTENSION / "dashboard.js").read_text(encoding="utf-8")
        background = (EXTENSION / "background.js").read_text(encoding="utf-8")
        experiment = (
            EXTENSION / "experiments" / "mail_views" / "implementation.js"
        ).read_text(encoding="utf-8")
        schema = json.loads(
            (EXTENSION / "experiments" / "mail_views" / "schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn('startsWith("unattended")', dashboard_script)
        self.assertIn('data-work-view="unattended"', (
            EXTENSION / "dashboard.html"
        ).read_text(encoding="utf-8"))
        self.assertIn("request.lookbackDays", background)
        self.assertIn("Ci.nsMsgSearchAttrib.AgeInDays", experiment)
        self.assertIn("Ci.nsMsgSearchOp.IsLessThan", experiment)
        self.assertIn("value.age = lookbackDays", experiment)
        parameters = schema[0]["functions"][0]["parameters"]
        self.assertEqual(parameters[1]["name"], "lookbackDays")
        self.assertTrue(parameters[1]["optional"])


if __name__ == "__main__":
    unittest.main()
