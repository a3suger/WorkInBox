const WORKINBOX_ORIGIN_HEADER = "X-WorkInBox-Origin-Message-ID";
const REQUESTED_TAG = "wib-requested";
const WAITING_ACTION_TAG = "wib-waiting-action";

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

async function beginSupportRequest(request) {
  const originMessageId = String(request.messageId || "").trim();
  const to = String(request.to || "").trim();
  const subject = String(request.subject || "").trim();
  const body = String(request.body || "");

  if (!originMessageId) {
    throw new Error("元メールの Message-ID がありません。");
  }
  if (!to) {
    throw new Error("支援者の宛先を入力してください。");
  }
  if (!subject) {
    throw new Error("依頼メールの件名を入力してください。");
  }

  await messenger.compose.beginNew(undefined, {
    to: [to],
    subject,
    plainTextBody: body,
    customHeaders: [
      {
        name: WORKINBOX_ORIGIN_HEADER,
        value: originMessageId,
      },
    ],
  });

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

messenger.runtime.onMessage.addListener((request) => {
  if (!request) {
    return undefined;
  }

  let operation;
  if (request.type === "workinbox-open-message") {
    operation = openMessageByHeaderMessageId(request.messageId);
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
