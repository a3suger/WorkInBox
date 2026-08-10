const WORKINBOX_URL = "http://127.0.0.1:8000/";

const openWorkInBoxButton = document.querySelector("#open-workinbox");

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
    const status = document.querySelector("#status");
    if (status) {
      status.textContent = `ERROR: ${error.message || error}`;
    }
  }
});
