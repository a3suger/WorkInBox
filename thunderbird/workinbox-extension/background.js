const WORKINBOX_ORIGIN_HEADER = "X-WorkInBox-Origin-Message-ID";
const REQUESTED_TAG = "wib-requested";

const WORK_VIEWS = {
  answer: { tagKey: "wib-answer", label: "回答必要" },
  deadline: { tagKey: "wib-deadline", label: "締切あり" },
  schedule: { tagKey: "wib-schedule", label: "スケジュール調整" },
  review: { tagKey: "wib-review", label: "読む・検討" },
  waitingReply: { tagKey: "wib-waiting-reply", label: "返信待ち" },
  waitingAction: { tagKey: "wib-waiting-action", label: "対応待ち" },
};

let workViewTabId = null;

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

async function openWorkView(viewName, imapTarget) {
  const view = WORK_VIEWS[viewName];
  if (!view) {
    throw new Error(`Unknown WorkInBox work view: ${viewName}`);
  }

  const { account, mailbox } = await resolveWorkViewMailbox(imapTarget);
  const mailTab = await resolveDedicatedWorkViewTab(mailbox);

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

  await messenger.tabs.update(mailTab.id, { active: true });

  const requestedTabTitle = `WIB:${view.label}`;
  const titleResult = await messenger.tabTitle.setTitle(mailTab.id, requestedTabTitle);
  if (!titleResult?.applied) {
    console.warn("[WorkInBox bridge] tab title was not applied as requested", titleResult);
  }

  return {
    ok: true,
    view: viewName,
    viewLabel: view.label,
    tagKey: view.tagKey,
    accountName: account.name || account.id,
    folderName: mailbox.name || imapTarget.mailbox,
    tabTitle: titleResult?.appliedTitle || requestedTabTitle,
    tabId: mailTab.id,
    dedicatedTab: true,
  };
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
  const method = String(request.method || "reply").trim();
  const requestKind = String(request.requestKind || "schedule_adjustment").trim();
  const to = String(request.to || "").trim();
  const cc = String(request.cc || "").trim();
  const keepReplySubject = request.keepReplySubject !== false;

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
  let composeTab;
  if (method === "reply") {
    composeTab = await messenger.compose.beginReply(originMessage.id, "replyToSender");
  } else if (method === "forward") {
    composeTab = await messenger.compose.beginForward(originMessage.id, "forwardInline");
  } else {
    throw new Error(`Unknown schedule request method: ${method}`);
  }

  const details = await messenger.compose.getComposeDetails(composeTab.id);
  const updates = {
    to: [to],
    cc: [cc],
    customHeaders: withOriginHeader(details.customHeaders, originMessageId),
    ...prependRequestBody(details, copy.body),
  };

  if (method === "forward" || !keepReplySubject) {
    updates.subject = copy.subject;
  }

  await messenger.compose.setComposeDetails(composeTab.id, updates);
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

async function applySupportRequestSentState(sendInfo) {
  const sentMessages = Array.isArray(sendInfo?.messages) ? sendInfo.messages : [];
  if (sentMessages.length === 0) {
    return;
  }

  let originMessageId = "";
  for (const sentMessage of sentMessages) {
    const full = await messenger.messages.getFull(sentMessage.id);
    originMessageId = headerValue(full, WORKINBOX_ORIGIN_HEADER);
    if (originMessageId) {
      break;
    }
  }

  if (!originMessageId) {
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
}

messenger.compose.onAfterSend.addListener((_tab, sendInfo) => {
  void applySupportRequestSentState(sendInfo).catch((error) => {
    console.error("[WorkInBox bridge] failed to apply support request state", error);
  });
});

messenger.tabs.onRemoved.addListener((tabId) => {
  if (tabId === workViewTabId) {
    workViewTabId = null;
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
    operation = openWorkView(request.view, request.imapTarget);
  } else if (request.type === "workinbox-compose-support-request") {
    operation = beginSupportRequest(request);
  } else {
    return undefined;
  }

  return operation.catch((error) => ({
    ok: false,
    error: error.message || String(error),
  }));
});