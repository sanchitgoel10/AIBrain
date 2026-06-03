chrome.action.onClicked.addListener(async () => {
  const url = chrome.runtime.getURL("popup.html");
  const windows = await chrome.windows.getAll({ populate: true, windowTypes: ["popup"] });
  const existing = windows.find((win) =>
    (win.tabs || []).some((tab) => (tab.url || "").startsWith(url))
  );
  if (existing?.id) {
    await chrome.windows.update(existing.id, { focused: true });
    return;
  }
  await chrome.windows.create({
    url,
    type: "popup",
    width: 390,
    height: 640,
    focused: true
  });
});
