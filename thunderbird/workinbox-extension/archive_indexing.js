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
      currentFolderProperty: current.folderProperty,
      neverPriority: current.neverPriority,
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
      return (
        `${item.accountId} ${item.path}\n` +
        `  Favorite ${favorite} / ${current}${arrow}\n` +
        `  priority=${item.currentPriority} never=${item.neverPriority} folderProperty=${JSON.stringify(item.currentFolderProperty)}`
      );
    })
    .join("\n");
}

function formatDiagnostic(item, result) {
  return [
    `SYNC DIAGNOSTIC: ${item.accountId} ${item.path}`,
    `requestedEnabled=${result.requestedEnabled}`,
    `before: enabled=${result.beforeEnabled} priority=${result.beforePriority} folderProperty=${JSON.stringify(result.beforeFolderProperty)}`,
    `after:  enabled=${result.afterEnabled} priority=${result.afterPriority} folderProperty=${JSON.stringify(result.afterFolderProperty)}`,
    `neverPriority=${result.neverPriority}`,
    `applied=${result.applied}`,
  ].join("\n");
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
      "索引を ON に戻したフォルダでは再索引が始まる場合があります。\n\n" +
      "診断モードでは 1 件ずつ反映を確認し、失敗した時点で停止します。\n\n続けますか？",
  );
  if (!confirmed) {
    return;
  }

  let completed = 0;
  for (const item of changes) {
    setArchiveStatus(`索引設定を同期・検証しています… ${completed}/${changes.length}`);
    const result = await messenger.glodaIndexing.setEnabled(
      item.accountId,
      item.path,
      item.desiredEnabled,
    );

    archiveIndexingPreview.textContent =
      `${formatDiagnostic(item, result)}\n\n` + archiveIndexingPreview.textContent;

    if (!result.applied) {
      setArchiveStatus(
        `ERROR: ${item.path} の索引設定が直後の確認で反映されませんでした。診断結果をコピーしてください。`,
      );
      syncArchiveIndexingButton.disabled = true;
      return;
    }

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
