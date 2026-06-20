/**
 * FishTrack Fish Prediction & Analytics Client-Side Script
 * Manages the calendar, leaflet maps, charts, predictions, and glossary elements.
 * Uses only actual buoy metrics (GPS, Satellites, Battery, Camera run, Sonar scan).
 */

// Global State
let currentDate = new Date(2026, 1, 19); // Default local time: February 19, 2026
let activeBuoyName = "BUOY-POSEIDON";
let predictionData = null;
let timelineData = null;
let fishProfiles = [];
let verifiedTelemetryDates = [];
let verifiedDetectionDates = [];

// Global jumpToDate function for warning banner
window.jumpToDate = function(year, month, day) {
    currentDate = new Date(year, month, day);
    updateDateDisplay();
    loadDataForSelectedDate();
};

// Leaflet Map Global
let leafletMap = null;
let buoyMarkers = {};
let hotspotCircles = [];

// Chart.js Globals
let correlationChartInstance = null;
let abundanceChartInstance = null;
let trendChartInstance = null;

// Initialize Page
document.addEventListener("DOMContentLoaded", async () => {
    // 1. Set selected date label on load
    updateDateDisplay();

    // 2. Initialize the Leaflet Map
    initMap();

    // 3. Set up Calendar Navigation Listeners
    document.getElementById("calPrevMonth").addEventListener("click", () => adjustMonth(-1));
    document.getElementById("calNextMonth").addEventListener("click", () => adjustMonth(1));
    document.getElementById("btnResetToday").addEventListener("click", resetToToday);

    // 4. Set up Search Listener for Glossary
    document.getElementById("fishSearchInput").addEventListener("input", filterGlossary);

    // 5. Fetch initial data
    await loadDataForSelectedDate();
    await loadTimelineData();
    await loadFishProfiles();
    
    // 6. Draw calendar days
    renderCalendar();

    // 7. Handle orientation/resize – re-render charts if visuals tab is open
    let _resizeTimer = null;
    window.addEventListener('resize', () => {
        clearTimeout(_resizeTimer);
        _resizeTimer = setTimeout(() => {
            const visPane = document.getElementById('tab-visuals');
            if (visPane && visPane.style.display !== 'none') {
                updateCharts();
            }
        }, 250);
    }, { passive: true });

    // Handle iOS orientation change
    window.addEventListener('orientationchange', () => {
        setTimeout(() => {
            const visPane = document.getElementById('tab-visuals');
            if (visPane && visPane.style.display !== 'none') {
                updateCharts();
            }
        }, 400);
    }, { passive: true });
});

// Update selected date string
function updateDateDisplay() {
    const yyyy = currentDate.getFullYear();
    const mm = String(currentDate.getMonth() + 1).padStart(2, '0');
    const dd = String(currentDate.getDate()).padStart(2, '0');
    const formatted = `${yyyy}-${mm}-${dd}`;
    document.getElementById("selectedDateLabel").textContent = formatted;
}

// Adjust month in calendar
function adjustMonth(delta) {
    currentDate.setMonth(currentDate.getMonth() + delta);
    renderCalendar();
    updateDateDisplay();
    loadDataForSelectedDate();
}

// Reset date to telemetry default (February 19, 2026)
async function resetToToday() {
    currentDate = new Date(2026, 1, 19); // 2026-02-19
    renderCalendar();
    updateDateDisplay();
    await loadDataForSelectedDate();
}

// Render Calendar Widget Days
function renderCalendar() {
    const calendarGrid = document.getElementById("calendarDaysGrid");
    if (!calendarGrid) return;

    // Set Month Label
    const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    document.getElementById("calMonthLabel").textContent = `${monthNames[currentDate.getMonth()]} ${currentDate.getFullYear()}`;

    calendarGrid.innerHTML = "";

    // Day Labels (Sun - Sat)
    const dayLabels = ["S", "M", "T", "W", "T", "F", "S"];
    dayLabels.forEach(lbl => {
        const el = document.createElement("div");
        el.className = "calendar-day-label";
        el.textContent = lbl;
        calendarGrid.appendChild(el);
    });

    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    const firstDayIndex = new Date(year, month, 1).getDay();
    const totalDays = new Date(year, month + 1, 0).getDate();

    // Render empty spaces
    for (let i = 0; i < firstDayIndex; i++) {
        const el = document.createElement("div");
        el.className = "calendar-day empty";
        calendarGrid.appendChild(el);
    }

    // Render calendar days
    for (let d = 1; d <= totalDays; d++) {
        const el = document.createElement("div");
        el.className = "calendar-day";
        
        el.innerHTML = `
            <span class="calendar-day-num">${d}</span>
            <div class="calendar-day-indicators"></div>
        `;

        // Check if selected
        if (d === currentDate.getDate()) {
            el.classList.add("active");
        }

        // Add indicator dots dynamically using verified lists
        const formattedDayStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        const indicatorsDiv = el.querySelector(".calendar-day-indicators");
        
        if (verifiedTelemetryDates && verifiedTelemetryDates.includes(formattedDayStr)) {
            const telemetryDot = document.createElement("span");
            telemetryDot.className = "indicator-dot dot-telemetry";
            telemetryDot.title = "GPS & Battery logs captured";
            indicatorsDiv.appendChild(telemetryDot);
        }
        if (verifiedDetectionDates && verifiedDetectionDates.includes(formattedDayStr)) {
            const detectionsDot = document.createElement("span");
            detectionsDot.className = "indicator-dot dot-detections";
            detectionsDot.title = "Camera YOLO & Sonar detections captured";
            indicatorsDiv.appendChild(detectionsDot);
        }

        el.addEventListener("click", () => {
            currentDate.setDate(d);
            // Re-render selected day active state
            document.querySelectorAll(".calendar-day").forEach(c => c.classList.remove("active"));
            el.classList.add("active");
            updateDateDisplay();
            loadDataForSelectedDate();
        });

        calendarGrid.appendChild(el);
    }
}

// Load Prediction Data from APIs
async function loadDataForSelectedDate() {
    const yyyy = currentDate.getFullYear();
    const mm = String(currentDate.getMonth() + 1).padStart(2, '0');
    const dd = String(currentDate.getDate()).padStart(2, '0');
    const formatted = `${yyyy}-${mm}-${dd}`;

    try {
        const response = await fetch(`/api/analytics/predict/${formatted}`);
        const result = await response.json();
        
        if (result.success) {
            predictionData = result.prediction;
            verifiedTelemetryDates = predictionData.verified_telemetry_dates || [];
            verifiedDetectionDates = predictionData.verified_detection_dates || [];
            updateDashboardUI();
            renderCalendar(); // Refresh calendar to show active and indicator highlights
        } else {
            console.error("API error:", result.error);
        }
    } catch (e) {
        console.error("Failed to load predictions:", e);
    }
}

// Fetch Timeline trend summaries
async function loadTimelineData() {
    try {
        const response = await fetch("/api/analytics/summary?days=14");
        const result = await response.json();
        if (result.success) {
            timelineData = result.timeline;
            updateCharts();
        }
    } catch (e) {
        console.error("Failed to load timeline data:", e);
    }
}

// Fetch fish glossary profiles
async function loadFishProfiles() {
    try {
        if (predictionData && predictionData.buoys[activeBuoyName]) {
            const list = predictionData.buoys[activeBuoyName].predictions;
            fishProfiles = list.map(item => ({
                scientific_name: item.scientific_name,
                common_name: item.common_name,
                availability: item.availability_period,
                municipalities: item.location_preference,
                depth_range: item.depth_range,
                importance: item.importance,
                citation: item.citation
            }));
            renderGlossary();
            updateCharts(); // Draw charts again after profiles load for the database breakdown
        }
    } catch (e) {
        console.error("Failed to build fish profiles:", e);
    }
}

// Update the entire Dashboard UI
function updateDashboardUI() {
    if (!predictionData) return;

    // 1. Render Buoy selector tabs
    renderBuoyTabs();

    // 1b. Check if activeBuoyName is still valid in prediction data
    const buoys = Object.keys(predictionData.buoys);
    if (buoys.length > 0 && !buoys.includes(activeBuoyName)) {
        activeBuoyName = buoys[0];
        renderBuoyTabs(); // re-render with the correct active tab
    }

    // 1c. Update map markers dynamically based on the received buoys
    updateMapMarkers();

    const buoyInfo = predictionData.buoys[activeBuoyName];
    if (!buoyInfo) return;

    // 2. Set current title/info
    document.getElementById("currentBuoyTitle").textContent = `${activeBuoyName} Telemetry Summary`;
    document.getElementById("currentBuoyDesc").textContent = `${buoyInfo.location_desc} | Coordinates: ${buoyInfo.coordinates.lat.toFixed(3)}, ${buoyInfo.coordinates.lon.toFixed(3)}`;
    
    // 3. Set header status badges
    const wqEl = document.getElementById("buoyWaterQuality");
    wqEl.textContent = buoyInfo.water_quality_status;
    wqEl.className = "status-pill " + (buoyInfo.water_quality_status === "Hardware Online" ? "success" : "danger");
    
    const bioEl = document.getElementById("buoyBiodiversity");
    bioEl.textContent = `Biodiversity: ${buoyInfo.biodiversity_indicator}`;
    bioEl.className = "status-pill " + (buoyInfo.biodiversity_indicator === "Optimal" ? "success" : "warning");

    // Update Telemetry Offline Warning Banner visibility
    const offlineBannerEl = document.getElementById("telemetryOfflineBanner");
    if (offlineBannerEl) {
        if (buoyInfo.environmental_conditions.has_data === false) {
            offlineBannerEl.style.display = "flex";
            const offlineBuoyNameEl = document.getElementById("offlineBuoyName");
            if (offlineBuoyNameEl) offlineBuoyNameEl.textContent = activeBuoyName;
            const offlineDateLabelEl = document.getElementById("offlineDateLabel");
            if (offlineDateLabelEl) {
                const yyyy = currentDate.getFullYear();
                const mm = String(currentDate.getMonth() + 1).padStart(2, '0');
                const dd = String(currentDate.getDate()).padStart(2, '0');
                offlineDateLabelEl.textContent = `${yyyy}-${mm}-${dd}`;
            }
        } else {
            offlineBannerEl.style.display = "none";
        }
    }

    // Update Reference Mode Warning Banner visibility
    const bannerEl = document.getElementById("referenceModeBanner");
    if (bannerEl) {
        if (buoyInfo.environmental_conditions.is_fallback) {
            bannerEl.style.display = "flex";
            const refDateLabel = document.getElementById("referenceDateLabel");
            if (refDateLabel) {
                refDateLabel.textContent = buoyInfo.environmental_conditions.reference_date;
            }
        } else {
            bannerEl.style.display = "none";
        }
    }

    // 4. Render Telemetry indicators (actual buoy parameters)
    renderTelemetryGrid(buoyInfo.environmental_conditions);

    // 5. Render Predictions list
    renderPredictionsList(buoyInfo.predictions);

    // 6. Render Recommendations and Warnings
    renderRecommendations(buoyInfo.recommendations, buoyInfo.alerts);

    // 7. Render AI Insights narrative
    renderAIInsights(buoyInfo);

    // 8. Update map marker highlights
    highlightActiveMapBuoy();
}

// Render Buoy Tabs
function renderBuoyTabs() {
    const tabContainer = document.getElementById("buoyTabBar");
    if (!tabContainer) return;

    const buoys = Object.keys(predictionData.buoys);
    tabContainer.innerHTML = buoys.map(bName => {
        const isActive = bName === activeBuoyName ? "active" : "";
        const indicator = bName === "BUOY-POSEIDON" ? "⚓" : (bName === "BUOY-AMPHITRITE" ? "🐚" : (bName === "BUOY-TRITON" ? "🔱" : "📡"));
        return `
            <button class="buoy-tab-btn ${isActive}" onclick="setActiveBuoy('${bName}')">
                <span>${indicator}</span> ${bName}
            </button>
        `;
    }).join('');
}

// Set active buoy tab
function setActiveBuoy(bName) {
    activeBuoyName = bName;
    updateDashboardUI();
    loadFishProfiles();
}

// Render actual buoy telemetry grid
function renderTelemetryGrid(env) {
    const grid = document.getElementById("telemetryGrid");
    if (!grid) return;

    const hasData = env.has_data !== false;

    const items = [
        { 
            label: "GPS Coordinates", 
            val: `${env.latitude.toFixed(3)}°, ${env.longitude.toFixed(3)}°`, 
            icon: "📍",
            isOffline: false 
        },
        { 
            label: "Satellites", 
            val: env.num_satellites !== null ? `${env.num_satellites} Sats` : "Offline", 
            icon: "🛰️",
            isOffline: env.num_satellites === null
        },
        { 
            label: "GPS Quality", 
            val: env.fix_quality || "Offline", 
            icon: "🛡️",
            isOffline: env.fix_quality === "Offline" || env.fix_quality === "No Fix"
        },
        { 
            label: "Battery Level", 
            val: env.battery_percent !== null ? `${env.battery_percent}%` : "Offline", 
            icon: "🔋",
            isOffline: env.battery_percent === null
        },
        { 
            label: "Battery Voltage", 
            val: env.battery_voltage_v !== null ? `${env.battery_voltage_v} V` : "-- V", 
            icon: "⚡",
            isOffline: env.battery_voltage_v === null
        },
        { 
            label: "BMS State", 
            val: env.battery_charge_state || "Offline", 
            icon: "🔌",
            isOffline: env.battery_charge_state === "Offline"
        },
        { 
            label: "Camera Runs", 
            val: `${env.camera_processed_frames} frames`, 
            icon: "📸",
            isOffline: env.camera_processed_frames === 0 && !hasData
        },
        { 
            label: "Sonar Runs", 
            val: `${env.sonar_total_scans} scans`, 
            icon: "📡",
            isOffline: env.sonar_total_scans === 0 && !hasData
        }
    ];

    grid.innerHTML = items.map(item => `
        <div class="telemetry-badge ${item.isOffline ? 'offline' : ''}">
            <span style="font-size:1.5rem; margin-bottom:0.25rem;">${item.icon}</span>
            <span class="telemetry-val">${item.val}</span>
            <span class="telemetry-label">${item.label}</span>
        </div>
    `).join('');
}

// Render prediction list cards
function renderPredictionsList(predictions) {
    const listContainer = document.getElementById("predictionsList");
    if (!listContainer) return;

    document.getElementById("predictionsCount").textContent = `${predictions.length} species predicted`;

    listContainer.innerHTML = predictions.slice(0, 15).map((pred, index) => {
        const confClass = pred.confidence.toLowerCase();
        
        const matchesHtml = pred.matches.map(m => `
            <div class="factor-item">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="color:var(--success);"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <span>${m}</span>
            </div>
        `).join('');

        const mismatchesHtml = pred.mismatches.map(m => `
            <div class="factor-item">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="color:var(--danger);"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                <span>${m}</span>
            </div>
        `).join('');

        return `
            <div style="display:flex; flex-direction:column; gap:0.25rem;">
                <div class="prediction-item-card" onclick="toggleDetailsCard('details-${index}')">
                    <div class="prediction-item-main">
                        <span class="fish-common-name">🐟 ${pred.common_name}</span>
                        <span class="fish-sci-name">${pred.scientific_name}</span>
                        <span class="fish-avail-badge">${pred.availability_period}</span>
                    </div>
                    <div class="confidence-pill ${confClass}">${pred.confidence}</div>
                    <div class="prob-meter-wrapper">
                        <div class="prob-bar-container">
                            <div class="prob-bar-fill" style="width: ${pred.probability}%;"></div>
                        </div>
                        <span class="prob-percentage">${pred.probability}%</span>
                    </div>
                </div>
                
                <!-- Hidden factor details pane with BFAR citation -->
                <div id="details-${index}" class="glass-panel" style="display:none; padding:1rem; border-radius:0 0 var(--radius-md) var(--radius-md); border-top:none; margin-top:-6px; animation: fadeIn var(--transition-fast) forwards;">
                    <div class="pred-factor-lists">
                        <div class="pred-factor-list">
                            <span class="factor-title match">Match Factors</span>
                            ${matchesHtml || '<span class="factor-item" style="color:var(--text-muted);">None</span>'}
                        </div>
                        <div class="pred-factor-list">
                            <span class="factor-title mismatch">Limiting Factors</span>
                            ${mismatchesHtml || '<span class="factor-item" style="color:var(--text-muted);">None</span>'}
                        </div>
                    </div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); margin-top:0.75rem; border-top:1px solid var(--border); padding-top:0.5rem; line-height:1.4;">
                        <strong>Municipality Availability:</strong> ${pred.location_preference}<br>
                        <strong>Typical Depth:</strong> ${pred.depth_range}<br>
                        <strong>Economic Value:</strong> ${pred.importance}<br>
                        <strong style="color:var(--primary);">BFAR MIMAROPA Citation:</strong> <span style="font-size:0.7rem; color:var(--text-muted);">${pred.citation}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('') + `
        <div style="font-size:0.7rem; text-align:center; padding:0.5rem; color:var(--text-muted); border-top:1px solid var(--border); margin-top:1rem; line-height:1.3;">
            ⚠️ Telemetry variables are restricted to verified hardware packets (GPS spatial vectors, Pico cell BMS indicators, camera captures, and acoustic sonar sweeps). Sourced from BFAR Marinduque registers.
        </div>
    `;
}

// Toggle prediction item details panel
function toggleDetailsCard(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = el.style.display === "none" ? "block" : "none";
}

// Render Recommendations & Warnings
function renderRecommendations(recs, alerts) {
    const alertsContainer = document.getElementById("alertsLogContainer");
    alertsContainer.innerHTML = "";

    if (alerts.length > 0) {
        alertsContainer.innerHTML = alerts.map(alt => {
            const iconColor = alt.type === "warning" ? "var(--danger)" : (alt.type === "caution" ? "var(--warning)" : "var(--info)");
            return `
                <div class="alert-item-card ${alt.type}">
                    <div class="alert-icon-svg" style="color: ${iconColor};">
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    </div>
                    <div class="alert-content-wrapper">
                        <h5>${alt.title}</h5>
                        <p>${alt.message}</p>
                    </div>
                </div>
            `;
        }).join('');
    } else {
        alertsContainer.innerHTML = `
            <div class="alert-item-card info" style="background:var(--success-light); border-color:rgba(34,197,94,0.15);">
                <div class="alert-icon-svg" style="color: var(--success);">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                </div>
                <div class="alert-content-wrapper">
                    <h5 style="color:var(--success);">Hardware BMS Online</h5>
                    <p>All connected nodes report healthy cell metrics. Satellites tracking count and cell decay curves remain stable.</p>
                </div>
            </div>
        `;
    }

    const recsContainer = document.getElementById("recsGrid");
    recsContainer.innerHTML = recs.map((rec, i) => {
        const labels = ["Spatial Intelligence", "Catch Recommendation", "Operational Guidance", "Energy Preservation"];
        return `
            <div class="rec-card">
                <strong>💡 ${labels[i] || 'Operational Guidance'}</strong>
                ${rec}
            </div>
        `;
    }).join('');
}

// Render AI Insights narrative based on actual buoy metrics
function renderAIInsights(buoyInfo) {
    const box = document.getElementById("aiInsightsBox");
    if (!box) return;

    if (buoyInfo.ai_analysis) {
        box.innerHTML = buoyInfo.ai_analysis;
        return;
    }

    const env = buoyInfo.environmental_conditions;
    const topFish = buoyInfo.predictions[0];
    const secondFish = buoyInfo.predictions[1];

    box.innerHTML = `
        <p><strong>Actual Telemetry Insights:</strong> Active buoy <strong>${activeBuoyName}</strong> is positioned at coordinates <strong>${env.latitude.toFixed(4)}°N, ${env.longitude.toFixed(4)}°E</strong> (${buoyInfo.location_desc}, ${env.water_body} zone). The onboard GPS receiver tracks <strong>${env.num_satellites} satellites</strong> with a robust <strong>${env.fix_quality}</strong>, and the LiFePO4 battery BMS cell registers a stable <strong>${env.battery_voltage_v} V (${env.battery_percent}% charge)</strong>.</p>
        <p><strong>BFAR Seasonality & Location Matches:</strong> Sourced from the authoritative BFAR MIMAROPA list noted by Joel G. Malabana (OIC PFO), the current month matches the prime availability cycle for <strong>${topFish.common_name}</strong> (${topFish.availability_period}). The location category matches the species' municipal profile: <em>"${topFish.location_preference}"</em>.</p>
        <p><strong>YOLO & Sonar Correlation:</strong> The buoy camera processed <strong>${env.camera_processed_frames} frames</strong>, while the sonar scanner recorded <strong>${env.sonar_total_scans} sweeps</strong> with <strong>${env.sonar_detections_count} acoustic biomass targets</strong>. These actual detection events provide verified biological evidence supporting a <strong>${topFish.probability}%</strong> presence probability for <strong>${topFish.common_name}</strong> and <strong>${secondFish.probability}%</strong> for <strong>${secondFish.common_name}</strong> in this sector.</p>
    `;
}

// Switch between prediction tabs
function switchPredictionTab(tabName) {
    const btns = document.querySelectorAll(".tab-btn");
    btns.forEach(btn => {
        btn.classList.remove("active");
    });
    
    document.querySelectorAll(".tab-pane").forEach(pane => {
        pane.classList.remove("active");
        pane.style.setProperty("display", "none", "important");
    });

    // Find the button that calls this tabName in its onclick attribute
    const clickedBtn = Array.from(btns).find(btn => {
        const onc = btn.getAttribute("onclick");
        return onc && onc.includes(tabName);
    });
    if (clickedBtn) clickedBtn.classList.add("active");

    const targetPane = document.getElementById(`tab-${tabName}`);
    if (targetPane) {
        targetPane.classList.add("active");
        targetPane.style.setProperty("display", "flex", "important");
    }

    // Re-render Chart.js graphs when visuals tab is displayed to calculate correct dimensions
    if (tabName === 'visuals') {
        updateCharts();
    }
}

// Render Glossary profiles list
function renderGlossary(filterText = "") {
    const grid = document.getElementById("fishGlossaryGrid");
    if (!grid) return;

    const search = filterText.toLowerCase().trim();
    const filtered = fishProfiles.filter(profile => {
        return profile.common_name.toLowerCase().includes(search) || 
               profile.scientific_name.toLowerCase().includes(search) ||
               profile.importance.toLowerCase().includes(search) ||
               profile.municipalities.toLowerCase().includes(search);
    });

    document.getElementById("glossaryCount").textContent = `${filtered.length} profiles`;

    if (filtered.length > 0) {
        grid.innerHTML = filtered.map(profile => `
            <div class="fish-glossary-card">
                <h4>
                    🐟 ${profile.common_name}
                    <span>${profile.scientific_name}</span>
                </h4>
                <div class="fish-attribute-row"><strong>Availability:</strong> <span>${profile.availability}</span></div>
                <div class="fish-attribute-row"><strong>Found in:</strong> <span>${profile.municipalities}</span></div>
                <div class="fish-attribute-row"><strong>Typical Depth:</strong> <span>${profile.depth_range}</span></div>
                <div class="fish-attribute-row" style="margin-top:0.25rem; font-size:0.75rem; border-top:1px dashed var(--border); padding-top:0.4rem;">
                    <strong>Ecological Value:</strong> <span>${profile.importance}</span>
                </div>
                <div style="font-size:0.65rem; color:var(--text-muted); margin-top:0.35rem; line-height:1.2; border-top:1px dotted var(--border); padding-top:0.3rem;">
                    <strong>Source:</strong> ${profile.citation}
                </div>
            </div>
        `).join('');
    } else {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1; padding: 2rem;">
                <p class="empty-text">No fish matching "${filterText}" found.</p>
            </div>
        `;
    }
}

// Filter Glossary items on search input
function filterGlossary(e) {
    renderGlossary(e.target.value);
}

// Initialize Leaflet Map
function initMap() {
    const mapEl = document.getElementById("predictionMap");
    if (!mapEl) return;

    leafletMap = L.map('predictionMap', {
        zoomControl: false,
        attributionControl: false
    }).setView([13.400, 121.900], 10);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18
    }).addTo(leafletMap);
}

let mapMarkersGroup = null; // Leaflet feature group to manage markers dynamically

// Render map markers dynamically based on actual prediction buoys list
function updateMapMarkers() {
    if (!leafletMap || !predictionData) return;

    // Clear existing markers/circles if any
    if (mapMarkersGroup) {
        leafletMap.removeLayer(mapMarkersGroup);
    }
    hotspotCircles.forEach(circle => leafletMap.removeLayer(circle));
    hotspotCircles = [];
    buoyMarkers = {};

    mapMarkersGroup = L.featureGroup().addTo(leafletMap);

    const colors = ["#4f46e5", "#0d9488", "#d97706", "#8b5cf6", "#ec4899", "#f59e0b"];
    let colorIdx = 0;

    Object.entries(predictionData.buoys).forEach(([name, buoyInfo]) => {
        const lat = buoyInfo.coordinates.lat;
        const lon = buoyInfo.coordinates.lon;
        const color = colors[colorIdx % colors.length];
        colorIdx++;

        const marker = L.circleMarker([lat, lon], {
            radius: 8,
            fillColor: color,
            originalColor: color, // Store color dynamically in options
            color: "#ffffff",
            weight: 2,
            fillOpacity: 1.0
        }).addTo(mapMarkersGroup);

        marker.bindPopup(`<strong>${name}</strong><br>Click to activate telemetry.`);
        
        marker.on("click", () => {
            setActiveBuoy(name);
        });

        buoyMarkers[name] = marker;

        const zone = L.circle([lat, lon], {
            radius: 3500,
            color: color,
            fillColor: color,
            fillOpacity: 0.08,
            weight: 1
        }).addTo(leafletMap);

        hotspotCircles.push(zone);
    });

    highlightActiveMapBuoy();
}

// Highlighting map active buoy
function highlightActiveMapBuoy() {
    if (!leafletMap || !buoyMarkers) return;

    Object.entries(buoyMarkers).forEach(([name, marker]) => {
        if (name === activeBuoyName) {
            marker.setStyle({
                radius: 12,
                weight: 3,
                fillColor: "#ff0055"
            });
            leafletMap.panTo(marker.getLatLng());
        } else {
            const originalColor = marker.options.originalColor || "#4f46e5";
            marker.setStyle({
                radius: 8,
                weight: 2,
                fillColor: originalColor
            });
        }
    });
}

// Update Chart.js Visualizations (Using actual data)
function updateCharts() {
    if (!timelineData) return;

    const dates = timelineData.map(d => d.date);
    const cameraCounts = timelineData.map(d => (d.buoys && d.buoys[activeBuoyName]) ? d.buoys[activeBuoyName].camera_detections : 0);
    const sonarCounts = timelineData.map(d => (d.buoys && d.buoys[activeBuoyName]) ? d.buoys[activeBuoyName].sonar_detections : 0);
    const totalDetections = timelineData.map(d => d.total_detections);

    // 1. Camera vs Sonar Correlation Chart
    const correlationCtx = document.getElementById("cameraSonarCorrelationChart");
    if (correlationCtx) {
        if (correlationChartInstance) correlationChartInstance.destroy();
        correlationChartInstance = new Chart(correlationCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'Camera Detections Count',
                        data: cameraCounts,
                        borderColor: 'rgba(79, 70, 229, 1)',
                        backgroundColor: 'rgba(79, 70, 229, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'Sonar Target Echoes',
                        data: sonarCounts,
                        borderColor: 'rgba(13, 148, 136, 1)',
                        backgroundColor: 'rgba(13, 148, 136, 0.05)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }

    // 2. Seasonal species database breakdown chart
    const abundanceCtx = document.getElementById("seasonalAbundanceChart");
    if (abundanceCtx && fishProfiles.length > 0) {
        // Compute ratios
        let yearRound = 0;
        let marchMay = 0;
        let aprilJune = 0;
        let other = 0;

        fishProfiles.forEach(p => {
            const av = p.availability.toLowerCase();
            if (av.includes("year-round")) yearRound++;
            else if (av.includes("march") && av.includes("may")) marchMay++;
            else if (av.includes("april") && av.includes("june")) aprilJune++;
            else other++;
        });

        if (abundanceChartInstance) abundanceChartInstance.destroy();
        abundanceChartInstance = new Chart(abundanceCtx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Year-round Resident', 'March–May Migrant', 'April–June Migrant', 'Other Cycle'],
                datasets: [{
                    data: [yearRound, marchMay, aprilJune, other],
                    backgroundColor: [
                        'rgba(13, 148, 136, 0.8)', // teal
                        'rgba(79, 70, 229, 0.8)', // indigo
                        'rgba(217, 119, 6, 0.8)', // amber
                        'rgba(148, 163, 184, 0.8)' // slate
                    ],
                    borderColor: 'var(--bg-surface)',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: 'var(--text-primary)',
                            boxWidth: 12,
                            font: { size: 10 }
                        }
                    }
                }
            }
        });
    }

    // 3. Total Abundance over Time chart
    const trendCtx = document.getElementById("occurrenceTrendChart");
    if (trendCtx) {
        if (trendChartInstance) trendChartInstance.destroy();
        trendChartInstance = new Chart(trendCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: dates,
                datasets: [{
                    label: 'Fleet-wide YOLO Detections',
                    data: totalDetections,
                    backgroundColor: 'rgba(217, 119, 6, 0.7)',
                    borderColor: 'rgba(217, 119, 6, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }
}
