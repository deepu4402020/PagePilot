// This event listener fires when the extension is first installed or updated.
chrome.runtime.onInstalled.addListener(() => {
  // We configure the side panel to open automatically when the user clicks the extension icon in the toolbar.
  // This provides a seamless, one-click experience without needing to use a popup menu.
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((error) => console.error("Error setting side panel behavior:", error));
  //hii i am comment
});
