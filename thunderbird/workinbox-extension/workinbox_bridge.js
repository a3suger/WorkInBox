function setButtonStatus(button, text) {
  const previous = button.dataset.wibOriginalLabel || button.textContent;
  button.dataset.wibOriginalLabel = previous;
  button.textContent = text;
}

async function loadImapTarget() {
  // In a Thunderbird content script, a root-relative fetch can be resolved
  // against the moz-extension origin. Build the URL explicitly from the WIB
  // page so the request always goes to the running WIB Web server.
  const targetUrl = new URL("/api/thunderbird/imap-target", window.location.href);
  const response = await fetch(targetUrl.href, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`WIB Web の IMAP 設定を取得できませんでした: HTTP ${response.status}`);
  }
  return response.json();
}

async function handleOpenMessage(button) {
  const messageId = button.dataset.wibOpenMessageId;
  if (!messageId) {
    return;
  }

  button.disabled = true;
  setButtonStatus(button, "Thunderbirdで検索中…");

  try {
    const response = await messenger.runtime.sendMessage({
      type: "workinbox-open-message",
      messageId,
    });

    if (!response?.ok) {
      throw new Error(response?.error || "Thunderbird 側でメールを開けませんでした。");
    }

    setButtonStatus(button, "開きました");
  } catch (error) {
    console.error("[WorkInBox bridge]", error);
    setButtonStatus(button, `失敗: ${error.message || error}`);
  } finally {
    window.setTimeout(() => {
      button.textContent = button.dataset.wibOriginalLabel || "Thunderbirdで開く";
      button.disabled = false;
    }, 2500);
  }
}

async function handleOpenWorkView(button) {
  const view = button.dataset.wibOpenWorkView;
  if (!view) {
    return;
  }

  button.disabled = true;
  button.title = "";
  setButtonStatus(button, "Thunderbirdで準備中…");

  try {
    const imapTarget = await loadImapTarget();
    const response = await messenger.runtime.sendMessage({
      type: "workinbox-open-work-view",
      view,
      imapTarget,
    });
    if (!response?.ok) {
      throw new Error(response?.error || "Thunderbird の作業ビューを開けませんでした。");
    }
    setButtonStatus(button, "開きました");
  } catch (error) {
    console.error("[WorkInBox bridge]", error);
    const message = error.message || String(error);
    button.title = message;
    setButtonStatus(button, `失敗: ${message}`);
  } finally {
    window.setTimeout(() => {
      button.textContent = button.dataset.wibOriginalLabel || "Thunderbirdで確認";
      button.disabled = false;
    }, 10000);
  }
}

async function handleSupportRequest(form) {
  const button = form.querySelector('button[type="submit"]');
  const data = new FormData(form);
  if (!button) {
    return;
  }

  button.disabled = true;
  setButtonStatus(button, "Thunderbirdで作成中…");

  try {
    const response = await messenger.runtime.sendMessage({
      type: "workinbox-compose-support-request",
      messageId: data.get("message_id"),
      requestKind: data.get("request_kind"),
      to: data.get("to"),
      cc: data.get("cc"),
    });

    if (!response?.ok) {
      throw new Error(response?.error || "Thunderbird 側で依頼メールを作成できませんでした。");
    }

    setButtonStatus(button, "作成しました");
  } catch (error) {
    console.error("[WorkInBox bridge]", error);
    setButtonStatus(button, `失敗: ${error.message || error}`);
  } finally {
    window.setTimeout(() => {
      button.textContent = button.dataset.wibOriginalLabel || "Thunderbirdで依頼メールを作成";
      button.disabled = false;
    }, 2500);
  }
}

document.addEventListener("click", (event) => {
  const workViewButton = event.target.closest("[data-wib-open-work-view]");
  if (workViewButton) {
    event.preventDefault();
    void handleOpenWorkView(workViewButton);
    return;
  }

  const messageButton = event.target.closest("[data-wib-open-message-id]");
  if (!messageButton) {
    return;
  }

  event.preventDefault();
  void handleOpenMessage(messageButton);
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-wib-support-request-form]");
  if (!form) {
    return;
  }

  event.preventDefault();
  void handleSupportRequest(form);
});
