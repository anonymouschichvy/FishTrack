// Initialize map
const map = L.map('map').setView([0, 0], 2);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19
}).addTo(map);

let markers = [];
let polyline = null;
let allPoints = [];

async function updateGPSData() {
    try {
        const response = await fetch('/api/gps_data');
        const data = await response.json();

        if (!data || !data.success) {
            throw new Error(data?.error || 'Failed to fetch GPS data');
        }

        markers.forEach(m => map.removeLayer(m));
        if (polyline) map.removeLayer(polyline);
        markers = [];

        let points = [];

        if (data.current && data.current.latitude && data.current.longitude) {
            const numSats = data.current.num_satellites
                ? parseInt(data.current.num_satellites)
                : data.current.satellites || 0;
            points.push({
                lat: data.current.latitude,
                lon: data.current.longitude,
                timestamp: data.current.recorded_at_utc || data.current.timestamp || new Date().toISOString(),
                speed: data.current.speed_kmh || 0,
                satellites: numSats,
                altitude: data.current.altitude_m || 0,
                fix_quality: data.current.fix_quality || 0
            });
        }

        if (data.history && Array.isArray(data.history)) {
            const historyPoints = data.history
                .filter(p => p.latitude && p.longitude)
                .map(p => ({
                    lat: p.latitude,
                    lon: p.longitude,
                    timestamp: p.recorded_at_utc || p.timestamp || new Date().toISOString(),
                    speed: p.speed_kmh || 0,
                    satellites: p.num_satellites ? parseInt(p.num_satellites) : p.satellites || 0,
                    altitude: p.altitude_m || 0,
                    fix_quality: p.fix_quality || 0
                }));
            // Sort history oldest to newest to ensure proper chronological path drawing
            historyPoints.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            if (historyPoints.length > 0) points = historyPoints;
        }

        allPoints = points;
        document.getElementById('point-count').textContent = points.length;
        document.getElementById('stat-points').textContent = points.length;

        if (points.length > 0) {
            const latLngs = points.map(p => [p.lat, p.lon]);
            polyline = L.polyline(latLngs, {
                color: '#6366f1', weight: 4, opacity: 0.8,
                smoothFactor: 1, dashArray: '10, 5'
            }).addTo(map);

            points.forEach((point, idx) => {
                const isFirst = idx === 0;
                const isLast = idx === points.length - 1;
                let markerStyle = 'background-color: var(--primary);';
                if (isFirst) markerStyle = 'background-color: var(--success);';
                else if (isLast) markerStyle = 'background-color: var(--danger);';

                const customIcon = L.divIcon({
                    html: `<div style="width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); ${markerStyle}"></div>`,
                    className: 'custom-marker-dot',
                    iconSize: [14, 14], iconAnchor: [7, 7]
                });

                const marker = L.marker([point.lat, point.lon], { icon: customIcon }).addTo(map);
                marker.bindPopup(`
                    <div style="min-width:220px;font-family:'Inter',sans-serif;">
                        <div style="font-weight:700;font-size:1.125rem;margin-bottom:0.75rem;color:#0f172a;">
                            Point ${idx + 1}
                            ${isFirst ? ' <span style="color:#10b981;">(Start)</span>' : isLast ? ' <span style="color:#ef4444;">(Latest)</span>' : ''}
                        </div>
                        <div style="font-size:0.875rem;color:#64748b;margin-bottom:1rem;font-family:'Cascadia Code',monospace;">
                            ${new Date(point.timestamp).toLocaleString()}
                        </div>
                        <div style="display:grid;gap:0.75rem;font-size:0.875rem;">
                            <div style="background:#f1f5f9;padding:0.5rem;border-radius:6px;">
                                <strong>Coordinates:</strong><br>
                                <span style="font-family:'Cascadia Code',monospace;">${point.lat.toFixed(6)}, ${point.lon.toFixed(6)}</span>
                            </div>
                            <div style="background:#f1f5f9;padding:0.5rem;border-radius:6px;">
                                <strong>Altitude:</strong> <span style="font-family:'Cascadia Code',monospace;">${point.altitude || 'N/A'}m</span>
                            </div>
                            <div style="background:#f1f5f9;padding:0.5rem;border-radius:6px;">
                                <strong>Speed:</strong> <span style="font-family:'Cascadia Code',monospace;">${parseFloat(point.speed || 0).toFixed(2)} km/h</span>
                            </div>
                            <div style="background:#f1f5f9;padding:0.5rem;border-radius:6px;">
                                <strong>Satellites:</strong> <span style="font-family:'Cascadia Code',monospace;">${point.satellites || 'N/A'}</span>
                            </div>
                            <div style="background:#f1f5f9;padding:0.5rem;border-radius:6px;">
                                <strong>Fix Quality:</strong> <span style="font-family:'Cascadia Code',monospace;">${getFixQualityText(point.fix_quality)}</span>
                            </div>
                        </div>
                    </div>
                `);
                markers.push(marker);
            });

            map.fitBounds(polyline.getBounds(), { padding: [50, 50] });

            const latestPoint = points[points.length - 1];
            document.getElementById('stat-satellites').textContent = latestPoint.satellites || 0;
            document.getElementById('stat-altitude').textContent = `${latestPoint.altitude || 0}m`;
            document.getElementById('stat-speed').textContent = `${parseFloat(latestPoint.speed || 0).toFixed(2)} km/h`;
            updateFixQualityBadge(latestPoint.fix_quality);
        }

        updateTimeline(points);
        document.getElementById('timestamp').textContent =
            `Last updated: ${new Date().toLocaleString()} • ${points.length} tracking points`;

    } catch (error) {
        console.error('Error fetching GPS data:', error);
        document.getElementById('timeline-container').innerHTML = `
            <div class="no-data">
                <div class="no-data-icon" style="color: var(--danger);">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                </div>
                <p class="no-data-text">Error loading GPS data: ${error.message}</p>
            </div>
        `;
    }
}

function updateTimeline(points) {
    const container = document.getElementById('timeline-container');

    if (!points || points.length === 0) {
        container.innerHTML = `
            <div class="no-data" style="padding: 2.5rem 1rem; text-align:center;">
                <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:0.75rem;"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                <p style="color:var(--text-muted);font-size:0.9rem;">No GPS tracking data available</p>
            </div>
        `;
        return;
    }

    const rows = points.map((point, idx) => {
        const isFirst = idx === 0;
        const isLast  = idx === points.length - 1;

        let badge = '';
        if (isFirst) badge = `<span class="dt-badge dt-badge--start">Start</span>`;
        else if (isLast) badge = `<span class="dt-badge dt-badge--latest"><span class="dt-pulse"></span>Latest</span>`;

        const dotColor = isFirst ? 'var(--success)' : isLast ? 'var(--danger)' : 'var(--primary)';
        const rowClass = isLast ? 'dt-row dt-row--latest' : 'dt-row';
        const fixLabel = getFixQualityText(point.fix_quality || 0);

        return `
        <tr class="${rowClass}" onclick="focusPoint(${point.lat}, ${point.lon}, ${idx})">
            <td class="dt-cell dt-cell--num">
                <span class="dt-dot" style="background:${dotColor};"></span>
                <span class="dt-num">${idx + 1}</span>
                ${badge}
            </td>
            <td class="dt-cell dt-cell--time">${new Date(point.timestamp).toLocaleString()}</td>
            <td class="dt-cell dt-cell--coord">${point.lat.toFixed(6)}, ${point.lon.toFixed(6)}</td>
            <td class="dt-cell dt-cell--val">${point.altitude || 0} m</td>
            <td class="dt-cell dt-cell--val">${point.satellites || 0}</td>
            <td class="dt-cell dt-cell--val">${parseFloat(point.speed || 0).toFixed(2)} km/h</td>
            <td class="dt-cell dt-cell--fix">${fixLabel}</td>
        </tr>`;
    }).join('');

    container.innerHTML = `
        <table class="drift-table" role="table" aria-label="Geographic Drift Timeline">
            <thead>
                <tr>
                    <th class="dt-th">#</th>
                    <th class="dt-th">Time</th>
                    <th class="dt-th">Coordinates</th>
                    <th class="dt-th">Alt</th>
                    <th class="dt-th">Sats</th>
                    <th class="dt-th">Speed</th>
                    <th class="dt-th">Fix</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>`;
}

function focusPoint(lat, lon, idx) {
    map.setView([lat, lon], 15, { animate: true, duration: 1 });
    if (markers[idx]) markers[idx].openPopup();
}

function getFixQualityText(quality) {
    const qualities = { 0:'No Fix', 1:'2D Fix', 2:'3D Fix', 3:'DGPS', 4:'RTK Fixed', 5:'RTK Float' };
    return qualities[quality] || 'Unknown';
}

function updateFixQualityBadge(quality) {
    const badge = document.getElementById('fix-quality');
    const text = getFixQualityText(quality);
    let color = 'var(--success)';
    if (quality === 0) { color = 'var(--danger)'; }
    else if (quality === 1) { color = 'var(--warning)'; }
    badge.innerHTML = `<span class="pulse status-dot" style="background: ${color}; margin-right: 6px;"></span><span>${text}</span>`;
    badge.style.color = color;
}

updateGPSData();
setInterval(updateGPSData, 30000);
