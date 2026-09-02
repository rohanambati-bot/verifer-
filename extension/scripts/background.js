/* VisionClick Copilot - Background Service Worker */
chrome.runtime.onInstalled.addListener(() => {
    console.log('[VisionClick] Extension installed successfully.');
});

// Handle messages from content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    // 1. Capture tab pixels cleanly without canvas CORS issues
    if (request.action === 'CAPTURE_TAB') {
        const windowId = sender.tab ? sender.tab.windowId : null;
        chrome.tabs.captureVisibleTab(windowId, { format: 'jpeg', quality: 80 }, (dataUrl) => {
            if (chrome.runtime.lastError || !dataUrl) {
                sendResponse({ success: false, dataUrl: null });
            } else {
                sendResponse({ success: true, dataUrl: dataUrl });
            }
        });
        return true;
    }

    // 2. Perform backend analyze requests with extension host permissions (bypasses Mixed Content / CORS)
    if (request.action === 'ANALYZE_TASK') {
        const backendUrl = request.backendUrl || 'http://127.0.0.1:8001';
        fetch(`${backendUrl}/api/extension/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request.payload)
        })
        .then(async (res) => {
            if (!res.ok) {
                const text = await res.text();
                throw new Error(`Server ${res.status}: ${text}`);
            }
            return res.json();
        })
        .then((data) => {
            sendResponse({ success: true, data: data });
        })
        .catch((err) => {
            sendResponse({ success: false, error: err.message });
        });
        return true;
    }

    // 3. Health check with candidate URLs via background worker (avoids browser popup CORS)
    if (request.action === 'CHECK_HEALTH') {
        const url = request.url || 'http://127.0.0.1:8001';
        fetch(`${url}/api/status`, { method: 'GET' })
        .then(async (res) => {
            if (res.ok) {
                const data = await res.json();
                return sendResponse({ success: true, data: data });
            }
            sendResponse({ success: false, error: `HTTP ${res.status}` });
        })
        .catch((err) => {
            sendResponse({ success: false, error: err.message });
        });
        return true;
    }
});
