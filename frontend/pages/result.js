chrome.storage.local.get("latestScreenshot", ({ latestScreenshot }) => {
  const img = document.getElementById("screenshot");
  if (latestScreenshot) {
    img.src = latestScreenshot;
  } else {
    img.hidden = true;
    document.getElementById("empty").hidden = false;
  }
});