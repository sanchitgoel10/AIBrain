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
  capture: document.getElementById("capture"),
  duplicateActions: document.getElementById("duplicateActions"),
  keepExisting: document.getElementById("keepExisting"),
  kind: document.getElementById("kind"),
  progress: document.getElementById("progressBar"),
  replaceExisting: document.getElementById("replaceExisting"),
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

function askOriginLabel(origin) {
  if (origin === "llm") return "Answered by LLM";
  if (origin === "sql_snippet") return "Answered from SQL snippets";
  return "No grounded answer";
}

function formatDiagnosticValue(value) {
  if (value === undefined || value === null || value === "") return "";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function diagnosticLine(label, value) {
  const formatted = formatDiagnosticValue(value);
  if (!formatted) return "";
  return `<div class="ask-diagnostic-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(formatted)}</strong></div>`;
}

function renderAskDiagnostics(current) {
  const diagnostics = current.diagnostics || {};
  const llm = diagnostics.llm || {};
  const retrieval = diagnostics.retrieval || {};
  const origin = diagnostics.answer_origin || "";
  const warnings = current.warnings || [];
  if (!origin && !warnings.length && !llm.status) return "";
  const rows = [
    diagnosticLine("Source", askOriginLabel(origin)),
    diagnosticLine("Fallback", diagnostics.fallback_reason),
    diagnosticLine("Warnings", warnings),
    diagnosticLine("Retrieval", retrieval.engine || current.engine),
    diagnosticLine("Terms", retrieval.query_terms),
    diagnosticLine("LLM", llm.attempted === true ? "attempted" : "not attempted"),
    diagnosticLine("Provider", llm.provider),
    diagnosticLine("Model", llm.model || current.model),
    diagnosticLine("Endpoint", llm.endpoint),
    diagnosticLine("Status", String(llm.status || "").replaceAll("_", " ")),
    diagnosticLine("HTTP", llm.response?.http_status),
    diagnosticLine("Duration", llm.duration_ms !== undefined ? `${llm.duration_ms} ms` : ""),
    diagnosticLine("Prompt", llm.request?.prompt_chars ? `${llm.request.prompt_chars} chars` : ""),
    diagnosticLine("Evidence", llm.request?.evidence_count),
    diagnosticLine("Error", llm.error_message),
    diagnosticLine("Response", llm.response?.body_excerpt || llm.response?.content_excerpt)
  ].join("");
  return `
    <details class="ask-diagnostics" ${origin !== "llm" || warnings.length ? "open" : ""}>
      <summary>Diagnostics <span>${escapeHtml(askOriginLabel(origin))}</span></summary>
      <div class="ask-diagnostics-body">${rows}</div>
    </details>
  `;
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
      ${renderAskDiagnostics(current)}
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
  const duplicate = capture.status === "duplicate" && Boolean(capture.duplicate);
  els.capture.classList.toggle("hidden", Boolean(capture.running) || duplicate);
  els.stopCapture.classList.toggle("hidden", !capture.running);
  els.duplicateActions.classList.toggle("hidden", !duplicate);
  setProgress(capture.status || "idle", capture.message || (tab.capturable === false ? "Open a YouTube video or article tab first." : "Ready."));
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

async function replaceExisting() {
  els.replaceExisting.disabled = true;
  setProgress("queued", "Preparing replacement capture.");
  try {
    const response = await sendMessage({ type: "replace-capture" });
    if (response?.ok && response.state) render(response.state);
  } finally {
    els.replaceExisting.disabled = false;
  }
}

async function keepExisting() {
  const response = await sendMessage({ type: "dismiss-duplicate" });
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
els.replaceExisting.addEventListener("click", replaceExisting);
els.keepExisting.addEventListener("click", keepExisting);
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
