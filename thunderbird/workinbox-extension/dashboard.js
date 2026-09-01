const WIB_URL = "http://127.0.0.1:8000/";
const CACHE_KEY = "workinboxExtensionDashboardCache";
const HEALTH_INTERVAL_MS = 30000;
const REQUEST_TIMEOUT_MS = 3000;

let currentConfig = null;
let online = false;
let refreshing = false;
let invalidationTimer = null;
let syncPollTimer = null;

function element(selector) {
  return document.querySelector(selector);
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("ja-JP");
}

async function fetchJson(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(new URL(path, WIB_URL).href, {
      cache: "no-store",
      signal: controller.signal,
      ...options,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } finally {
    window.clearTimeout(timeout);
  }
}

async function storedCache() {
  const stored = await messenger.storage.local.get(CACHE_KEY);
  return stored[CACHE_KEY] || {};
}

async function updateStoredCache(updates) {
  const current = await storedCache();
  const next = { ...current, ...updates };
  await messenger.storage.local.set({ [CACHE_KEY]: next });
  return next;
}

function setConnection(state, detail, health = {}, syncStatus = {}) {
  const panel = element("#connection");
  panel.className = `connection ${state}`;
  const labels = {
    checking: "WIB接続を確認中",
    online: "WIB接続中",
    degraded: "WIBの一部が利用できません",
    offline: "WIB接続不可",
  };
  element("#connection-label").textContent = labels[state] || labels.offline;
  element("#connection-detail").textContent = detail;
  element("#wib-version").textContent = health.version || "-";
  element("#last-sync").textContent = formatDate(health.last_sync_at);
  element("#sync-state").textContent = syncStatus.running ? "同期実行中" : (state === "offline" ? "確認できません" : "停止中");
}

function setOnlineControls(isOnline, syncRunning = false) {
  element("#open-wib").disabled = !isOnline;
  element("#normal-sync").disabled = !isOnline || syncRunning;
  element("#normal-sync").textContent = syncRunning ? "通常同期を実行中…" : "通常同期";
  element("#open-tasks").disabled = false;
  document.querySelectorAll("[data-wib-path]").forEach((button) => {
    button.disabled = !isOnline;
  });
  element("#wib-only-note").textContent = isOnline
    ? "AI・SQLite・専用ワークフロー機能をWIB Webで利用できます。"
    : "WIBへ接続できないため、AI・SQLite・専用ワークフロー機能は利用できません。";
}

function renderDeadlineSummary(summary, cached = false) {
  document.querySelectorAll("[data-deadline-count]").forEach((node) => {
    const value = summary?.[node.dataset.deadlineCount];
    node.textContent = Number.isInteger(value) ? String(value) : "-";
  });
  element("#deadline-summary-source").textContent = `${cached ? "WIB最終取得値" : "WIB現在値"}（${formatDate(summary?.generated_at)}）`;
}

function renderCounts(result, cached = false) {
  const counts = result?.counts || {};
  document.querySelectorAll("[data-count]").forEach((node) => {
    const value = counts[node.dataset.count];
    node.textContent = Number.isInteger(value) ? String(value) : "-";
  });
  if (result?.lookbackDays) {
    element("#lookback-note").textContent = `未着眼件数は直近 ${result.lookbackDays} 日間を対象にしています。`;
  }
  const source = result?.accountName && result?.folderName
    ? `${result.accountName} / ${result.folderName}`
    : "対象mailbox";
  element("#count-source").textContent = `${source} — ${cached ? "保存済み集計" : "Thunderbird 現在値"}（${formatDate(result?.countedAt)}）`;
}

async function refreshCounts(config, cache) {
  if (!config?.imapTarget || !config?.lookbackDays) {
    if (cache?.counts) renderCounts(cache.counts, true);
    throw new Error("WIBへ一度接続し、対象mailbox設定を取得してください。");
  }

  const response = await messenger.runtime.sendMessage({
    type: "workinbox-dashboard-counts",
    imapTarget: config.imapTarget,
    lookbackDays: config.lookbackDays,
  });
  if (!response?.ok) {
    if (cache?.counts) renderCounts(cache.counts, true);
    throw new Error(response?.error || "Thunderbirdの件数を集計できませんでした。");
  }
  renderCounts(response, false);
  await updateStoredCache({ counts: response });
}

async function refreshAll(refreshMessageCounts = true) {
  if (refreshing) return;
  refreshing = true;
  element("#refresh").disabled = true;
  element("#error").hidden = true;
  setConnection("checking", "WIB APIへ接続しています…");

  const cache = await storedCache();
  let health = {};
  let syncStatus = {};
  try {
    const [healthResult, bootstrap, syncResult, deadlineSummary] = await Promise.all([
      fetchJson("/api/health"),
      fetchJson("/api/extension/bootstrap"),
      fetchJson("/api/sync-status").catch(() => ({})),
      fetchJson("/api/deadlines/summary"),
    ]);
    health = healthResult;
    syncStatus = syncResult;
    currentConfig = {
      imapTarget: bootstrap.imap_target,
      lookbackDays: bootstrap.new_mail_lookback_days,
    };
    online = health.status === "ok";
    const state = online ? "online" : "degraded";
    const now = new Date().toISOString();
    const updated = await updateStoredCache({ config: currentConfig, health, deadlineSummary, lastConnectedAt: now });
    renderDeadlineSummary(deadlineSummary, false);
    element("#last-connected").textContent = formatDate(updated.lastConnectedAt);
    setConnection(state, online ? "WIB APIを利用できます。" : "WIBは応答していますが一部機能を利用できません。", health, syncStatus);
  } catch (error) {
    online = false;
    currentConfig = cache.config || null;
    health = cache.health || {};
    if (cache.deadlineSummary) renderDeadlineSummary(cache.deadlineSummary, true);
    element("#last-connected").textContent = formatDate(cache.lastConnectedAt);
    setConnection("offline", `保存済み設定でThunderbird通常作業を継続します。${error.message ? ` (${error.message})` : ""}`, health, {});
  }

  const syncRunning = Boolean(syncStatus.running);
  setOnlineControls(online, syncRunning);
  if (refreshMessageCounts) {
    try {
      await refreshCounts(currentConfig, cache);
    } catch (error) {
      element("#error").textContent = error.message || String(error);
      element("#error").hidden = false;
    }
  }
  element("#count-progress").hidden = true;
  element("#refresh").disabled = false;
  refreshing = false;
  window.clearTimeout(syncPollTimer);
  if (online && syncRunning) {
    syncPollTimer = window.setTimeout(() => void refreshAll(false), 2000);
  }
}

async function startNormalSync() {
  if (!online) throw new Error("WIBへ接続できないため通常同期を開始できません。");
  element("#normal-sync").disabled = true;
  element("#normal-sync").textContent = "通常同期を開始中…";
  try {
    const response = await fetchJson("/api/sync", { method: "POST" });
    if (!response.ok) {
      throw new Error(response.error || "通常同期を開始できませんでした。");
    }
    await refreshAll(false);
  } catch (error) {
    setOnlineControls(online, false);
    throw error;
  }
}

async function openWorkView(button) {
  if (!currentConfig?.imapTarget) {
    throw new Error("対象mailbox設定がありません。WIBへ一度接続してください。");
  }
  button.disabled = true;
  try {
    const response = await messenger.runtime.sendMessage({
      type: "workinbox-open-work-view",
      view: button.dataset.workView,
      imapTarget: currentConfig.imapTarget,
      lookbackDays: button.dataset.workView.startsWith("unattended")
        ? currentConfig.lookbackDays
        : null,
    });
    if (!response?.ok) throw new Error(response?.error || "作業ビューを開けませんでした。");
  } finally {
    button.disabled = false;
  }
}

async function openWib(path = "/") {
  if (!online) throw new Error("WIBへ接続できません。");
  await messenger.tabs.create({
    url: new URL(path, WIB_URL).href,
    active: true,
    linkHandler: "balanced",
  });
}

async function openTasks() {
  const response = await messenger.runtime.sendMessage({ type: "workinbox-open-tasks" });
  if (!response?.ok) throw new Error(response?.error || "ThunderbirdのToDoを開けませんでした。");
}

document.addEventListener("click", (event) => {
  const workView = event.target.closest("[data-work-view]");
  const wibPath = event.target.closest("[data-wib-path]");
  let operation = null;
  if (workView) operation = openWorkView(workView);
  else if (wibPath) operation = openWib(wibPath.dataset.wibPath);
  else if (event.target.closest("#open-wib")) operation = openWib();
  else if (event.target.closest("#normal-sync")) operation = startNormalSync();
  else if (event.target.closest("#open-tasks")) operation = openTasks();
  else if (event.target.closest("#refresh")) operation = refreshAll();
  if (operation) {
    void operation.catch((error) => {
      element("#error").textContent = error.message || String(error);
      element("#error").hidden = false;
    });
  }
});

messenger.runtime.onMessage.addListener((message) => {
  if (message?.type === "workinbox-dashboard-progress") {
    element("#count-progress").hidden = false;
    element("#count-progress").textContent = `集計中: ${message.current}件`;
  }
  if (message?.type === "workinbox-dashboard-invalidated") {
    window.clearTimeout(invalidationTimer);
    invalidationTimer = window.setTimeout(() => void refreshAll(), 1200);
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) void refreshAll();
});
document.addEventListener("DOMContentLoaded", () => void refreshAll());
window.setInterval(() => void refreshAll(false), HEALTH_INTERVAL_MS);
