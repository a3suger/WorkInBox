const SNAPSHOT_KEY = "preWorkInBoxTagSnapshot";
const SNAPSHOT_SCHEMA = "workinbox-thunderbird-tags/v1";

// Thunderbird sorts tags by ordinal (falling back to the tag key).
// Numeric shortcuts are reserved for tags that the user may intentionally
// apply as workflow/organization choices in Thunderbird:
// 1-2 dedicated workflow, 3-5 normal workflow, 6 organizing.
const WIB_TAGS = Object.freeze([
  { key: "wib-deadline", tag: "締切あり", color: "#D32F2F", ordinal: "!01" },
  { key: "wib-schedule", tag: "スケジュール調整", color: "#F57C00", ordinal: "!02" },
  { key: "wib-answer", tag: "返信必要", color: "#1976D2", ordinal: "!03" },
  { key: "wib-review", tag: "見る・検討", color: "#039BE5", ordinal: "!04" },
  { key: "wib-watch", tag: "注目", color: "#7B1FA2", ordinal: "!05" },
  { key: "wib-bulk", tag: "一括処理", color: "#424242", ordinal: "!06" },
  { key: "wib-pending", tag: "判定保留", color: "#757575" },
  { key: "wib-deadline-done", tag: "締切登録済み", color: "#8E2424" },
  { key: "wib-schedule-done", tag: "スケジュール対応済み", color: "#A65300" },
  { key: "wib-waiting-reply", tag: "返信待ち", color: "#388E3C" },
  { key: "wib-waiting-action", tag: "対応待ち", color: "#7CB342" },
  { key: "wib-action-ready", tag: "対応あり", color: "#558B2F" },
  { key: "wib-requested", tag: "依頼済み", color: "#795548" },
]);

const WIB_KEYS = new Set(WIB_TAGS.map((item) => item.key));
const LEGACY_WIB_KEYS = new Set(["wib-important", "wib-batch"]);
const MANAGED_WIB_KEYS = new Set([...WIB_KEYS, ...LEGACY_WIB_KEYS]);

const statusElement = document.querySelector("#status");
const currentTagsElement = document.querySelector("#current-tags");
const createSnapshotButton = document.querySelector("#create-snapshot");
const exportSnapshotButton = document.querySelector("#export-snapshot");
const provisionTagsButton = document.querySelector("#provision-tags");
const restoreSnapshotButton = document.querySelector("#restore-snapshot");
const restoreFileInput = document.querySelector("#restore-file");

function setStatus(message) {
  statusElement.textContent = message;
}

function copyTag(tag) {
  return {
    key: tag.key,
    tag: tag.tag,
    color: tag.color,
    ordinal: tag.ordinal || "",
  };
}

async function getStoredSnapshot() {
  const stored = await messenger.storage.local.get(SNAPSHOT_KEY);
  return stored[SNAPSHOT_KEY] || null;
}

async function getThunderbirdVersion() {
  try {
    const info = await messenger.runtime.getBrowserInfo();
    return info.version || null;
  } catch (_error) {
    return null;
  }
}

function validateSnapshot(snapshot) {
  if (!snapshot || snapshot.schema !== SNAPSHOT_SCHEMA || !Array.isArray(snapshot.tags)) {
    throw new Error("WorkInBox のタグバックアップJSONではありません。");
  }

  for (const tag of snapshot.tags) {
    if (
      !tag ||
      typeof tag.key !== "string" ||
      typeof tag.tag !== "string" ||
      typeof tag.color !== "string"
    ) {
      throw new Error("タグバックアップJSONの形式が正しくありません。");
    }
  }

  return snapshot;
}

async function refresh() {
  const [snapshot, tags] = await Promise.all([
    getStoredSnapshot(),
    messenger.messages.tags.list(),
  ]);

  exportSnapshotButton.disabled = !snapshot;
  restoreSnapshotButton.disabled = !snapshot;
  provisionTagsButton.disabled = !snapshot;
  createSnapshotButton.disabled = Boolean(snapshot);

  currentTagsElement.textContent = JSON.stringify(tags.map(copyTag), null, 2);

  const registeredWibCount = tags.filter((tag) => WIB_KEYS.has(tag.key)).length;
  if (snapshot) {
    setStatus(
      `タグスナップショット保存済み。WIBタグ ${registeredWibCount}/${WIB_TAGS.length} 個を確認しました。`,
    );
  } else if (tags.some((tag) => MANAGED_WIB_KEYS.has(tag.key))) {
    setStatus(
      "タグスナップショットは未保存です。既存 WIB 環境のため、現在のタグ状態を移行前スナップショットとして保存してから新しい WIB タグへ移行します。",
    );
  } else {
    setStatus("導入前スナップショットはまだ保存されていません。");
  }
}

async function createSnapshot() {
  if (await getStoredSnapshot()) {
    throw new Error("タグスナップショットは既に保存されています。自動上書きはしません。");
  }

  const tags = await messenger.messages.tags.list();
  const existingWibTags = tags.filter((tag) => MANAGED_WIB_KEYS.has(tag.key));
  const snapshot = {
    schema: SNAPSHOT_SCHEMA,
    createdAt: new Date().toISOString(),
    thunderbirdVersion: await getThunderbirdVersion(),
    tags: tags.map(copyTag),
  };

  await messenger.storage.local.set({ [SNAPSHOT_KEY]: snapshot });
  if (existingWibTags.length > 0) {
    setStatus(
      `現在のタグ状態を移行前スナップショットとして保存しました（WIB系 ${existingWibTags.length} 個 / 全 ${snapshot.tags.length} 個）。`,
    );
  } else {
    setStatus(`導入前スナップショットを保存しました（タグ ${snapshot.tags.length} 個）。`);
  }
  await refresh();
}

async function exportSnapshot() {
  const snapshot = await getStoredSnapshot();
  if (!snapshot) {
    throw new Error("書き出せるタグスナップショットがありません。");
  }

  const json = JSON.stringify(snapshot, null, 2) + "\n";
  const blob = new Blob([json], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  try {
    await messenger.downloads.download({
      url,
      filename: "thunderbird-tags-before-workinbox.json",
      saveAs: true,
    });
    setStatus("タグスナップショットのJSON書き出しを開始しました。");
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
}

async function ensureWibTag(definition) {
  let tags = await messenger.messages.tags.list();
  let existing = tags.find((tag) => tag.key === definition.key);

  if (!existing) {
    await messenger.messages.tags.create(
      definition.key,
      definition.tag,
      definition.color,
    );
    tags = await messenger.messages.tags.list();
    existing = tags.find((tag) => tag.key === definition.key);
  }

  if (!existing) {
    throw new Error(`${definition.key} の作成後にタグ定義を取得できませんでした。`);
  }

  const properties = {};
  if (existing.tag !== definition.tag) {
    properties.tag = definition.tag;
  }
  if (existing.color !== definition.color.toUpperCase()) {
    properties.color = definition.color;
  }
  if ((definition.ordinal || "") !== (existing.ordinal || "")) {
    properties.ordinal = definition.ordinal || "";
  }

  if (Object.keys(properties).length > 0) {
    await messenger.messages.tags.update(definition.key, properties);
  }
}

async function provisionTags() {
  if (!(await getStoredSnapshot())) {
    throw new Error("WIBタグ登録の前にタグスナップショットを保存してください。");
  }

  for (const definition of WIB_TAGS) {
    await ensureWibTag(definition);
  }

  // Remove only obsolete Thunderbird tag definitions. Existing IMAP keywords
  // on messages are deliberately left untouched so historical data is not
  // destructively rewritten during this migration.
  const currentTags = await messenger.messages.tags.list();
  for (const tag of currentTags) {
    if (LEGACY_WIB_KEYS.has(tag.key)) {
      await messenger.messages.tags.delete(tag.key);
    }
  }

  setStatus(
    `${WIB_TAGS.length}個のWIBタグを登録し、専用/通常ワークフローと一括処理を数字キー 1〜6 に配置しました。`,
  );
  await refresh();
}

async function restoreTag(tag, currentByKey) {
  const existing = currentByKey.get(tag.key);
  const properties = {
    tag: tag.tag,
    color: tag.color,
    ordinal: tag.ordinal || "",
  };

  if (existing) {
    await messenger.messages.tags.update(tag.key, properties);
  } else {
    await messenger.messages.tags.create(tag.key, tag.tag, tag.color);
    await messenger.messages.tags.update(tag.key, { ordinal: tag.ordinal || "" });
  }
}

async function restoreSnapshot(snapshot, sourceLabel) {
  validateSnapshot(snapshot);

  const confirmed = window.confirm(
    `${sourceLabel}から Thunderbird のタグ定義を復元します。\n\n` +
      "現在のWIBタグ定義を削除し、バックアップに記録されたタグの表示名・色・並び順を戻します。\n" +
      "メール上の wib-* IMAP keyword は削除しません。\n\n続けますか？",
  );
  if (!confirmed) {
    return;
  }

  let current = await messenger.messages.tags.list();
  for (const tag of current) {
    if (MANAGED_WIB_KEYS.has(tag.key)) {
      await messenger.messages.tags.delete(tag.key);
    }
  }

  current = await messenger.messages.tags.list();
  const currentByKey = new Map(current.map((tag) => [tag.key, tag]));

  for (const tag of snapshot.tags) {
    await restoreTag(tag, currentByKey);
  }

  setStatus(`${sourceLabel}からタグ定義を復元しました。`);
  await refresh();
}

async function restoreStoredSnapshot() {
  const snapshot = await getStoredSnapshot();
  if (!snapshot) {
    throw new Error("保存済みのタグスナップショットがありません。");
  }
  await restoreSnapshot(snapshot, "保存済みスナップショット");
}

async function restoreFromFile(file) {
  if (!file) {
    return;
  }

  const text = await file.text();
  let snapshot;
  try {
    snapshot = JSON.parse(text);
  } catch (_error) {
    throw new Error("選択したファイルは有効なJSONではありません。");
  }
  await restoreSnapshot(snapshot, file.name);
}

function handle(action) {
  return async (...args) => {
    try {
      await action(...args);
    } catch (error) {
      console.error("[WorkInBox connector]", error);
      setStatus(`ERROR: ${error.message || error}`);
    }
  };
}

createSnapshotButton.addEventListener("click", handle(createSnapshot));
exportSnapshotButton.addEventListener("click", handle(exportSnapshot));
provisionTagsButton.addEventListener("click", handle(provisionTags));
restoreSnapshotButton.addEventListener("click", handle(restoreStoredSnapshot));
restoreFileInput.addEventListener(
  "change",
  handle(async (event) => {
    await restoreFromFile(event.target.files?.[0]);
    event.target.value = "";
  }),
);

document.addEventListener("DOMContentLoaded", handle(refresh));
