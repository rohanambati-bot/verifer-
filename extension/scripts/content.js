/* VisionClick Copilot - Content Script with Continuous Autopilot */
(function() {
    'use strict';

    let backendUrl = 'http://127.0.0.1:8001';

    // Prevent duplicate injection
    if (window.__VISIONCLICK_INJECTED__) {
        return;
    }
    window.__VISIONCLICK_INJECTED__ = true;

    let isAutopilotRunning = false;
    let autopilotDelayMs = 2000;
    let autoSubmitEnabled = true;
    let processedTaskCount = 0;
    let lastProcessedTaskId = null;
    let autopilotTimer = null;
    let floatingHud = null;

    // Check if Autopilot was enabled specifically for this website origin
    chrome.storage.local.get(['autopilotRunning', 'autopilotOrigin', 'loopDelay', 'autoSubmit', 'backendUrl'], (res) => {
        if (res.backendUrl) {
            backendUrl = res.backendUrl;
        }
        const currentOrigin = window.location.origin;
        // Strictly only auto-resume if this website's origin matches the enabled origin
        if (res.autopilotRunning && res.autopilotOrigin && res.autopilotOrigin === currentOrigin) {
            autopilotDelayMs = (res.loopDelay || 2) * 1000;
            autoSubmitEnabled = res.autoSubmit !== false;
            startAutopilot(autopilotDelayMs, autoSubmitEnabled);
        }
    });

    // Listen for messages from popup
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === 'EXTRACT_PAGE_DATA') {
            (async () => {
                try {
                    const data = await extractPageData();
                    sendResponse(data);
                } catch (err) {
                    console.error('[VisionClick] Extraction error:', err);
                    sendResponse({ error: err.message, statements: [] });
                }
            })();
            return true; // Keep message channel open for async response
        }

        if (request.action === 'APPLY_DECISIONS') {
            (async () => {
                try {
                    const results = await applyDecisions(request.decisions || []);
                    let submitted = false;

                    if (request.autoSubmit) {
                        await new Promise(r => setTimeout(r, 600));
                        submitted = triggerSubmit();
                    }

                    sendResponse({ success: true, results, submitted });
                } catch (err) {
                    console.error('[VisionClick] Application error:', err);
                    sendResponse({ error: err.message });
                }
            })();
            return true;
        }

        if (request.action === 'START_AUTOPILOT') {
            autopilotDelayMs = (request.delay || 2) * 1000;
            autoSubmitEnabled = request.autoSubmit !== false;
            startAutopilot(autopilotDelayMs, autoSubmitEnabled);
            sendResponse({ status: 'started' });
            return true;
        }

        if (request.action === 'STOP_AUTOPILOT') {
            stopAutopilot();
            sendResponse({ status: 'stopped' });
            return true;
        }
    });

    /**
     * Start continuous autopilot loop (origin-scoped).
     */
    function startAutopilot(delayMs, autoSubmit) {
        isAutopilotRunning = true;
        autopilotDelayMs = delayMs;
        autoSubmitEnabled = autoSubmit;
        chrome.storage.local.set({ 
            autopilotRunning: true,
            autopilotOrigin: window.location.origin
        });

        createFloatingHud();
        updateHudStatus('Starting analysis...');

        // Start initial step after short pause
        clearTimeout(autopilotTimer);
        autopilotTimer = setTimeout(runAutopilotStep, 1000);
    }

    /**
     * Stop continuous autopilot loop.
     */
    function stopAutopilot() {
        isAutopilotRunning = false;
        clearTimeout(autopilotTimer);
        chrome.storage.local.set({ 
            autopilotRunning: false,
            autopilotOrigin: null
        });
        removeFloatingHud();
        console.log('[VisionClick] Autopilot stopped.');
    }

    /**
     * Single step in the continuous loop (Turbo Speed).
     */
    async function runAutopilotStep() {
        if (!isAutopilotRunning) return;

        const pageData = await extractPageData();

        if (!pageData.statements || pageData.statements.length === 0) {
            updateHudStatus('Waiting for task...');
            autopilotTimer = setTimeout(runAutopilotStep, 200);
            return;
        }

        // Avoid re-submitting the exact same task if DOM hasn't transitioned yet
        if (pageData.task_id && pageData.task_id === lastProcessedTaskId) {
            waitForNextTask();
            return;
        }

        try {
            updateHudStatus(`⚡ Analyzing ${pageData.statements.length} items...`);

            const result = await analyzeTaskBackend({
                task_id: pageData.task_id || 'autopilot_task',
                video_url: pageData.video_url || '',
                statements: pageData.statements,
                frames_base64: pageData.frames_base64 || []
            });

            const decisions = result.decisions || [];

            updateHudStatus(`⚡ Clicking ${decisions.length} predictions...`);
            await applyDecisions(decisions);
            processedTaskCount++;
            lastProcessedTaskId = pageData.task_id;

            if (autoSubmitEnabled) {
                await new Promise(r => setTimeout(r, 60));
                triggerSubmit();
                updateHudStatus(`✅ Submitted #${processedTaskCount}! Loading next...`);
                // Actively watch for next task transition immediately
                waitForNextTask();
            } else {
                updateHudStatus(`Task #${processedTaskCount} complete.`);
                autopilotTimer = setTimeout(runAutopilotStep, Math.max(autopilotDelayMs, 300));
            }

        } catch (err) {
            updateHudStatus(`Retrying: ${err.message || 'Connecting'}...`);
            autopilotTimer = setTimeout(runAutopilotStep, 1000);
        }
    }

    /**
     * Executes backend analyze call via Background service worker (immune to Mixed Content / CORS) with direct fetch fallback.
     */
    async function analyzeTaskBackend(payload) {
        try {
            const resp = await new Promise((resolve) => {
                chrome.runtime.sendMessage({
                    action: 'ANALYZE_TASK',
                    backendUrl: backendUrl,
                    payload: payload
                }, (response) => {
                    if (chrome.runtime.lastError || !response) {
                        resolve(null);
                    } else {
                        resolve(response);
                    }
                });
            });

            if (resp && resp.success && resp.data) {
                return resp.data;
            } else if (resp && resp.error) {
                throw new Error(resp.error);
            }
        } catch (e) {
            // Try direct fetch
        }

        const res = await fetch(`${backendUrl}/api/extension/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            throw new Error(`Server returned ${res.status}`);
        }
        return await res.json();
    }

    /**
     * Fast-polls the DOM (every 75ms) to detect when the next task or statements load.
     */
    function waitForNextTask() {
        if (!isAutopilotRunning) return;
        clearTimeout(autopilotTimer);

        let checks = 0;
        const maxChecks = 40; // up to 3 seconds max
        const interval = setInterval(async () => {
            if (!isAutopilotRunning) {
                clearInterval(interval);
                return;
            }

            checks++;
            const currentData = await extractPageData();
            const hasNewTask = currentData.task_id && currentData.task_id !== lastProcessedTaskId;
            const hasStatements = currentData.statements && currentData.statements.length > 0;

            if (hasNewTask && hasStatements) {
                clearInterval(interval);
                runAutopilotStep();
            } else if (checks >= maxChecks) {
                clearInterval(interval);
                lastProcessedTaskId = null; // force retry
                runAutopilotStep();
            }
        }, 75);
    }

    /**
     * Checks whether an element is inside navigation, sidebar, header or footer.
     */
    function isIgnoredContainer(elem) {
        if (!elem) return true;
        // Strictly check semantic nav, aside, header, footer or role="navigation"
        const parent = elem.closest('nav, aside, header, footer, [role="navigation"], #sidebar');
        return parent !== null;
    }

    /**
     * Finds statement row elements using adaptive multi-strategy detection.
     */
    function findStatementRows() {
        // Strategy 1: Pair-Walk — Find containers that have exactly 2 action buttons + statement text
        const allButtons = Array.from(document.querySelectorAll('button, [role="button"]')).filter(b => !isIgnoredContainer(b));
        const candidateRows = new Map();

        allButtons.forEach(btn => {
            const txt = (btn.innerText || '').toLowerCase();
            if (txt.includes('submit') || txt.includes('continue') || txt.includes('clear') || txt.includes('next') || txt.includes('save') || txt.includes('reset')) {
                return;
            }

            let parent = btn.parentElement;
            let depth = 0;
            while (parent && depth < 5 && parent !== document.body && parent.tagName.toLowerCase() !== 'main') {
                const btnsInside = Array.from(parent.querySelectorAll('button, [role="button"]'));
                if (btnsInside.length === 2) {
                    const text = extractStatementText(parent);
                    if (text && text.length >= 3 && !text.toLowerCase().includes('clear segment') && !text.toLowerCase().includes('submit and continue')) {
                        candidateRows.set(parent, btnsInside);
                        break;
                    }
                }
                parent = parent.parentElement;
                depth++;
            }
        });

        if (candidateRows.size > 0) {
            return Array.from(candidateRows.keys());
        }

        // Strategy 2: Specific data-testid or class selectors
        const selectors = [
            '[data-testid="statement-row"]',
            '.statement-row',
            '.statement',
            '.annotation-row',
            '.task-row',
            '.question-row',
            '[data-statement-id]'
        ];

        for (const sel of selectors) {
            const elems = Array.from(document.querySelectorAll(sel)).filter(el => !isIgnoredContainer(el));
            if (elems && elems.length > 0) {
                const valid = elems.filter(el => extractStatementText(el).length > 2);
                if (valid.length > 0) return valid;
            }
        }

        // Strategy 3: Rows with thumbs emoji in text
        const rows = [];
        allButtons.forEach(btn => {
            const text = btn.innerText || btn.getAttribute('aria-label') || '';
            if (text.includes('👍') || text.includes('👎')) {
                const parentRow = btn.closest('div[class*="row"], li, div[class*="item"], tr, div[class*="flex"]');
                if (parentRow && !isIgnoredContainer(parentRow) && !rows.includes(parentRow)) {
                    rows.push(parentRow);
                }
            }
        });

        return rows;
    }

    /**
     * Extracts plain statement text from row container.
     */
    function extractStatementText(row) {
        if (!row) return '';

        // Check if there is an explicit statement text container
        const textElem = row.querySelector('[data-testid="statement-text"], .statement-text, [class*="statement"], [class*="text-"], p, label');
        if (textElem && textElem.innerText && textElem.innerText.trim().length > 3) {
            let t = textElem.innerText.trim();
            t = cleanStatementText(t);
            if (t.length > 2) return t;
        }

        // Clone element to safely remove buttons and number badges
        const clone = row.cloneNode(true);
        const toRemove = clone.querySelectorAll('button, svg, [role="button"], [class*="badge"], [class*="number"], [class*="btn"], input');
        toRemove.forEach(el => el.remove());

        let raw = clone.innerText || '';
        return cleanStatementText(raw);
    }

    function cleanStatementText(raw) {
        if (!raw) return '';
        let cleaned = raw
            .replace(/[👍👎]/g, ' ')
            .replace(/thumbs\s*(?:up|down)/gi, ' ')
            .replace(/^\s*\d+[\.\)\:\-]\s*/, '') // Remove "1. ", "3 ", "4) "
            .replace(/^\s*#\d+\s*[\:\-]?\s*/, '') // Remove "#1: "
            .replace(/\s+/g, ' ')
            .trim();
        return cleaned;
    }

    /**
     * Captures live frame snapshots from video element via canvas or background tab capture.
     */
    async function captureVideoFrames() {
        const video = document.querySelector('video');
        
        // Strategy 1: Try HTML5 canvas capture if allowed (same-origin / un-tainted)
        if (video) {
            try {
                const w = video.videoWidth || video.clientWidth || 640;
                const h = video.videoHeight || video.clientHeight || 480;
                const canvas = document.createElement('canvas');
                canvas.width = Math.min(640, w);
                canvas.height = Math.min(480, h);
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const base64 = canvas.toDataURL('image/jpeg', 0.80);
                if (base64 && base64.length > 500) {
                    return [base64];
                }
            } catch (e) {
                // Cross-origin CDN video without CORS headers — silently fall through to Tab Capture
            }
        }

        // Strategy 2: Request visible tab screenshot from background service worker (bypasses CORS)
        try {
            const resp = await new Promise((resolve) => {
                chrome.runtime.sendMessage({ action: 'CAPTURE_TAB' }, (response) => {
                    if (chrome.runtime.lastError || !response || !response.dataUrl) {
                        resolve(null);
                    } else {
                        resolve(response.dataUrl);
                    }
                });
            });
            if (resp) {
                return [resp];
            }
        } catch (e) {
            // Background capture unavailable
        }

        return [];
    }

    /**
     * Extract video, statements, and live frames from current DOM.
     */
    async function extractPageData() {
        let taskId = '';
        const idElem = document.querySelector('[data-task-id], [data-testid="task-id"], #task-id');
        if (idElem) {
            taskId = idElem.getAttribute('data-task-id') || idElem.innerText.replace(/Task:\s*/i, '').trim();
        }
        if (!taskId) {
            const match = window.location.href.match(/[?&]task(?:_id)?=([^&]+)/i);
            taskId = match ? match[1] : `task_${Date.now()}`;
        }

        let videoUrl = '';
        const videoElem = document.querySelector('video');
        if (videoElem) {
            videoUrl = videoElem.currentSrc || videoElem.src || '';
            if (!videoUrl) {
                const sourceElem = videoElem.querySelector('source');
                if (sourceElem) {
                    videoUrl = sourceElem.src || '';
                }
            }
        }

        const frames = await captureVideoFrames();
        const statements = [];
        const rows = findStatementRows();

        rows.forEach((row, index) => {
            const stmtId = row.getAttribute('data-statement-id') || String(index + 1);
            const text = extractStatementText(row);

            if (text && text.length > 2) {
                statements.push({
                    id: parseInt(stmtId, 10) || index + 1,
                    text: text
                });
            }
        });

        console.log(`[VisionClick] Extracted ${statements.length} statements:`, statements);

        return {
            task_id: taskId,
            video_url: videoUrl,
            statements: statements,
            frames_base64: frames
        };
    }

    /**
     * Apply predictions by clicking 👍 or 👎 on each statement row sequentially.
     */
    async function applyDecisions(decisions) {
        const rows = findStatementRows();
        const applied = [];

        for (let i = 0; i < decisions.length; i++) {
            const decision = decisions[i];
            const isTrue = decision.answer === true;
            const targetIndex = decision.statement_id - 1;

            let row = null;
            if (targetIndex >= 0 && targetIndex < rows.length) {
                row = rows[targetIndex];
            } else {
                row = document.querySelector(`[data-statement-id="${decision.statement_id}"]`);
            }

            if (!row) continue;

            const btn = findActionButton(row, isTrue);
            if (btn) {
                await clickElement(btn);
                highlightSelection(btn, isTrue);
                applied.push({ statement_id: decision.statement_id, clicked: true });
                // Micro delay for React state flush
                await new Promise(r => setTimeout(r, 25));
            }
        }

        return applied;
    }

    /**
     * Dispatches full set of click/pointer events with realistic micro-delays so modern frameworks (React, Vue) register state changes.
     */
    async function clickElement(el) {
        if (!el) return;
        try {
            el.scrollIntoView({ behavior: 'instant', block: 'nearest' });
        } catch (e) {}

        el.focus();

        const eventInit = { bubbles: true, cancelable: true, composed: true, view: window };
        const child = el.querySelector('svg') || el.firstElementChild || el;

        // Pointer & Mouse Down sequence
        el.dispatchEvent(new PointerEvent('pointerdown', eventInit));
        el.dispatchEvent(new MouseEvent('mousedown', eventInit));
        if (child !== el) {
            child.dispatchEvent(new PointerEvent('pointerdown', eventInit));
            child.dispatchEvent(new MouseEvent('mousedown', eventInit));
        }

        // Fast tap delay (8ms)
        await new Promise(r => setTimeout(r, 8));

        // Pointer & Mouse Up sequence
        el.dispatchEvent(new PointerEvent('pointerup', eventInit));
        el.dispatchEvent(new MouseEvent('mouseup', eventInit));
        if (child !== el) {
            child.dispatchEvent(new PointerEvent('pointerup', eventInit));
            child.dispatchEvent(new MouseEvent('mouseup', eventInit));
        }

        // Click trigger
        el.click();
        if (child !== el) {
            child.dispatchEvent(new MouseEvent('click', eventInit));
        }

        // Input & Change event notification
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }

    /**
     * Finds thumbs up or down button inside statement row.
     */
    function findActionButton(row, isThumbsUp) {
        const emoji = isThumbsUp ? '👍' : '👎';
        const label = isThumbsUp ? 'thumbs up' : 'thumbs down';
        const testid = isThumbsUp ? 'thumbs-up' : 'thumbs-down';

        // 1. Semantic attributes and testids
        const selectors = [
            `[data-testid="${testid}"]`,
            `button[data-testid*="${testid}"]`,
            `button[aria-label*="${label}" i]`,
            `button[aria-label*="${emoji}"]`,
            `button[title*="${label}" i]`,
            `button.btn-${testid}`
        ];

        for (const sel of selectors) {
            const el = row.querySelector(sel);
            if (el) return el;
        }

        // 2. Buttons containing emoji or text
        const buttons = Array.from(row.querySelectorAll('button, input[type="button"], [role="button"]'));
        for (const btn of buttons) {
            const text = (btn.innerText || '') + ' ' + (btn.getAttribute('aria-label') || '') + ' ' + (btn.getAttribute('title') || '') + ' ' + (btn.className || '');
            const lower = text.toLowerCase();
            if (isThumbsUp && (text.includes('👍') || lower.includes('thumbs up') || lower.includes('thumb-up') || lower.includes('like') || lower.includes('positive') || lower.includes('true') || lower.includes('yes') || lower.includes('up'))) {
                return btn;
            }
            if (!isThumbsUp && (text.includes('👎') || lower.includes('thumbs down') || lower.includes('thumb-down') || lower.includes('dislike') || lower.includes('negative') || lower.includes('false') || lower.includes('no') || lower.includes('down'))) {
                return btn;
            }
        }

        // 3. Fallback for 2 buttons in a row: 1st button = thumbs up (TRUE), 2nd button = thumbs down (FALSE)
        if (buttons.length === 2) {
            return isThumbsUp ? buttons[0] : buttons[1];
        } else if (buttons.length >= 2) {
            // Find the last 2 buttons in the row
            const lastTwo = buttons.slice(-2);
            return isThumbsUp ? lastTwo[0] : lastTwo[1];
        }

        return null;
    }

    function highlightSelection(btn, isTrue) {
        btn.style.transition = 'all 0.3s ease';
        btn.style.boxShadow = isTrue
            ? '0 0 14px rgba(34, 197, 94, 0.9)'
            : '0 0 14px rgba(239, 68, 68, 0.9)';
        btn.style.border = isTrue
            ? '2px solid #22c55e'
            : '2px solid #ef4444';
        btn.style.borderRadius = '8px';
    }

    /**
     * Finds and clicks the submit button on the webpage.
     */
    function triggerSubmit() {
        const submitBtn = findSubmitButton();
        if (!submitBtn) {
            console.warn('[VisionClick] Submit button not found on page.');
            return false;
        }

        console.log('[VisionClick] Auto-submitting task...');
        submitBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });

        setTimeout(() => {
            clickElement(submitBtn);
        }, 300);

        return true;
    }

    /**
     * Detects the submit/next button using semantic and text selectors.
     */
    function findSubmitButton() {
        const selectors = [
            'button[data-testid="submit-button"]',
            '#submit-btn',
            'button[type="submit"]',
            '.submit-button',
            '.btn-submit',
            'button.submit',
            'button.primary'
        ];

        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && !isIgnoredContainer(el)) {
                const txt = (el.innerText || el.value || '').toLowerCase();
                if (txt.includes('submit') || txt.includes('next') || txt.includes('save') || txt.includes('continue') || txt.includes('complete')) {
                    return el;
                }
            }
        }

        const allButtons = Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]')).filter(b => !isIgnoredContainer(b));
        for (const btn of allButtons) {
            const txt = (btn.innerText || btn.value || '').toLowerCase();
            if (txt.includes('submit and continue') || txt.includes('submit') || txt.includes('continue') || txt.includes('next') || txt.includes('complete') || txt.includes('save & continue')) {
                return btn;
            }
        }

        return null;
    }

    /**
     * Floating On-Screen Autopilot HUD Indicator
     */
    function createFloatingHud() {
        if (floatingHud) return;

        floatingHud = document.createElement('div');
        floatingHud.id = '__visionclick_hud__';
        floatingHud.style.cssText = `
            position: fixed;
            top: 16px;
            right: 16px;
            z-index: 999999;
            background: rgba(15, 23, 42, 0.92);
            color: #f8fafc;
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 12px;
            padding: 10px 14px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 13px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            backdrop-filter: blur(12px);
            display: flex;
            align-items: center;
            gap: 10px;
        `;

        const title = document.createElement('span');
        title.innerHTML = '<strong>🤖 VisionClick Autopilot</strong>';

        const status = document.createElement('span');
        status.id = '__visionclick_hud_status__';
        status.style.color = '#94a3b8';
        status.textContent = 'Running...';

        const stopBtn = document.createElement('button');
        stopBtn.textContent = 'Stop';
        stopBtn.style.cssText = `
            background: #ef4444;
            color: white;
            border: none;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
        `;
        stopBtn.addEventListener('click', stopAutopilot);

        floatingHud.appendChild(title);
        floatingHud.appendChild(status);
        floatingHud.appendChild(stopBtn);
        document.body.appendChild(floatingHud);
    }

    function updateHudStatus(text) {
        const el = document.getElementById('__visionclick_hud_status__');
        if (el) {
            el.textContent = text;
        }
    }

    function removeFloatingHud() {
        if (floatingHud && floatingHud.parentNode) {
            floatingHud.parentNode.removeChild(floatingHud);
            floatingHud = null;
        }
    }

    console.log('[VisionClick] Content script loaded with Continuous Autopilot.');
})();
