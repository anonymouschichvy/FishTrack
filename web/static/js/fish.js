/**
 * FishTrack Fish Detection Monitor Page Handler
 */

let speciesChart = null;

// Stable hash function for rendering consistent bounding box mock coordinates
function getHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    return Math.abs(hash);
}

function getSpeciesIcon(speciesName) {
    return `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" style="margin-right:4px; color: var(--secondary);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 16s9-15 20-4C11 23 2 16 2 16Z"/><circle cx="18" cy="10" r="1"/></svg>`;
}

function updateSpeciesDistributionChart(speciesFreq) {
    const ctx = document.getElementById('speciesChart');
    if (!ctx) return;

    const entries = Object.entries(speciesFreq).sort((a, b) => b[1] - a[1]);
    const labels = entries.map(([species, _]) => species);
    const data = entries.map(([_, count]) => count);

    if (speciesChart) {
        speciesChart.data.labels = labels;
        speciesChart.data.datasets[0].data = data;
        speciesChart.update();
    } else {
        speciesChart = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Detections Count',
                    data: data,
                    backgroundColor: 'rgba(13, 148, 136, 0.7)',
                    borderColor: 'rgba(13, 148, 136, 1)',
                    borderWidth: 1.5,
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: 'y', // horizontal bar chart
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            stepSize: 1
                        }
                    },
                    y: {
                        grid: {
                            display: false
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
}

async function updateFishData() {
    try {
        const response = await fetch('/api/fish_data');
        const data = await response.json();
        
        console.log('Fish API Response:', data);
        
        if (!data || !data.summary) {
            console.error('Invalid data structure:', data);
            throw new Error('Invalid data structure received from API');
        }
        
        // Update stats counters
        document.getElementById('total-images').textContent = data.summary.total_images || 0;
        document.getElementById('total-detections').textContent = data.summary.total_detections || 0;
        document.getElementById('unique-species').textContent = data.summary.unique_species || 0;
        
        // Update species ranking list (Leaderboard)
        const speciesList = document.getElementById('species-list');
        const speciesEntries = Object.entries(data.summary.species_frequency).sort((a, b) => b[1] - a[1]);
        
        const topSpeciesCountEl = document.getElementById('topSpeciesCount');
        if (topSpeciesCountEl) {
            topSpeciesCountEl.textContent = `${speciesEntries.length} classes detected`;
        }

        if (speciesEntries.length > 0) {
            const maxCount = Math.max(...speciesEntries.map(([_, count]) => count));
            
            speciesList.innerHTML = speciesEntries.slice(0, 5).map(([species, count], index) => {
                const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;
                const icon = getSpeciesIcon(species);
                const rank = index + 1;
                const rankClass = rank === 1 ? 'rank-1' : (rank === 2 ? 'rank-2' : (rank === 3 ? 'rank-3' : 'rank-other'));
                
                return `
                    <div class="species-item" style="animation-delay: ${0.05 * index}s;">
                        <span class="rank-badge ${rankClass}">${rank}</span>
                        <div class="species-details">
                            <div class="species-header" style="display:flex; justify-content:space-between; font-size:0.875rem; margin-bottom:0.15rem; width:100%;">
                                <div class="species-name">
                                    <span class="species-icon">${icon}</span>
                                    ${species}
                                </div>
                                <span class="species-count">${count} detections</span>
                            </div>
                            <div class="species-bar-container">
                                <div class="species-bar" style="width: ${percentage}%;"></div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            speciesList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                    </div>
                    <p class="empty-text">No species data available</p>
                </div>
            `;
        }
        
        // Update recent detections cards
        const detectionsGrid = document.getElementById('detections');
        const recentDetections = data.recent_detections.slice(0, 12);
        
        if (recentDetections.length > 0) {
            detectionsGrid.innerHTML = recentDetections.map((det, index) => {
                const imgName = det["Image Name"] || det["Image Filename"] || 'Image Capture';
                const fishCount = det["Fish Detected"] !== undefined ? det["Fish Detected"] : (det["Species Count"] || 0);
                const speciesList = det["Species Detected"] || [];
                
                // Construct high-tech viewfinder target bounding boxes
                const targetsHtml = speciesList.slice(0, 2).map((sp, sIdx) => {
                    const hVal = getHash(sp.species + imgName + sIdx);
                    const top = 12 + (hVal % 38);       // 12% to 50%
                    const left = 12 + ((hVal >> 3) % 43); // 12% to 55%
                    const width = 28 + ((hVal >> 6) % 18); // 28% to 46%
                    const height = 28 + ((hVal >> 9) % 18); // 28% to 46%
                    
                    const confVal = sp.confidence >= 0.85 ? 'high-conf' : (sp.confidence >= 0.70 ? 'medium-conf' : 'low-conf');
                    const speciesAbbr = sp.common_name ? sp.common_name.split(' ')[0] : sp.species.substring(0, 6);
                    
                    return `
                        <div class="cv-target-box ${confVal}" style="top:${top}%; left:${left}%; width:${width}%; height:${height}%;">
                            <span class="cv-target-label">${speciesAbbr} ${(sp.confidence * 100).toFixed(0)}%</span>
                        </div>
                    `;
                }).join('');
                
                return `
                    <div class="detection-card" style="animation-delay: ${0.03 * index}s;">
                        <div class="detection-header">
                            <div style="display:flex; align-items:center; gap:0.5rem;">
                                <svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
                                <span style="font-weight:700; font-size:0.825rem; max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${imgName}">${imgName}</span>
                            </div>
                            <span class="status-pill info" style="font-size:0.725rem; padding:0.2rem 0.5rem; font-weight:bold;">${fishCount} Fish</span>
                        </div>
                        
                        <!-- Premium CV Viewfinder Mock -->
                        <div class="cv-viewfinder">
                            <div class="cv-grid"></div>
                            <div class="cv-crosshair"></div>
                            <div class="cv-corners"></div>
                            ${targetsHtml}
                        </div>

                        <div class="species-detected">
                            ${speciesList.slice(0, 3).map(sp => {
                                const confClass = sp.confidence >= 0.85 ? 'confidence-high' : (sp.confidence >= 0.70 ? 'confidence-med' : 'confidence-low');
                                return `
                                    <div class="species-detection">
                                        <span>${getSpeciesIcon(sp.species)} <strong>${sp.common_name || sp.species}</strong></span>
                                        <span class="confidence ${confClass}">${(sp.confidence * 100).toFixed(0)}%</span>
                                    </div>
                                `;
                            }).join('')}
                            ${speciesList.length === 0 ? `
                                <div class="species-detection" style="justify-content: center; color: var(--text-muted); font-size:0.8rem; text-align:center;">
                                    No detections (Background)
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            detectionsGrid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                    </div>
                    <p class="empty-text">No recent detections available</p>
                </div>
            `;
        }
        
        // Update Chart.js horizontal bar graph
        updateSpeciesDistributionChart(data.summary.species_frequency);
        
    } catch (error) {
        console.error('Error updating fish data:', error);
        document.getElementById('detections').innerHTML = `
            <div class="empty-state">
                <div class="empty-icon" style="color: var(--danger);">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                </div>
                <p class="empty-text">Error loading fish data: ${error.message}</p>
            </div>
        `;
    }
}

// Initial load
updateFishData();

// Poll telemetry every 10 seconds
setInterval(updateFishData, 10000);
