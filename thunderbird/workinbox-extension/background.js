const WORKINBOX_ORIGIN_HEADER = "X-WorkInBox-Origin-Message-ID";
const REQUESTED_TAG = "wib-requested";
const WAITING_ACTION_TAG = "wib-waiting-action";
const WORK_VIEW_ACCOUNT_STORAGE_KEY = "workinboxWorkViewAccountId";

const WORK_VIEW_TAGS = {
  answer: "wib-answer",
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

async function resolveConfiguredWorkViewInbox() {
  const stored = await messenger.storage.local.get(WORK_VIEW_ACCOUNT_STORAGE_KEY);
  const accountId = String(stored?.[WORK_VIEW_ACCOUNT_STORAGE_KEY] || "").trim();
  if (!accountId) {
    throw new Error("Quick Filter PoC の対象アカウントが未設定です。WorkInBox ポップアップで対象アカウントを設定してください。");
  }

  let account;
  try {
    account = await messenger.accounts.get(accountId, true);
  } catch (_error) {
    throw new Error("設定済みのThunderbirdアカウントが見つかりません。WorkInBox ポップアップで対象アカウントを設定し直してください。");
  }

  const inbox = findSpecialFolder(account?.rootFolder, "inbox");
  if (!inbox) {
    throw new Error(`設定済みアカウント「${account?.name || accountId}」の INBOX を見つけられませんでした。`);
  }

  return {
    account,
    inbox,
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

async function resolveDedicatedWorkViewTab(inbox) {
  const existing = await getExistingWorkViewTab();
  if (existing) {
    await messenger.mailTabs.update(existing.id, {
      displayedFolder: inbox,
    });
    return messenger.mailTabs.get(existing.id);
  }

  const created = await messenger.mailTabs.create({
    displayedFolder: inbox,
  });
  workViewTabId = created.id;
  return created;
}

async function openWorkView(viewName) {
  const tagKey = WORK_VIEW_TAGS[viewName];
  if (!tagKey) {
    throw new Error(`Unknown WorkInBox work view: ${viewName}`);
  }

  const { account, inbox } = await resolveConfiguredWorkViewInbox();
  const mailTab = await resolveDedicatedWorkViewTab(inbox);

  await messenger.mailTabs.setQuickFilter(mailTab.id, {
    show: true,
    flagged: true,
    tags: {
      mode: "all",
      tags: {
        [tagKey]: true,
      },
    },
  });

  await messenger.tabs.update(mailTab.id, { active: true });

  return {
    ok: true,
    view: viewName,
    tagKey,
    accountName: account.name || account.id,
    folderName: inbox.name || "INBOX",
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

  await addTag(originMessage, REQUESTED_TAG);
  for (const sentMessage of sentMessages) {
    await addTag(sentMessage, WAITING_ACTION_TAG, { flagged: true });
  }
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
    operation = openWorkView(request.view);
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
