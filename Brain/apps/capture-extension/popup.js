const BRIDGE_URL = "http://127.0.0.1:8765/capture";
const STATUS_URL = "http://127.0.0.1:8765/status";
const BRAIN_STATUS_URL = "http://127.0.0.1:8765/brain-status";
const SEMANTIC_RESET_URL = "http://127.0.0.1:8765/semantic-reset";
const ASK_URL = "http://127.0.0.1:8765/ask";
const OPEN_SOURCE_URL = "http://127.0.0.1:8765/open-source";
const MAX_ARTICLE_SCREENSHOTS = 30;
const SCREENSHOT_PRIMARY_HOSTS = ["the-ken.com", "ft.com"];
const DIRECT_TEXT_MIN_CHARS = 1800;
const DIRECT_TEXT_GOOD_CHARS = 4500;

const state = {
  tab: null
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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isCaptureUrl(url) {
  return /^https?:\/\//i.test(url || "");
}

function isYoutubeUrl(url) {
  return /(^https?:\/\/)?([^/]+\.)?(youtube\.com\/watch|youtu\.be\/)/i.test(url || "");
}

function hostnameFor(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch (_error) {
    return "";
  }
}

function hasBlockerText(text) {
  return /subscribe|sign in|log in|unlock|members only|continue reading|already a subscriber|paywall/.test(String(text || "").toLowerCase());
}

function shouldPreferScreenshotOcr(tab, page) {
  const hostname = hostnameFor(tab?.url || "");
  if (SCREENSHOT_PRIMARY_HOSTS.some((host) => hostname === host || hostname.endsWith(`.${host}`))) {
    return true;
  }
  const text = String(page?.text || "");
  return hasBlockerText(text) && text.length < DIRECT_TEXT_GOOD_CHARS;
}

function directExtractionLooksComplete(page) {
  const text = String(page?.text || "").trim();
  if (text.length < DIRECT_TEXT_MIN_CHARS) return false;
  if (hasBlockerText(text) && text.length < DIRECT_TEXT_GOOD_CHARS) return false;
  return true;
}

function setProgress(status, message) {
  els.progress.className = `progress-bar ${status || "idle"}`;
  els.status.textContent = message || "Ready.";
  const badgeMap = {
    queued: ["ATB", "#155EEF"],
    capturing: ["ATB", "#7C3AED"],
    ingesting: ["ATB", "#0F766E"],
    maintenance: ["ATB", "#B45309"],
    done: ["ATB", "#16833A"],
    error: ["ERR", "#B42318"]
  };
  const [text, color] = badgeMap[status] || ["ATB", "#155EEF"];
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
}

function setMode(mode) {
  const ask = mode === "ask";
  els.addPanel.classList.toggle("hidden", ask);
  els.askPanel.classList.toggle("hidden", !ask);
  els.tabAdd.classList.toggle("active", !ask);
  els.tabAsk.classList.toggle("active", ask);
  if (ask) els.askQuery.focus();
}

function updateBrainStatus(status) {
  if (!status) return;
  const count = status.captures_since_compile || 0;
  const threshold = status.semantic_threshold || 10;
  els.compileCard.classList.toggle("due", Boolean(status.semantic_due));
  if (status.semantic_due) {
    els.compileStatus.textContent = `${count}/${threshold} captures. Run Codex semantic compile.`;
  } else {
    els.compileStatus.textContent = `${count}/${threshold} captures since semantic compile.`;
  }
}

async function refreshBrainStatus() {
  try {
    const response = await fetch(BRAIN_STATUS_URL);
    const payload = await response.json().catch(() => ({}));
    if (response.ok && payload.ok) updateBrainStatus(payload.brain_status);
  } catch (_error) {
    els.compileStatus.textContent = "Bridge not available.";
  }
}

function renderAskResponse(payload) {
  const answer = (payload.answer || "").trim();
  if (answer) {
    els.askAnswer.classList.remove("hidden");
    els.askAnswer.innerHTML = `
      <div class="answer-label">Answer</div>
      <div class="answer-text">${escapeHtml(answer)}</div>
    `;
  } else {
    els.askAnswer.classList.add("hidden");
    els.askAnswer.innerHTML = "";
  }
  renderAskResults(payload.sources || payload.results || []);
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function extractVisiblePage() {
  const pick = (...selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const value = node?.content || node?.textContent;
      if (value && value.trim()) return value.trim();
    }
    return "";
  };
  const article =
    document.querySelector("article") ||
    document.querySelector("main") ||
    document.querySelector("[role='main']") ||
    document.body;
  const text = (article?.innerText || document.body.innerText || "")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim()
    .slice(0, 300000);
  return {
    title: pick("meta[property='og:title']", "meta[name='twitter:title']") || document.title,
    author: pick("meta[name='author']", "meta[property='article:author']", "[rel='author']"),
    date: pick("meta[property='article:published_time']", "meta[name='date']", "time[datetime]"),
    excerpt: pick("meta[name='description']", "meta[property='og:description']", "meta[name='twitter:description']") || text.slice(0, 700),
    text,
    textLength: text.length
  };
}

function articleScrollPlan() {
  function isWindowScrollRoot(element) {
    return !element || element === document.body || element === document.documentElement || element === document.scrollingElement;
  }

  function findScrollRoot() {
    const documentRoot = document.scrollingElement || document.documentElement || document.body;
    const candidates = [documentRoot, ...document.querySelectorAll("main, article, [role='main'], div, section")];
    let best = documentRoot;
    let bestScrollable = Math.max((documentRoot?.scrollHeight || 0) - (window.innerHeight || documentRoot?.clientHeight || 0), 0);
    for (const candidate of candidates) {
      if (!candidate || candidate === document.body || candidate === document.documentElement) continue;
      const style = window.getComputedStyle(candidate);
      const overflowY = `${style.overflowY} ${style.overflow}`;
      const scrollable = Math.max((candidate.scrollHeight || 0) - (candidate.clientHeight || 0), 0);
      const visibleEnough = candidate.clientHeight > 250 && candidate.clientWidth > 280;
      const canScroll = /(auto|scroll|overlay)/.test(overflowY) || scrollable > 500;
      if (visibleEnough && canScroll && scrollable > bestScrollable) {
        best = candidate;
        bestScrollable = scrollable;
      }
    }
    return best;
  }

  const scrollRoot = findScrollRoot();
  const usesWindow = isWindowScrollRoot(scrollRoot);
  const height = usesWindow
    ? Math.max(document.body?.scrollHeight || 0, document.documentElement?.scrollHeight || 0)
    : scrollRoot.scrollHeight;
  const viewport = Math.max(usesWindow ? window.innerHeight || 800 : scrollRoot.clientHeight || 800, 500);
  const maxY = Math.max(height - viewport, 0);
  const step = Math.max(Math.floor(viewport * 0.82), 350);
  const article =
    document.querySelector("article") ||
    document.querySelector("[data-testid*='article']") ||
    document.querySelector(".article-body") ||
    document.querySelector(".story-content") ||
    document.querySelector(".post-content") ||
    document.querySelector("main") ||
    document.querySelector("[role='main']");
  const rect = article?.getBoundingClientRect();
  let startY = 0;
  let endY = maxY;
  if (rect && rect.height > viewport * 1.2) {
    startY = Math.max(0, Math.floor(rect.top + window.scrollY - 80));
    const articleBottom = Math.floor(rect.bottom + window.scrollY);
    endY = Math.max(startY, Math.min(maxY, articleBottom - Math.floor(viewport * 0.85)));
  }
  const stopNodes = document.querySelectorAll(
    "footer, [id*='comment' i], [class*='comment' i], [id*='related' i], [class*='related' i], [id*='recommend' i], [class*='recommend' i], [id*='newsletter' i], [class*='newsletter' i]"
  );
  for (const stopNode of stopNodes) {
    const stopRect = stopNode.getBoundingClientRect();
    if (!stopRect || stopRect.height < 40) continue;
    const stopTop = Math.floor(stopRect.top + window.scrollY);
    if (stopTop > startY + viewport && stopTop < endY + viewport) {
      endY = Math.max(startY, Math.min(endY, stopTop - viewport));
      break;
    }
  }
  const positions = [];
  for (let y = startY; y <= endY; y += step) {
    positions.push(y);
    if (positions.length >= MAX_ARTICLE_SCREENSHOTS) break;
  }
  if (!positions.includes(endY) && positions.length < MAX_ARTICLE_SCREENSHOTS) {
    positions.push(endY);
  }
  return {
    originalY: window.scrollY || 0,
    originalElementY: usesWindow ? 0 : scrollRoot.scrollTop || 0,
    positions: [...new Set(positions)],
    startY,
    endY,
    scrollMode: usesWindow ? "window" : "element",
    title: document.title
  };
}

function scrollToCapturePosition(y) {
  function isWindowScrollRoot(element) {
    return !element || element === document.body || element === document.documentElement || element === document.scrollingElement;
  }

  function findScrollRoot() {
    const documentRoot = document.scrollingElement || document.documentElement || document.body;
    const candidates = [documentRoot, ...document.querySelectorAll("main, article, [role='main'], div, section")];
    let best = documentRoot;
    let bestScrollable = Math.max((documentRoot?.scrollHeight || 0) - (window.innerHeight || documentRoot?.clientHeight || 0), 0);
    for (const candidate of candidates) {
      if (!candidate || candidate === document.body || candidate === document.documentElement) continue;
      const style = window.getComputedStyle(candidate);
      const overflowY = `${style.overflowY} ${style.overflow}`;
      const scrollable = Math.max((candidate.scrollHeight || 0) - (candidate.clientHeight || 0), 0);
      const visibleEnough = candidate.clientHeight > 250 && candidate.clientWidth > 280;
      const canScroll = /(auto|scroll|overlay)/.test(overflowY) || scrollable > 500;
      if (visibleEnough && canScroll && scrollable > bestScrollable) {
        best = candidate;
        bestScrollable = scrollable;
      }
    }
    return best;
  }

  const scrollRoot = findScrollRoot();
  if (isWindowScrollRoot(scrollRoot)) {
    window.scrollTo(0, y);
    return { y: window.scrollY || y, mode: "window" };
  }
  scrollRoot.scrollTo(0, y);
  return { y: scrollRoot.scrollTop || y, mode: "element" };
}

async function getActiveTab() {
  const queries = [
    { active: true, currentWindow: true },
    { active: true, lastFocusedWindow: true },
    { active: true }
  ];
  for (const query of queries) {
    const tabs = await chrome.tabs.query(query);
    const tab = tabs.find((item) => isCaptureUrl(item?.url || ""));
    if (tab) return tab;
  }

  const windows = await chrome.windows.getAll({ populate: true, windowTypes: ["normal"] });
  const focused = windows.find((item) => item.focused);
  const ordered = focused ? [focused, ...windows.filter((item) => item.id !== focused.id)] : windows;
  for (const win of ordered) {
    const tab = (win.tabs || []).find((item) => item.active && isCaptureUrl(item.url || ""));
    if (tab) return tab;
  }

  const tabs = await chrome.tabs.query({});
  return tabs
    .filter((item) => isCaptureUrl(item.url || ""))
    .sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0))[0] || null;
}

async function captureArticleScreenshots(tab) {
  const planResults = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: articleScrollPlan
  });
  const plan = planResults?.[0]?.result || { positions: [0], originalY: 0 };
  const screenshots = [];
  const positions = (plan.positions || [0]).slice(0, MAX_ARTICLE_SCREENSHOTS);
  setProgress("capturing", `Planned ${positions.length} article screenshots using ${plan.scrollMode || "window"} scroll.`);
  for (let index = 0; index < positions.length; index += 1) {
    const y = positions[index];
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: scrollToCapturePosition,
      args: [y]
    });
    await sleep(450);
    setProgress("capturing", `Capturing article screenshot ${index + 1}/${positions.length} for OCR.`);
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    screenshots.push({ y, dataUrl });
  }
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: scrollToCapturePosition,
    args: [plan.scrollMode === "element" ? plan.originalElementY || 0 : plan.originalY || 0]
  });
  return screenshots;
}

async function getArticlePayload(tab) {
  if (isYoutubeUrl(tab?.url || "")) return null;
  let page = null;
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractVisiblePage
    });
    page = results?.[0]?.result || null;
  } catch (error) {
    page = {
      title: tab.title || "Article",
      author: "",
      date: "",
      excerpt: "",
      text: "",
      textLength: 0,
      extractionError: error.message
    };
  }
  const useScreenshotAsPrimary = shouldPreferScreenshotOcr(tab, page);
  const canUseDirect = !useScreenshotAsPrimary && directExtractionLooksComplete(page);
  if (canUseDirect) {
    page.extractionMethod = "browser-dom";
    page.discardDomTextForOcr = false;
    page.captureDecision = "direct";
    return page;
  }

  setProgress("capturing", "Direct text looked incomplete. Capturing screenshots for OCR.");
  page = page || { title: tab.title || "Article", author: "", date: "", excerpt: "", text: "", textLength: 0 };
  page.screenshots = await captureArticleScreenshots(tab);
  page.extractionMethod = "screenshot-ocr";
  page.discardDomTextForOcr = useScreenshotAsPrimary;
  page.captureDecision = "fallback-ocr";
  return page;
}

async function pollJob(jobId) {
  for (let attempt = 0; attempt < 360; attempt += 1) {
    await sleep(1500);
    const response = await fetch(`${STATUS_URL}?job_id=${encodeURIComponent(jobId)}`);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Status returned HTTP ${response.status}`);
    }
    const job = payload.job || {};
    setProgress(job.status, job.message || "AI Brain capture is running.");
    if (job.status === "done") {
      setProgress("done", `Saved ${job.path || "source note"} and linked ${job.ingest_path || "Wiki note"}.`);
      updateBrainStatus(job.brain_status);
      return;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "Capture failed");
    }
  }
  throw new Error("Capture is still running after 9 minutes. Check the bridge terminal.");
}

async function resetSemanticCounter() {
  els.resetCompile.disabled = true;
  try {
    const response = await fetch(SEMANTIC_RESET_URL, { method: "POST" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Reset failed");
    updateBrainStatus(payload.brain_status);
  } catch (_error) {
    els.compileStatus.textContent = "Could not reset counter.";
  } finally {
    els.resetCompile.disabled = false;
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
  try {
    const response = await fetch(`${ASK_URL}?query=${encodeURIComponent(query)}`);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Search failed");
    renderAskResponse(payload);
  } catch (error) {
    els.askResults.innerHTML = `<div class="result"><div class="result-title">${escapeHtml(error.message)}</div></div>`;
  } finally {
    els.askSubmit.disabled = false;
  }
}

async function revealSource(path) {
  if (!path) return;
  await fetch(`${OPEN_SOURCE_URL}?path=${encodeURIComponent(path)}`);
}

async function startCapture() {
  const tab = state.tab;
  const url = tab?.url || "";
  if (!isCaptureUrl(url)) {
    setProgress("error", "This tab does not have a normal http/https URL.");
    return;
  }

  els.capture.disabled = true;
  try {
    setProgress("queued", "Preparing active tab.");
    const page = await getArticlePayload(tab);
    if (page) {
      const screenshotCount = Array.isArray(page.screenshots) ? page.screenshots.length : 0;
      if (screenshotCount) {
        setProgress("queued", `Captured ${screenshotCount} screenshots. Sending to OCR.`);
      } else {
        setProgress("queued", `Using direct article text (${page.textLength.toLocaleString()} characters).`);
      }
    }
    const response = await fetch(BRIDGE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title: tab.title || "", page })
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Bridge returned HTTP ${response.status}`);
    }
    await pollJob(payload.job_id);
  } catch (error) {
    setProgress("error", `${error.message} Start scripts/run_capture_bridge.sh and reload the extension if needed.`);
  } finally {
    els.capture.disabled = false;
  }
}

async function init() {
  chrome.action.setBadgeText({ text: "ATB" });
  chrome.action.setBadgeBackgroundColor({ color: "#155EEF" });
  state.tab = await getActiveTab();
  const tab = state.tab;
  els.title.textContent = tab?.title || "No active tab";
  els.url.textContent = tab?.url || "";
  els.kind.textContent = isYoutubeUrl(tab?.url || "") ? "YouTube transcript" : "Article page";
  if (!isCaptureUrl(tab?.url || "")) {
    els.capture.disabled = true;
    setProgress("error", "Open a YouTube video or article tab first.");
  } else {
    setProgress("queued", "Ready to add this active tab.");
  }
  await refreshBrainStatus();
}

els.capture.addEventListener("click", startCapture);
els.resetCompile.addEventListener("click", resetSemanticCounter);
els.tabAdd.addEventListener("click", () => setMode("add"));
els.tabAsk.addEventListener("click", () => setMode("ask"));
els.askForm.addEventListener("submit", askBrain);
els.askResults.addEventListener("click", (event) => {
  const button = event.target.closest("[data-path]");
  if (button) revealSource(button.dataset.path || "");
});
init();
