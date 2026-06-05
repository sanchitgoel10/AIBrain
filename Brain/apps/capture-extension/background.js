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
const STORAGE_KEY = "aiBrainUiState";

let uiState = {
  tab: null,
  capture: { status: "idle", message: "Ready.", running: false },
  ask: { status: "idle", query: "", answer: "", results: [], running: false },
  brainStatus: null
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

function badgeFor(status) {
  const badgeMap = {
    queued: ["ATB", "#155EEF"],
    capturing: ["ATB", "#7C3AED"],
    ingesting: ["ATB", "#0F766E"],
    maintenance: ["ATB", "#B45309"],
    done: ["ATB", "#16833A"],
    error: ["ERR", "#B42318"]
  };
  return badgeMap[status] || ["ATB", "#155EEF"];
}

async function loadState() {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  if (stored?.[STORAGE_KEY]) {
    uiState = { ...uiState, ...stored[STORAGE_KEY] };
  }
  return uiState;
}

async function saveState(patch = {}) {
  uiState = { ...uiState, ...patch };
  await chrome.storage.local.set({ [STORAGE_KEY]: uiState });
  const [text, color] = badgeFor(uiState.capture?.status);
  await chrome.action.setBadgeText({ text });
  await chrome.action.setBadgeBackgroundColor({ color });
  return uiState;
}

async function updateCapture(status, message, extra = {}) {
  await saveState({
    capture: {
      ...(uiState.capture || {}),
      ...extra,
      status,
      message,
      running: ["queued", "capturing", "ingesting", "maintenance"].includes(status),
      updatedAt: new Date().toISOString()
    }
  });
}

async function updateAsk(patch = {}) {
  await saveState({
    ask: {
      ...(uiState.ask || {}),
      ...patch,
      updatedAt: new Date().toISOString()
    }
  });
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

function articleScrollSnapshot() {
  function isWindowRoot(element) {
    return !element || element === window || element === document || element === document.body || element === document.documentElement || element === document.scrollingElement;
  }

  function candidateInfo(element, label) {
    const usesWindow = isWindowRoot(element);
    const root = usesWindow ? document.scrollingElement || document.documentElement || document.body : element;
    const viewport = Math.max(usesWindow ? window.innerHeight || 800 : root.clientHeight || 800, 500);
    const height = usesWindow
      ? Math.max(document.body?.scrollHeight || 0, document.documentElement?.scrollHeight || 0, root?.scrollHeight || 0)
      : root.scrollHeight || 0;
    const y = usesWindow ? window.scrollY || root?.scrollTop || 0 : root.scrollTop || 0;
    return {
      label,
      y,
      maxY: Math.max(height - viewport, 0),
      viewport,
      scrollMode: usesWindow ? "window" : "element"
    };
  }

  function scrollCandidates() {
    const root = document.scrollingElement || document.documentElement || document.body;
    const pointed = document.elementFromPoint(Math.floor(window.innerWidth / 2), Math.floor(window.innerHeight * 0.65));
    const ancestors = [];
    for (let node = pointed; node && node.nodeType === Node.ELEMENT_NODE; node = node.parentElement) {
      ancestors.push(node);
    }
    const elements = [
      window,
      root,
      ...ancestors,
      ...document.querySelectorAll("article, main, [role='main'], [data-testid*='article' i], [class*='article' i], [class*='story' i], [class*='content' i], div, section")
    ];
    const seen = new Set();
    return elements
      .filter((element) => {
        if (!element) return false;
        const key = element === window ? "window" : element;
        if (seen.has(key)) return false;
        seen.add(key);
        if (isWindowRoot(element)) return true;
        const rect = element.getBoundingClientRect();
        const scrollable = Math.max((element.scrollHeight || 0) - (element.clientHeight || 0), 0);
        const style = window.getComputedStyle(element);
        const overflowY = `${style.overflowY} ${style.overflow}`;
        return rect.height > 180 && rect.width > 280 && scrollable > 120 && (/(auto|scroll|overlay)/.test(overflowY) || scrollable > 500);
      })
      .map((element, index) => ({ element, label: element === window ? "window" : `${element.tagName?.toLowerCase() || "node"}-${index}` }))
      .sort((a, b) => candidateInfo(b.element, b.label).maxY - candidateInfo(a.element, a.label).maxY);
  }

  function articleEndVisible() {
    const contentRoot =
      document.querySelector("article") ||
      document.querySelector("[data-testid*='article' i]") ||
      document.querySelector("[class*='article' i]") ||
      document.querySelector("[class*='story' i]") ||
      document.querySelector("main") ||
      document.querySelector("[role='main']");
    const contentRect = contentRoot?.getBoundingClientRect();
    const viewportCenterX = window.innerWidth / 2;
    const contentLeft = contentRect && contentRect.width > 320 ? contentRect.left : window.innerWidth * 0.22;
    const contentRight = contentRect && contentRect.width > 320 ? contentRect.right : window.innerWidth * 0.78;
    const stopNodes = document.querySelectorAll(
      "footer, [id*='comment' i], [class*='comment' i], [id*='related' i], [class*='related' i], [id*='recommend' i], [class*='recommend' i], [id*='newsletter' i], [class*='newsletter' i], [aria-label*='comment' i]"
    );
    for (const node of stopNodes) {
      const rect = node.getBoundingClientRect();
      if (!rect || rect.height < 35 || rect.width < 240) continue;
      const intersectsArticleColumn =
        (rect.left <= viewportCenterX && rect.right >= viewportCenterX) ||
        (rect.left < contentRight && rect.right > contentLeft && rect.width > Math.min(420, window.innerWidth * 0.45));
      if (intersectsArticleColumn && rect.top > window.innerHeight * 0.18 && rect.top < window.innerHeight * 0.72) return true;
    }
    return false;
  }

  const best = scrollCandidates()[0] || { element: window, label: "window" };
  const info = candidateInfo(best.element, best.label);
  return {
    ...info,
    step: Math.max(Math.floor(info.viewport * 0.82), 350),
    articleEnded: articleEndVisible()
  };
}

async function advanceArticleScroll(step) {
  function isWindowRoot(element) {
    return !element || element === window || element === document || element === document.body || element === document.documentElement || element === document.scrollingElement;
  }

  function candidateInfo(element, label) {
    const usesWindow = isWindowRoot(element);
    const root = usesWindow ? document.scrollingElement || document.documentElement || document.body : element;
    const viewport = Math.max(usesWindow ? window.innerHeight || 800 : root.clientHeight || 800, 500);
    const height = usesWindow
      ? Math.max(document.body?.scrollHeight || 0, document.documentElement?.scrollHeight || 0, root?.scrollHeight || 0)
      : root.scrollHeight || 0;
    const y = usesWindow ? window.scrollY || root?.scrollTop || 0 : root.scrollTop || 0;
    return {
      element,
      label,
      y,
      maxY: Math.max(height - viewport, 0),
      viewport,
      scrollMode: usesWindow ? "window" : "element"
    };
  }

  function scrollCandidates() {
    const root = document.scrollingElement || document.documentElement || document.body;
    const pointed = document.elementFromPoint(Math.floor(window.innerWidth / 2), Math.floor(window.innerHeight * 0.65));
    const ancestors = [];
    for (let node = pointed; node && node.nodeType === Node.ELEMENT_NODE; node = node.parentElement) {
      ancestors.push(node);
    }
    const elements = [
      window,
      root,
      ...ancestors,
      ...document.querySelectorAll("article, main, [role='main'], [data-testid*='article' i], [class*='article' i], [class*='story' i], [class*='content' i], div, section")
    ];
    const seen = new Set();
    return elements
      .filter((element) => {
        if (!element) return false;
        const key = element === window ? "window" : element;
        if (seen.has(key)) return false;
        seen.add(key);
        if (isWindowRoot(element)) return true;
        const rect = element.getBoundingClientRect();
        const scrollable = Math.max((element.scrollHeight || 0) - (element.clientHeight || 0), 0);
        const style = window.getComputedStyle(element);
        const overflowY = `${style.overflowY} ${style.overflow}`;
        return rect.height > 180 && rect.width > 280 && scrollable > 120 && (/(auto|scroll|overlay)/.test(overflowY) || scrollable > 500);
      })
      .map((element, index) => ({ element, label: element === window ? "window" : `${element.tagName?.toLowerCase() || "node"}-${index}` }))
      .sort((a, b) => candidateInfo(b.element, b.label).maxY - candidateInfo(a.element, a.label).maxY);
  }

  function scrollElement(element, amount) {
    if (isWindowRoot(element)) {
      const root = document.scrollingElement || document.documentElement || document.body;
      window.scrollBy(0, amount);
      if (root) root.scrollTop = (root.scrollTop || 0) + amount;
      return;
    }
    element.scrollTop = (element.scrollTop || 0) + amount;
    if (typeof element.scrollBy === "function") element.scrollBy(0, amount);
  }

  function articleEndVisible() {
    const contentRoot =
      document.querySelector("article") ||
      document.querySelector("[data-testid*='article' i]") ||
      document.querySelector("[class*='article' i]") ||
      document.querySelector("[class*='story' i]") ||
      document.querySelector("main") ||
      document.querySelector("[role='main']");
    const contentRect = contentRoot?.getBoundingClientRect();
    const viewportCenterX = window.innerWidth / 2;
    const contentLeft = contentRect && contentRect.width > 320 ? contentRect.left : window.innerWidth * 0.22;
    const contentRight = contentRect && contentRect.width > 320 ? contentRect.right : window.innerWidth * 0.78;
    const stopNodes = document.querySelectorAll(
      "footer, [id*='comment' i], [class*='comment' i], [id*='related' i], [class*='related' i], [id*='recommend' i], [class*='recommend' i], [id*='newsletter' i], [class*='newsletter' i], [aria-label*='comment' i]"
    );
    for (const node of stopNodes) {
      const rect = node.getBoundingClientRect();
      if (!rect || rect.height < 35 || rect.width < 240) continue;
      const intersectsArticleColumn =
        (rect.left <= viewportCenterX && rect.right >= viewportCenterX) ||
        (rect.left < contentRight && rect.right > contentLeft && rect.width > Math.min(420, window.innerWidth * 0.45));
      if (intersectsArticleColumn && rect.top > window.innerHeight * 0.18 && rect.top < window.innerHeight * 0.72) return true;
    }
    return false;
  }

  function wheelNudge(amount) {
    const target = document.elementFromPoint(Math.floor(window.innerWidth / 2), Math.floor(window.innerHeight * 0.65)) || document.body;
    target.dispatchEvent(new WheelEvent("wheel", { deltaY: amount, bubbles: true, cancelable: true, view: window }));
  }

  const candidates = scrollCandidates();
  for (const candidate of candidates) {
    const before = candidateInfo(candidate.element, candidate.label);
    if (before.maxY <= 8 && before.scrollMode !== "window") continue;
    scrollElement(candidate.element, step);
    wheelNudge(step);
    await new Promise((resolve) => setTimeout(resolve, 180));
    const after = candidateInfo(candidate.element, candidate.label);
    if (Math.abs(after.y - before.y) > 8) {
      return {
        y: after.y,
        moved: true,
        maxY: after.maxY,
        viewport: after.viewport,
        step: Math.max(Math.floor(after.viewport * 0.82), 350),
        scrollMode: after.scrollMode,
        articleEnded: articleEndVisible()
      };
    }
  }

  wheelNudge(step);
  await new Promise((resolve) => setTimeout(resolve, 240));
  const fallback = candidateInfo(window, "window");
  return {
    y: fallback.y,
    moved: false,
    maxY: fallback.maxY,
    viewport: fallback.viewport,
    step: Math.max(Math.floor(fallback.viewport * 0.82), 350),
    scrollMode: fallback.scrollMode,
    articleEnded: articleEndVisible()
  };
}

function restoreArticleScroll(original) {
  const root = document.scrollingElement || document.documentElement || document.body;
  if (root) root.scrollTop = original?.y || 0;
  window.scrollTo(0, original?.y || 0);
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
  const initialResults = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: articleScrollSnapshot
  });
  const initial = initialResults?.[0]?.result || { y: 0, step: 650, scrollMode: "window" };
  const screenshots = [];
  let state = initial;
  let stagnantMoves = 0;
  await updateCapture("capturing", `Starting article screenshots using ${initial.scrollMode || "window"} scroll.`);
  for (let index = 0; index < MAX_ARTICLE_SCREENSHOTS; index += 1) {
    await sleep(index === 0 ? 250 : 500);
    const snapshotResults = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: articleScrollSnapshot
    });
    state = snapshotResults?.[0]?.result || state;
    await updateCapture("capturing", `Capturing article screenshot ${index + 1}/${MAX_ARTICLE_SCREENSHOTS} for OCR.`);
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    screenshots.push({ y: state.y || 0, scrollMode: state.scrollMode || "window", dataUrl });
    if (index >= 3 && state.articleEnded) break;
    if (index >= MAX_ARTICLE_SCREENSHOTS - 1) break;
    const advanceResults = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: advanceArticleScroll,
      args: [state.step || 650]
    });
    state = advanceResults?.[0]?.result || state;
    if (state.moved) {
      stagnantMoves = 0;
    } else {
      stagnantMoves += 1;
      if (stagnantMoves >= 2) break;
    }
    if (state.maxY > 0 && state.y >= state.maxY - 16) break;
  }
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: restoreArticleScroll,
    args: [initial]
  });
  await updateCapture("capturing", `Captured ${screenshots.length} article screenshots using ${initial.scrollMode || "window"} scroll.`);
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

  await updateCapture("capturing", "Direct text looked incomplete. Capturing screenshots for OCR.");
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
    await updateCapture(job.status, job.message || "AI Brain capture is running.", { bridgeJobId: jobId });
    if (job.status === "done") {
      await saveState({ brainStatus: job.brain_status || uiState.brainStatus });
      await updateCapture("done", `Saved ${job.path || "source note"} and linked ${job.ingest_path || "Wiki note"}.`, {
        path: job.path || "",
        ingestPath: job.ingest_path || ""
      });
      return;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "Capture failed");
    }
  }
  throw new Error("Capture is still running after 9 minutes. Check the bridge terminal.");
}

async function refreshContext() {
  const tab = await getActiveTab();
  const activeTabInfo = tab ? {
    id: tab.id,
    windowId: tab.windowId,
    title: tab.title || "",
    url: tab.url || "",
    kind: isYoutubeUrl(tab.url || "") ? "YouTube transcript" : "Article page",
    capturable: isCaptureUrl(tab.url || "")
  } : null;
  const capture = uiState.capture || {};
  const captureMatchesActiveTab = Boolean(capture.tabUrl && activeTabInfo?.url && capture.tabUrl === activeTabInfo.url);
  const displayTabInfo = capture.running && capture.tabUrl ? {
    title: capture.tabTitle || "Capture in progress",
    url: capture.tabUrl,
    kind: isYoutubeUrl(capture.tabUrl) ? "YouTube transcript" : "Article page",
    capturable: true
  } : activeTabInfo;
  const captureState = !capture.running && capture.tabUrl && activeTabInfo?.url && !captureMatchesActiveTab ? {
    status: "idle",
    message: "Ready to add this active tab.",
    running: false,
    tabUrl: "",
    tabTitle: "",
    bridgeJobId: "",
    path: "",
    ingestPath: "",
    updatedAt: new Date().toISOString()
  } : capture;
  await saveState({ tab: displayTabInfo, capture: captureState });
  try {
    const response = await fetch(BRAIN_STATUS_URL);
    const payload = await response.json().catch(() => ({}));
    if (response.ok && payload.ok) await saveState({ brainStatus: payload.brain_status });
  } catch (_error) {
    await saveState({ brainStatus: null });
  }
  return uiState;
}

async function startCapture() {
  if (uiState.capture?.running) return;
  await refreshContext();
  const tab = await getActiveTab();
  const url = tab?.url || "";
  if (!isCaptureUrl(url)) {
    await updateCapture("error", "Open a YouTube video or article tab first.", { running: false });
    return;
  }

  try {
    await updateCapture("queued", "Preparing active tab.", { tabUrl: url, tabTitle: tab.title || "" });
    const page = await getArticlePayload(tab);
    if (page) {
      const screenshotCount = Array.isArray(page.screenshots) ? page.screenshots.length : 0;
      if (screenshotCount) {
        await updateCapture("queued", `Captured ${screenshotCount} screenshots. Sending to OCR.`);
      } else {
        await updateCapture("queued", `Using direct article text (${page.textLength.toLocaleString()} characters).`);
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
    await updateCapture("error", `${error.message} Start scripts/run_capture_bridge.sh and reload the extension if needed.`, { running: false });
  }
}

async function askBrain(query) {
  if (!query || uiState.ask?.running) return;
  await updateAsk({ status: "searching", query, answer: "", results: [], running: true, error: "" });
  try {
    const response = await fetch(`${ASK_URL}?query=${encodeURIComponent(query)}`);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Search failed");
    await updateAsk({
      status: "done",
      query,
      answer: payload.answer || "",
      results: payload.sources || payload.results || [],
      running: false,
      error: ""
    });
  } catch (error) {
    await updateAsk({ status: "error", query, answer: "", results: [], running: false, error: error.message });
  }
}

async function resetSemanticCounter() {
  const response = await fetch(SEMANTIC_RESET_URL, { method: "POST" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Reset failed");
  await saveState({ brainStatus: payload.brain_status || null });
}

async function revealSource(path) {
  if (!path) return;
  await fetch(`${OPEN_SOURCE_URL}?path=${encodeURIComponent(path)}`);
}

async function brainWindowBounds() {
  const width = 390;
  const height = 500;
  const edgeMargin = 12;
  const topOffset = 48;
  const browserWindow = await chrome.windows.getLastFocused({ windowTypes: ["normal"] }).catch(() => null);
  if (!browserWindow) return { width, height };
  return {
    width,
    height,
    left: Math.max((browserWindow.left || 0) + edgeMargin, (browserWindow.left || 0) + (browserWindow.width || width) - width - edgeMargin),
    top: Math.max((browserWindow.top || 0) + edgeMargin, (browserWindow.top || 0) + topOffset)
  };
}

chrome.action.onClicked.addListener(async () => {
  await loadState();
  if (!uiState.capture?.running) await refreshContext();
  const url = chrome.runtime.getURL("popup.html");
  const windows = await chrome.windows.getAll({ populate: true, windowTypes: ["popup"] });
  const existing = windows.find((win) =>
    (win.tabs || []).some((tab) => (tab.url || "").startsWith(url))
  );
  const bounds = await brainWindowBounds();
  if (existing?.id) {
    await chrome.windows.update(existing.id, { ...bounds, focused: true });
    return;
  }
  await chrome.windows.create({
    url,
    type: "popup",
    ...bounds,
    focused: true
  });
});

chrome.tabs.onActivated.addListener(() => {
  if (!uiState.capture?.running) refreshContext().catch(() => {});
});

chrome.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
  if (!tab.active || uiState.capture?.running) return;
  if (changeInfo.url || changeInfo.title || changeInfo.status === "complete") {
    refreshContext().catch(() => {});
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    await loadState();
    if (message?.type === "get-state") {
      await refreshContext();
      sendResponse({ ok: true, state: uiState });
      return;
    }
    if (message?.type === "start-capture") {
      startCapture();
      sendResponse({ ok: true, state: uiState });
      return;
    }
    if (message?.type === "ask") {
      askBrain(String(message.query || "").trim());
      sendResponse({ ok: true, state: uiState });
      return;
    }
    if (message?.type === "reset-semantic") {
      await resetSemanticCounter();
      sendResponse({ ok: true, state: uiState });
      return;
    }
    if (message?.type === "reveal-source") {
      await revealSource(message.path || "");
      sendResponse({ ok: true, state: uiState });
      return;
    }
    sendResponse({ ok: false, error: "Unknown message" });
  })().catch((error) => sendResponse({ ok: false, error: error.message }));
  return true;
});

loadState().then(() => refreshContext()).catch(() => {});
