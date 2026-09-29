// PagePilot — Background Service Worker (Chrome MV3)
chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((error) => console.error('[PagePilot] Side panel error:', error));
});
