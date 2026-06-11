const state = {
  ui: null,
  mode: "add"
};

const els = {
  addPanel: document.getElementById("addPanel"),
  askAnswer: document.getElementById("askAnswer"),
  askForm: document.getElementById("askForm"),
  askPanel: document.getElementById("askPanel"),
  askQuery: document.getElementById("askQuery"),
  askResults: document.getElementById("askResults"),
  askSubmit: document.getElementById("askSubmit"),
  compileCard: document.getElementById("compileCard"),
  compileStatus: document.getElementById("compileStatus"),
  capture: document.getElementById("capture"),
  kind: document.getElementById("kind"),
  progress: document.getElementById("progressBar"),
  status: document.getElementById("status"),
  stopCapture: document.getElementById("stopCapture"),
  tabAdd: document.getElementById("tabAdd"),
  tabAsk: document.getElementById("tabAsk"),
  title: document.getElementById("title"),
  url: document.getElementById("url")
};

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function sendMessage(message) {
  return chrome.runtime.sendMessage(message);
}

function setProgress(status, message) {
  els.progress.className = `progress-bar ${status || "idle"}`;
  els.status.textContent = message || "Ready.";
}

function setMode(mode) {
  state.mode = mode;
  const ask = mode === "ask";
  els.addPanel.classList.toggle("hidden", ask);
  els.askPanel.classList.toggle("hidden", !ask);
  els.tabAdd.classList.toggle("active", !ask);
  els.tabAsk.classList.toggle("active", ask);
  if (ask) els.askQuery.focus();
}

function updateBrainStatus(status) {
  if (!status) {
    els.compileStatus.textContent = "Bridge not available.";
    return;
  }
  const pending = status.semantic_pending || 0;
  const total = status.total_sources || 0;
  els.compileCard.classList.toggle("due", pending > 0);
  els.compileStatus.textContent = pending
    ? `${pending} of ${total} sources pending daily compile.`
    : `All ${total} sources semantically compiled.`;
}

function renderAskResults(results) {
  if (!results.length) {
    els.askResults.innerHTML = '<div class="result"><div class="result-title">No matches</div></div>';
    return;
  }
  els.askResults.innerHTML = results.map((result) => `
    <article class="result">
      <div class="result-title">${escapeHtml(result.title || result.path || "Result")}</div>
      <div class="result-path">${escapeHtml(result.path || "")}</div>
      <div class="result-snippet">${escapeHtml(result.snippet || "")}</div>
      <div class="result-actions">
        <button class="source-action" type="button" data-path="${escapeHtml(result.path || "")}">Reveal</button>
      </div>
    </article>
  `).join("");
}

function renderAsk(ask) {
  const current = ask || {};
  els.askSubmit.disabled = Boolean(current.running);
  if (current.query && els.askQuery.value !== current.query && !els.askQuery.matches(":focus")) {
    els.askQuery.value = current.query;
  }
  if (current.running) {
    els.askAnswer.classList.add("hidden");
    els.askAnswer.innerHTML = "";
    els.askResults.innerHTML = '<div class="result"><div class="result-title">Searching...</div></div>';
    return;
  }
  if (current.error) {
    els.askAnswer.classList.add("hidden");
    els.askAnswer.innerHTML = "";
    els.askResults.innerHTML = `<div class="result"><div class="result-title">${escapeHtml(current.error)}</div></div>`;
    return;
  }
  if (current.answer) {
    els.askAnswer.classList.remove("hidden");
    els.askAnswer.innerHTML = `
      <div class="answer-label">Answer</div>
      <div class="answer-text">${escapeHtml(current.answer)}</div>
    `;
  } else {
    els.askAnswer.classList.add("hidden");
    els.askAnswer.innerHTML = "";
  }
  renderAskResults(current.results || []);
}

function render(ui) {
  state.ui = ui || {};
  const tab = state.ui.tab || {};
  const capture = state.ui.capture || {};

  els.title.textContent = tab.title || "No active tab";
  els.url.textContent = tab.url || "";
  els.kind.textContent = tab.kind || "Reading active tab";
  els.capture.disabled = tab.capturable === false;
  els.capture.classList.toggle("hidden", Boolean(capture.running));
  els.stopCapture.classList.toggle("hidden", !capture.running);
  setProgress(capture.status || "idle", capture.message || (tab.capturable === false ? "Open a YouTube video or article tab first." : "Ready."));
  updateBrainStatus(state.ui.brainStatus || null);
  renderAsk(state.ui.ask || {});
}

async function refreshState() {
  const response = await sendMessage({ type: "get-state" });
  if (response?.ok) render(response.state);
}

async function startCapture() {
  els.capture.disabled = true;
  setProgress("queued", "Preparing active tab.");
  const response = await sendMessage({ type: "start-capture" });
  if (response?.ok && response.state) render(response.state);
}

async function stopCapture() {
  els.stopCapture.disabled = true;
  setProgress("cancelled", "Stopping capture...");
  try {
    const response = await sendMessage({ type: "stop-capture" });
    if (response?.ok && response.state) render(response.state);
  } finally {
    els.stopCapture.disabled = false;
  }
}

async function askBrain(event) {
  event.preventDefault();
  const query = els.askQuery.value.trim();
  if (!query) return;
  els.askSubmit.disabled = true;
  els.askAnswer.classList.add("hidden");
  els.askAnswer.innerHTML = "";
  els.askResults.innerHTML = '<div class="result"><div class="result-title">Searching...</div></div>';
  const response = await sendMessage({ type: "ask", query });
  if (response?.ok && response.state) render(response.state);
}

async function revealSource(path) {
  if (!path) return;
  await sendMessage({ type: "reveal-source", path });
}

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local") return;
  const next = changes.aiBrainUiState?.newValue;
  if (next) render(next);
});

els.capture.addEventListener("click", startCapture);
els.stopCapture.addEventListener("click", stopCapture);
els.tabAdd.addEventListener("click", () => setMode("add"));
els.tabAsk.addEventListener("click", () => setMode("ask"));
els.askForm.addEventListener("submit", askBrain);
els.askResults.addEventListener("click", (event) => {
  const button = event.target.closest("[data-path]");
  if (button) revealSource(button.dataset.path || "");
});

refreshState().catch((error) => {
  setProgress("error", error.message || "Could not read extension state.");
});
