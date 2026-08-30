const WORKINBOX_URL = "http://127.0.0.1:8000/";
const WORKINBOX_IMAP_TARGET_URL = `${WORKINBOX_URL}api/thunderbird/imap-target`;

const openWorkInBoxButton = document.querySelector("#open-workinbox");
const openExtensionDashboardButton = document.querySelector("#open-extension-dashboard");
const workViewKindSelect = document.querySelector("#work-view-kind");
const openWorkViewButton = document.querySelector("#open-work-view");

function setStatus(text) {
  const status = document.querySelector("#status");
  if (status) {
    status.textContent = text;
  }
}

async function loadWorkInBoxImapTarget() {
  const response = await fetch(WORKINBOX_IMAP_TARGET_URL, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`WIB Web の IMAP 設定を取得できませんでした: HTTP ${response.status}`);
  }

  const target = await response.json();
  if (!target?.host || !target?.username || !Number.isInteger(target?.port) || !target?.mailbox) {
    throw new Error("WIB Web から取得した IMAP 設定が不正です。");
  }
  return target;
}

openExtensionDashboardButton.addEventListener("click", async () => {
  try {
    const response = await messenger.runtime.sendMessage({
      type: "workinbox-open-dashboard",
    });
    if (!response?.ok) {
      throw new Error(response?.error || "Extensionダッシュボードを開けませんでした。");
    }
    window.close();
  } catch (error) {
    console.error("[WorkInBox dashboard]", error);
    setStatus(`ERROR: ${error.message || error}`);
  }
});

openWorkInBoxButton.addEventListener("click", async () => {
  try {
    await messenger.tabs.create({
      url: WORKINBOX_URL,
      active: true,
      linkHandler: "balanced",
    });
    window.close();
  } catch (error) {
    console.error("[WorkInBox bridge]", error);
    setStatus(`ERROR: ${error.message || error}`);
  }
});

openWorkViewButton.addEventListener("click", async () => {
  const view = workViewKindSelect.value;
  const viewLabel = workViewKindSelect.selectedOptions[0]?.textContent || view;

  openWorkViewButton.disabled = true;
  setStatus(`${viewLabel} の対象 IMAP アカウントを確認しています…`);

  try {
    const imapTarget = await loadWorkInBoxImapTarget();
    setStatus(`${viewLabel} の Quick Filter を適用しています…`);

    const response = await messenger.runtime.sendMessage({
      type: "workinbox-open-work-view",
      view,
      imapTarget,
    });

    if (!response?.ok) {
      throw new Error(response?.error || "Quick Filter を適用できませんでした。");
    }

    setStatus(`${response.accountName || "WIB対象アカウント"} / ${response.folderName || imapTarget.mailbox} で ${response.viewLabel || viewLabel} + スター付きの表示に切り替えました。`);
    window.close();
  } catch (error) {
    console.error("[WorkInBox bridge]", error);
    setStatus(`ERROR: ${error.message || error}`);
    openWorkViewButton.disabled = false;
  }
});
