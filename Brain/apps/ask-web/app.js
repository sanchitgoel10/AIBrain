const els = {
  answer: document.getElementById("answer"),
  answerMeta: document.getElementById("answerMeta"),
  answerSection: document.getElementById("answerSection"),
  askButton: document.getElementById("askButton"),
  connectionStatus: document.getElementById("connectionStatus"),
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

function renderAnswer(payload) {
  els.answer.textContent = payload.answer || "I couldn't find this in the Brain.";
  els.answerMeta.textContent = payload.model || payload.engine || "";
  els.answerSection.hidden = false;
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
