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

    def test_dedicated_views_require_active_tag_and_exclude_completed_tags(self) -> None:
        implementation = (
            EXTENSION / "experiments" / "mail_views" / "implementation.js"
        ).read_text(encoding="utf-8")
        schema = json.loads(
            (EXTENSION / "experiments" / "mail_views" / "schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("function createWorkflowView", implementation)
        self.assertIn("Ci.nsMsgSearchOp.Contains", implementation)
        self.assertIn("for (const keyword of excludedTags)", implementation)
        self.assertIn("Ci.nsMsgSearchOp.DoesntContain", implementation)
        self.assertIn("Ci.nsMsgMessageFlags.Marked", implementation)
        self.assertIn("async ensureWorkflowView", implementation)
        self.assertIn(
            "ensureWorkflowView",
            [function["name"] for function in schema[0]["functions"]],
        )

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
        self.assertIn("messenger.mailViews.ensureWorkflowView(", background)
        self.assertIn('excludedTags: ["wib-deadline-done"]', background)
        self.assertIn(
            'excludedTags: [REQUESTED_TAG, "wib-schedule-done"]',
            background,
        )
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

    def test_message_display_action_opens_preview_menu(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        background = (EXTENSION / "background.js").read_text(encoding="utf-8")

        self.assertEqual(
            manifest["message_display_action"]["default_title"],
            "WIB操作メニュー",
        )
        self.assertEqual(
            manifest["message_display_action"]["default_popup"],
            "message_menu.html",
        )
        menu = (EXTENSION / "message_menu.html").read_text(encoding="utf-8")
        script = (EXTENSION / "message_menu.js").read_text(encoding="utf-8")
        self.assertIn("通常フロー", menu)
        self.assertIn("専用フロー", menu)
        self.assertIn("締切登録を開始／続ける", menu)
        self.assertIn("スケジュール調整を開始／続ける", menu)
        self.assertIn("プレビューのみ", script)
        self.assertIn('data-dedicated-workflow="deadline"', menu)
        self.assertIn('data-dedicated-workflow="schedule"', menu)
        self.assertIn('data-dismiss-dedicated-workflow="deadline"', menu)
        self.assertIn('data-dismiss-dedicated-workflow="schedule"', menu)
        self.assertIn("messenger.messageDisplay.getDisplayedMessage(tab.id)", script)
        self.assertIn('"workinbox-open-dedicated-workflow"', script)
        self.assertIn('"workinbox-dismiss-dedicated-workflow"', script)
        self.assertIn("request.thunderbirdMessageId", background)
        self.assertIn("resolveDisplayedMessage(thunderbirdMessageId, messageId)", background)
        self.assertIn("messenger.messages.get(thunderbirdMessageId)", background)
        self.assertIn("thunderbirdMessageId: message.id", script)
        self.assertIn("OPEN_WORKFLOW_TAGS", background)
        self.assertIn("remainingTags.some((tag) => OPEN_WORKFLOW_TAGS.has(tag))", background)
        self.assertIn("tags: completedTags", background)
        self.assertIn("flagged: false", background)
        self.assertIn("await addTag(message, tagKey, { flagged: true })", background)
        self.assertIn('messenger.runtime.getURL("workflow_launcher.html")', background)
        self.assertTrue((EXTENSION / "workflow_launcher.html").is_file())
        launcher = (EXTENSION / "workflow_launcher.js").read_text(encoding="utf-8")
        self.assertIn('new URL("api/health", WIB_URL)', launcher)
        self.assertIn('type: "workinbox-prepare-dedicated-workflow"', launcher)
        self.assertIn('target.searchParams.set("message_id", messageId)', launcher)
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

    def test_settings_page_is_limited_to_maintenance_tools(self) -> None:
        popup = (EXTENSION / "popup.html").read_text(encoding="utf-8")

        for label in ("Archive indexing policy", "タグスナップショット", "WIBタグ登録", "復元"):
            self.assertIn(label, popup)
        for label in ("Extension ダッシュボード", "WorkInBox Web UI", "WIB 作業ビュー"):
            self.assertNotIn(label, popup)

    def test_extension_dashboard_is_registered_and_opened_in_a_reused_tab(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        popup = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        background = (EXTENSION / "background.js").read_text(encoding="utf-8")
        dashboard_script = (EXTENSION / "dashboard.js").read_text(encoding="utf-8")

        self.assertEqual(manifest["version"], "0.3.21")
        self.assertTrue((EXTENSION / "dashboard.html").is_file())
        self.assertTrue((EXTENSION / "dashboard.js").is_file())
        self.assertTrue((EXTENSION / "dashboard.css").is_file())
        self.assertNotIn("Extension ダッシュボード", popup)
        self.assertNotIn("WorkInBox Web UI", popup)
        self.assertNotIn("WIB 作業ビュー", popup)
        self.assertNotIn('src="popup_bridge.js"', popup)
        self.assertFalse((EXTENSION / "popup_bridge.js").exists())
        self.assertIn('messenger.runtime.getURL("dashboard.html")', background)
        self.assertIn("getExistingDashboardTab()", background)
        self.assertIn('DASHBOARD_SPACE_BUTTON_ID = "workinbox_dashboard"', background)
        self.assertIn("let workViewTabTitle = null", background)
        self.assertIn("messenger.tabs.onUpdated.addListener", background)
        self.assertIn("messenger.tabs.onActivated.addListener", background)
        self.assertIn("restoreWorkViewTabTitle(tabId)", background)
        tab_title = (EXTENSION / "experiments/tab_title/implementation.js").read_text(encoding="utf-8")
        self.assertIn("new win.MutationObserver", tab_title)
        self.assertIn('attributeFilter: ["label"]', tab_title)
        self.assertIn("applyTitle(tabInfo, tabNode, requestedTitle)", tab_title)
        self.assertIn("messenger.spacesToolbar.addButton(", background)
        self.assertIn("messenger.spacesToolbar.updateButton(", background)
        self.assertIn("messenger.spacesToolbar.clickButton(", background)
        self.assertIn('url: "dashboard.html"', background)
        self.assertIn('16: "icons/workinbox.svg"', background)
        self.assertIn('32: "icons/workinbox.svg"', background)
        self.assertNotIn("browser_action", manifest)
        self.assertEqual(manifest["options_ui"]["page"], "popup.html")
        self.assertIn("WorkInBox 設定・ツール", popup)
        self.assertIn('id="open-settings"', (EXTENSION / "dashboard.html").read_text(encoding="utf-8"))
        self.assertIn("messenger.runtime.openOptionsPage()", dashboard_script)
        self.assertIn('type: "workinbox-open-tasks"', dashboard_script)
        self.assertIn('messenger.tabs.query({ type: "tasks" })', background)
        self.assertIn("tasksSpace", manifest["experiment_apis"])

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
            "bulkArchive",
        ):
            self.assertIn(f'data-count="{count_name}"', dashboard)
        self.assertIn('type: "workinbox-dashboard-counts"', dashboard_script)
        self.assertIn("currentConfig.lookbackDays", dashboard_script)
        self.assertIn('fetchJson("/api/health")', dashboard_script)
        self.assertIn('fetchJson("/api/extension/bootstrap")', dashboard_script)
        self.assertIn('fetchJson("/api/deadlines/summary")', dashboard_script)
        self.assertIn('data-deadline-count="overdue"', dashboard)
        self.assertIn('data-deadline-count="due_within_7_days"', dashboard)
        self.assertIn('id="open-tasks"', dashboard)
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
        self.assertIn('countName === "deadline" && tags.has("wib-deadline-done")', background)
        self.assertIn('tags.has("wib-schedule-done")', background)
        self.assertIn('tags.has(REQUESTED_TAG) || tags.has("wib-schedule-done")', background)
        self.assertIn('data-work-view="bulkArchive"', dashboard)
        self.assertIn('bulkArchive: { label: "整理済み・アーカイブ待ち", bulkArchive: true }', background)
        self.assertIn("counts.bulkArchive += 1", background)
        self.assertIn("[LEGACY_BULK_TAG]: true", background)
        self.assertIn("ensureBulkArchiveView", background)
        self.assertIn("WIB 整理済み・アーカイブ待ち", (
            EXTENSION / "experiments" / "mail_views" / "implementation.js"
        ).read_text(encoding="utf-8"))

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
