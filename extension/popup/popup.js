/* VisionClick Copilot - Popup Script */
(function() {
    'use strict';

    let activeBackendUrl = 'http://127.0.0.1:8000';
    const CANDIDATE_URLS = [
        'http://127.0.0.1:8000',
        'http://127.0.0.1:8001',
        'http://localhost:8000',
        'http://localhost:8001'
    ];

    const backendStatusEl = document.getElementById('backend-status');
    const backendTextEl = document.getElementById('backend-text');
    const backendUrlEl = document.getElementById('backend-url');
    const btnAnalyze = document.getElementById('btn-analyze');
    const btnText = document.getElementById('btn-text');
    const btnAutopilot = document.getElementById('btn-autopilot');
    const autopilotText = document.getElementById('autopilot-text');
    const loopDelayInput = document.getElementById('loop-delay-input');
    const autoSelectToggle = document.getElementById('auto-select-toggle');
    const autoSubmitToggle = document.getElementById('auto-submit-toggle');
    const statusMessageEl = document.getElementById('status-message');
    const resultsListEl = document.getElementById('results-list');
    const resultsCountEl = document.getElementById('results-count');

    let currentTabOrigin = '';
    let currentTabId = null;

    // Load saved preferences and check active tab origin
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const tab = tabs && tabs[0];
        if (tab && tab.url) {
            try {
                currentTabOrigin = new URL(tab.url).origin;
                currentTabId = tab.id;
            } catch (e) {}
        }

        chrome.storage.local.get(['autoSelect', 'autoSubmit', 'loopDelay', 'autopilotRunning', 'autopilotOrigin', 'backendUrl'], (res) => {
            if (typeof res.autoSelect === 'boolean') autoSelectToggle.checked = res.autoSelect;
            if (typeof res.autoSubmit === 'boolean') autoSubmitToggle.checked = res.autoSubmit;
            if (res.loopDelay) loopDelayInput.value = res.loopDelay;
            if (res.backendUrl) {
                activeBackendUrl = res.backendUrl;
                if (backendUrlEl) backendUrlEl.textContent = activeBackendUrl;
            }
            // Strictly check if autopilot is active on THIS tab's origin
            if (res.autopilotRunning && res.autopilotOrigin && res.autopilotOrigin === currentTabOrigin) {
                setAutopilotUI(true);
            } else {
                setAutopilotUI(false);
            }
            checkBackendHealth();
        });
    });

    autoSelectToggle.addEventListener('change', () => {
        chrome.storage.local.set({ autoSelect: autoSelectToggle.checked });
    });

    autoSubmitToggle.addEventListener('change', () => {
        chrome.storage.local.set({ autoSubmit: autoSubmitToggle.checked });
    });

    loopDelayInput.addEventListener('change', () => {
        chrome.storage.local.set({ loopDelay: parseFloat(loopDelayInput.value) || 0.2 });
    });

    function setAutopilotUI(isRunning) {
        if (isRunning) {
            btnAutopilot.className = 'btn-autopilot running';
            autopilotText.textContent = '⏹ Stop Continuous Autopilot';
            showStatus('Autopilot Active on this website — analyzing & submitting tasks...', 'success');
        } else {
            btnAutopilot.className = 'btn-autopilot';
            autopilotText.textContent = '🤖 Start Continuous Autopilot';
        }
    }


    // Check backend health on load with auto-discovery across candidate ports
    async function checkBackendHealth() {
        const urlsToTry = [activeBackendUrl, ...CANDIDATE_URLS.filter(u => u !== activeBackendUrl)];
        for (const url of urlsToTry) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 1200);
                const res = await fetch(`${url}/api/status`, { method: 'GET', signal: controller.signal });
                clearTimeout(timeoutId);
                if (res.ok) {
                    const data = await res.json();
                    if (data && 'status' in data) {
                        activeBackendUrl = url;
                        chrome.storage.local.set({ backendUrl: activeBackendUrl });
                        backendStatusEl.className = 'backend-status online';
                        backendTextEl.textContent = 'Backend Online';
                        if (backendUrlEl) backendUrlEl.textContent = activeBackendUrl;
                        return true;
                    }
                }
            } catch (e) {
                // Try next
            }
        }
        backendStatusEl.className = 'backend-status offline';
        backendTextEl.textContent = 'Backend Offline';
        if (backendUrlEl) backendUrlEl.textContent = activeBackendUrl;
        return false;
    }


    function showStatus(message, type = 'info') {
        statusMessageEl.textContent = message;
        statusMessageEl.className = `status-message ${type}`;
    }

    function hideStatus() {
        statusMessageEl.className = 'status-message hidden';
    }

    function setLoading(isLoading) {
        btnAnalyze.disabled = isLoading;
        btnText.textContent = isLoading ? 'Analyzing Video...' : 'Analyze Active Page';
    }

    // Autopilot Toggle Button (Strictly Tab & Origin Scoped)
    btnAutopilot.addEventListener('click', async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab || !tab.id || !tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) {
            showStatus('Autopilot cannot run on internal browser pages.', 'error');
            return;
        }

        const tabOrigin = new URL(tab.url).origin;
        const { autopilotRunning = false, autopilotOrigin = '' } = await chrome.storage.local.get(['autopilotRunning', 'autopilotOrigin']);
        
        const isRunningOnThisOrigin = autopilotRunning && autopilotOrigin === tabOrigin;
        const newState = !isRunningOnThisOrigin;

        if (newState) {
            await chrome.storage.local.set({ 
                autopilotRunning: true, 
                autopilotOrigin: tabOrigin,
                autopilotTabId: tab.id
            });
            setAutopilotUI(true);
        } else {
            await chrome.storage.local.set({ 
                autopilotRunning: false, 
                autopilotOrigin: null,
                autopilotTabId: null
            });
            setAutopilotUI(false);
        }

        try {
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                files: ['scripts/content.js']
            });
        } catch (e) {}

        await chrome.tabs.sendMessage(tab.id, {
            action: newState ? 'START_AUTOPILOT' : 'STOP_AUTOPILOT',
            delay: parseFloat(loopDelayInput.value) || 0.2,
            autoSubmit: autoSubmitToggle.checked
        });
    });

    // Main single-analyze flow
    btnAnalyze.addEventListener('click', async () => {

        hideStatus();
        setLoading(true);

        const isOnline = await checkBackendHealth();
        if (!isOnline) {
            showStatus(`VisionClick server is not running on ${activeBackendUrl}. Start it with "python run.py --dashboard"`, 'error');
            setLoading(false);
            return;
        }

        try {
            // 1. Get active tab
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tab || !tab.id) {
                showStatus('Cannot access active tab.', 'error');
                setLoading(false);
                return;
            }

            // 2. Ensure content script is injected
            try {
                await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    files: ['scripts/content.js']
                });
            } catch (e) {
                console.warn('Content script already present or permission restricted:', e);
            }

            // 3. Extract page data from active tab
            showStatus('Extracting statements & video from page...', 'info');
            const pageData = await chrome.tabs.sendMessage(tab.id, { action: 'EXTRACT_PAGE_DATA' });

            if (!pageData || !pageData.statements || pageData.statements.length === 0) {
                showStatus('No statements or video found on current tab. Make sure you are on an annotation page.', 'error');
                setLoading(false);
                return;
            }

            showStatus(`Analyzing ${pageData.statements.length} statements with VisionClick...`, 'info');

            // 4. Send to VisionClick local backend via Background Worker
            let result = null;
            try {
                const bgResp = await new Promise((resolve) => {
                    chrome.runtime.sendMessage({
                        action: 'ANALYZE_TASK',
                        backendUrl: activeBackendUrl,
                        payload: {
                            task_id: pageData.task_id || 'active_tab_task',
                            video_url: pageData.video_url || '',
                            statements: pageData.statements,
                            frames_base64: pageData.frames_base64 || []
                        }
                    }, (response) => {
                        resolve(response);
                    });
                });

                if (bgResp && bgResp.success && bgResp.data) {
                    result = bgResp.data;
                } else if (bgResp && bgResp.error) {
                    throw new Error(bgResp.error);
                }
            } catch (e) {}

            if (!result) {
                const response = await fetch(`${activeBackendUrl}/api/extension/analyze`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        task_id: pageData.task_id || 'active_tab_task',
                        video_url: pageData.video_url || '',
                        statements: pageData.statements,
                        frames_base64: pageData.frames_base64 || []
                    })
                });

                if (!response.ok) {
                    const err = await response.text();
                    throw new Error(`Analysis failed (${response.status}): ${err}`);
                }
                result = await response.json();
            }

            const decisions = result.decisions || [];

            // 5. Render results in popup
            renderResults(decisions);
            showStatus(`Analysis complete! (${decisions.length} predictions)`, 'success');

            // 6. If auto-select toggle is enabled, send back to content script
            if (autoSelectToggle.checked) {
                const res = await chrome.tabs.sendMessage(tab.id, {
                    action: 'APPLY_DECISIONS',
                    decisions: decisions,
                    autoSubmit: autoSubmitToggle.checked
                });
                if (autoSubmitToggle.checked && res && res.submitted) {
                    showStatus('Predictions applied and task submitted automatically!', 'success');
                }
            }


        } catch (err) {
            console.error('Error during analysis:', err);
            showStatus(`Error: ${err.message}`, 'error');
        } finally {
            setLoading(false);
        }
    });

    function renderResults(decisions) {
        if (!decisions || decisions.length === 0) {
            resultsListEl.innerHTML = '<div class="empty-state"><p>No decisions generated.</p></div>';
            resultsCountEl.textContent = '0 items';
            return;
        }

        resultsCountEl.textContent = `${decisions.length} items`;
        let html = '';

        decisions.forEach(d => {
            const isTrue = d.answer === true;
            const actionIcon = isTrue ? '👍' : '👎';
            const actionText = isTrue ? 'TRUE' : 'FALSE';
            const decisionClass = isTrue ? 'true' : 'false';
            const confPct = Math.round((d.confidence || 0) * 100);
            const reasonText = d.explanation || (d.evidence && d.evidence.length > 0 ? d.evidence[0].reason : 'Evidence verified');

            html += `
                <div class="result-card">
                    <div class="result-header">
                        <div class="result-decision ${decisionClass}">
                            <span>${actionIcon}</span>
                            <span>${actionText}</span>
                        </div>
                        <span class="result-confidence">${confPct}% confidence</span>
                    </div>
                    <div class="result-text"><strong>#${d.statement_id}:</strong> ${escapeHtml(d.statement_text)}</div>
                    <div class="result-reason">${escapeHtml(reasonText)}</div>
                </div>
            `;
        });

        resultsListEl.innerHTML = html;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // Initialize
    checkBackendHealth();
})();
