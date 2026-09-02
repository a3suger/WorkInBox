"use strict";

const WIB_URL = "http://127.0.0.1:8000/";
const params = new URLSearchParams(window.location.search);
const kind = params.get("kind");
const messageId = params.get("message_id");
const title = document.querySelector("#title");
const detail = document.querySelector("#detail");
const retry = document.querySelector("#retry");

async function connect() {
  retry.hidden = true;
  title.textContent = "WIBへ接続しています";
  detail.textContent = "選択したメールの専用フローを準備しています…";
  if (!(["deadline", "schedule"].includes(kind)) || !messageId) {
    title.textContent = "専用フローを開けません";
    detail.textContent = "対象メールまたは専用フローの指定が不正です。";
    return;
  }
  try {
    const response = await fetch(new URL("api/health", WIB_URL), { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const health = await response.json();
    if (health.status !== "ok") throw new Error("WIBの一部機能を利用できません");
    const path = kind === "deadline" ? "deadlines/message" : "schedules/message";
    const target = new URL(path, WIB_URL);
    target.searchParams.set("message_id", messageId);
    window.location.replace(target.href);
  } catch (error) {
    title.textContent = "WIBへ接続できません";
    detail.textContent = `WIBを起動し、SSH tunnelを確認してから再試行してください。(${error.message || error})`;
    retry.hidden = false;
  }
}

retry.addEventListener("click", () => void connect());
void connect();
