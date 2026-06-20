// Search & Command Palette Handler for FishTrack Base Station

const paletteData = [
    // Pages / Navigation
    { title: "Dashboard", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>`, category: "Navigation", description: "Base station main metrics, active nodes, and map summary", action: () => window.location.href = "/" },
    { title: "Networks Map", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 15V9m-4 4H10M9 6h6"/></svg>`, category: "Navigation", description: "D3.js dynamic mesh node routing and RF hops diagram", action: () => window.location.href = "/networks/" },
    { title: "Command Center", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`, category: "Navigation", description: "Queue preset script commands for remote buoy nodes", action: () => window.location.href = "/commands/" },
    { title: "Linux Console", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>`, category: "Navigation", description: "Interactive terminal shell bridge for buoy nodes", action: () => window.location.href = "/linux_commands/" },
    { title: "Job Scheduler", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`, category: "Navigation", description: "Configure recurring or delayed telemetry sweeps", action: () => window.location.href = "/scheduler/" },
    { title: "Fish Detections Monitor", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 12c0 3.037-3.714 5.5-8.5 5.5-.963 0-1.884-.102-2.735-.29C10.63 17.583 9 19 9 19c-.3 0-.5-.2-.5-.5v-2.022C5.074 15.358 2 13.568 2 12c0-1.568 3.074-3.358 6.5-4.478V5.5c0-.3.2-.5.5-.5 0 0 1.63 1.417 2.765 1.79C12.616 6.602 13.537 6.5 14.5 6.5c4.786 0 8.5 2.463 8.5 5.5z"/><circle cx="18" cy="11" r="1"/></svg>`, category: "Navigation", description: "Real-time AI camera species classifications feed", action: () => window.location.href = "/monitors/fish/" },
    { title: "Sonar Profiler", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 0 1 10 10H2a10 10 0 0 1 10-10zm0 4a6 6 0 0 1 6 6H6a6 6 0 0 1 6-6zm0 4a2 2 0 0 1 2 2H10a2 2 0 0 1 2-2z"/></svg>`, category: "Navigation", description: "Sonar depth scanner water-column profiling graphics", action: () => window.location.href = "/monitors/sonar/" },
    { title: "GPS Tracking", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`, category: "Navigation", description: "Geographic coordinate logs and map tracks", action: () => window.location.href = "/monitors/gps/" },
    { title: "Battery Health Monitor", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="6" width="18" height="12" rx="2" ry="2"/><line x1="23" y1="11" x2="23" y2="13"/></svg>`, category: "Navigation", description: "BMS capacity logs, cell metrics, and charge curves", action: () => window.location.href = "/monitors/battery/" },
    { title: "System Settings", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`, category: "Navigation", description: "Configure discovery timings and expected node list", action: () => window.location.href = "/settings/" },

    // Quick Actions
    { title: "Toggle Color Theme", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`, category: "System Actions", description: "Switch between dark mode and light mode", action: () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        const btn = document.querySelector('.theme-pill');
        if (btn) {
            btn.classList.toggle('dark', newTheme === 'dark');
            btn.setAttribute('aria-pressed', newTheme === 'dark');
        }
        closePalette();
    }},
    { title: "Start Guided Tour", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>`, category: "System Actions", description: "Launch step-by-step onboarding walkthrough", action: () => {
        closePalette();
        if (window.startOnboardingTour) window.startOnboardingTour();
    }},
    { title: "Submit Operator Feedback", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`, category: "System Actions", description: "Open issue logging and severity checklist dialog", action: () => {
        closePalette();
        if (window.openFeedbackModal) window.openFeedbackModal();
    }},
    { title: "Clear All Events", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`, category: "System Actions", description: "Purge local events database in notification drawer", action: () => {
        if (window.clearNotifications) window.clearNotifications();
        closePalette();
    }},

    // Glossary / Knowledge Base
    { title: "LoRa (Long Range)", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`, category: "Glossary", description: "Low-power radio standard operating on sub-GHz ISM band.", action: () => showGlossaryInfo("LoRa", "A spread-spectrum modulation technique derived from chirp spread spectrum (CSS) technology, designed for low-power, long-distance telemetry.") },
    { title: "RSSI — Signal Strength", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`, category: "Glossary", description: "Received Signal Strength Indicator in dBm. Closer to 0 is stronger.", action: () => showGlossaryInfo("RSSI", "A measurement of power present in a received radio signal. Closer to 0 dBm is stronger; marine links usually operate between -30 dBm (excellent) and -110 dBm (disconnect).") },
    { title: "SNR — Signal-to-Noise", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`, category: "Glossary", description: "Signal-to-noise ratio in dB. Higher is cleaner.", action: () => showGlossaryInfo("SNR", "The ratio of signal power to noise power. Positive values indicate a strong signal, while negative values indicate the signal is below the noise floor.") },
    { title: "BMS — Power Controller", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`, category: "Glossary", description: "Battery Management System protecting cell balancing.", action: () => showGlossaryInfo("BMS", "Battery Management System. Electronic controller protecting lithium cells from overvoltage, undervoltage, and overcurrent conditions.") },
    { title: "YOLO Species Model", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`, category: "Glossary", description: "AI neural network detecting fish frames in milliseconds.", action: () => showGlossaryInfo("YOLO Model", "You Only Look Once. A fast, state-of-the-art neural network architecture used for real-time underwater species object detection.") },
    { title: "Hop Count", icon: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`, category: "Glossary", description: "Number of intermediate mesh transmitters routing packets.", action: () => showGlossaryInfo("Hops", "The number of intermediate relay transmitters a packet travels through from source buoy to base station.") }
];

// ─── CSS injected once — all palette colours live here ───────────────────────
// Uses your app's existing --text / --text-secondary / --border / --bg-hover
// vars, with sensible light-mode fallbacks so nothing is ever invisible.
(function injectPaletteStyles() {
    if (document.getElementById('palette-styles')) return;
    const s = document.createElement('style');
    s.id = 'palette-styles';
    s.textContent = `
        /* ── palette item text ── */
        .palette-item-title {
            font-size: 13.5px;
            font-weight: 600;
            color: var(--text, #111827);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 1px;
        }
        .palette-item-desc {
            font-size: 12px;
            color: var(--text-secondary, #6b7280);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        /* ── section header ── */
        .palette-section-header {
            padding: 8px 10px 3px;
            font-size: 10.5px;
            font-weight: 600;
            color: var(--text-muted, #9ca3af);
            letter-spacing: 0.08em;
            text-transform: uppercase;
            user-select: none;
        }
        /* ── icon box ── */
        .palette-icon-box {
            width: 32px;
            height: 32px;
            flex-shrink: 0;
            border-radius: 7px;
            border: 1px solid var(--border, rgba(0,0,0,0.1));
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-secondary, #6b7280);
        }
        .palette-icon-box.cat-nav    { background: rgba(79, 106, 240, 0.1); }
        .palette-icon-box.cat-system { background: rgba(139, 92, 246, 0.1); }
        .palette-icon-box.cat-gloss  { background: rgba(16, 185, 129, 0.1); }

        /* ── category badge ── */
        .palette-badge {
            flex-shrink: 0;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
            white-space: nowrap;
        }
        .palette-badge.cat-nav {
            background: rgba(79, 106, 240, 0.12);
            color: var(--primary, #4f6af0);
            border: 1px solid rgba(79, 106, 240, 0.25);
        }
        .palette-badge.cat-system {
            background: rgba(139, 92, 246, 0.12);
            color: #7c3aed;
            border: 1px solid rgba(139, 92, 246, 0.25);
        }
        .palette-badge.cat-gloss {
            background: rgba(16, 185, 129, 0.12);
            color: #059669;
            border: 1px solid rgba(16, 185, 129, 0.25);
        }

        /* ── dark mode overrides ── */
        [data-theme="dark"] .palette-item-title  { color: var(--text, rgba(255,255,255,0.92)); }
        [data-theme="dark"] .palette-item-desc   { color: var(--text-secondary, rgba(255,255,255,0.45)); }
        [data-theme="dark"] .palette-section-header { color: var(--text-muted, rgba(255,255,255,0.3)); }
        [data-theme="dark"] .palette-icon-box    { border-color: rgba(255,255,255,0.08); color: rgba(255,255,255,0.55); }
        [data-theme="dark"] .palette-badge.cat-nav    { color: #818cf8; border-color: rgba(129,140,248,0.3); }
        [data-theme="dark"] .palette-badge.cat-system { color: #c084fc; border-color: rgba(192,132,252,0.3); }
        [data-theme="dark"] .palette-badge.cat-gloss  { color: #34d399; border-color: rgba(52,211,153,0.3); }

        /* ── hover row ── */
        .palette-item:hover { background: var(--bg-hover, rgba(0,0,0,0.05)) !important; }
        [data-theme="dark"] .palette-item:hover { background: var(--bg-hover, rgba(255,255,255,0.06)) !important; }

        /* ── empty state ── */
        .palette-empty {
            padding: 2.5rem 1rem;
            text-align: center;
            color: var(--text-secondary, #9ca3af);
            font-size: 13px;
        }
    `;
    document.head.appendChild(s);
})();

// ─── helpers ─────────────────────────────────────────────────────────────────

function catClass(category) {
    if (category === "Navigation")     return "cat-nav";
    if (category === "System Actions") return "cat-system";
    if (category === "Glossary")       return "cat-gloss";
    return "";
}

// ─── PALETTE OPEN / CLOSE ────────────────────────────────────────────────────

function openPalette() {
    const modal = document.getElementById('paletteModal');
    if (!modal) return;
    modal.showModal();
    const input = document.getElementById('paletteInput');
    if (input) { input.value = ""; input.focus(); }
    renderPaletteResults(paletteData);
}

function closePalette() {
    const modal = document.getElementById('paletteModal');
    if (modal) modal.close();
}

// ─── SEARCH FILTER ───────────────────────────────────────────────────────────

function filterPaletteResults() {
    const input = document.getElementById('paletteInput');
    if (!input) return;
    const query = input.value.toLowerCase().trim();
    if (!query) { renderPaletteResults(paletteData); return; }
    const filtered = paletteData.filter(item =>
        item.title.toLowerCase().includes(query) ||
        item.category.toLowerCase().includes(query) ||
        item.description.toLowerCase().includes(query)
    );
    renderPaletteResults(filtered);
}

// ─── RENDER ──────────────────────────────────────────────────────────────────

function renderPaletteResults(items) {
    const container = document.getElementById('paletteResults');
    if (!container) return;
    window.currentPaletteItems = items;

    if (items.length === 0) {
        container.innerHTML = `
            <div class="palette-empty">
                <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:block;margin:0 auto 8px;opacity:0.4;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                No results found matching your search.
            </div>`;
        return;
    }

    // Group by category preserving insertion order
    const groups = {};
    items.forEach((item, index) => {
        if (!groups[item.category]) groups[item.category] = [];
        groups[item.category].push({ ...item, _index: index });
    });

    let html = '';
    for (const [cat, catItems] of Object.entries(groups)) {
        const cc = catClass(cat);
        html += `<div class="palette-section-header">${cat}</div>`;
        catItems.forEach(item => {
            html += `
                <div
                    class="palette-item"
                    id="palette-item-${item._index}"
                    onclick="executePaletteItem(${item._index})"
                    style="display:flex;align-items:center;gap:12px;padding:8px 10px;border-radius:8px;cursor:pointer;margin-bottom:1px;transition:background 0.12s ease;"
                >
                    <div class="palette-icon-box ${cc}">${item.icon}</div>
                    <div style="flex:1;min-width:0;">
                        <div class="palette-item-title">${item.title}</div>
                        <div class="palette-item-desc">${item.description}</div>
                    </div>
                    <span class="palette-badge ${cc}">${item.category}</span>
                </div>`;
        });
    }
    container.innerHTML = html;
}

// ─── EXECUTE ─────────────────────────────────────────────────────────────────

function executePaletteItem(index) {
    const items = window.currentPaletteItems || paletteData;
    if (items[index] && typeof items[index].action === 'function') {
        items[index].action();
    }
}

// ─── GLOSSARY ────────────────────────────────────────────────────────────────

function showGlossaryInfo(title, definition) {
    closePalette();
    const drawer = document.getElementById('helpDrawer');
    if (!drawer) return;
    const drawerBody = drawer.querySelector('.help-drawer-body');
    if (drawerBody) {
        if (!window.originalHelpContent) {
            window.originalHelpContent = drawerBody.innerHTML;
        }
        drawerBody.innerHTML = `
            <div class="help-section" style="animation:fadeIn 0.3s ease;">
                <h4 style="color:var(--primary);font-size:1.15rem;margin-bottom:0.5rem;display:flex;align-items:center;gap:0.5rem;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                    <span>${title}</span>
                </h4>
                <p style="font-size:0.92rem;line-height:1.6;color:var(--text-primary, var(--text));">${definition}</p>
            </div>
            <div style="margin-top:2rem;">
                <button class="btn btn-secondary" onclick="restorePageDocs()" style="font-size:0.8rem;padding:0.5rem 1rem;">View Page Docs</button>
            </div>`;
    }
    drawer.classList.add('active');
}

window.restorePageDocs = function() {
    const drawer = document.getElementById('helpDrawer');
    if (!drawer) return;
    const drawerBody = drawer.querySelector('.help-drawer-body');
    if (drawerBody && window.originalHelpContent) {
        drawerBody.innerHTML = window.originalHelpContent;
    }
};

// ─── KEYBOARD SHORTCUTS ──────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        openPalette();
    }
    if (e.key === 'Escape') closePalette();
});

document.addEventListener('click', (e) => {
    const modal = document.getElementById('paletteModal');
    if (modal && e.target === modal) closePalette();
});