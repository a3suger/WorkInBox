"use strict";

const status = document.querySelector("#status");

for (const button of document.querySelectorAll("button")) {
  button.addEventListener("click", () => {
    status.textContent = `「${button.textContent.trim()}」は現在プレビューのみです。`;
  });
}
