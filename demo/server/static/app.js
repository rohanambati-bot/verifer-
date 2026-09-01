/* Demo Annotation Site - JavaScript */
(function() {
    'use strict';

    var answers = {};  // statement_id -> true/false
    var TASK_DATA = null;

    function init() {
        var scriptEl = document.getElementById('task-data-script');
        if (scriptEl && scriptEl.textContent) {
            try {
                TASK_DATA = JSON.parse(scriptEl.textContent);
            } catch (e) {
                console.error("Failed to parse TASK_DATA", e);
            }
        }

        if (!TASK_DATA || !TASK_DATA.task_id) {
            document.getElementById('statements-list').innerHTML =
                '<p style="text-align:center;color:#94a3b8">No tasks available.</p>';
            return;
        }

        // Set task ID
        var taskIdEl = document.getElementById('task-id');
        taskIdEl.textContent = 'Task: ' + TASK_DATA.task_id;
        taskIdEl.setAttribute('data-task-id', TASK_DATA.task_id);

        // Set video source
        var video = document.getElementById('task-video');
        var source = video.querySelector('source');
        var videoFile = TASK_DATA.video || TASK_DATA.task_id + '.mp4';
        source.src = '/videos/' + videoFile;
        video.load();

        // Build statement rows
        var list = document.getElementById('statements-list');
        list.innerHTML = '';

        (TASK_DATA.statements || []).forEach(function(stmt) {
            var row = document.createElement('div');
            row.className = 'statement-row';
            row.setAttribute('role', 'listitem');
            row.setAttribute('data-testid', 'statement-row');
            row.setAttribute('data-statement-id', stmt.id);

            row.innerHTML =
                '<span class="statement-number">' + stmt.id + '.</span>' +
                '<span class="statement-text" data-testid="statement-text">' + escapeHtml(stmt.text) + '</span>' +
                '<div class="statement-buttons">' +
                    '<button class="btn-thumb" data-testid="thumbs-up" ' +
                        'aria-label="thumbs up for statement ' + stmt.id + '" ' +
                        'aria-pressed="false" ' +
                        'onclick="selectAnswer(' + stmt.id + ', true, this)">👍</button>' +
                    '<button class="btn-thumb" data-testid="thumbs-down" ' +
                        'aria-label="thumbs down for statement ' + stmt.id + '" ' +
                        'aria-pressed="false" ' +
                        'onclick="selectAnswer(' + stmt.id + ', false, this)">👎</button>' +
                '</div>';

            list.appendChild(row);
        });
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Global function called from onclick
    window.selectAnswer = function(statementId, isTrue, btnEl) {
        answers[statementId] = isTrue;

        // Update button states
        var row = btnEl.closest('.statement-row');
        var buttons = row.querySelectorAll('.btn-thumb');
        buttons.forEach(function(btn) {
            btn.classList.remove('selected');
            btn.setAttribute('aria-pressed', 'false');
            btn.setAttribute('data-selected', 'false');
        });

        btnEl.classList.add('selected');
        btnEl.setAttribute('aria-pressed', 'true');
        btnEl.setAttribute('data-selected', 'true');
        row.classList.add('answered');
    };

    // Global submit function
    window.submitTask = function() {
        if (!TASK_DATA) return;

        // Check all statements answered
        var allAnswered = true;
        (TASK_DATA.statements || []).forEach(function(stmt) {
            if (answers[stmt.id] === undefined) {
                allAnswered = false;
            }
        });

        if (!allAnswered) {
            showFeedback('Please answer all statements before submitting.', 'error');
            return;
        }

        // Submit to server
        fetch('/api/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: TASK_DATA.task_id,
                answers: answers
            })
        })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            showFeedback('Task submitted successfully!', 'success');
            if (data.next_task) {
                setTimeout(function() { location.reload(); }, 1500);
            }
        })
        .catch(function(err) {
            showFeedback('Submission error: ' + err.message, 'error');
        });
    };

    function showFeedback(message, type) {
        var el = document.getElementById('feedback');
        el.textContent = message;
        el.className = 'feedback ' + type;
    }

    // Initialize on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
