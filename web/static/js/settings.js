let originalSettings = {};

async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        originalSettings = { ...settings };
        document.getElementById('discovery_interval').value = settings.discovery_interval || 60;
        document.getElementById('neighbor_timeout').value   = settings.neighbor_timeout   || 300;
        const activeList = settings.active_list || [];
        document.getElementById('active_list').value = Array.isArray(activeList) ? activeList.join('\n') : '';
    } catch (e) {
        console.error('Error loading settings:', e);
        showMessage(`Error loading settings: ${e.message}`, 'error');
    }
}

async function saveSettings() {
    const saveBtn = document.getElementById('saveBtn');
    const originalHTML = saveBtn.innerHTML;

    try {
        saveBtn.classList.add('loading');
        saveBtn.innerHTML = '<span class="loading"></span> <span>Saving...</span>';

        const activeListArray = document.getElementById('active_list').value
            .split('\n').map(s => s.trim()).filter(s => s.length > 0);

        const settings = {
            discovery_interval: parseInt(document.getElementById('discovery_interval').value),
            neighbor_timeout:   parseInt(document.getElementById('neighbor_timeout').value),
            active_list: activeListArray
        };

        if (settings.discovery_interval < 10 || settings.discovery_interval > 600) {
            showMessage('Discovery interval must be between 10 and 600 seconds', 'error'); return;
        }
        if (settings.neighbor_timeout < 60 || settings.neighbor_timeout > 1800) {
            showMessage('Neighbor timeout must be between 60 and 1800 seconds', 'error'); return;
        }
        if (settings.active_list.length === 0) {
            showMessage('Please add at least one BUOY node to the active list', 'error'); return;
        }

        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        const result = await response.json();

        if (response.ok && result.success) {
            originalSettings = { ...settings };
            showMessage('Settings saved successfully! Active node list updated immediately. Restart BASE station to apply network timing changes.', 'success');
        } else {
            showMessage('Failed to save settings. Please try again.', 'error');
        }
    } catch (e) {
        console.error('Error saving settings:', e);
        showMessage(`Error: ${e.message}`, 'error');
    } finally {
        saveBtn.classList.remove('loading');
        saveBtn.innerHTML = originalHTML;
    }
}

function resetForm() {
    document.getElementById('discovery_interval').value = originalSettings.discovery_interval || 60;
    document.getElementById('neighbor_timeout').value   = originalSettings.neighbor_timeout   || 300;
    const activeList = originalSettings.active_list || [];
    document.getElementById('active_list').value = Array.isArray(activeList) ? activeList.join('\n') : '';
    showMessage('Settings reset to last saved values.', 'success');
}

function showMessage(text, type) {
    const msg = document.getElementById('message');
    msg.textContent = text;
    msg.className = `message ${type} show`;
    setTimeout(() => msg.classList.remove('show'), 8000);
}

loadSettings();

document.addEventListener('keydown', e => {
    if (e.ctrlKey && e.key === 's') { e.preventDefault(); saveSettings(); }
});
