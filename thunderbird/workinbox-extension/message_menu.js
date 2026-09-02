"use strict";

const status = document.querySelector("#status");

for (const button of document.querySelectorAll("button")) {
  button.addEventListener("click", async () => {
    const kind = button.dataset.dedicatedWorkflow;
    const dismissKind = button.dataset.dismissDedicatedWorkflow;
    if (kind || dismissKind) {
      button.disabled = true;
      status.textContent = "選択中のメールを確認しています…";
      try {
        const tabs = await messenger.tabs.query({ active: true, currentWindow: true });
        const tab = tabs[0];
        const message = tab ? await messenger.messageDisplay.getDisplayedMessage(tab.id) : null;
        if (!message?.headerMessageId) {
          throw new Error("表示中のメールのMessage-IDを取得できませんでした。");
        }
        const response = await messenger.runtime.sendMessage({
          type: kind
            ? "workinbox-open-dedicated-workflow"
            : "workinbox-dismiss-dedicated-workflow",
          kind: kind || dismissKind,
          messageId: message.headerMessageId,
        });
        if (!response?.ok) {
          throw new Error(response?.error || "専用フローを開けませんでした。");
        }
        if (dismissKind) {
          status.textContent = response.completed
            ? "専用フローを終了し、一括処理にしました。"
            : "専用フローを外しました。ほかのWIB作業を継続します。";
          window.setTimeout(() => window.close(), 700);
        } else {
          window.close();
        }
      } catch (error) {
        status.textContent = `ERROR: ${error.message || error}`;
        button.disabled = false;
      }
      return;
    }
    status.textContent = `「${button.textContent.trim()}」は現在プレビューのみです。`;
  });
}
