/* VisionClick Dashboard - JavaScript */
(function() {
    'use strict';

    const statusEl = document.getElementById('agent-status');
    const statusBadge = document.getElementById('status-badge');
    const currentTask = document.getElementById('current-task');
    const currentStatement = document.getElementById('current-statement');
    const videoProgress = document.getElementById('video-progress');
    const tasksCompleted = document.getElementById('tasks-completed');
    const accuracy = document.getElementById('accuracy');
    const avgLatency = document.getElementById('avg-latency');
    const tasksPerHour = document.getElementById('tasks-per-hour');
    const framesAnalyzed = document.getElementById('frames-analyzed');
    const errorCount = document.getElementById('error-count');
    const decisionsBody = document.getElementById('decisions-body');
    const evidencePanel = document.getElementById('evidence-panel');

    // WebSocket connection
    let ws = null;
    let reconnectTimer = null;

    function connectWebSocket() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(protocol + '//' + location.host + '/ws');

        ws.onopen = function() {
            console.log('WebSocket connected');
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
        };

        ws.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            } catch (e) {
                console.error('Parse error:', e);
            }
        };

        ws.onclose = function() {
            console.log('WebSocket disconnected, reconnecting...');
            reconnectTimer = setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = function(err) {
            console.error('WebSocket error:', err);
        };
    }

    function updateDashboard(data) {
        // Status
        if (data.status) {
            statusEl.textContent = data.status;
            statusBadge.className = 'status-badge';
            if (['OBSERVING', 'ANALYZING', 'REASONING', 'VERIFYING',
                 'CLICKING', 'SUBMITTING'].includes(data.status)) {
                statusBadge.classList.add('active');
            } else if (data.status === 'ERROR') {
                statusBadge.classList.add('error');
            }
        }

        // Current task info
        if (data.current_task) currentTask.textContent = data.current_task;
        if (data.current_statement) currentStatement.textContent = data.current_statement;
        if (typeof data.video_progress === 'number') {
            videoProgress.style.width = data.video_progress + '%';
        }
        if (typeof data.frames_analyzed === 'number') {
            framesAnalyzed.textContent = data.frames_analyzed.toLocaleString();
        }

        // Decisions
        if (data.decisions && data.decisions.length > 0) {
            updateDecisionsTable(data.decisions);
        }
    }

    function updateDecisionsTable(decisions) {
        let html = '';
        decisions.slice(-20).reverse().forEach(function(d) {
            const answerBadge = d.answer
                ? '<span class="badge badge-true">👍 TRUE</span>'
                : '<span class="badge badge-false">👎 FALSE</span>';
            const levelClass = 'badge-' + (d.confidence_level || 'review');
            const confPct = ((d.confidence || 0) * 100).toFixed(1) + '%';
            const time = d.created_at ? new Date(d.created_at).toLocaleTimeString() : '—';

            html += '<tr>' +
                '<td>' + (d.task_id || '—') + '</td>' +
                '<td>' + (d.statement_text || 'Statement ' + d.statement_id) + '</td>' +
                '<td>' + answerBadge + '</td>' +
                '<td>' + confPct + '</td>' +
                '<td><span class="badge ' + levelClass + '">' + (d.confidence_level || '—') + '</span></td>' +
                '<td>' + time + '</td>' +
                '</tr>';
        });
        if (html) decisionsBody.innerHTML = html;
    }

    // Fetch stats periodically
    async function fetchStats() {
        try {
            const resp = await fetch('/api/stats');
            if (resp.ok) {
                const stats = await resp.json();
                if (typeof stats.tasks_completed === 'number') {
                    tasksCompleted.textContent = stats.tasks_completed;
                }
                if (typeof stats.avg_confidence === 'number' && stats.total_statements > 0) {
                    accuracy.textContent = (stats.avg_confidence * 100).toFixed(1) + '%';
                }
                if (typeof stats.avg_latency_ms === 'number' && stats.avg_latency_ms > 0) {
                    avgLatency.textContent = Math.round(stats.avg_latency_ms).toLocaleString();
                    const tph = Math.round(3600000 / stats.avg_latency_ms);
                    tasksPerHour.textContent = tph.toLocaleString();
                }
                if (typeof stats.error_count === 'number') {
                    errorCount.textContent = stats.error_count;
                }
            }
        } catch (e) {
            // Silent fail on stats fetch
        }
    }

    // Fetch decisions periodically
    async function fetchDecisions() {
        try {
            const resp = await fetch('/api/decisions');
            if (resp.ok) {
                const decisions = await resp.json();
                if (decisions.length > 0) {
                    updateDecisionsTable(decisions);
                }
            }
        } catch (e) {
            // Silent fail
        }
    }

    // Initialize
    connectWebSocket();
    fetchStats();
    fetchDecisions();

    // Periodic refresh
    setInterval(fetchStats, 5000);
    setInterval(fetchDecisions, 5000);
})();
