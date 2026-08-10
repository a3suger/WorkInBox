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

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-wib-open-message-id]");
  if (!button) {
    return;
  }

  event.preventDefault();
  void handleOpenMessage(button);
});
