chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "extract-youtube-defuddle") return;

  function isoDurationSeconds(value) {
    const match = String(value || "").match(/^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$/i);
    if (!match) return 0;
    return Number(match[1] || 0) * 3600 + Number(match[2] || 0) * 60 + Number(match[3] || 0);
  }

  function youtubeDurationSeconds(video) {
    if (Number.isFinite(video?.duration) && video.duration > 0) return video.duration;

    for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const parsed = JSON.parse(script.textContent || "null");
        const items = Array.isArray(parsed) ? parsed : [parsed];
        const videoData = items.find((item) => item?.["@type"] === "VideoObject" && item.duration);
        const duration = isoDurationSeconds(videoData?.duration);
        if (duration > 0) return duration;
      } catch (_error) {
        // Continue to YouTube's inline player metadata.
      }
    }

    for (const script of document.scripts) {
      const match = (script.textContent || "").match(/"lengthSeconds"\s*:\s*"(\d+)"/);
      if (match) return Number(match[1] || 0);
    }
    return 0;
  }

  (async () => {
    if (!globalThis.Defuddle) throw new Error("Defuddle is not loaded.");
    const parsed = await Promise.race([
      new globalThis.Defuddle(document, { url: location.href }).parseAsync(),
      new Promise((_, reject) => setTimeout(() => reject(new Error("Defuddle timed out.")), 10000))
    ]);
    const variables = parsed?.variables || {};
    const video = document.querySelector("video");
    sendResponse({
      ok: true,
      data: {
        title: variables.title || document.title.replace(/\s*-\s*YouTube\s*$/, ""),
        author: variables.author || "",
        language: variables.language || "",
        transcript: variables.transcript || "",
        currentTime: video?.currentTime || 0,
        duration: youtubeDurationSeconds(video)
      }
    });
  })().catch((error) => {
    sendResponse({ ok: false, error: error?.message || String(error) });
  });

  return true;
});
