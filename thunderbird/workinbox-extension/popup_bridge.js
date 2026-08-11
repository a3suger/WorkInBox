const WORKINBOX_URL = "http://127.0.0.1:8000/";
const WORK_VIEW_ACCOUNT_STORAGE_KEY = "workinboxWorkViewAccountId";

const openWorkInBoxButton = document.querySelector("#open-workinbox");
const workViewAccountSelect = document.querySelector("#work-view-account");
const saveWorkViewAccountButton = document.querySelector("#save-work-view-account");
const workViewKindSelect = document.querySelector("#work-view-kind");
const openWorkViewButton = document.querySelector("#open-work-view");

function setStatus(text) {
  const status = document.querySelector("#status");
  if (status) {
    status.textContent = text;
  }
}

async function loadWorkViewAccounts() {
  const accounts = await messenger.accounts.list();
  const stored = await messenger.storage.local.get(WORK_VIEW_ACCOUNT_STORAGE_KEY);
  const selectedAccountId = String(stored?.[WORK_VIEW_ACCOUNT_STORAGE_KEY] || "");

  workViewAccountSelect.replaceChildren();

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "対象アカウントを選択";
  workViewAccountSelect.appendChild(placeholder);

  for (const account of accounts) {
    if (account.type !== "imap") {
      continue;
    }

    const option = document.createElement("option");
    option.value = account.id;
    option.textContent = account.name || account.id;
    option.selected = account.id === selectedAccountId;
    workViewAccountSelect.appendChild(option);
  }

  if (selectedAccountId) {
    const selectedOption = [...workViewAccountSelect.options].find(
      (option) => option.value === selectedAccountId,
    );
    if (!selectedOption) {
      workViewAccountSelect.value = "";
      setStatus("保存済みの対象アカウントが見つかりません。選択し直してください。");
    }
  }
}

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

saveWorkViewAccountButton.addEventListener("click", async () => {
  const accountId = workViewAccountSelect.value;
  if (!accountId) {
    setStatus("Quick Filter PoC の対象アカウントを選択してください。");
    return;
  }

  try {
    await messenger.storage.local.set({
      [WORK_VIEW_ACCOUNT_STORAGE_KEY]: accountId,
    });
    const accountName = workViewAccountSelect.selectedOptions[0]?.textContent || accountId;
    setStatus(`Quick Filter PoC の対象を「${accountName}」に保存しました。`);
  } catch (error) {
    console.error("[WorkInBox bridge]", error);
    setStatus(`ERROR: ${error.message || error}`);
  }
});

openWorkViewButton.addEventListener("click", async () => {
  const view = workViewKindSelect.value;
  const viewLabel = workViewKindSelect.selectedOptions[0]?.textContent || view;

  openWorkViewButton.disabled = true;
  setStatus(`${viewLabel} の Quick Filter を適用しています…`);

  try {
    const response = await messenger.runtime.sendMessage({
      type: "workinbox-open-work-view",
      view,
    });

    if (!response?.ok) {
      throw new Error(response?.error || "Quick Filter を適用できませんでした。");
    }

    setStatus(`${response.accountName || "設定アカウント"} / ${response.folderName || "INBOX"} で ${response.viewLabel || viewLabel} + スター付きの表示に切り替えました。`);
    window.close();
  } catch (error) {
    console.error("[WorkInBox bridge]", error);
    setStatus(`ERROR: ${error.message || error}`);
    openWorkViewButton.disabled = false;
  }
});

void loadWorkViewAccounts().catch((error) => {
  console.error("[WorkInBox bridge]", error);
  setStatus(`ERROR: ${error.message || error}`);
});
