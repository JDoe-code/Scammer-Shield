function isEmailOpen() {
  // An open email has a message body inside Gmail's main pane
  return !!document.querySelector('div[role="main"] .a3s');
}

function updateButtonVisibility() {
  const container = document.querySelector(".right-corder-container");
  if (!container) return;
  container.classList.toggle("scanner-hidden", !isEmailOpen());
}

function injectScannerButton() {
  if (document.querySelector(".right-corder-container")) return;

  const container = document.createElement("div");
  container.className = "right-corder-container scanner-hidden";

  const button = document.createElement("button");
  button.className = "right-corder-container-button";
  button.type = "button";

  const shortText = document.createElement("span");
  shortText.className = "short-text";
  shortText.textContent = "+";

  const longText = document.createElement("span");
  longText.className = "long-text";
  longText.textContent = "Scan";

  button.append(shortText, longText);
  container.appendChild(button);
  document.body.appendChild(container);

  button.addEventListener("mouseenter", () => {
    longText.classList.add("show-long-text");
  });

  button.addEventListener("mouseleave", () => {
    longText.classList.remove("show-long-text");
  });

  button.addEventListener("click", async () => {
    if (!chrome.runtime?.id) {
      console.warn("Extension context invalidated. Please refresh Gmail.");
      return;
    }

    container.style.setProperty("display", "none", "important");

    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    await new Promise((r) => setTimeout(r, 150));

    const target =
      document.querySelector('div[role="main"]') ||
      document.querySelector(".a3s") ||
      document.body;
    const r = target.getBoundingClientRect();

    try {
      await chrome.runtime.sendMessage({
        action: "capture_and_open_scan_window",
        rect: { left: r.left, top: r.top, right: r.right, bottom: r.bottom },
        viewport: { w: window.innerWidth, h: window.innerHeight }
      });
    } catch (error) {
      console.error("Failed to start scan:", error);
    } finally {
      container.style.removeProperty("display");
    }
  });

  updateButtonVisibility();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", injectScannerButton);
} else {
  injectScannerButton();
}

// Gmail is a single-page app, so re-check whenever the page changes.
// The check is debounced because Gmail updates its DOM constantly.
let checkTimer = null;
function scheduleCheck() {
  clearTimeout(checkTimer);
  checkTimer = setTimeout(() => {
    injectScannerButton();        // re-add the button if Gmail removed it
    updateButtonVisibility();
  }, 150);
}

window.addEventListener("hashchange", scheduleCheck);

const observer = new MutationObserver(scheduleCheck);
if (document.body) {
  observer.observe(document.body, { childList: true, subtree: true });
}