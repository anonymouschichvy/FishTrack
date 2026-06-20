let availableCommands = {};
let updateInterval = null;

function switchTab(tab) {
    const tabScripts = document.getElementById('tab-scripts');
    const tabLinux = document.getElementById('tab-linux');
    const secLinux = document.getElementById('section-linux');

    if (tabScripts) tabScripts.classList.toggle('active', tab === 'scripts');
    if (tabLinux) tabLinux.classList.toggle('active', tab === 'linux');
    if (secScripts) secScripts.style.display = tab === 'scripts' ? 'block' : 'none';
    if (secLinux) secLinux.style.display = tab === 'linux' ? 'block' : 'none';
}

function setQuickCommand(cmd) {
    const cmdInput = document.getElementById('linux-command');
    if (cmdInput) cmdInput.value = cmd;
}

function showOutput(output) {
    const outText = document.getElementById('output-text');
    const outModal = document.getElementById('output-modal');
    if (outText && outModal) {
        outText.textContent = output;
        outModal.classList.add('active');
    }
}

function closeOutputModal() {
    const outModal = document.getElementById('output-modal');
    if (outModal) {
        outModal.classList.remove('active');
    }
}

async function loadData() {
    try {
        const activeList = await fetch('/api/active_list').then(r => r.json());
        const commands   = await fetch('/api/commands').then(r => r.json());

        const nodeOptions = '<option value="">Select a node...</option>' +
            activeList.nodes.map(node =>
                `<option value="${node.codename}">${node.codename} (${node.status})</option>`
            ).join('');

        const targetEl = document.getElementById('target');
        const linuxTargetEl = document.getElementById('linux-target');

        if (targetEl) targetEl.innerHTML = nodeOptions;
        if (linuxTargetEl) linuxTargetEl.innerHTML = nodeOptions;

        availableCommands = commands.available_commands || {};

        const scriptsList = document.getElementById('scripts-list');
        if (scriptsList && Object.keys(availableCommands).length > 0) {
            scriptsList.innerHTML = Object.entries(availableCommands).map(([key, cmd]) => `
                <div class="script-checkbox" id="checkbox-${key}" onclick="toggleScript('${key}')">
                    <div class="checkbox-header">
                        <input type="checkbox" id="script-${key}" value="${key}" onclick="event.stopPropagation(); toggleScript('${key}')">
                        <div class="script-content">
                            <div class="script-title">${cmd.label}</div>
                            <div class="script-description">${cmd.description}</div>
                        </div>
                    </div>
                    <div id="args-${key}" class="args-container">
                        <label class="form-label">Arguments (Optional)</label>
                        <input type="text" id="args-input-${key}" placeholder="e.g., --time 30s --mode auto" onclick="event.stopPropagation()">
                    </div>
                </div>
            `).join('');
        }

        if (commands.active_commands) {
            updateCommandStatus(commands.active_commands);
        }
        
        loadLinuxCommands();

    } catch (error) {
        console.error('Error loading data:', error);
        showAlert('Error loading data: ' + error.message, 'error');
    }
}

function toggleScript(scriptKey) {
    const checkbox    = document.getElementById(`script-${scriptKey}`);
    if (!checkbox) return;
    checkbox.checked  = !checkbox.checked;
    const checkboxDiv = document.getElementById(`checkbox-${scriptKey}`);
    const argsDiv     = document.getElementById(`args-${scriptKey}`);
    if (checkbox.checked) {
        if (checkboxDiv) checkboxDiv.classList.add('selected');
        if (argsDiv) argsDiv.classList.add('active');
    } else {
        if (checkboxDiv) checkboxDiv.classList.remove('selected');
        if (argsDiv) argsDiv.classList.remove('active');
    }
}

function updateCommandStatus(commands) {
    const tbody = document.querySelector('#commands-status');
    if (!tbody) return;
    if (!commands || commands.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state"><div class="empty-state-icon"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/></svg></div><p>No active script commands queued</p></td></tr>`;
        return;
    }
    tbody.innerHTML = commands.map(cmd => `
        <tr>
            <td><span class="command-id">${cmd.command_id}</span></td>
            <td><strong class="code">${cmd.target}</strong></td>
            <td class="code">${(cmd.scripts || []).join(', ')}</td>
            <td>${Object.entries(cmd.status || {}).map(([script, status]) =>
                `<span class="status-badge status-${status.toLowerCase()}">${script}: ${status}</span>`
            ).join(' ')}</td>
            <td><span class="ack-icon ${cmd.ack_received ? 'ack-received' : 'ack-pending'}">${cmd.ack_received ? 'Received' : 'Pending'}</span></td>
            <td class="code">${cmd.sent_at || '-'}</td>
        </tr>
    `).join('');
}

async function loadLinuxCommands() {
    try {
        const response = await fetch('/api/linux_commands');
        const data = await response.json();
        if (data && data.active_linux_commands) {
            updateLinuxCommandStatus(data.active_linux_commands);
        }
    } catch (error) {
        console.error('Error loading Linux commands:', error);
    }
}

function updateLinuxCommandStatus(commands) {
    const tbody = document.querySelector('#linux-commands-status');
    if (!tbody) return;
    if (!commands || commands.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state"><div class="empty-state-icon"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg></div><p>No active Linux command logs found</p></td></tr>`;
        return;
    }
    tbody.innerHTML = commands.map(cmd => `
        <tr>
            <td><span class="command-id">${cmd.command_id}</span></td>
            <td><strong class="code">${cmd.target}</strong></td>
            <td class="code" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;" title="${cmd.command}">${cmd.command}</td>
            <td><span class="status-badge status-${(cmd.status || 'unknown').toLowerCase()}">${cmd.status}</span></td>
            <td><span class="code">${cmd.exit_code !== null && cmd.exit_code !== undefined ? cmd.exit_code : '-'}</span></td>
            <td>${cmd.output
                ? `<div class="output-cell" style="text-decoration: underline; color: var(--primary);" onclick="showOutput(\`${cmd.output.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`)">${cmd.output.substring(0, 40)}...</div>`
                : '<span style="color:var(--text-secondary);">Waiting...</span>'
            }</td>
        </tr>
    `).join('');
}

async function sendCommand() {
    const targetEl = document.getElementById('target');
    if (!targetEl) return;
    const target = targetEl.value;
    if (!target) { showAlert('Please select a target node', 'error'); return; }

    const scripts = [], args = {};
    Object.keys(availableCommands).forEach(key => {
        const checkbox = document.getElementById(`script-${key}`);
        if (checkbox && checkbox.checked) {
            scripts.push(key);
            const argsInputEl = document.getElementById(`args-input-${key}`);
            const argsInput = argsInputEl ? argsInputEl.value.trim() : '';
            args[key] = argsInput ? argsInput.split(/\s+/) : [];
        }
    });

    if (scripts.length === 0) { showAlert('Please select at least one script', 'error'); return; }

    const btn = document.getElementById('send-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>Sending...</span>';
    }

    try {
        const response = await fetch('/api/commands', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target, scripts, args })
        });
        const result = await response.json();
        if (result.success) {
            showAlert(`Command sent successfully! ID: ${result.command_id}`, 'success');
            setTimeout(async () => {
                const commands = await fetch('/api/commands').then(r => r.json());
                updateCommandStatus(commands.active_commands);
            }, 1000);
        } else {
            showAlert(`Error: ${result.error}`, 'error');
        }
    } catch (e) {
        showAlert(`Error: ${e.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>Send Command</span>';
        }
    }
}

async function sendLinuxCommand() {
    const targetEl = document.getElementById('linux-target');
    const commandEl = document.getElementById('linux-command');
    if (!targetEl || !commandEl) return;

    const target = targetEl.value;
    const command = commandEl.value.trim();
    
    if (!target)  { showAlert('Please select a target node', 'error'); return; }
    if (!command) { showAlert('Please enter a command', 'error'); return; }

    const btn = document.getElementById('linux-send-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>Executing...</span>';
    }

    try {
        const response = await fetch('/api/linux_commands', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target, command })
        });
        const result = await response.json();
        if (result.success) {
            showAlert(`Linux command sent! ID: ${result.command_id}`, 'success');
            commandEl.value = '';
            setTimeout(loadLinuxCommands, 1000);
        } else {
            showAlert(`Error: ${result.error}`, 'error');
        }
    } catch (e) {
        showAlert(`Error: ${e.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>Execute Command</span>';
        }
    }
}

function showAlert(text, type) {
    const alert = document.getElementById('alert');
    if (!alert) {
        // Fallback to standard alert or toast if element is not in DOM
        console.log(`[ALERT] [${type}] ${text}`);
        return;
    }
    alert.textContent = text;
    alert.className = `alert alert-${type} show`;
    setTimeout(() => alert.className = 'alert', 5000);
}

async function refreshCommandStatus() {
    try {
        const commands = await fetch('/api/commands').then(r => r.json());
        if (commands && commands.active_commands) {
            updateCommandStatus(commands.active_commands);
        }
        loadLinuxCommands();
    } catch (error) {
        console.error('Error refreshing status:', error);
    }
}

// Initial load
loadData();
updateInterval = setInterval(refreshCommandStatus, 5000);
