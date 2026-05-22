const BRIDGE_URL = "http://127.0.0.1:8765/capture";

async function showStatus(text, title) {
  await chrome.action.setBadgeText({ text });
  await chrome.action.setBadgeBackgroundColor({
    color: text === "OK" ? "#167C3A" : "#B42318"
  });
  await chrome.action.setTitle({ title });
  setTimeout(() => {
    chrome.action.setBadgeText({ text: "" });
    chrome.action.setTitle({ title: "Capture to AI Brain" });
  }, 5000);
}

function isCaptureUrl(url) {
  return /^https?:\/\//i.test(url || "");
}

chrome.action.onClicked.addListener(async (tab) => {
  const url = tab?.url || "";
  const title = tab?.title || "";

  if (!isCaptureUrl(url)) {
    await showStatus("ERR", "AI Brain capture skipped: this tab has no normal http/https URL.");
    return;
  }

  try {
    const response = await fetch(BRIDGE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title })
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Bridge returned HTTP ${response.status}`);
    }
    await showStatus("OK", `Captured to AI Brain: ${payload.path || title || url}`);
  } catch (error) {
    await showStatus("ERR", `AI Brain bridge error: ${error.message}. Start scripts/run_capture_bridge.sh first.`);
  }
});
