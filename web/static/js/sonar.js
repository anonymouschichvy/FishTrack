async function updateSonarData() {
    try {
        const response = await fetch('/api/sonar_data');
        const data = await response.json();

        if (!data || !data.success) {
            throw new Error(data?.error || 'Failed to fetch sonar data');
        }

        const records = data.records || [];
        const totalScans = data.total_scans || records.length;
        const detections = data.detections || records.filter(r => r['Fish Detect'] > 0).length;
        const totalFish = records.reduce((sum, r) => sum + (r['Fish Detect'] || 0), 0);
        const detectionRate = totalScans > 0 ? (detections / totalScans * 100) : 0;

        animateValue('total-scans', 0, totalScans, 1000);
        animateValue('scans-with-fish', 0, detections, 1000);
        animateValue('total-fish', 0, totalFish, 1000);

        document.getElementById('detection-rate').textContent = detectionRate.toFixed(1);
        updateProgressCircle(detectionRate);

        document.getElementById('timestamp').innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display: inline; vertical-align: middle; margin-right: 6px;">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            Last updated: ${new Date().toLocaleString()}
        `;

        updateRecentScans(records.slice(0, 20));

    } catch (error) {
        console.error('Error fetching sonar data:', error);
        const grid = document.getElementById('scans-grid');
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="15" y1="9" x2="9" y2="15"></line>
                        <line x1="9" y1="9" x2="15" y2="15"></line>
                    </svg>
                </div>
                <p class="empty-text">Error loading sonar data: ${error.message}</p>
            </div>
        `;
    }
}

function animateValue(id, start, end, duration) {
    const element = document.getElementById(id);
    const range = end - start;
    const increment = range / (duration / 16);
    let current = start;

    const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
            current = end;
            clearInterval(timer);
        }
        element.textContent = Math.floor(current).toLocaleString();
    }, 16);
}

function updateProgressCircle(percentage) {
    const circle = document.getElementById('progress-circle');
    const chartPercentage = document.getElementById('chart-percentage');
    const circumference = 2 * Math.PI * 140;
    const offset = circumference - (percentage / 100) * circumference;
    circle.style.strokeDashoffset = offset;
    chartPercentage.textContent = Math.round(percentage) + '%';
}

function updateRecentScans(scans) {
    const grid = document.getElementById('scans-grid');

    if (!scans || scans.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="8" x2="12" y2="12"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                </div>
                <p class="empty-text">No recent scans available</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = scans.map((scan, index) => {
        const fishCount = scan["Fish Detect"] || 0;
        const imageName = scan["Image Name"] || 'Unknown';
        const detections = scan.Detections || [];
        const cardClass = fishCount > 0 ? "scan-card has-fish" : "scan-card";

        return `
            <div class="${cardClass}" style="animation-delay: ${0.1 * index}s;">
                <div class="scan-header">
                    <div class="scan-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                        </svg>
                    </div>
                    <div class="scan-name">${imageName}</div>
                </div>

                <div class="fish-count-display">
                    <div class="fish-count-number">${fishCount}</div>
                    <div class="fish-count-label">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 12s4-6 9-6 9 6 9 6-4 6-9 6-9-6-9-6z"/>
                            <circle cx="9" cy="12" r="1"/>
                        </svg>
                        Fish Detected
                    </div>
                </div>

                ${detections.length > 0 ? `
                    <div class="detection-details">
                        ${detections.map((det, idx) => `
                            <div class="detection-item">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="12" cy="12" r="10"></circle>
                                    <polyline points="12 6 12 12 16 14"></polyline>
                                </svg>
                                Detection ${idx + 1}: ${formatDetection(det)}
                            </div>
                        `).join('')}
                    </div>
                ` : `
                    <div class="detection-details">
                        <div class="detection-item" style="text-align:center;color:var(--gray);">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"></circle>
                                <line x1="12" y1="8" x2="12" y2="12"></line>
                                <line x1="12" y1="16" x2="12.01" y2="16"></line>
                            </svg>
                            No detailed detection data
                        </div>
                    </div>
                `}
            </div>
        `;
    }).join('');
}

function formatDetection(detection) {
    if (typeof detection === 'object') {
        return Object.entries(detection).map(([k, v]) => `${k}: ${v}`).join(', ');
    }
    return JSON.stringify(detection);
}

updateSonarData();
setInterval(updateSonarData, 10000);