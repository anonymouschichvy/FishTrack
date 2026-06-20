let batteryChart = null;

function getBatteryIcon(percent, charging) {
    if (charging) return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="16" height="10" rx="2"/><line x1="20" y1="10" x2="20" y2="14"/><polyline points="14 4 18 8 14 12"/></svg>`;
    if (percent === 100) return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="16" height="10" rx="2"/><rect x="4" y="9" width="12" height="6" fill="currentColor"/></svg>`;
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="16" height="10" rx="2"/><rect x="4" y="9" width="${Math.round((percent / 100) * 12)}" height="6" fill="currentColor"/></svg>`;
}

function getPercentClass(percent) {
    if (percent > 60) return 'percent-high';
    if (percent > 20) return 'percent-medium';
    return 'percent-low';
}

function getBarClass(percent) {
    if (percent > 60) return 'bar-high';
    if (percent > 20) return 'bar-medium';
    return 'bar-low';
}

function getStatusText(chargeState) {
    if (!chargeState) return 'Unknown';
    if (chargeState.includes('charging')) return 'Charging';
    if (chargeState.includes('full'))     return 'Full';
    if (chargeState.includes('idle'))     return 'Idle';
    return 'Discharging';
}

function getStatusClass(chargeState) {
    if (!chargeState) return 'status-warning';
    if (chargeState.includes('charging')) return 'status-charging';
    if (chargeState.includes('full'))     return 'status-full';
    return 'status-discharging';
}

function parseCells(cellsData) {
    if (!cellsData) return [];
    const cells = [];
    for (let i = 1; i <= 4; i++) {
        const key = `cell${i}`;
        if (cellsData[key]) {
            const mv = cellsData[key];
            cells.push({ name: `Cell ${i}`, voltage_mv: mv, voltage: mv / 1000 });
        }
    }
    return cells;
}

function renderCellCard(cell) {
    const lowVoltage  = cell.voltage_mv < 3150;
    const percentClass = lowVoltage ? 'percent-low'  : 'percent-high';
    const barClass    = lowVoltage ? 'bar-low'       : 'bar-high';
    const statusClass = lowVoltage ? 'status-warning' : 'status-full';
    const statusText  = lowVoltage ? 'Low'           : 'Good';
    
    // LiFePO4 operating range approx 3.0V to 3.6V per cell
    const cellPercent = Math.min(100, Math.max(0, ((cell.voltage - 3.0) / (3.6 - 3.0)) * 100));

    return `
        <div class="battery-card">
            <div class="battery-header">
                <div class="battery-name">
                    <span class="battery-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="2" y="7" width="16" height="10" rx="2"/>
                            <rect x="4" y="9" width="${Math.round(cellPercent / 100 * 12)}" height="6" fill="currentColor"/>
                        </svg>
                    </span>
                    <span class="battery-title">${cell.name}</span>
                </div>
                <span class="battery-status ${statusClass}">${statusText}</span>
            </div>
            <div class="battery-percent ${percentClass}">${cell.voltage.toFixed(2)} V</div>
            <div class="battery-bar-container">
                <div class="battery-bar ${barClass}" style="width:${cellPercent}%"></div>
            </div>
            <div class="battery-details">
                <div class="detail-item"><div class="detail-label">Voltage (mV)</div><div class="detail-value">${cell.voltage_mv} mV</div></div>
                <div class="detail-item"><div class="detail-label">Status</div><div class="detail-value" style="font-size:0.95rem; font-weight:600;">${lowVoltage ? 'Under 3.15 V' : 'Balanced'}</div></div>
            </div>
            ${lowVoltage ? `
            <div class="warning-banner">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4m0 4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/></svg>
                <span>Voltage Critical</span>
            </div>` : ''}
        </div>
    `;
}

function updateBatteryChart(readings) {
    const ctx = document.getElementById('batteryChart');
    if (!ctx) return;

    // Filter out errors and sort chronologically (oldest to newest)
    const validReadings = readings.filter(r => !r.error && r.timestamp);
    if (validReadings.length === 0) return;
    
    const chronologicalReadings = [...validReadings].reverse();

    const labels = chronologicalReadings.map(r => {
        const d = new Date(r.timestamp * 1000);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    });
    const voltages = chronologicalReadings.map(r => r.voltage_v);
    const currents = chronologicalReadings.map(r => r.current_ma);

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#d1d5db' : '#475569';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(148, 163, 184, 0.1)';

    if (batteryChart) {
        batteryChart.data.labels = labels;
        batteryChart.data.datasets[0].data = voltages;
        batteryChart.data.datasets[1].data = currents;
        
        // Update scales & tick colors dynamically for theme change
        batteryChart.options.scales['y-voltage'].title.color = textColor;
        batteryChart.options.scales['y-voltage'].ticks.color = textColor;
        batteryChart.options.scales['y-voltage'].grid.color = gridColor;
        
        batteryChart.options.scales['y-current'].title.color = textColor;
        batteryChart.options.scales['y-current'].ticks.color = textColor;
        
        batteryChart.options.scales.x.ticks.color = textColor;
        batteryChart.options.scales.x.grid.color = gridColor;
        
        batteryChart.options.plugins.legend.labels.color = textColor;
        
        batteryChart.update();
    } else {
        batteryChart = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Pack Voltage (V)',
                        data: voltages,
                        borderColor: '#0284c7',
                        backgroundColor: 'rgba(2, 132, 199, 0.1)',
                        borderWidth: 2,
                        yAxisID: 'y-voltage',
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'Current Draw (mA)',
                        data: currents,
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.05)',
                        borderWidth: 2,
                        yAxisID: 'y-current',
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    'y-voltage': {
                        type: 'linear',
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Voltage (V)',
                            color: textColor
                        },
                        ticks: {
                            color: textColor
                        },
                        grid: {
                            color: gridColor
                        }
                    },
                    'y-current': {
                        type: 'linear',
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Current (mA)',
                            color: textColor
                        },
                        ticks: {
                            color: textColor
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    },
                    x: {
                        ticks: {
                            color: textColor
                        },
                        grid: {
                            color: gridColor
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: textColor,
                            font: {
                                family: 'system-ui, -apple-system, sans-serif'
                            }
                        }
                    }
                }
            }
        });

        // Listen for theme mutations to immediately redraw the chart
        const themeObserver = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === 'data-theme' && batteryChart) {
                    const isDarkTheme = document.documentElement.getAttribute('data-theme') === 'dark';
                    const activeColor = isDarkTheme ? '#d1d5db' : '#475569';
                    const activeGrid = isDarkTheme ? 'rgba(255, 255, 255, 0.08)' : 'rgba(148, 163, 184, 0.1)';

                    batteryChart.options.scales['y-voltage'].title.color = activeColor;
                    batteryChart.options.scales['y-voltage'].ticks.color = activeColor;
                    batteryChart.options.scales['y-voltage'].grid.color = activeGrid;

                    batteryChart.options.scales['y-current'].title.color = activeColor;
                    batteryChart.options.scales['y-current'].ticks.color = activeColor;

                    batteryChart.options.scales.x.ticks.color = activeColor;
                    batteryChart.options.scales.x.grid.color = activeGrid;

                    batteryChart.options.plugins.legend.labels.color = activeColor;
                    batteryChart.update();
                }
            });
        });
        themeObserver.observe(document.documentElement, { attributes: true });
    }
}

async function updateBatteryData() {
    try {
        const response = await fetch('/api/battery_data');
        const data = await response.json();

        const grid = document.getElementById('battery-grid');

        if (!data || !data.success) {
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="loading-text" style="font-size:1.5rem;color:#991b1b;">API Error</div>
                    <div class="loading-text">${data?.error || 'Failed to fetch battery data'}</div>
                </div>`;
            return;
        }

        if (data.recent_readings && data.recent_readings.length > 0) {
            const latestReading = data.recent_readings[0];

            if (latestReading.error) {
                grid.innerHTML = `
                    <div class="empty-state">
                        <div class="loading-text" style="font-size:1.5rem;color:#991b1b;">Error</div>
                        <div class="loading-text">${latestReading.error}</div>
                    </div>`;
                return;
            }

            // Update stats cards
            const percent = latestReading.percent || 0;
            const chargeState = latestReading.charge_state || 'unknown';
            const statusText = getStatusText(chargeState);
            const charging = chargeState.includes('charging');

            // Header system badge
            const systemBadge = document.getElementById('system-status-badge');
            if (systemBadge) {
                systemBadge.textContent = `BMS: ${statusText}`;
                systemBadge.className = `status-badge ${charging ? 'charging' : 'discharging'}`;
            }

            // Remaining capacity card
            const capVal = document.getElementById('capacity-val');
            const capPct = document.getElementById('capacity-pct');
            if (capVal && capPct) {
                capVal.textContent = `${latestReading.remaining_mah || 0} mAh`;
                capPct.textContent = `${percent}% capacity available`;
                capPct.className = `stat-change ${getPercentClass(percent)}`;
            }

            // Voltage card
            const voltVal = document.getElementById('voltage-val');
            const vbusVal = document.getElementById('vbus-val');
            if (voltVal && vbusVal) {
                voltVal.textContent = `${(latestReading.voltage_v || 0).toFixed(2)} V`;
                vbusVal.textContent = `VBUS: ${(latestReading.vbus_voltage_v || 0).toFixed(2)} V (Solar Input)`;
            }

            // Current draw / charge card
            const currVal = document.getElementById('current-val');
            const runVal = document.getElementById('runtime-val');
            if (currVal && runVal) {
                const draw = latestReading.current_ma || 0;
                currVal.textContent = `${draw >= 0 ? '+' : ''}${draw} mA`;
                currVal.style.color = draw >= 0 ? 'var(--success)' : 'var(--danger)';

                if (charging && latestReading.time_to_full_min) {
                    runVal.textContent = `Est: ${latestReading.time_to_full_min} mins to full`;
                } else if (!charging && latestReading.time_to_empty_min) {
                    const hrs = (latestReading.time_to_empty_min / 60).toFixed(1);
                    runVal.textContent = `Est: ${hrs} hrs remaining`;
                } else {
                    runVal.textContent = `BMS State: ${statusText}`;
                }
            }

            // Cell cards
            const cells = parseCells(latestReading.cells);
            if (cells.length > 0) {
                grid.innerHTML = cells.map(renderCellCard).join('');
            } else {
                grid.innerHTML = `<div class="empty-state"><div class="loading-text">No battery cell telemetry available.</div></div>`;
            }

            // Update Chart.js trends
            updateBatteryChart(data.recent_readings);

        } else {
            grid.innerHTML = `<div class="empty-state"><div class="loading-text">No battery readings found.</div></div>`;
        }

    } catch (error) {
        console.error('Error updating battery data:', error);
        document.getElementById('battery-grid').innerHTML = `
            <div class="empty-state">
                <div class="loading-text" style="color:#991b1b">Connection Error</div>
                <div class="loading-text">Could not load battery data: ${error.message}</div>
            </div>`;
    }
}

// Initial fetch
updateBatteryData();

// Poll telemetry every 10 seconds (aligned with simulator feed frequency)
setInterval(updateBatteryData, 10000);
