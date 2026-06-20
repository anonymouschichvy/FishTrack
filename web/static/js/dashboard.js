/**
 * FishTrack Dashboard Page Handler
 * Handles live telemetry updates + educational chart initializations
 */

let populationChart = null;
let rssiChart = null;

/* ═══════════════════════════════════════════════════════════
   LIVE TELEMETRY UPDATES
   ═══════════════════════════════════════════════════════════ */

async function updateDashboard() {
    try {
        const statusRes = await fetch('/api/status');
        const status = await statusRes.json();

        // Update timestamp
        const now = new Date();
        document.getElementById('timestamp').textContent =
            `Last updated: ${now.toLocaleString()}`;

        // Update stats
        document.getElementById('messages-sent').textContent =
            status.stats?.packets_sent || 0;
        document.getElementById('messages-received').textContent =
            status.stats?.packets_received || 0;
        document.getElementById('connection-status').textContent =
            status.connection_healthy ? 'Healthy' : 'Disconnected';

        // Update status badge
        const badge = document.getElementById('status-badge');
        if (status.connection_healthy) {
            badge.className = 'status-badge status-online';
            badge.innerHTML = '<span class="pulse status-dot status-active"></span> System Online';
        } else {
            badge.className = 'status-badge status-offline';
            badge.innerHTML = '<span class="status-dot" style="background: #ef4444;"></span> System Offline';
        }

        // Fetch neighbors
        const neighborsRes = await fetch('/api/neighbors');
        const neighbors = await neighborsRes.json();

        document.getElementById('neighbor-count').textContent =
            neighbors.total_neighbors || 0;

        const tbody = document.getElementById('neighbor-table');
        if (neighbors.neighbors && neighbors.neighbors.length > 0) {
            tbody.innerHTML = neighbors.neighbors.map(n => `
                <tr>
                    <td><strong>${n.codename}</strong></td>
                    <td>${formatTimestamp(n.last_seen)}</td>
                    <td>${n.rssi || 'N/A'}</td>
                    <td><span class="status-dot status-active"></span> ${n.status}</td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; color: #64748b;">
                        No neighbors detected
                    </td>
                </tr>
            `;
        }

        updateActivityFeed(status);

    } catch (error) {
        console.error('Error updating dashboard:', error);
    }
}

function formatTimestamp(timestamp) {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString();
}

function updateActivityFeed(status) {
    const feed = document.getElementById('activity-feed');
    const activities = [];

    activities.push({ time: new Date(), type: 'info', text: 'System initialized successfully' });

    if (status.stats?.packets_received > 0) {
        activities.push({
            time: new Date(Date.now() - 60000),
            type: 'info',
            text: `Received ${status.stats.packets_received} packets`
        });
    }

    if (status.connection_healthy) {
        activities.push({ time: new Date(Date.now() - 120000), type: 'success', text: 'LoRa connection established' });
    } else {
        activities.push({ time: new Date(Date.now() - 120000), type: 'warning', text: 'LoRa connection unavailable' });
    }

    if (status.stats?.packets_sent > 0) {
        activities.push({
            time: new Date(Date.now() - 180000),
            type: 'info',
            text: `Transmitted ${status.stats.packets_sent} outbound packets`
        });
    }

    feed.innerHTML = activities.map(a => `
        <div class="activity-item activity-${a.type}">
            <div class="activity-meta">
                <div class="activity-time">${a.time.toLocaleTimeString()}</div>
                <span class="activity-badge ${a.type}">${a.type.toUpperCase()}</span>
            </div>
            <div class="activity-text">${a.text}</div>
        </div>
    `).join('');
}

// Initial load
updateDashboard();

// Auto-refresh every 5 seconds
setInterval(updateDashboard, 5000);


/* ═══════════════════════════════════════════════════════════
   CONSERVATION COUNTERS — Animated on scroll
   ═══════════════════════════════════════════════════════════ */

function animateCounter(element, target, suffix, duration = 1800) {
    let start = 0;
    const step = target / (duration / 16);

    const tick = () => {
        start = Math.min(start + step, target);
        const formatted = target >= 1000
            ? Math.floor(start).toLocaleString()
            : Math.floor(start).toString();
        element.textContent = formatted + suffix;
        if (start < target) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
}

function initCounters() {
    const items = document.querySelectorAll('.counter-item');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const item = entry.target;
                const target = parseInt(item.dataset.target, 10);
                const suffix = item.dataset.suffix || '';
                const numEl = item.querySelector('.counter-number');
                if (numEl && !item.dataset.animated) {
                    item.dataset.animated = 'true';
                    animateCounter(numEl, target, suffix);
                }
            }
        });
    }, { threshold: 0.4 });

    items.forEach(item => observer.observe(item));
}


/* ═══════════════════════════════════════════════════════════
   POPULATION TREND CHART (Chart.js)
   ═══════════════════════════════════════════════════════════ */

function initPopulationChart() {
    const ctx = document.getElementById('populationChart');
    if (!ctx || typeof Chart === 'undefined') return;

    const years = ['2015','2016','2017','2018','2019','2020','2021','2022','2023','2024'];

    // BFAR Philippine fisheries production index (normalized to 2015 = 1.0)
    // Bangus: dominant aquaculture, steadily increasing production
    const bangusgData    = [1.00, 1.05, 1.10, 1.14, 1.18, 1.12, 1.19, 1.24, 1.28, 1.33];
    // Galunggong: wild capture, declining due to overfishing pressure
    const galunggongData = [1.00, 0.92, 0.87, 0.83, 0.78, 0.72, 0.70, 0.67, 0.65, 0.63];
    // Lapu-lapu: reef fishery, gradual decline with coral reef degradation
    const lapulапuData   = [1.00, 0.97, 0.94, 0.91, 0.89, 0.86, 0.84, 0.83, 0.81, 0.80];

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';
    const textColor = isDark ? '#94a3b8' : '#64748b';

    const isMobile = window.innerWidth <= 768;

    populationChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: years,
            datasets: [
                {
                    label: 'Bangus / Milkfish (Chanos chanos)',
                    data: bangusgData,
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56,189,248,0.08)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#38bdf8',
                    pointRadius: isMobile ? 3 : 5,
                    pointHoverRadius: isMobile ? 5 : 8,
                    borderWidth: 2.5,
                },
                {
                    label: 'Galunggong / Round Scad (Decapterus macrosoma)',
                    data: galunggongData,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245,158,11,0.08)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#f59e0b',
                    pointRadius: isMobile ? 3 : 5,
                    pointHoverRadius: isMobile ? 5 : 8,
                    borderWidth: 2.5,
                },
                {
                    label: 'Lapu-lapu / Tiger Grouper (Epinephelus fuscoguttatus)',
                    data: lapulапuData,
                    borderColor: '#f97316',
                    backgroundColor: 'rgba(249,115,22,0.08)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#f97316',
                    pointRadius: isMobile ? 3 : 5,
                    pointHoverRadius: isMobile ? 5 : 8,
                    borderWidth: 2.5,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, /* Let CSS container control the height */
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: {
                    position: isMobile ? 'bottom' : 'top',
                    align: 'start',
                    labels: {
                        color: textColor,
                        font: { family: "'Inter', sans-serif", size: isMobile ? 10 : 12 },
                        usePointStyle: true,
                        pointStyleWidth: isMobile ? 8 : 12,
                        boxHeight: 6,
                        padding: isMobile ? 8 : 16,
                        /* Shorten label text on mobile */
                        generateLabels: isMobile ? (chart) => {
                            return chart.data.datasets.map((ds, i) => ({
                                text: ds.label.split(' (')[0].split(' / ')[0], /* e.g. "Bangus" */
                                fillStyle: ds.borderColor,
                                strokeStyle: ds.borderColor,
                                pointStyle: 'circle',
                                hidden: false,
                                datasetIndex: i
                            }));
                        } : undefined,
                    }
                },
                tooltip: {
                    backgroundColor: isDark ? '#1e293b' : '#0f172a',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    borderColor: 'rgba(99,102,241,0.3)',
                    borderWidth: 1,
                    padding: isMobile ? 8 : 12,
                    callbacks: {
                        label: ctx => ` ${ctx.dataset.label.split('(')[0].trim()}: ${ctx.parsed.y.toFixed(2)}x`,
                        title: ctx => `Year: ${ctx[0].label}`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: gridColor },
                    ticks: {
                        color: textColor,
                        font: { family: "'Inter', sans-serif", size: isMobile ? 9 : 11 },
                        maxRotation: isMobile ? 45 : 0,
                    }
                },
                y: {
                    grid: { color: gridColor },
                    ticks: {
                        color: textColor,
                        font: { family: "'Inter', sans-serif", size: isMobile ? 9 : 11 },
                        callback: v => v.toFixed(1) + 'x'
                    },
                    title: {
                        display: !isMobile, /* Hide Y-axis title on mobile to save space */
                        text: 'Relative Production Index (2015 = 1.0) — DA-BFAR Data',
                        color: textColor,
                        font: { family: "'Inter', sans-serif", size: 11 }
                    }
                }
            }
        }
    });
}


/* ═══════════════════════════════════════════════════════════
   RSSI GUIDE CHART (Horizontal Bar)
   ═══════════════════════════════════════════════════════════ */

function initRssiChart() {
    const ctx = document.getElementById('rssiGuideChart');
    if (!ctx || typeof Chart === 'undefined') return;

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#94a3b8' : '#64748b';
    const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';

    rssiChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Poor (<−105)', 'Fair (−105 to −90)', 'Good (−90 to −70)', 'Excellent (−70 to −50)'],
            datasets: [{
                label: 'Signal Quality Range (dBm)',
                data: [15, 25, 35, 55],
                backgroundColor: ['#ef4444','#f59e0b','#0ea5e9','#10b981'],
                borderRadius: 8,
                borderSkipped: false,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: isDark ? '#1e293b' : '#0f172a',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    callbacks: {
                        label: ctx => ` Relative Quality Score: ${ctx.parsed.x}/55`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: gridColor },
                    ticks: { color: textColor, font: { size: 10 } },
                    title: {
                        display: true,
                        text: 'Relative Quality Score →',
                        color: textColor,
                        font: { size: 10 }
                    }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: textColor, font: { family: "'Inter', sans-serif", size: 11 } }
                }
            }
        }
    });
}


/* ═══════════════════════════════════════════════════════════
   SPECIES CARD: Touch support for mobile flip
   ═══════════════════════════════════════════════════════════ */

/**
 * Species card flip:
 * – Desktop: CSS :hover handles flip (pointer:fine + hover media query)
 * – Mobile/touch: tap toggles .flipped class on the inner element
 * A second tap anywhere outside resets all cards (clean UX).
 */
function initSpeciesCardTouch() {
    const cards = document.querySelectorAll('.species-card');

    cards.forEach(card => {
        // Prevent scroll-swipe from triggering flip on mobile carousel
        let touchStartX = 0;
        let touchStartY = 0;
        let isDragging = false;

        card.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            isDragging = false;
        }, { passive: true });

        card.addEventListener('touchmove', (e) => {
            const dx = Math.abs(e.touches[0].clientX - touchStartX);
            const dy = Math.abs(e.touches[0].clientY - touchStartY);
            // If user is swiping horizontally, don't flip
            if (dx > 10 || dy > 10) isDragging = true;
        }, { passive: true });

        card.addEventListener('touchend', (e) => {
            if (isDragging) return; // Ignore swipes — only pure taps flip
            e.preventDefault(); // Prevent ghost click on iOS
            const inner = card.querySelector('.species-card-inner');
            const isFlipped = inner.classList.contains('flipped');

            // Collapse all other flipped cards first
            document.querySelectorAll('.species-card-inner.flipped').forEach(el => {
                if (el !== inner) el.classList.remove('flipped');
            });

            inner.classList.toggle('flipped', !isFlipped);
        });

        // Desktop click also toggles (for hybrid pointer devices / touch monitors)
        card.addEventListener('click', () => {
            // Only activate on non-hover-capable devices
            if (window.matchMedia('(hover: none)').matches) {
                const inner = card.querySelector('.species-card-inner');
                // Already handled by touchend on real touch; this covers desktop touch screens
                inner.classList.toggle('flipped');
            }
        });
    });

    // Tap outside any card to collapse all flipped cards
    document.addEventListener('touchstart', (e) => {
        if (!e.target.closest('.species-card')) {
            document.querySelectorAll('.species-card-inner.flipped')
                .forEach(el => el.classList.remove('flipped'));
        }
    }, { passive: true });
}


/* ═══════════════════════════════════════════════════════════
   MOBILE SIDEBAR: Swipe-to-close gesture + overlay
   ═══════════════════════════════════════════════════════════ */

/**
 * closeSidebarOnMobile: Called by overlay tap or swipe-left.
 * Mirrors toggleMenu() but only closes — safe to call from overlay click.
 */
function closeSidebarOnMobile() {
    const sidebar = document.getElementById('sidebarNav');
    const overlay = document.getElementById('sidebarOverlay');
    if (!sidebar) return;
    sidebar.classList.remove('active');
    if (overlay) overlay.classList.remove('active');
}

/**
 * Patch toggleMenu (defined in onboarding.js / theme.js) to also
 * show/hide the overlay backdrop when sidebar opens/closes on mobile.
 */
document.addEventListener('DOMContentLoaded', () => {
    const sidebar  = document.getElementById('sidebarNav');
    const overlay  = document.getElementById('sidebarOverlay');
    const menuBtn  = document.querySelector('.menu-toggle');

    if (menuBtn && sidebar && overlay) {
        // Intercept the existing menu toggle click
        menuBtn.addEventListener('click', () => {
            // After the default toggleMenu runs, sync overlay state
            requestAnimationFrame(() => {
                const isOpen = sidebar.classList.contains('active');
                overlay.classList.toggle('active', isOpen);
            });
        }, { capture: true });
    }

    // Swipe-right-to-close: detect horizontal swipe on sidebar
    if (sidebar) {
        let swipeStartX = 0;
        sidebar.addEventListener('touchstart', e => {
            swipeStartX = e.touches[0].clientX;
        }, { passive: true });
        sidebar.addEventListener('touchend', e => {
            const dx = swipeStartX - e.changedTouches[0].clientX;
            if (dx > 60) { // Swiped left ≥ 60px — close
                closeSidebarOnMobile();
            }
        }, { passive: true });
    }
});


/* ═══════════════════════════════════════════════════════════
   INIT ALL EDUCATIONAL COMPONENTS
   ═══════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
    initCounters();
    initPopulationChart();
    initRssiChart();
    initSpeciesCardTouch();

    // Listen for theme mutations to immediately update chart colors
    const themeObserver = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            if (mutation.attributeName === 'data-theme') {
                const isDarkTheme = document.documentElement.getAttribute('data-theme') === 'dark';
                const textColor = isDarkTheme ? '#94a3b8' : '#64748b';
                const gridColor = isDarkTheme ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)';

                if (populationChart) {
                    populationChart.options.scales.x.grid.color = gridColor;
                    populationChart.options.scales.y.grid.color = gridColor;
                    populationChart.options.scales.x.ticks.color = textColor;
                    populationChart.options.scales.y.ticks.color = textColor;
                    if (populationChart.options.scales.x.title) {
                        populationChart.options.scales.x.title.color = textColor;
                    }
                    if (populationChart.options.scales.y.title) {
                        populationChart.options.scales.y.title.color = textColor;
                    }
                    if (populationChart.options.plugins.legend && populationChart.options.plugins.legend.labels) {
                        populationChart.options.plugins.legend.labels.color = textColor;
                    }
                    populationChart.update();
                }

                if (rssiChart) {
                    rssiChart.options.scales.x.grid.color = gridColor;
                    rssiChart.options.scales.x.ticks.color = textColor;
                    if (rssiChart.options.scales.x.title) {
                        rssiChart.options.scales.x.title.color = textColor;
                    }
                    rssiChart.options.scales.y.ticks.color = textColor;
                    if (rssiChart.options.plugins.tooltip) {
                        rssiChart.options.plugins.tooltip.backgroundColor = isDarkTheme ? '#1e293b' : '#0f172a';
                    }
                    rssiChart.update();
                }
            }
        }
    });
    themeObserver.observe(document.documentElement, { attributes: true });
});
