"use strict";

const status = document.querySelector("#status");
const description = document.querySelector("#menu-description");
let currentMessage = null;

async function displayedMessage() {
  const tabs = await messenger.tabs.query({ active: true, currentWindow: true });
  const tab = tabs[0];
  const message = tab ? await messenger.messageDisplay.getDisplayedMessage(tab.id) : null;
  if (!message?.headerMessageId) throw new Error("表示中のメールのMessage-IDを取得できませんでした。");
  return message;
}

function requestFor(message, values = {}) {
  return { ...values, messageId: message.headerMessageId, thunderbirdMessageId: message.id };
}

async function sendOperation(button, request, successText) {
  button.disabled = true;
  status.textContent = "処理しています…";
  try {
    const response = await messenger.runtime.sendMessage(request);
    if (!response?.ok) throw new Error(response?.error || "処理に失敗しました。");
    status.textContent = typeof successText === "function" ? successText(response) : successText;
    window.setTimeout(() => window.close(), 500);
  } catch (error) {
    status.textContent = `ERROR: ${error.message || error}`;
    button.disabled = false;
  }
}

async function initialize() {
  currentMessage = await displayedMessage();
  const response = await messenger.runtime.sendMessage(requestFor(currentMessage, {
    type: "workinbox-message-menu-state",
  }));
  if (!response?.ok) throw new Error(response?.error || "メールの状態を確認できませんでした。");

  const actionReady = Boolean(response.actionReady);
  document.querySelector("#action-ready-menu").hidden = !actionReady;
  document.querySelector("#normal-menu").hidden = actionReady;
  document.querySelector("#dedicated-menu").hidden = actionReady;
  document.querySelector("#completion-menu").hidden = actionReady;
  description.textContent = actionReady
    ? "対応ありメールへの処理を選んでください。"
    : "通常フロー、専用フロー、または終了操作を選んでください。";
  for (const button of document.querySelectorAll("[data-normal-workflow]")) {
    const selected = button.dataset.normalWorkflow === response.normalWorkflow;
    button.classList.toggle("selected", selected);
    button.querySelector(".check").textContent = selected ? "✓" : "　";
  }
}

for (const button of document.querySelectorAll("button")) {
  button.addEventListener("click", () => {
    const kind = button.dataset.dedicatedWorkflow;
    const dismissKind = button.dataset.dismissDedicatedWorkflow;
    const normalWorkflow = button.dataset.normalWorkflow;
    const completion = button.dataset.completion;
    const actionReady = button.dataset.actionReady;
    if (kind || dismissKind) {
      void sendOperation(button, requestFor(currentMessage, {
        type: kind ? "workinbox-open-dedicated-workflow" : "workinbox-dismiss-dedicated-workflow",
        kind: kind || dismissKind,
      }), dismissKind ? (response) => response.completed
        ? "専用フローを終了し、一括処理にしました。"
        : "専用フローを外しました。ほかのWIB作業を継続します。" : "専用フローを開きました。");
    } else if (normalWorkflow) {
      void sendOperation(button, requestFor(currentMessage, {
        type: "workinbox-set-normal-workflow", tagKey: normalWorkflow,
      }), "通常フローを変更しました。");
    } else if (completion) {
      void sendOperation(button, requestFor(currentMessage, {
        type: "workinbox-complete-message", mode: completion,
      }), completion === "record" ? "Record登録メールを作成します。" : "通常終了しました。");
    } else if (actionReady) {
      void sendOperation(button, requestFor(currentMessage, {
        type: "workinbox-handle-action-ready", action: actionReady,
      }), actionReady === "finish" ? "返信せず終了しました。" : "返信メールを作成します。");
    }
  });
}

void initialize().catch((error) => {
  description.textContent = "メニューを表示できません。";
  status.textContent = `ERROR: ${error.message || error}`;
});
