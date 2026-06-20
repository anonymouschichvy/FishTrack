let availableCommands = {};
let activeNodes = [];

async function loadData() {
    try {
        const schedules  = await fetch('/api/schedules').then(r => r.json());
        if (schedules) {
            displaySchedules(schedules.schedules || []);
            displayNextRuns(schedules.next_scheduled || []);
        }

        const activeList = await fetch('/api/active_list').then(r => r.json());
        if (activeList && activeList.nodes) {
            activeNodes = activeList.nodes;
        }

        const commands   = await fetch('/api/commands').then(r => r.json());
        if (commands) {
            availableCommands = commands.available_commands || {};
        }
    } catch (e) {
        console.error('Error loading scheduler data:', e);
    }
}

function displaySchedules(schedules) {
    const grid = document.getElementById('schedules-grid');
    if (!grid) return;
    if (!schedules || schedules.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>
                </div>
                <p class="empty-text">No active schedules configured. Select "New Schedule" to create one.</p>
            </div>`;
        return;
    }

    grid.innerHTML = schedules.map((s, index) => {
        const scriptsList = s.scripts ? (Array.isArray(s.scripts) ? s.scripts : [s.scripts]) : [];
        return `
            <div class="schedule-card ${s.enabled ? '' : 'disabled'}" style="animation-delay:${index * 0.05}s">
                <div class="schedule-header">
                    <div class="schedule-name">${s.name || 'Unnamed Schedule'}</div>
                    <div class="status-badge status-${s.enabled ? 'enabled' : 'disabled'}">
                        ${s.enabled ? 'Enabled' : 'Disabled'}
                    </div>
                </div>
                <div class="schedule-info">
                    <div class="info-row"><span class="info-label">Target:</span><span class="info-value">${s.target || 'All Nodes'}</span></div>
                    <div class="info-row"><span class="info-label">Scripts:</span><span class="info-value">${scriptsList.join(', ')}</span></div>
                    <div class="info-row"><span class="info-label">Frequency:</span><span class="info-value">${(s.frequency || 'once').toUpperCase()}</span></div>
                    ${s.time_of_day ? `<div class="info-row"><span class="info-label">Time:</span><span class="info-value">${s.time_of_day}</span></div>` : ''}
                    <div class="info-row"><span class="info-label">Next Run:</span><span class="info-value">${s.next_run || 'N/A'}</span></div>
                    <div class="info-row"><span class="info-label">Run Count:</span><span class="info-value">${s.run_count || 0}</span></div>
                </div>
                <div class="schedule-actions">
                    <button class="btn btn-small btn-toggle" onclick="toggleSchedule('${s.id}')">
                        <span>${s.enabled ? 'Disable' : 'Enable'}</span>
                    </button>
                    <button class="btn btn-small btn-delete" onclick="deleteSchedule('${s.id}')">
                        <span>Delete</span>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function displayNextRuns(nextRuns) {
    const container = document.getElementById('next-runs');
    if (!container) return;
    if (!nextRuns || nextRuns.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                </div>
                <p class="empty-text">No upcoming scheduled executions</p>
            </div>`;
        return;
    }
    container.innerHTML = nextRuns.map((s, index) => {
        const scriptsList = s.scripts ? (Array.isArray(s.scripts) ? s.scripts : [s.scripts]) : [];
        return `
            <div class="next-run-item" style="animation-delay:${index * 0.05}s">
                <div class="next-run-name">
                    <svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" style="margin-right:6px; color:var(--primary);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    ${s.name || 'Scheduled Job'}
                </div>
                <div class="next-run-details">Target: ${s.target || 'All'} | Scripts: ${scriptsList.join(', ')}</div>
                <div class="countdown">Next run: ${s.next_run || 'Pending'}</div>
            </div>
        `;
    }).join('');
}

function openNewScheduleModal() {
    const targetSelect = document.getElementById('target-node');
    if (targetSelect) {
        targetSelect.innerHTML = '<option value="">Select a node...</option>' +
            activeNodes.map(node => `<option value="${node.codename}">${node.codename} (${node.status})</option>`).join('');
    }

    const scriptsDiv = document.getElementById('scripts-checkboxes');
    if (scriptsDiv && availableCommands) {
        scriptsDiv.innerHTML = Object.entries(availableCommands).map(([key, cmd]) => `
            <label class="checkbox-label">
                <input type="checkbox" value="${key}">${cmd.label}
            </label>
        `).join('');
    }

    const modal = document.getElementById('newScheduleModal');
    if (modal) modal.classList.add('active');
}

function closeModal() {
    const modal = document.getElementById('newScheduleModal');
    if (modal) modal.classList.remove('active');
}

function updateFrequencyFields() {
    const freqEl = document.getElementById('frequency');
    if (!freqEl) return;
    const frequency     = freqEl.value;
    const timeField     = document.getElementById('time-field');
    const daysField     = document.getElementById('days-field');
    const intervalField = document.getElementById('interval-field');
    
    if (timeField) timeField.style.display = 'none';
    if (daysField) daysField.style.display = 'none';
    if (intervalField) intervalField.style.display = 'none';

    if (frequency === 'once' || frequency === 'daily') {
        if (timeField) timeField.style.display = 'block';
    } else if (frequency === 'hourly') {
        if (timeField) {
            timeField.style.display = 'block';
            const timeOfDayEl = document.getElementById('time-of-day');
            if (timeOfDayEl) timeOfDayEl.value = '00:00';
        }
    } else if (frequency === 'weekly') {
        if (timeField) timeField.style.display = 'block';
        if (daysField) daysField.style.display = 'block';
    } else if (frequency === 'interval') {
        if (intervalField) intervalField.style.display = 'block';
    }
}

async function createSchedule() {
    const nameEl = document.getElementById('schedule-name');
    const targetEl = document.getElementById('target-node');
    const freqEl = document.getElementById('frequency');
    
    if (!nameEl || !targetEl || !freqEl) return;

    const name      = nameEl.value.trim();
    const target    = targetEl.value;
    const frequency = freqEl.value;
    if (!name || !target) { alert('Please fill in all required fields'); return; }

    const scripts = Array.from(document.querySelectorAll('#scripts-checkboxes input:checked')).map(cb => cb.value);
    if (scripts.length === 0) { alert('Please select at least one script'); return; }

    const schedule = { name, target, scripts, frequency };

    if (['once', 'daily', 'hourly'].includes(frequency)) {
        const timeEl = document.getElementById('time-of-day');
        if (timeEl) schedule.time_of_day = timeEl.value;
    }
    if (frequency === 'weekly') {
        const timeEl = document.getElementById('time-of-day');
        if (timeEl) schedule.time_of_day = timeEl.value;
        schedule.days_of_week = Array.from(document.querySelectorAll('#days-field input:checked')).map(cb => parseInt(cb.value));
        if (schedule.days_of_week.length === 0) { alert('Please select at least one day of the week'); return; }
    }
    if (frequency === 'interval') {
        const intervalEl = document.getElementById('interval-minutes');
        if (intervalEl) schedule.interval_minutes = parseInt(intervalEl.value) || 60;
    }

    const argsEl = document.getElementById('command-args');
    const argsText = argsEl ? argsEl.value.trim() : '';
    if (argsText) {
        const args = {};
        scripts.forEach(script => {
            args[script] = argsText.split('\n').flatMap(line => line.trim().split(/\s+/)).filter(a => a);
        });
        schedule.args = args;
    }

    try {
        const response = await fetch('/api/schedules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(schedule)
        });
        const result = await response.json();
        if (result.success) {
            closeModal();
            loadData();
            alert('Schedule created successfully!');
        } else {
            alert('Error creating schedule');
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function toggleSchedule(scheduleId) {
    try {
        const result = await fetch(`/api/scheduler/toggle/${scheduleId}`, { method: 'POST' }).then(r => r.json());
        if (result.success) loadData();
    } catch (e) {
        console.error('Error toggling schedule:', e);
    }
}

async function deleteSchedule(scheduleId) {
    if (!confirm('Are you sure you want to delete this schedule?')) return;
    try {
        const result = await fetch(`/api/schedules/${scheduleId}`, { method: 'DELETE' }).then(r => r.json());
        if (result.success) loadData();
    } catch (e) {
        console.error('Error deleting schedule:', e);
    }
}

// Initial load
loadData();
// Poll scheduler queue every 15 seconds
setInterval(loadData, 15000);
