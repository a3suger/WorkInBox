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

async function openInThreadedMailTab(message) {
  const tab = await messenger.mailTabs.create({
    active: true,
    folderPaneVisible: true,
    messagePaneVisible: true,
    viewType: "groupedByThread",
  });

  try {
    await messenger.mailTabs.setSelectedMessages(tab.id, [message.id]);
  } catch (error) {
    try {
      await messenger.tabs.remove(tab.id);
    } catch (_closeError) {
      // Best effort only. The fallback below is more important than cleanup.
    }
    throw error;
  }

  return tab;
}

async function openMessageByHeaderMessageId(messageId) {
  const message = await findMessageByHeaderMessageId(messageId);
  if (!message) {
    throw new Error(`Message-ID ${messageId} のメールを Thunderbird で見つけられませんでした。`);
  }

  let displayMode = "threaded-mail-tab";
  try {
    await openInThreadedMailTab(message);
  } catch (error) {
    console.warn(
      "[WorkInBox bridge] Threaded mail tab failed; falling back to message display.",
      error,
    );
    displayMode = "message-display-fallback";
    await messenger.messageDisplay.open({
      messageId: message.id,
      location: "tab",
      active: true,
    });
  }

  return {
    ok: true,
    subject: message.subject || "",
    headerMessageId: message.headerMessageId || messageId,
    displayMode,
  };
}

messenger.runtime.onMessage.addListener((request) => {
  if (!request || request.type !== "workinbox-open-message") {
    return undefined;
  }

  return openMessageByHeaderMessageId(request.messageId)
    .catch((error) => ({
      ok: false,
      error: error.message || String(error),
    }));
});
