const WORKINBOX_ORIGIN_HEADER = "X-WorkInBox-Origin-Message-ID";
const WORKINBOX_ACTION_HEADER = "X-WorkInBox-Action";
const WORKINBOX_REQUEST_ID_HEADER = "X-WorkInBox-Request-ID";
const RECORD_ACTION = "create-record";
const REQUESTED_TAG = "wib-requested";
const BULK_TAG = "wib-bulk";
const LEGACY_BULK_TAG = "wib-batch";
const BULK_TAG_DEFINITION = {
  key: BULK_TAG,
  tag: "一括処理",
  color: "#424242",
};
const NORMAL_WORKFLOW_TAGS = new Set(["wib-answer", "wib-review", "wib-watch"]);
const NORMAL_SELECTION_TAGS = new Set([...NORMAL_WORKFLOW_TAGS, "wib-pending"]);
const OPEN_WORKFLOW_TAGS = new Set([
  ...NORMAL_WORKFLOW_TAGS,
  "wib-deadline",
  "wib-schedule",
  "wib-pending",
  "wib-waiting-reply",
  "wib-waiting-action",
  "wib-action-ready",
]);
const DASHBOARD_SPACE_BUTTON_ID = "workinbox_dashboard";
const DASHBOARD_SPACE_BUTTON_PROPERTIES = Object.freeze({
  url: "dashboard.html",
  title: "WorkInBox",
  defaultIcons: {
    16: "icons/workinbox.svg",
    32: "icons/workinbox.svg",
  },
});

const WORK_VIEWS = {
  unattended: { label: "未着眼", unattended: true, unread: false },
  "unattended-unread": { label: "未着眼・未読", unattended: true, unread: true },
  "unattended-read": { label: "未着眼・既読", unattended: true, unread: false },
  answer: { tagKey: "wib-answer", label: "返信必要" },
  deadline: {
    tagKey: "wib-deadline",
    label: "締切あり",
    excludedTags: ["wib-deadline-done"],
  },
  schedule: {
    tagKey: "wib-schedule",
    label: "スケジュール調整",
    excludedTags: [REQUESTED_TAG, "wib-schedule-done"],
  },
  pending: { tagKey: "wib-pending", label: "判定保留" },
  review: { tagKey: "wib-review", label: "見る・検討" },
  watch: { tagKey: "wib-watch", label: "注目" },
  waitingReply: { tagKey: "wib-waiting-reply", label: "返信待ち" },
  waitingAction: { tagKey: "wib-waiting-action", label: "対応待ち" },
  actionReady: { tagKey: "wib-action-ready", label: "対応あり" },
  bulkArchive: { label: "整理済み・アーカイブ待ち", bulkArchive: true },
};

let workViewTabId = null;
let workViewTabTitle = null;
let dashboardTabId = null;
let dedicatedWorkflowTabId = null;
const pendingSupportRequests = new Map();
const pendingMenuComposes = new Map();

async function registerDashboardSpaceButton() {
  try {
    return await messenger.spacesToolbar.addButton(
      DASHBOARD_SPACE_BUTTON_ID,
      DASHBOARD_SPACE_BUTTON_PROPERTIES,
    );
  } catch (error) {
    // The button can survive a background-script reload. Keep its properties
    // current instead of treating an existing button as a startup failure.
    try {
      await messenger.spacesToolbar.updateButton(
        DASHBOARD_SPACE_BUTTON_ID,
        DASHBOARD_SPACE_BUTTON_PROPERTIES,
      );
      return null;
    } catch (_updateError) {
      throw error;
    }
  }
}

const dashboardSpaceReady = registerDashboardSpaceButton().catch((error) => {
  console.error("[WorkInBox dashboard] failed to register spaces toolbar button", error);
  return null;
});

const DASHBOARD_TAG_COUNTS = Object.freeze({
  answer: "wib-answer",
  review: "wib-review",
  watch: "wib-watch",
  deadline: "wib-deadline",
  schedule: "wib-schedule",
  pending: "wib-pending",
  waitingReply: "wib-waiting-reply",
  waitingAction: "wib-waiting-action",
  actionReady: "wib-action-ready",
});
const DASHBOARD_CACHE_KEY = "workinboxExtensionDashboardCache";

function messageIdCandidates(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return [];
  }

  const withoutBrackets = raw.replace(/^<|>$/g, "");
  return [...new Set([raw, withoutBrackets].filter(Boolean))];
}

async function findMessageByHeaderMessageId(messageId) {
  for (const candidate of messageIdCandidates(messageId)) {
    const result = await messenger.messages.query({
      headerMessageId: candidate,
      messagesPerPage: 10,
    });
    if (result.messages.length > 0) {
      return result.messages[0];
    }
  }

  return null;
}

async function openMessageByHeaderMessageId(messageId) {
  const message = await findMessageByHeaderMessageId(messageId);
  if (!message) {
    throw new Error(`Message-ID ${messageId} のメールを Thunderbird で見つけられませんでした。`);
  }

  await messenger.messageDisplay.open({
    messageId: message.id,
    location: "tab",
    active: true,
  });

  return {
    ok: true,
    subject: message.subject || "",
    headerMessageId: message.headerMessageId || messageId,
  };
}

function findSpecialFolder(folder, specialUse) {
  if (!folder) {
    return null;
  }

  const specialUses = Array.isArray(folder.specialUse) ? folder.specialUse : [];
  if (specialUses.includes(specialUse) || folder.type === specialUse) {
    return folder;
  }

  for (const child of folder.subFolders || []) {
    const found = findSpecialFolder(child, specialUse);
    if (found) {
      return found;
    }
  }

  return null;
}

function normalizeMailboxPath(value) {
  return String(value || "")
    .trim()
    .replace(/^\/+/, "")
    .replace(/\/+$/, "");
}

function findFolderByMailboxPath(folder, mailbox) {
  if (!folder) {
    return null;
  }

  const expected = normalizeMailboxPath(mailbox);
  const folderPath = normalizeMailboxPath(folder.path);
  if (folderPath === expected) {
    return folder;
  }

  if (!expected.includes("/") && String(folder.name || "") === expected) {
    return folder;
  }

  for (const child of folder.subFolders || []) {
    const found = findFolderByMailboxPath(child, expected);
    if (found) {
      return found;
    }
  }

  return null;
}

function normalizeHost(value) {
  return String(value || "").trim().toLowerCase().replace(/\.$/, "");
}

function normalizeUsername(value) {
  return String(value || "").trim().toLowerCase();
}

function usernameLocalPart(value) {
  const normalized = normalizeUsername(value);
  const at = normalized.indexOf("@");
  return at >= 0 ? normalized.slice(0, at) : normalized;
}

function usernamesEquivalent(left, right) {
  const normalizedLeft = normalizeUsername(left);
  const normalizedRight = normalizeUsername(right);
  if (normalizedLeft === normalizedRight) {
    return true;
  }

  return (
    usernameLocalPart(normalizedLeft) === usernameLocalPart(normalizedRight)
    && (normalizedLeft.includes("@") || normalizedRight.includes("@"))
  );
}

async function resolveImapAccount(imapTarget) {
  const expectedHost = normalizeHost(imapTarget?.host);
  const expectedUsername = normalizeUsername(imapTarget?.username);
  const expectedPort = Number(imapTarget?.port);

  if (!expectedHost || !expectedUsername || !Number.isInteger(expectedPort)) {
    throw new Error("WIB Web から渡された IMAP 対象設定が不正です。");
  }

  const accounts = await messenger.accounts.list();
  const matches = [];
  const observed = [];

  for (const account of accounts) {
    if (account.type !== "imap") {
      continue;
    }

    let serverInfo;
    try {
      serverInfo = await messenger.imapAccounts.getServerInfo(account.id);
    } catch (error) {
      console.warn("[WorkInBox bridge] failed to inspect Thunderbird IMAP account", account.id, error);
      observed.push(`${account.name || account.id}: server情報取得失敗`);
      continue;
    }

    observed.push(
      `${account.name || account.id}: ${serverInfo?.username || "?"}@${serverInfo?.host || "?"}:${serverInfo?.port ?? "?"}`,
    );

    if (normalizeHost(serverInfo?.host) !== expectedHost) {
      continue;
    }
    if (Number(serverInfo?.port) !== expectedPort) {
      continue;
    }
    if (!usernamesEquivalent(serverInfo?.username, expectedUsername)) {
      continue;
    }
    matches.push(account);
  }

  if (matches.length === 0) {
    const observedText = observed.length > 0 ? observed.join(" / ") : "IMAPアカウントなし";
    throw new Error(
      `Thunderbird に WIB 設定と一致する IMAP アカウントがありません。WIB=${expectedUsername}@${expectedHost}:${expectedPort} / Thunderbird=${observedText}`,
    );
  }
  if (matches.length > 1) {
    const names = matches.map((account) => account.name || account.id).join(", ");
    throw new Error(
      `Thunderbird に WIB 設定と一致する IMAP アカウントが複数あります: ${names}`,
    );
  }

  return messenger.accounts.get(matches[0].id, true);
}

async function resolveWorkViewMailbox(imapTarget) {
  const mailboxName = String(imapTarget?.mailbox || "").trim();
  if (!mailboxName) {
    throw new Error("WIB Web から渡された mailbox 設定が空です。");
  }

  const account = await resolveImapAccount(imapTarget);
  let mailbox;
  if (mailboxName.toUpperCase() === "INBOX") {
    mailbox = findSpecialFolder(account.rootFolder, "inbox");
  } else {
    mailbox = findFolderByMailboxPath(account.rootFolder, mailboxName);
  }

  if (!mailbox) {
    throw new Error(
      `Thunderbird アカウント「${account.name || account.id}」で WIB 設定の mailbox「${mailboxName}」を見つけられませんでした。`,
    );
  }

  return {
    account,
    mailbox,
  };
}

async function getExistingWorkViewTab() {
  if (workViewTabId === null) {
    return null;
  }

  try {
    return await messenger.mailTabs.get(workViewTabId);
  } catch (_error) {
    workViewTabId = null;
    return null;
  }
}

async function resolveDedicatedWorkViewTab(mailbox) {
  const existing = await getExistingWorkViewTab();
  if (existing) {
    await messenger.mailTabs.update(existing.id, {
      displayedFolder: mailbox,
    });
    return messenger.mailTabs.get(existing.id);
  }

  const created = await messenger.mailTabs.create({
    displayedFolder: mailbox,
  });
  workViewTabId = created.id;
  return created;
}

async function applyWorkView(mailTab, view, lookbackDays) {
  if (view.unattended) {
    await messenger.mailTabs.setQuickFilter(mailTab.id, { show: false });
    await messenger.mailViews.ensureUnattendedView(mailTab.id, lookbackDays);
    if (view.unread) {
      await messenger.mailTabs.setQuickFilter(mailTab.id, {
        show: true,
        unread: true,
      });
    }
  } else if (view.bulkArchive) {
    await messenger.mailViews.ensureBulkArchiveView(mailTab.id);
    await messenger.mailTabs.setQuickFilter(mailTab.id, {
      show: true,
      tags: {
        mode: "any",
        tags: {
          [BULK_TAG]: true,
          [LEGACY_BULK_TAG]: true,
        },
      },
    });
  } else if (view.excludedTags) {
    await messenger.mailTabs.setQuickFilter(mailTab.id, { show: false });
    await messenger.mailViews.ensureWorkflowView(
      mailTab.id,
      view.label,
      view.tagKey,
      view.excludedTags,
    );
  } else {
    await messenger.mailViews.resetView(mailTab.id);
    await messenger.mailTabs.setQuickFilter(mailTab.id, {
      show: true,
      flagged: true,
      tags: {
        mode: "all",
        tags: {
          [view.tagKey]: true,
        },
      },
    });
  }
}

async function openWorkView(viewName, imapTarget, lookbackDays = null) {
  const view = WORK_VIEWS[viewName];
  if (!view) {
    throw new Error(`Unknown WorkInBox work view: ${viewName}`);
  }

  const { account, mailbox } = await resolveWorkViewMailbox(imapTarget);
  let mailTab = await resolveDedicatedWorkViewTab(mailbox);

  try {
    await applyWorkView(mailTab, view, lookbackDays);
  } catch (error) {
    // Opening a message can leave the reused tab without a three-pane view.
    // Replace only the dedicated WIB tab and retry with a fresh mail tab.
    console.warn("[WorkInBox bridge] rebuilding unavailable work-view tab", error);
    try {
      await messenger.tabs.remove(mailTab.id);
    } catch (_removeError) {
      // The tab may already have disappeared while recovering.
    }
    workViewTabId = null;
    workViewTabTitle = null;
    mailTab = await resolveDedicatedWorkViewTab(mailbox);
    await applyWorkView(mailTab, view, lookbackDays);
  }

  await messenger.tabs.update(mailTab.id, { active: true });

  const requestedTabTitle = `WIB:${view.label}`;
  workViewTabTitle = requestedTabTitle;
  const titleResult = await messenger.tabTitle.setTitle(mailTab.id, requestedTabTitle);
  if (!titleResult?.applied) {
    console.warn("[WorkInBox bridge] tab title was not applied as requested", titleResult);
  }

  return {
    ok: true,
    view: viewName,
    viewLabel: view.label,
    tagKey: view.tagKey || "",
    accountName: account.name || account.id,
    folderName: mailbox.name || imapTarget.mailbox,
    tabTitle: titleResult?.appliedTitle || requestedTabTitle,
    tabId: mailTab.id,
    dedicatedTab: true,
    unattended: Boolean(view.unattended),
    lookbackDays: view.unattended ? lookbackDays : null,
    unreadQuickFilter: Boolean(view.unattended && view.unread),
  };
}

async function restoreWorkViewTabTitle(tabId) {
  if (tabId !== workViewTabId || !workViewTabTitle) {
    return;
  }
  const result = await messenger.tabTitle.setTitle(tabId, workViewTabTitle);
  if (!result?.applied) {
    console.warn("[WorkInBox bridge] failed to restore work-view tab title", result);
  }
}

async function getExistingDashboardTab() {
  if (dashboardTabId === null) {
    return null;
  }
  try {
    return await messenger.tabs.get(dashboardTabId);
  } catch (_error) {
    dashboardTabId = null;
    return null;
  }
}

async function openDashboard() {
  await dashboardSpaceReady;
  try {
    const spaceTab = await messenger.spacesToolbar.clickButton(
      DASHBOARD_SPACE_BUTTON_ID,
    );
    dashboardTabId = spaceTab.id;
    return { ok: true, tabId: spaceTab.id, reused: true, space: true };
  } catch (error) {
    console.warn("[WorkInBox dashboard] spaces toolbar button is unavailable", error);
  }

  const existing = await getExistingDashboardTab();
  if (existing) {
    await messenger.tabs.update(existing.id, { active: true });
    return { ok: true, tabId: existing.id, reused: true };
  }

  const created = await messenger.tabs.create({
    url: messenger.runtime.getURL("dashboard.html"),
    active: true,
  });
  dashboardTabId = created.id;
  return { ok: true, tabId: created.id, reused: false };
}

async function openTasksSpace() {
  const existing = await messenger.tabs.query({ type: "tasks" });
  if (existing.length > 0) {
    await messenger.tabs.update(existing[0].id, { active: true });
    return { ok: true, tabId: existing[0].id, reused: true };
  }
  const result = await messenger.tasksSpace.open();
  return { ok: Boolean(result?.opened), reused: false };
}

async function openDedicatedWorkflow(kind, messageId, thunderbirdMessageId) {
  const definitions = {
    deadline: { tagKey: "wib-deadline" },
    schedule: { tagKey: "wib-schedule" },
  };
  const definition = definitions[kind];
  if (!definition) {
    throw new Error(`Unknown dedicated workflow: ${kind}`);
  }

  const launcherUrl = new URL(messenger.runtime.getURL("workflow_launcher.html"));
  launcherUrl.searchParams.set("kind", kind);
  launcherUrl.searchParams.set("message_id", messageId);
  if (Number.isInteger(thunderbirdMessageId)) {
    launcherUrl.searchParams.set("thunderbird_message_id", String(thunderbirdMessageId));
  }

  if (dedicatedWorkflowTabId !== null) {
    try {
      const tab = await messenger.tabs.update(dedicatedWorkflowTabId, {
        url: launcherUrl.href,
        active: true,
      });
      return { ok: true, tabId: tab.id, reused: true };
    } catch (_error) {
      dedicatedWorkflowTabId = null;
    }
  }

  const tab = await messenger.tabs.create({ url: launcherUrl.href, active: true });
  dedicatedWorkflowTabId = tab.id;
  return { ok: true, tabId: tab.id, reused: false };
}

async function resolveDisplayedMessage(thunderbirdMessageId, messageId) {
  if (Number.isInteger(thunderbirdMessageId)) {
    try {
      return await messenger.messages.get(thunderbirdMessageId);
    } catch (_error) {
      // Fall back to Message-ID lookup if Thunderbird no longer has this row.
    }
  }
  return findMessageByHeaderMessageId(messageId);
}

async function prepareDedicatedWorkflow(kind, messageId, thunderbirdMessageId) {
  const tagKeys = {
    deadline: "wib-deadline",
    schedule: "wib-schedule",
  };
  const tagKey = tagKeys[kind];
  if (!tagKey) {
    throw new Error(`Unknown dedicated workflow: ${kind}`);
  }
  const message = await resolveDisplayedMessage(thunderbirdMessageId, messageId);
  if (!message) {
    throw new Error(`Message-ID ${messageId} のメールを Thunderbird で見つけられませんでした。`);
  }
  await addTag(message, tagKey, { flagged: true });
  return { ok: true };
}

async function dismissDedicatedWorkflow(kind, messageId, thunderbirdMessageId) {
  const tagKeys = {
    deadline: "wib-deadline",
    schedule: "wib-schedule",
  };
  const removedTagKey = tagKeys[kind];
  if (!removedTagKey) {
    throw new Error(`Unknown dedicated workflow: ${kind}`);
  }
  const message = await resolveDisplayedMessage(thunderbirdMessageId, messageId);
  if (!message) {
    throw new Error(`Message-ID ${messageId} のメールを Thunderbird で見つけられませんでした。`);
  }

  const remainingTags = (message.tags || []).filter((tag) => tag !== removedTagKey);
  const hasOtherOpenWorkflow = remainingTags.some((tag) => OPEN_WORKFLOW_TAGS.has(tag));
  if (hasOtherOpenWorkflow) {
    await messenger.messages.update(message.id, { tags: remainingTags });
    return { ok: true, completed: false };
  }

  const bulkTagKey = await resolveBulkTagKey();
  const completedTags = [...new Set([...remainingTags, bulkTagKey])];
  await messenger.messages.update(message.id, {
    tags: completedTags,
    flagged: false,
  });
  return { ok: true, completed: true };
}

function emptyDashboardCounts() {
  return {
    unattendedTotal: 0,
    unattendedUnread: 0,
    unattendedRead: 0,
    answer: 0,
    review: 0,
    watch: 0,
    deadline: 0,
    schedule: 0,
    pending: 0,
    waitingReply: 0,
    waitingAction: 0,
    actionReady: 0,
    bulkArchive: 0,
  };
}

function dashboardSince(lookbackDays) {
  const since = new Date();
  since.setHours(0, 0, 0, 0);
  since.setDate(since.getDate() - (lookbackDays - 1));
  return since;
}

function countDashboardMessage(counts, message, since) {
  const tags = new Set(message.tags || []);
  const flagged = Boolean(message.flagged);
  const read = Boolean(message.read);
  const received = message.date instanceof Date ? message.date : new Date(message.date);
  const recent = !Number.isNaN(received.getTime()) && received >= since;
  const bulk = tags.has(BULK_TAG) || tags.has(LEGACY_BULK_TAG);

  if (recent && !flagged && !bulk) {
    counts.unattendedTotal += 1;
    counts[read ? "unattendedRead" : "unattendedUnread"] += 1;
  }

  if (!flagged) {
    return;
  }
  for (const [countName, tagKey] of Object.entries(DASHBOARD_TAG_COUNTS)) {
    if (countName === "deadline" && tags.has("wib-deadline-done")) {
      continue;
    }
    if (
      countName === "schedule"
      && (tags.has(REQUESTED_TAG) || tags.has("wib-schedule-done"))
    ) {
      continue;
    }
    if (tags.has(tagKey)) {
      counts[countName] += 1;
    }
  }
}

async function scanDashboardQuery(queryInfo, onMessage, progress) {
  let page = await messenger.messages.query({
    ...queryInfo,
    messagesPerPage: 100,
  });

  while (page) {
    for (const message of page.messages || []) {
      onMessage(message);
      progress.current += 1;
    }
    void messenger.runtime.sendMessage({
      type: "workinbox-dashboard-progress",
      current: progress.current,
    }).catch(() => undefined);
    if (!page.id) {
      break;
    }
    page = await messenger.messages.continueList(page.id);
  }
}

async function dashboardCounts(imapTarget, rawLookbackDays) {
  const lookbackDays = Number(rawLookbackDays);
  if (!Number.isInteger(lookbackDays) || lookbackDays < 1) {
    throw new Error("WIBのnew_mail_lookback_daysが不正です。");
  }

  const { account, mailbox } = await resolveWorkViewMailbox(imapTarget);
  const counts = emptyDashboardCounts();
  const since = dashboardSince(lookbackDays);
  const progress = { current: 0 };
  const countMessage = (message) => countDashboardMessage(counts, message, since);

  // The lookback applies only to unattended counts. Let Thunderbird filter by
  // date and star state before returning messages to the extension.
  await scanDashboardQuery({
    folderId: mailbox.id,
    fromDate: since,
    flagged: false,
  }, countMessage, progress);

  // Completed bulk-processing mail is periodically reviewed and archived.
  // Keep this mailbox-wide and let Thunderbird filter before returning rows.
  await scanDashboardQuery({
    folderId: mailbox.id,
    flagged: false,
    tags: {
      mode: "any",
      tags: {
        [BULK_TAG]: true,
        [LEGACY_BULK_TAG]: true,
      },
    },
  }, () => {
    counts.bulkArchive += 1;
  }, progress);

  // Workflow counts cover the entire mailbox, but Thunderbird returns only
  // starred messages carrying at least one dashboard tag.
  await scanDashboardQuery({
    folderId: mailbox.id,
    flagged: true,
    tags: {
      mode: "any",
      tags: Object.fromEntries(
        Object.values(DASHBOARD_TAG_COUNTS).map((tagKey) => [tagKey, true]),
      ),
    },
  }, countMessage, progress);

  const result = {
    ok: true,
    counts,
    lookbackDays,
    countedAt: new Date().toISOString(),
    accountName: account.name || account.id,
    folderName: mailbox.name || imapTarget.mailbox,
    processed: progress.current,
  };
  const stored = await messenger.storage.local.get(DASHBOARD_CACHE_KEY);
  await messenger.storage.local.set({
    [DASHBOARD_CACHE_KEY]: {
      ...(stored[DASHBOARD_CACHE_KEY] || {}),
      config: { imapTarget, lookbackDays },
      counts: result,
    },
  });
  return result;
}

function notifyDashboardInvalidated() {
  void messenger.runtime.sendMessage({
    type: "workinbox-dashboard-invalidated",
  }).catch(() => undefined);
}

for (const eventName of ["onUpdated", "onNewMailReceived", "onMoved", "onCopied", "onDeleted"]) {
  const event = messenger.messages[eventName];
  if (event?.addListener) {
    event.addListener(notifyDashboardInvalidated);
  }
}

function requestCopy(requestKind) {
  if (requestKind === "schedule_entry") {
    return {
      subject: "スケジュール入力",
      body: "スケジュール入力をお願いします。",
    };
  }
  if (requestKind === "schedule_adjustment") {
    return {
      subject: "スケジュール調整",
      body: "スケジュール調整をお願いします。",
    };
  }
  throw new Error(`Unknown schedule request kind: ${requestKind}`);
}

function withOriginHeader(headers, originMessageId) {
  const current = Array.isArray(headers) ? headers : [];
  const withoutOrigin = current.filter(
    (header) => String(header?.name || "").toLowerCase() !== WORKINBOX_ORIGIN_HEADER.toLowerCase(),
  );
  return [
    ...withoutOrigin,
    {
      name: WORKINBOX_ORIGIN_HEADER,
      value: originMessageId,
    },
  ];
}

function withWorkInBoxHeaders(headers, values) {
  const names = new Set(Object.keys(values).map((name) => name.toLowerCase()));
  const current = (Array.isArray(headers) ? headers : []).filter(
    (header) => !names.has(String(header?.name || "").toLowerCase()),
  );
  return [
    ...current,
    ...Object.entries(values).map(([name, value]) => ({ name, value })),
  ];
}

async function selfAddressForMessage(message) {
  const accountId = message?.folder?.accountId;
  if (!accountId) throw new Error("元メールのアカウントを確認できませんでした。");
  const account = await messenger.accounts.get(accountId);
  const identities = Array.isArray(account?.identities) ? account.identities : [];
  const identity = identities.find((item) => item.email) || null;
  if (!identity?.email) throw new Error("自分宛てのメールアドレスを確認できませんでした。");
  return identity.email;
}

async function messageMenuState(messageId, thunderbirdMessageId) {
  const message = await resolveDisplayedMessage(thunderbirdMessageId, messageId);
  if (!message) throw new Error("表示中のメールを取得できませんでした。");
  const tags = new Set(message.tags || []);
  return {
    ok: true,
    actionReady: tags.has("wib-action-ready"),
    normalWorkflow: [...NORMAL_WORKFLOW_TAGS].find((tag) => tags.has(tag)) || null,
  };
}

async function setNormalWorkflow(messageId, thunderbirdMessageId, tagKey) {
  if (!NORMAL_WORKFLOW_TAGS.has(tagKey)) throw new Error("通常フローの指定が不正です。");
  const message = await resolveDisplayedMessage(thunderbirdMessageId, messageId);
  if (!message) throw new Error("表示中のメールを取得できませんでした。");
  if ((message.tags || []).includes("wib-action-ready")) throw new Error("対応ありメールでは通常フローを変更できません。");
  const tags = (message.tags || []).filter((tag) => (
    !NORMAL_SELECTION_TAGS.has(tag) && tag !== BULK_TAG && tag !== LEGACY_BULK_TAG
  ));
  await messenger.messages.update(message.id, { tags: [...new Set([...tags, tagKey])], flagged: true });
  return { ok: true };
}

async function beginRecordRequest(message) {
  const to = await selfAddressForMessage(message);
  const requestId = crypto.randomUUID();
  const composeTab = await messenger.compose.beginNew({ to: [to] });
  const details = await messenger.compose.getComposeDetails(composeTab.id);
  await messenger.compose.setComposeDetails(composeTab.id, {
    customHeaders: withWorkInBoxHeaders(details.customHeaders, {
      [WORKINBOX_ACTION_HEADER]: RECORD_ACTION,
      [WORKINBOX_ORIGIN_HEADER]: message.headerMessageId,
      [WORKINBOX_REQUEST_ID_HEADER]: requestId,
    }),
  });
  pendingMenuComposes.set(composeTab.id, { action: RECORD_ACTION, messageId: message.id });
  return { ok: true };
}

async function completeMessage(messageId, thunderbirdMessageId, mode) {
  const message = await resolveDisplayedMessage(thunderbirdMessageId, messageId);
  if (!message) throw new Error("表示中のメールを取得できませんでした。");
  if ((message.tags || []).includes("wib-action-ready")) throw new Error("対応ありメールでは通常終了を選べません。");
  if (!(message.tags || []).some((tag) => NORMAL_WORKFLOW_TAGS.has(tag))) {
    throw new Error("回答必要・見る／検討・注目のいずれもないため終了できません。");
  }
  if (mode === "record") return beginRecordRequest(message);
  if (mode !== "normal") throw new Error("終了方法の指定が不正です。");
  const bulkTagKey = await resolveBulkTagKey();
  await addTag(message, bulkTagKey);
  await messenger.messages.update(message.id, { flagged: false });
  return { ok: true };
}

async function handleActionReady(messageId, thunderbirdMessageId, action) {
  const message = await resolveDisplayedMessage(thunderbirdMessageId, messageId);
  if (!message) throw new Error("表示中のメールを取得できませんでした。");
  if (!(message.tags || []).includes("wib-action-ready")) throw new Error("このメールには対応ありタグがありません。");
  if (action === "finish") {
    const bulkTagKey = await resolveBulkTagKey();
    await addTag(message, bulkTagKey);
    await messenger.messages.update(message.id, { flagged: false });
    return { ok: true };
  }
  if (!new Set(["question", "thanks"]).has(action)) throw new Error("対応方法の指定が不正です。");
  const composeTab = await messenger.compose.beginReply(message.id, "replyToSender");
  const details = await messenger.compose.getComposeDetails(composeTab.id);
  await messenger.compose.setComposeDetails(composeTab.id, {
    customHeaders: withWorkInBoxHeaders(details.customHeaders, {
      [WORKINBOX_ACTION_HEADER]: action === "thanks" ? "support-thanks" : "support-question",
    }),
  });
  pendingMenuComposes.set(composeTab.id, { action, messageId: message.id });
  return { ok: true };
}

function prependRequestBody(details, requestText) {
  if (details.isPlainText || typeof details.body !== "string") {
    return {
      plainTextBody: `${requestText}\n\n${details.plainTextBody || ""}`,
    };
  }

  const escaped = requestText
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  return {
    body: `<div>${escaped}</div><br>${details.body || ""}`,
  };
}

async function beginSupportRequest(request) {
  const originMessageId = String(request.messageId || "").trim();
  const requestKind = String(request.requestKind || "schedule_adjustment").trim();
  const to = String(request.to || "").trim();
  const cc = String(request.cc || "").trim();

  if (!originMessageId) {
    throw new Error("元メールの Message-ID がありません。");
  }
  if (!to) {
    throw new Error("支援者の宛先を入力してください。");
  }
  if (!cc) {
    throw new Error("Cc に自分のメールアドレスを入力してください。");
  }

  const originMessage = await findMessageByHeaderMessageId(originMessageId);
  if (!originMessage) {
    throw new Error(`Message-ID ${originMessageId} の元メールを Thunderbird で見つけられませんでした。`);
  }

  const copy = requestCopy(requestKind);
  // M2 is deliberately a separate thread, but the supporter needs the source
  // message for context. An inline forward includes M1 in the body without
  // making M2 a reply in M1's thread. The WorkInBox relation is still carried
  // explicitly by X-WorkInBox-Origin-Message-ID.
  const composeTab = await messenger.compose.beginForward(
    originMessage.id,
    "forwardInline",
  );
  const details = await messenger.compose.getComposeDetails(composeTab.id);
  const updates = {
    to: [to],
    cc: [cc],
    subject: copy.subject,
    customHeaders: withOriginHeader(details.customHeaders, originMessageId),
    ...prependRequestBody(details, copy.body),
  };

  await messenger.compose.setComposeDetails(composeTab.id, updates);
  pendingSupportRequests.set(composeTab.id, originMessageId);
  console.info(
    "[WorkInBox bridge] support request compose tracked",
    composeTab.id,
    originMessageId,
  );
  return { ok: true };
}

function headerValue(messagePart, headerName) {
  const headers = messagePart?.headers || {};
  const target = headerName.toLowerCase();
  for (const [name, values] of Object.entries(headers)) {
    if (name.toLowerCase() !== target) {
      continue;
    }
    if (Array.isArray(values)) {
      return String(values[0] || "").trim();
    }
    return String(values || "").trim();
  }
  return "";
}

async function addTag(message, tagKey, { flagged } = {}) {
  const tags = [...new Set([...(message.tags || []), tagKey])];
  const properties = { tags };
  if (typeof flagged === "boolean") {
    properties.flagged = flagged;
  }
  await messenger.messages.update(message.id, properties);
}

async function resolveBulkTagKey() {
  const registeredTags = await messenger.messages.tags.list();
  const current = registeredTags.find((tag) => tag.key === BULK_TAG);
  if (current) {
    return current.key;
  }

  // Older WIB installations used wib-batch for the same visible tag.
  // Thunderbird rejects creating another tag with the same display name, so
  // keep using the valid legacy key until the explicit tag migration is run.
  const legacy = registeredTags.find((tag) => tag.key === LEGACY_BULK_TAG);
  if (legacy) {
    return legacy.key;
  }

  const sameLabel = registeredTags.find(
    (tag) => tag.tag === BULK_TAG_DEFINITION.tag,
  );
  if (sameLabel) {
    return sameLabel.key;
  }

  await messenger.messages.tags.create(
    BULK_TAG_DEFINITION.key,
    BULK_TAG_DEFINITION.tag,
    BULK_TAG_DEFINITION.color,
  );
  return BULK_TAG;
}

async function setNormalCompletionActionStatus(tabId, badgeText, title) {
  await messenger.messageDisplayAction.setBadgeText({ tabId, text: badgeText });
  await messenger.messageDisplayAction.setTitle({ tabId, title });
  window.setTimeout(() => {
    void messenger.messageDisplayAction.setBadgeText({ tabId, text: "" });
    void messenger.messageDisplayAction.setTitle({
      tabId,
      title: "WIB: 通常ワークフローを終了",
    });
  }, 3000);
}

async function completeDisplayedNormalWorkflow(tab) {
  const message = await messenger.messageDisplay.getDisplayedMessage(tab.id);
  if (!message) {
    throw new Error("表示中のメールを取得できませんでした。");
  }
  if (!(message.tags || []).some((tag) => NORMAL_WORKFLOW_TAGS.has(tag))) {
    throw new Error(
      "返信必要・見る／検討・注目のいずれもないため、通常終了できません。",
    );
  }

  // Thunderbird applies `flagged` before `tags` when both are sent in one
  // update. In a flagged Quick Filter that can remove the message from the
  // view before the keyword update completes. Apply the tag first, then unstar.
  // Do not immediately re-read the message: Thunderbird can return a stale
  // MessageHeader while the IMAP keyword update is still propagating.
  const bulkTagKey = await resolveBulkTagKey();
  await addTag(message, bulkTagKey);
  await messenger.messages.update(message.id, { flagged: false });
  await setNormalCompletionActionStatus(tab.id, "✓", "WIB: 通常終了しました");
}

async function originMessageIdFromSentMessages(sendInfo) {
  const sentMessages = Array.isArray(sendInfo?.messages) ? sendInfo.messages : [];
  for (const sentMessage of sentMessages) {
    const full = await messenger.messages.getFull(sentMessage.id);
    if (headerValue(full, WORKINBOX_ACTION_HEADER)) {
      continue;
    }
    const originMessageId = headerValue(full, WORKINBOX_ORIGIN_HEADER);
    if (originMessageId) {
      return originMessageId;
    }
  }
  return "";
}

async function applySupportRequestSentState(tab, sendInfo) {
  const tabId = tab?.id;
  let originMessageId = tabId === undefined ? "" : pendingSupportRequests.get(tabId) || "";

  try {
    if (!originMessageId) {
      originMessageId = await originMessageIdFromSentMessages(sendInfo);
      if (originMessageId) {
        console.info(
          "[WorkInBox bridge] recovered support request origin from sent message",
          originMessageId,
        );
      }
    }

    if (!originMessageId) {
      console.warn("[WorkInBox bridge] support request sent without a recoverable origin Message-ID");
      return;
    }

    const originMessage = await findMessageByHeaderMessageId(originMessageId);
    if (!originMessage) {
      console.error(
        "[WorkInBox bridge] support request sent, but origin message was not found:",
        originMessageId,
      );
      return;
    }

    // The extension only records that the support request was sent. The INBOX
    // copy becomes starred + waiting-action during the next normal TriageBox run.
    await addTag(originMessage, REQUESTED_TAG);
    console.info(
      "[WorkInBox bridge] marked support request origin as requested",
      originMessageId,
    );
  } finally {
    if (tabId !== undefined) {
      pendingSupportRequests.delete(tabId);
    }
  }
}

messenger.compose.onAfterSend.addListener((tab, sendInfo) => {
  void applySupportRequestSentState(tab, sendInfo).catch((error) => {
    console.error("[WorkInBox bridge] failed to apply support request state", error);
  });
  const pending = pendingMenuComposes.get(tab?.id);
  if (!pending) return;
  pendingMenuComposes.delete(tab.id);
  if (pending.action !== "thanks" && pending.action !== RECORD_ACTION) return;
  void messenger.messages.get(pending.messageId).then(async (message) => {
    const bulkTagKey = await resolveBulkTagKey();
    await addTag(message, bulkTagKey);
  }).catch((error) => {
    console.error("[WorkInBox menu] failed to mark sent operation for tracking", error);
  });
});

messenger.compose.onBeforeSend.addListener(async (tab, details) => {
  const pending = pendingMenuComposes.get(tab?.id);
  if (pending?.action === RECORD_ACTION && !String(details?.subject || "").trim()) {
    return { cancel: true };
  }
  return {};
});

messenger.messageDisplayAction.onClicked.addListener((tab) => {
  void completeDisplayedNormalWorkflow(tab).catch(async (error) => {
    console.error("[WorkInBox normal completion]", error);
    await setNormalCompletionActionStatus(
      tab.id,
      "!",
      `WIB: ${error.message || error}`,
    );
  });
});

messenger.tabs.onRemoved.addListener((tabId) => {
  pendingMenuComposes.delete(tabId);
  pendingSupportRequests.delete(tabId);
  if (tabId === workViewTabId) {
    workViewTabId = null;
    workViewTabTitle = null;
  }
  if (tabId === dashboardTabId) {
    dashboardTabId = null;
  }
  if (tabId === dedicatedWorkflowTabId) {
    dedicatedWorkflowTabId = null;
  }
});

messenger.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (
    tabId === workViewTabId
    && workViewTabTitle
    && typeof changeInfo.title === "string"
    && changeInfo.title !== workViewTabTitle
  ) {
    void restoreWorkViewTabTitle(tabId).catch((error) => {
      console.warn("[WorkInBox bridge] could not preserve work-view tab title", error);
    });
  }
});

messenger.tabs.onActivated.addListener(({ tabId }) => {
  if (tabId === workViewTabId && workViewTabTitle) {
    void restoreWorkViewTabTitle(tabId).catch((error) => {
      console.warn("[WorkInBox bridge] could not restore active work-view tab title", error);
    });
  }
});

messenger.runtime.onMessage.addListener((request) => {
  if (!request) {
    return undefined;
  }

  let operation;
  if (request.type === "workinbox-open-message") {
    operation = openMessageByHeaderMessageId(request.messageId);
  } else if (request.type === "workinbox-open-work-view") {
    operation = openWorkView(request.view, request.imapTarget, request.lookbackDays);
  } else if (request.type === "workinbox-compose-support-request") {
    operation = beginSupportRequest(request);
  } else if (request.type === "workinbox-open-dashboard") {
    operation = openDashboard();
  } else if (request.type === "workinbox-dashboard-counts") {
    operation = dashboardCounts(request.imapTarget, request.lookbackDays);
  } else if (request.type === "workinbox-open-tasks") {
    operation = openTasksSpace();
  } else if (request.type === "workinbox-open-dedicated-workflow") {
    operation = openDedicatedWorkflow(
      request.kind,
      request.messageId,
      request.thunderbirdMessageId,
    );
  } else if (request.type === "workinbox-prepare-dedicated-workflow") {
    operation = prepareDedicatedWorkflow(
      request.kind,
      request.messageId,
      request.thunderbirdMessageId,
    );
  } else if (request.type === "workinbox-dismiss-dedicated-workflow") {
    operation = dismissDedicatedWorkflow(
      request.kind,
      request.messageId,
      request.thunderbirdMessageId,
    );
  } else if (request.type === "workinbox-message-menu-state") {
    operation = messageMenuState(request.messageId, request.thunderbirdMessageId);
  } else if (request.type === "workinbox-set-normal-workflow") {
    operation = setNormalWorkflow(request.messageId, request.thunderbirdMessageId, request.tagKey);
  } else if (request.type === "workinbox-complete-message") {
    operation = completeMessage(request.messageId, request.thunderbirdMessageId, request.mode);
  } else if (request.type === "workinbox-handle-action-ready") {
    operation = handleActionReady(request.messageId, request.thunderbirdMessageId, request.action);
  } else {
    return undefined;
  }

  return operation.catch((error) => ({
    ok: false,
    error: error.message || String(error),
  }));
});
