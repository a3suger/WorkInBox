"use strict";

const WIB_URL = "http://127.0.0.1:8000/";
const form = document.querySelector("#add-form");
const input = document.querySelector("#address");
const list = document.querySelector("#sender-list");
const table = document.querySelector("#sender-table");
const empty = document.querySelector("#empty");
const errorBox = document.querySelector("#error");

async function fetchJson(path, options = {}) {
  const response = await fetch(new URL(path, WIB_URL).href, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_error) { /* no JSON */ }
    throw new Error(detail);
  }
  return response.json();
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString("ja-JP") : "-";
}

function render(items) {
  list.replaceChildren();
  for (const item of items) {
    const row = document.createElement("tr");
    const address = document.createElement("td");
    address.textContent = item.address;
    const count = document.createElement("td");
    count.textContent = String(item.match_count || 0);
    const matched = document.createElement("td");
    matched.textContent = formatDate(item.last_matched_at);
    const action = document.createElement("td");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "削除";
    button.addEventListener("click", () => void remove(item.address, button));
    action.append(button);
    row.append(address, count, matched, action);
    list.append(row);
  }
  table.hidden = items.length === 0;
  empty.hidden = items.length !== 0;
}

async function refresh() {
  try {
    const result = await fetchJson("/api/advertising-senders");
    document.querySelector("#connection").className = "connection online";
    document.querySelector("#connection-label").textContent = "WIB接続中";
    document.querySelector("#connection-detail").textContent = "広告送信者を追加・削除できます。";
    form.querySelector("button").disabled = false;
    input.disabled = false;
    errorBox.hidden = true;
    render(result.items || []);
  } catch (error) {
    document.querySelector("#connection").className = "connection offline";
    document.querySelector("#connection-label").textContent = "WIB接続不可";
    document.querySelector("#connection-detail").textContent = "DBの一覧・追加・削除にはWIB接続が必要です。";
    form.querySelector("button").disabled = true;
    input.disabled = true;
    errorBox.textContent = error.message || String(error);
    errorBox.hidden = false;
  }
}

async function remove(address, button) {
  button.disabled = true;
  try {
    await fetchJson("/api/advertising-senders", {
      method: "DELETE",
      body: JSON.stringify({ address }),
    });
    await refresh();
  } catch (error) {
    errorBox.textContent = error.message || String(error);
    errorBox.hidden = false;
    button.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void (async () => {
    form.querySelector("button").disabled = true;
    try {
      await fetchJson("/api/advertising-senders", {
        method: "POST",
        body: JSON.stringify({ address: input.value }),
      });
      input.value = "";
      await refresh();
    } catch (error) {
      errorBox.textContent = error.message || String(error);
      errorBox.hidden = false;
      form.querySelector("button").disabled = false;
    }
  })();
});

void refresh();
