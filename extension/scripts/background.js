/* VisionClick Copilot - Background Service Worker */
chrome.runtime.onInstalled.addListener(() => {
    console.log('[VisionClick] Extension installed successfully.');
});

// Handle tab screen capture requests from content script to bypass canvas CORS
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'CAPTURE_TAB') {
        const windowId = sender.tab ? sender.tab.windowId : null;
        chrome.tabs.captureVisibleTab(windowId, { format: 'jpeg', quality: 80 }, (dataUrl) => {
            if (chrome.runtime.lastError || !dataUrl) {
                sendResponse({ success: false, dataUrl: null });
            } else {
                sendResponse({ success: true, dataUrl: dataUrl });
            }
        });
        return true; // Keep message channel open for async response
    }
});
