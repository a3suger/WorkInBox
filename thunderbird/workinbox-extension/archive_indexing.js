const archiveIndexingStatus = document.querySelector("#archive-indexing-status");
const archiveIndexingPreview = document.querySelector("#archive-indexing-preview");
const previewArchiveIndexingButton = document.querySelector("#preview-archive-indexing");
const syncArchiveIndexingButton = document.querySelector("#sync-archive-indexing");

const ARCHIVE_DIAGNOSTIC_KEY = "archiveIndexingLastDiagnostic";

let archiveIndexingPlan = [];
let syncArmed = false;

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

async function saveDiagnostic(text) {
  await messenger.storage.local.set({
    [ARCHIVE_DIAGNOSTIC_KEY]: {
      savedAt: new Date().toISOString(),
      text,
    },
  });
}

async function restoreDiagnostic() {
  const stored = await messenger.storage.local.get(ARCHIVE_DIAGNOSTIC_KEY);
  const diagnostic = stored[ARCHIVE_DIAGNOSTIC_KEY];
  if (!diagnostic?.text) {
    return;
  }

  archiveIndexingPreview.textContent =
    `前回の同期診断 (${diagnostic.savedAt})\n\n${diagnostic.text}`;
  setArchiveStatus("前回の同期診断を表示しています。必要なら再度プレビューしてください。");
}

function resetSyncArm() {
  syncArmed = false;
  syncArchiveIndexingButton.textContent = "現在の Favorite 状態と索引設定を同期";
}

async function previewArchiveIndexing() {
  resetSyncArm();
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
    resetSyncArm();
    return;
  }

  if (!syncArmed) {
    syncArmed = true;
    syncArchiveIndexingButton.textContent = `もう一度押して ${changes.length} 件を同期`;
    setArchiveStatus(
      `確認: ${changes.length} 件を Favorite 状態に合わせます。もう一度同期ボタンを押すと実行します。`,
    );
    return;
  }

  resetSyncArm();
  let completed = 0;
  let diagnosticText = "";

  for (const item of changes) {
    setArchiveStatus(`索引設定を同期・検証しています… ${completed}/${changes.length}`);
    const result = await messenger.glodaIndexing.setEnabled(
      item.accountId,
      item.path,
      item.desiredEnabled,
    );

    diagnosticText = formatDiagnostic(item, result);
    await saveDiagnostic(diagnosticText);
    archiveIndexingPreview.textContent =
      `${diagnosticText}\n\n` + archiveIndexingPreview.textContent;

    if (!result.applied) {
      setArchiveStatus(
        `ERROR: ${item.path} の索引設定が直後の確認で反映されませんでした。診断結果は保存済みです。`,
      );
      syncArchiveIndexingButton.disabled = true;
      return;
    }

    completed += 1;
  }

  await previewArchiveIndexing();
  const successText = `同期完了: ${completed} 件を変更しました。`;
  await saveDiagnostic(successText);
  setArchiveStatus(successText);
}

function handleArchiveAction(action) {
  return async () => {
    try {
      await action();
    } catch (error) {
      console.error("[WorkInBox archive indexing]", error);
      const diagnosticText = `ERROR: ${error.stack || error.message || error}`;
      await saveDiagnostic(diagnosticText);
      archiveIndexingPreview.textContent = diagnosticText;
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

document.addEventListener("DOMContentLoaded", handleArchiveAction(restoreDiagnostic));
