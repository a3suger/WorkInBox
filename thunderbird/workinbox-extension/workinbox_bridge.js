function setButtonStatus(button, text) {
  const previous = button.dataset.wibOriginalLabel || button.textContent;
  button.dataset.wibOriginalLabel = previous;
  button.textContent = text;
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
  const button = event.target.closest("[data-wib-open-message-id]");
  if (!button) {
    return;
  }

  event.preventDefault();
  void handleOpenMessage(button);
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-wib-support-request-form]");
  if (!form) {
    return;
  }

  event.preventDefault();
  void handleSupportRequest(form);
});
