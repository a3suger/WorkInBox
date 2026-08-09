const TEST_TAG = Object.freeze({
  key: "wib-deadline",
  tag: "締切あり",
  color: "#d9534f",
});

async function ensureTestTag() {
  const tags = await messenger.messages.tags.list();
  const existing = tags.find((tag) => tag.key === TEST_TAG.key);

  if (existing) {
    const needsUpdate =
      existing.tag !== TEST_TAG.tag || existing.color !== TEST_TAG.color;

    if (needsUpdate) {
      await messenger.messages.tags.update(TEST_TAG.key, {
        tag: TEST_TAG.tag,
        color: TEST_TAG.color,
      });
      console.log(
        `[WorkInBox tag test] Updated ${TEST_TAG.key} -> ${TEST_TAG.tag}`,
      );
    } else {
      console.log(
        `[WorkInBox tag test] ${TEST_TAG.key} is already registered as ${TEST_TAG.tag}`,
      );
    }
    return;
  }

  const createdKey = await messenger.messages.tags.create(
    TEST_TAG.key,
    TEST_TAG.tag,
    TEST_TAG.color,
  );

  console.log(
    `[WorkInBox tag test] Created ${createdKey} -> ${TEST_TAG.tag}`,
  );
}

ensureTestTag().catch((error) => {
  console.error("[WorkInBox tag test] Failed to register test tag", error);
});
