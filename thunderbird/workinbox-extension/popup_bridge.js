const WORKINBOX_URL = "http://127.0.0.1:8000/";

const openWorkInBoxButton = document.querySelector("#open-workinbox");
const openAnswerWorkViewButton = document.querySelector("#open-answer-work-view");

function setStatus(text) {
  const status = document.querySelector("#status");
  if (status) {
    status.textContent = text;
  }
}

openWorkInBoxButton.addEventListener("click", async () => {
  try {
    await messenger.tabs.create({
      url: WORKINBOX_URL,
      active: true,
      linkHandler: "balanced",
    });
    window.close();
  } catch (error) {
    console.error("[WorkInBox bridge]", error);
    setStatus(`ERROR: ${error.message || error}`);
  }
});

openAnswerWorkViewButton.addEventListener("click", async () => {
  openAnswerWorkViewButton.disabled = true;
  setStatus("回答必要の Quick Filter を適用しています…");

  try {
    const response = await messenger.runtime.sendMessage({
      type: "workinbox-open-work-view",
      view: "answer",
    });

    if (!response?.ok) {
      throw new Error(response?.error || "Quick Filter を適用できませんでした。");
    }

    setStatus(`${response.folderName || "INBOX"} で回答必要 + スター付きの表示に切り替えました。`);
    window.close();
  } catch (error) {
    console.error("[WorkInBox bridge]", error);
    setStatus(`ERROR: ${error.message || error}`);
    openAnswerWorkViewButton.disabled = false;
  }
});
