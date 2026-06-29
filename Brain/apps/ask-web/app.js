const els = {
  answer: document.getElementById("answer"),
  answerMeta: document.getElementById("answerMeta"),
  answerSection: document.getElementById("answerSection"),
  askButton: document.getElementById("askButton"),
  connectionStatus: document.getElementById("connectionStatus"),
  diagnosticsBody: document.getElementById("diagnosticsBody"),
  diagnosticsDetails: document.getElementById("diagnosticsDetails"),
  diagnosticsSection: document.getElementById("diagnosticsSection"),
  diagnosticsSummary: document.getElementById("diagnosticsSummary"),
  error: document.getElementById("error"),
  form: document.getElementById("askForm"),
  question: document.getElementById("question"),
  sourceCount: document.getElementById("sourceCount"),
  sources: document.getElementById("sources"),
  sourcesSection: document.getElementById("sourcesSection")
};

function setConnection(state, text) {
  els.connectionStatus.dataset.state = state;
  els.connectionStatus.textContent = text;
}

function setError(message = "") {
  els.error.hidden = !message;
  els.error.textContent = message;
}

function uniqueSources(payload) {
  const items = [...(payload.sources || []), ...(payload.results || [])];
  const seen = new Set();
  return items.filter((item) => {
    const key = item.path || item.title || JSON.stringify(item);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function renderSources(items) {
  els.sources.replaceChildren();
  for (const item of items) {
    const source = document.createElement("article");
    source.className = "source";

    const title = document.createElement("h2");
    title.className = "source-title";
    title.textContent = item.title || item.path || "Source";
    source.appendChild(title);

    if (item.path) {
      const path = document.createElement("p");
      path.className = "source-path";
      path.textContent = item.path;
      source.appendChild(path);
    }

    if (item.snippet) {
      const snippet = document.createElement("p");
      snippet.className = "source-snippet";
      snippet.textContent = item.snippet;
      source.appendChild(snippet);
    }
    els.sources.appendChild(source);
  }
  els.sourceCount.textContent = String(items.length);
  els.sourcesSection.hidden = items.length === 0;
}

function originLabel(origin) {
  if (origin === "llm") return "Answered by LLM";
  if (origin === "sql_snippet") return "Answered from SQL snippets";
  return "No grounded answer";
}

function statusLabel(status) {
  return String(status || "unknown").replaceAll("_", " ");
}

function addDiagnosticRow(parent, label, value) {
  if (value === undefined || value === null || value === "") return;
  const row = document.createElement("div");
  row.className = "diagnostic-row";

  const key = document.createElement("dt");
  key.textContent = label;
  row.appendChild(key);

  const val = document.createElement("dd");
  val.textContent = Array.isArray(value) ? value.join(", ") : String(value);
  row.appendChild(val);

  parent.appendChild(row);
}

function renderDiagnostics(payload) {
  const diagnostics = payload.diagnostics || {};
  const llm = diagnostics.llm || {};
  const retrieval = diagnostics.retrieval || {};
  const origin = diagnostics.answer_origin || "";
  const warnings = payload.warnings || [];

  els.diagnosticsBody.replaceChildren();
  els.diagnosticsSummary.textContent = originLabel(origin);
  els.answerMeta.textContent = `${originLabel(origin)}${payload.model ? ` · ${payload.model}` : ""}`;

  const body = document.createElement("dl");
  body.className = "diagnostic-grid";

  addDiagnosticRow(body, "Answer source", originLabel(origin));
  addDiagnosticRow(body, "Fallback reason", diagnostics.fallback_reason);
  addDiagnosticRow(body, "Warnings", warnings);
  addDiagnosticRow(body, "Retrieval engine", retrieval.engine || payload.engine);
  addDiagnosticRow(body, "Query terms", retrieval.query_terms);
  addDiagnosticRow(body, "FTS query", retrieval.fts_query);
  addDiagnosticRow(body, "Candidates", retrieval.candidate_count);
  addDiagnosticRow(body, "Selected evidence", retrieval.selected_source_ids);
  addDiagnosticRow(body, "LLM attempted", llm.attempted === true ? "yes" : "no");
  addDiagnosticRow(body, "LLM provider", llm.provider);
  addDiagnosticRow(body, "LLM model", llm.model || payload.model);
  addDiagnosticRow(body, "LLM endpoint", llm.endpoint);
  addDiagnosticRow(body, "LLM status", statusLabel(llm.status));
  addDiagnosticRow(body, "Duration", llm.duration_ms !== undefined ? `${llm.duration_ms} ms` : "");
  addDiagnosticRow(body, "HTTP status", llm.response?.http_status);
  addDiagnosticRow(body, "Prompt size", llm.request?.prompt_chars ? `${llm.request.prompt_chars} chars` : "");
  addDiagnosticRow(body, "Evidence sent", llm.request?.evidence_count);
  addDiagnosticRow(body, "Response size", llm.response?.content_chars ? `${llm.response.content_chars} chars` : "");
  addDiagnosticRow(body, "LLM confidence", llm.response?.confidence || payload.confidence);
  addDiagnosticRow(body, "LLM source ids", llm.response?.source_ids);
  addDiagnosticRow(body, "Error type", llm.error_type);
  addDiagnosticRow(body, "Error message", llm.error_message);
  addDiagnosticRow(body, "Response excerpt", llm.response?.body_excerpt || llm.response?.content_excerpt);

  els.diagnosticsBody.appendChild(body);
  els.diagnosticsSection.hidden = false;
  els.diagnosticsDetails.open = origin !== "llm" || warnings.length > 0;
}

function renderAnswer(payload) {
  els.answer.textContent = payload.answer || "I couldn't find this in the Brain.";
  els.answerSection.hidden = false;
  renderDiagnostics(payload);
  renderSources(uniqueSources(payload));
}

async function checkConnection() {
  try {
    const response = await fetch("/health", { cache: "no-store" });
    if (!response.ok) throw new Error();
    setConnection("connected", "Mac connected");
  } catch (_error) {
    setConnection("offline", "Mac unavailable");
  }
}

async function ask(event) {
  event.preventDefault();
  const query = els.question.value.trim();
  if (!query) return;

  setError();
  els.askButton.disabled = true;
  els.askButton.textContent = "Thinking...";
  els.answerSection.hidden = true;
  els.diagnosticsSection.hidden = true;
  els.sourcesSection.hidden = true;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 130000);
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 5 }),
      signal: controller.signal
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Ask failed.");
    renderAnswer(payload);
    localStorage.setItem("aibrain:last-query", query);
    localStorage.setItem("aibrain:last-answer", JSON.stringify(payload));
    setConnection("connected", "Mac connected");
  } catch (error) {
    const message = error?.name === "AbortError"
      ? "The answer took too long. Try again."
      : error?.message || "Could not reach your Mac.";
    setError(message);
    setConnection("offline", "Mac unavailable");
  } finally {
    clearTimeout(timeout);
    els.askButton.disabled = false;
    els.askButton.textContent = "Ask";
  }
}

els.form.addEventListener("submit", ask);

const previousQuery = localStorage.getItem("aibrain:last-query");
const previousAnswer = localStorage.getItem("aibrain:last-answer");
if (previousQuery) els.question.value = previousQuery;
if (previousAnswer) {
  try {
    renderAnswer(JSON.parse(previousAnswer));
  } catch (_error) {
    localStorage.removeItem("aibrain:last-answer");
  }
}
checkConnection();
