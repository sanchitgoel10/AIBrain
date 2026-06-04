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
  resetCompile: document.getElementById("resetCompile"),
  status: document.getElementById("status"),
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
  const count = status.captures_since_compile || 0;
  const threshold = status.semantic_threshold || 10;
  els.compileCard.classList.toggle("due", Boolean(status.semantic_due));
  if (status.semantic_due) {
    els.compileStatus.textContent = `${count}/${threshold} captures. Run Codex semantic compile.`;
  } else {
    els.compileStatus.textContent = `${count}/${threshold} captures since semantic compile.`;
  }
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
  els.capture.disabled = Boolean(capture.running) || tab.capturable === false;
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

async function resetSemanticCounter() {
  els.resetCompile.disabled = true;
  try {
    const response = await sendMessage({ type: "reset-semantic" });
    if (response?.ok && response.state) render(response.state);
  } catch (_error) {
    els.compileStatus.textContent = "Could not reset counter.";
  } finally {
    els.resetCompile.disabled = false;
  }
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
els.resetCompile.addEventListener("click", resetSemanticCounter);
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
