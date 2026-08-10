const archiveIndexingStatus = document.querySelector("#archive-indexing-status");
const archiveIndexingPreview = document.querySelector("#archive-indexing-preview");
const previewArchiveIndexingButton = document.querySelector("#preview-archive-indexing");
const syncArchiveIndexingButton = document.querySelector("#sync-archive-indexing");

let archiveIndexingPlan = [];

function setArchiveStatus(message) {
  archiveIndexingStatus.textContent = message;
}

function flattenFolders(folder) {
  const result = [folder];
  for (const child of folder.subFolders || []) {
    result.push(...flattenFolders(child));
  }
  return result;
}

async function getArchiveFolders() {
  const roots = await messenger.folders.query({ specialUse: ["archives"] });
  const byId = new Map();

  for (const root of roots) {
    const completeRoot = await messenger.folders.get(root.id, true);
    for (const folder of flattenFolders(completeRoot)) {
      if (!folder.isVirtual && folder.accountId) {
        byId.set(folder.id, folder);
      }
    }
  }

  return [...byId.values()].sort((a, b) => {
    const accountCompare = a.accountId.localeCompare(b.accountId);
    return accountCompare || a.path.localeCompare(b.path, "ja");
  });
}

async function buildArchiveIndexingPlan() {
  const folders = await getArchiveFolders();
  const plan = [];

  for (const folder of folders) {
    const current = await messenger.glodaIndexing.getStatus(folder.accountId, folder.path);
    const desiredEnabled = Boolean(folder.isFavorite);
    plan.push({
      id: folder.id,
      accountId: folder.accountId,
      path: folder.path,
      name: folder.name,
      favorite: desiredEnabled,
      currentEnabled: current.enabled,
      currentPriority: current.priority,
      desiredEnabled,
      needsChange: current.enabled !== desiredEnabled,
    });
  }

  return plan;
}

function formatPlan(plan) {
  if (plan.length === 0) {
    return "Archive フォルダが見つかりませんでした。";
  }

  return plan
    .map((item) => {
      const favorite = item.favorite ? "ON " : "OFF";
      const current = item.currentEnabled ? "index ON " : "index OFF";
      const desired = item.desiredEnabled ? "index ON" : "index OFF";
      const arrow = item.needsChange ? ` -> ${desired}` : " (変更なし)";
      return `${item.accountId} ${item.path}\n  Favorite ${favorite} / ${current}${arrow}`;
    })
    .join("\n");
}

async function previewArchiveIndexing() {
  setArchiveStatus("Archive の Favorite 状態と索引設定を確認しています…");
  archiveIndexingPlan = await buildArchiveIndexingPlan();
  archiveIndexingPreview.textContent = formatPlan(archiveIndexingPlan);

  const changes = archiveIndexingPlan.filter((item) => item.needsChange).length;
  syncArchiveIndexingButton.disabled = changes === 0;
  setArchiveStatus(
    `Archive ${archiveIndexingPlan.length} フォルダを確認しました。変更予定は ${changes} 件です。`,
  );
}

async function syncArchiveIndexing() {
  if (archiveIndexingPlan.length === 0) {
    await previewArchiveIndexing();
  }

  const changes = archiveIndexingPlan.filter((item) => item.needsChange);
  if (changes.length === 0) {
    setArchiveStatus("Favorite 状態と Gloda indexing はすでに一致しています。");
    return;
  }

  const confirmed = window.confirm(
    `Archive ${changes.length} フォルダの Gloda indexing を Favorite 状態に合わせます。\n\n` +
      "Favorite ON は索引対象、Favorite OFF は索引対象外になります。\n" +
      "索引を ON に戻したフォルダでは再索引が始まる場合があります。\n\n続けますか？",
  );
  if (!confirmed) {
    return;
  }

  let completed = 0;
  for (const item of changes) {
    setArchiveStatus(`索引設定を同期しています… ${completed}/${changes.length}`);
    await messenger.glodaIndexing.setEnabled(
      item.accountId,
      item.path,
      item.desiredEnabled,
    );
    completed += 1;
  }

  await previewArchiveIndexing();
  setArchiveStatus(`Archive の索引設定を同期しました（${completed} 件変更）。`);
}

function handleArchiveAction(action) {
  return async () => {
    try {
      await action();
    } catch (error) {
      console.error("[WorkInBox archive indexing]", error);
      setArchiveStatus(`ERROR: ${error.message || error}`);
      syncArchiveIndexingButton.disabled = true;
    }
  };
}

previewArchiveIndexingButton.addEventListener(
  "click",
  handleArchiveAction(previewArchiveIndexing),
);
syncArchiveIndexingButton.addEventListener(
  "click",
  handleArchiveAction(syncArchiveIndexing),
);
