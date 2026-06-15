chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "extract-youtube-defuddle") return;

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
        duration: video?.duration || 0
      }
    });
  })().catch((error) => {
    sendResponse({ ok: false, error: error?.message || String(error) });
  });

  return true;
});
