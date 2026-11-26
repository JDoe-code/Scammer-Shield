chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "capture_and_open_scan_window") {
    chrome.tabs.captureVisibleTab(
      sender.tab.windowId,
      { format: "jpeg", quality: 85 },
      (dataUrl) => {
        if (chrome.runtime.lastError) {
          console.error("Capture error:", chrome.runtime.lastError.message);
          sendResponse({ success: false });
          return;
        }

        chrome.storage.local.set({ latestScreenshot: dataUrl }, () => {
          chrome.windows.create({
            url: chrome.runtime.getURL("result.html"),
            type: "popup",
            width: 800,
            height: 700
          });
          sendResponse({ success: true });
        });
      }
    );
    return true; // keep sendResponse alive asynchronously
  }
});