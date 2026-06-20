// FishTrack Mesh Routing Map Visualizer & Data Controller

let nodeBatteryMap = {};
let showLinkFlow = true;
let showLinkLabels = true;
let zoom = null;

function formatTime(timestamp) {
    if (!timestamp) return 'Never';
    return new Date(timestamp * 1000).toLocaleString('en-US', {
        month: '2-digit', day: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
    });
}

function getStatusClass(status) {
    return `status-${(status || 'unknown').toLowerCase()}`;
}

function getSignalQuality(rssi) {
    if (!rssi || rssi === 'N/A') return { text: 'No Signal', class: 'signal-none', icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--text-muted);"><line x1="1" y1="1" x2="23" y2="23"/><path d="M2 20h.01" style="opacity:0.3;"/><path d="M7 20v-4" style="opacity:0.3;"/><path d="M12 20v-8" style="opacity:0.3;"/><path d="M17 20v-12" style="opacity:0.3;"/><path d="M22 20V4" style="opacity:0.3;"/></svg>` };
    const rssiNum = parseInt(rssi);
    if (rssiNum >= -50) return { text: 'Excellent', class: 'signal-excellent', icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--success);"><path d="M2 20h.01"/><path d="M7 20v-4"/><path d="M12 20v-8"/><path d="M17 20v-12"/><path d="M22 20V4"/></svg>` };
    if (rssiNum >= -70) return { text: 'Good',      class: 'signal-good',      icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--success); opacity:0.95;"><path d="M2 20h.01"/><path d="M7 20v-4"/><path d="M12 20v-8"/><path d="M17 20v-12"/><path d="M22 20v-16" style="opacity:0.3;"/></svg>` };
    if (rssiNum >= -80) return { text: 'Fair',      class: 'signal-fair',      icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--warning);"><path d="M2 20h.01"/><path d="M7 20v-4"/><path d="M12 20v-8"/><path d="M17 20v-12" style="opacity:0.3;"/><path d="M22 20V4" style="opacity:0.3;"/></svg>` };
    return { text: 'Poor', class: 'signal-poor', icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--danger);"><path d="M2 20h.01"/><path d="M7 20v-4"/><path d="M12 20v-8" style="opacity:0.3;"/><path d="M17 20v-12" style="opacity:0.3;"/><path d="M22 20V4" style="opacity:0.3;"/></svg>` };
}

function animateValue(id, start, end, duration) {
    const element = document.getElementById(id);
    if (!element) return;
    const range = end - start;
    const increment = range / (duration / 16);
    let current = start;
    const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
            current = end; clearInterval(timer);
        }
        element.textContent = Math.floor(current);
    }, 16);
}

// Fetch battery data to construct codename -> percentage lookup map
async function fetchBatteryStats() {
    try {
        const response = await fetch('/api/data/battery?limit=50');
        const resJson = await response.json();
        if (resJson.success && resJson.data) {
            const sorted = [...resJson.data].sort((a, b) => {
                const tA = a._metadata?.received_at || 0;
                const tB = b._metadata?.received_at || 0;
                return tA - tB;
            });
            sorted.forEach(d => {
                const codename = d._metadata?.received_from;
                const pct = d.battery?.percent;
                if (codename && pct !== undefined) {
                    nodeBatteryMap[codename] = pct;
                }
            });
        }
    } catch (error) {
        console.error('Error fetching battery metrics:', error);
    }
}

// D3.js Network Topology Map Rendering
let simulation = null;

function renderTopologyGraph(nodesData, linksData) {
    const svg = d3.select("#topologySvg");
    if (svg.empty()) return;

    // Clear existing SVG
    svg.selectAll("*").remove();

    const width = svg.node().getBoundingClientRect().width || 500;
    const height = 450;

    // Define main SVG containers
    const gContainer = svg.append("g");

    // Add Zoom/Pan Behavior
    zoom = d3.zoom()
        .scaleExtent([0.5, 3])
        .on("zoom", (event) => {
            gContainer.attr("transform", event.transform);
        });
    svg.call(zoom);

    // Bind Zoom Buttons (if not already bound)
    const zoomInBtn = document.getElementById("zoomInBtn");
    const zoomOutBtn = document.getElementById("zoomOutBtn");
    const zoomResetBtn = document.getElementById("zoomResetBtn");
    const toggleFlowBtn = document.getElementById("toggleFlowBtn");
    const toggleLabelsBtn = document.getElementById("toggleLabelsBtn");

    if (zoomInBtn) {
        zoomInBtn.onclick = () => {
            svg.transition().duration(250).call(zoom.scaleBy, 1.3);
        };
    }
    if (zoomOutBtn) {
        zoomOutBtn.onclick = () => {
            svg.transition().duration(250).call(zoom.scaleBy, 1 / 1.3);
        };
    }
    if (zoomResetBtn) {
        zoomResetBtn.onclick = () => {
            svg.transition().duration(350).call(zoom.transform, d3.zoomIdentity);
        };
    }
    if (toggleFlowBtn) {
        toggleFlowBtn.onclick = () => {
            showLinkFlow = !showLinkFlow;
            d3.selectAll(".flow-link").style("display", showLinkFlow ? "block" : "none");
            toggleFlowBtn.style.color = showLinkFlow ? "var(--primary)" : "var(--text-muted)";
        };
        toggleFlowBtn.style.color = showLinkFlow ? "var(--primary)" : "var(--text-muted)";
    }
    if (toggleLabelsBtn) {
        toggleLabelsBtn.onclick = () => {
            showLinkLabels = !showLinkLabels;
            d3.selectAll(".link-label").style("display", showLinkLabels ? "block" : "none");
            toggleLabelsBtn.style.color = showLinkLabels ? "var(--primary)" : "var(--text-muted)";
        };
        toggleLabelsBtn.style.color = showLinkLabels ? "var(--primary)" : "var(--text-muted)";
    }

    // Filter and construct node list
    const nodes = [
        { id: "BASE", label: "BASE STATION (SINK)", type: "BASE", status: "ONLINE", x: width / 2, y: height / 2, fx: width / 2, fy: height / 2 }
    ];

    nodesData.forEach(n => {
        if (n.codename !== "BASE") {
            nodes.push({
                id: n.codename,
                label: n.codename,
                type: "BUOY",
                status: n.status || "ONLINE",
                hops: n.hops !== 'N/A' ? parseInt(n.hops) : 1,
                rssi: n.rssi || -70
            });
        }
    });

    // Build links list based on hops hierarchy
    const links = [];
    nodes.forEach(n => {
        if (n.type === "BASE") return;
        
        if (n.hops === 1) {
            links.push({ source: n.id, target: "BASE", rssi: n.rssi, type: "direct" });
        } else {
            // Find a parent candidate that has hops = n.hops - 1
            const parent = nodes.find(p => p.type === "BUOY" && p.hops === n.hops - 1);
            if (parent) {
                links.push({ source: n.id, target: parent.id, rssi: n.rssi, type: "relay" });
            } else {
                links.push({ source: n.id, target: "BASE", rssi: n.rssi, type: "relay" });
            }
        }
    });

    // Setup force simulation
    simulation = d3.forceSimulation(nodes)
        .force("link", d3.forceLink(links).id(d => d.id).distance(130))
        .force("charge", d3.forceManyBody().strength(-280))
        .force("collision", d3.forceCollide().radius(50))
        .force("center", d3.forceCenter(width / 2, height / 2));

    // Draw base connection links (thick lines)
    const link = gContainer.append("g")
        .selectAll(".base-link")
        .data(links)
        .enter().append("line")
        .attr("class", "base-link")
        .attr("stroke", d => {
            const rssiNum = parseInt(d.rssi);
            if (rssiNum >= -70) return "var(--success)";
            if (rssiNum >= -90) return "var(--warning)";
            return "var(--danger)";
        })
        .attr("stroke-width", 3.5)
        .attr("opacity", 0.7);

    // Draw telemetry packet streams (dash animation line)
    const flowLink = gContainer.append("g")
        .selectAll(".flow-link")
        .data(links)
        .enter().append("line")
        .attr("class", "flow-link link-traffic-flow")
        .attr("stroke-width", 1.5)
        .style("display", showLinkFlow ? "block" : "none");

    // Draw link label (RSSI value on mid-points)
    const linkText = gContainer.append("g")
        .selectAll(".link-label")
        .data(links)
        .enter().append("text")
        .attr("class", "link-label")
        .text(d => `${d.rssi} dBm`)
        .attr("font-size", "0.725rem")
        .attr("font-family", "monospace")
        .attr("font-weight", "bold")
        .attr("fill", "var(--text-secondary)")
        .attr("text-anchor", "middle")
        .style("display", showLinkLabels ? "block" : "none");

    // Draw nodes groups
    const node = gContainer.append("g")
        .selectAll("g")
        .data(nodes)
        .enter().append("g")
        .call(drag(simulation));

    // Base Station Concentric Ripples
    node.filter(d => d.type === "BASE")
        .append("circle")
        .attr("class", "base-ripple")
        .attr("r", 22);

    node.filter(d => d.type === "BASE")
        .append("circle")
        .attr("class", "base-ripple base-ripple-2")
        .attr("r", 22);

    // Base Station central element
    node.filter(d => d.type === "BASE")
        .append("circle")
        .attr("r", 22)
        .attr("fill", "var(--primary)")
        .attr("stroke", "var(--bg-surface)")
        .attr("stroke-width", 2)
        .attr("cursor", "pointer")
        .style("filter", "drop-shadow(0px 0px 8px rgba(79, 70, 229, 0.45))");

    // Buoy node elements
    node.filter(d => d.type === "BUOY")
        .append("circle")
        .attr("r", 15)
        .attr("fill", d => {
            if (d.status === "ONLINE") return "var(--success)";
            if (d.status === "IDLE") return "var(--warning)";
            return "var(--danger)";
        })
        .attr("stroke", "var(--bg-surface)")
        .attr("stroke-width", 1.5)
        .attr("cursor", "pointer");

    // Outer battery percentage ring arc for Buoys
    const arcGenerator = d3.arc()
        .innerRadius(17.5)
        .outerRadius(20.5)
        .startAngle(0);

    node.filter(d => d.type === "BUOY")
        .append("path")
        .attr("d", d => {
            const percent = nodeBatteryMap[d.id] !== undefined ? nodeBatteryMap[d.id] : 100;
            const endAngle = (percent / 100) * 2 * Math.PI;
            return arcGenerator({ endAngle: endAngle });
        })
        .attr("fill", d => {
            const percent = nodeBatteryMap[d.id] !== undefined ? nodeBatteryMap[d.id] : 100;
            if (percent > 60) return "var(--success)";
            if (percent > 25) return "var(--warning)";
            return "var(--danger)";
        });

    // Draw inner letters
    node.append("text")
        .attr("text-anchor", "middle")
        .attr("dy", ".3em")
        .attr("fill", "white")
        .attr("font-size", d => d.type === "BASE" ? "0.85rem" : "0.7rem")
        .attr("font-family", "monospace")
        .attr("font-weight", "bold")
        .attr("cursor", "pointer")
        .text(d => d.type === "BASE" ? "BS" : d.id.replace("BUOY-", "").substring(0, 3));

    // Draw node labels
    node.append("text")
        .attr("dx", d => d.type === "BASE" ? 28 : 25)
        .attr("dy", 4)
        .text(d => d.id === "BASE" ? "BASE STATION" : d.id)
        .attr("font-size", "0.8rem")
        .attr("font-weight", "700")
        .attr("fill", "var(--text-primary)")
        .attr("pointer-events", "none");

    // Tooltip handling
    const tooltip = document.getElementById("mapTooltip");

    node.on("mouseover", function(event, d) {
        if (!tooltip) return;
        if (d.id === "BASE") {
            tooltip.innerHTML = `
                <div class="tooltip-header">
                    <span class="tooltip-codename">BASE STATION</span>
                    <span class="tooltip-status" style="color:var(--primary)">SINK</span>
                </div>
                <div class="tooltip-body">
                    <div class="tooltip-row">
                        <span>Role:</span>
                        <span class="tooltip-val">Gateway Receiver</span>
                    </div>
                    <div class="tooltip-row">
                        <span>Hops:</span>
                        <span class="tooltip-val">0 (Direct)</span>
                    </div>
                    <div class="tooltip-row">
                        <span>Link Mode:</span>
                        <span class="tooltip-val">Mesh Center</span>
                    </div>
                </div>
            `;
        } else {
            const percent = nodeBatteryMap[d.id] !== undefined ? nodeBatteryMap[d.id] : 100;
            const statusColor = d.status === 'ONLINE' ? 'var(--success)' : (d.status === 'IDLE' ? 'var(--warning)' : 'var(--danger)');
            const batteryColor = percent > 60 ? 'var(--success)' : (percent > 25 ? 'var(--warning)' : 'var(--danger)');
            tooltip.innerHTML = `
                <div class="tooltip-header">
                    <span class="tooltip-codename">${d.id}</span>
                    <span class="tooltip-status" style="color:${statusColor}">${d.status}</span>
                </div>
                <div class="tooltip-body">
                    <div class="tooltip-row">
                        <span>Hops:</span>
                        <span class="tooltip-val">${d.hops} Hops</span>
                    </div>
                    <div class="tooltip-row">
                        <span>RSSI:</span>
                        <span class="tooltip-val">${d.rssi} dBm</span>
                    </div>
                    <div class="tooltip-battery-container">
                        <span style="font-size:0.75rem; font-weight:700;">BATTERY:</span>
                        <div class="tooltip-battery-bar">
                            <div class="tooltip-battery-fill" style="width:${percent}%; background:${batteryColor};"></div>
                        </div>
                        <span style="font-size:0.8rem; font-weight:bold; color:var(--text-primary);">${percent}%</span>
                    </div>
                </div>
            `;
        }
        tooltip.style.opacity = 1;
    })
    .on("mousemove", function(event) {
        if (!tooltip) return;
        const wrapper = document.querySelector('.svg-container-wrapper');
        const rect = wrapper.getBoundingClientRect();
        const tooltipX = event.clientX - rect.left;
        const tooltipY = event.clientY - rect.top;
        tooltip.style.left = `${tooltipX}px`;
        tooltip.style.top = `${tooltipY}px`;
        tooltip.style.transform = `translate(-50%, -115%)`;
    })
    .on("mouseleave", function() {
        if (tooltip) tooltip.style.opacity = 0;
    })
    .on("click", function(event, d) {
        event.stopPropagation();
        inspectNode(d, nodesData, linksData);
    });

    // Close inspector on clicking SVG background
    svg.on("click", function(event) {
        if (event.target.tagName === "svg") {
            window.closeNodeInspector();
        }
    });

    // Simulation tick handler
    simulation.on("tick", () => {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        flowLink
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        linkText
            .attr("x", d => (d.source.x + d.target.x) / 2)
            .attr("y", d => (d.source.y + d.target.y) / 2 - 8);

        node
            .attr("transform", d => `translate(${d.x},${d.y})`);
    });

    // Drag behavior definition
    function drag(sim) {
        function dragstarted(event, d) {
            if (!event.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        function dragended(event, d) {
            if (!event.active) sim.alphaTarget(0);
            if (d.type !== "BASE") {
                d.fx = null;
                d.fy = null;
            }
        }
        return d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended);
    }
}

function inspectNode(d, nodesData, linksData) {
    const card = document.getElementById("nodeInspectCard");
    if (!card) return;
    
    // Show inspect panel
    card.classList.add("active");
    
    // Set node name
    const nameEl = document.getElementById("inspectNodeName");
    if (nameEl) nameEl.textContent = d.id === "BASE" ? "BASE STATION" : d.id;
    
    // Find node status and seen from nodesData
    const nodeInfo = nodesData.find(n => n.codename === d.id) || {};
    
    const statusEl = document.getElementById("inspectNodeStatus");
    if (statusEl) {
        const rawStatus = d.id === "BASE" ? "ONLINE" : (nodeInfo.status || d.status || "ONLINE");
        statusEl.textContent = rawStatus;
        statusEl.className = `inspect-value status-badge ${getStatusClass(rawStatus)}`;
    }
    
    const batteryEl = document.getElementById("inspectNodeBattery");
    if (batteryEl) {
        batteryEl.textContent = d.id === "BASE" ? "100% (Sink Grid)" : `${nodeBatteryMap[d.id] !== undefined ? nodeBatteryMap[d.id] : '100'}%`;
    }
    
    const hopsEl = document.getElementById("inspectNodeHops");
    if (hopsEl) {
        hopsEl.textContent = d.id === "BASE" ? "0 (Direct Gateway)" : `${d.hops} ${d.hops === 1 ? 'Hop' : 'Hops'}`;
    }
    
    const seenEl = document.getElementById("inspectNodeSeen");
    if (seenEl) {
        seenEl.textContent = d.id === "BASE" ? "Always Connected" : formatTime(nodeInfo.last_seen || Math.floor(Date.now() / 1000));
    }
    
    // Populate peers table
    const peersBody = document.getElementById("inspectPeersTableBody");
    if (peersBody) {
        const peers = [];
        
        // Find links involving this node
        linksData.forEach(link => {
            if (link.codename === d.id) {
                peers.push({ neighbor: link.neighbor || 'BASE', rssi: link.rssi, direct: link.last_direct });
            } else if (link.neighbor === d.id) {
                peers.push({ neighbor: link.codename, rssi: link.rssi, direct: link.last_direct });
            }
        });
        
        // Add direct links to base station if hops == 1
        if (d.type === "BUOY" && d.hops === 1) {
            if (!peers.some(p => p.neighbor === 'BASE')) {
                peers.push({ neighbor: 'BASE', rssi: d.rssi, direct: true });
            }
        }
        
        if (peers.length > 0) {
            peersBody.innerHTML = peers.map(p => {
                const signal = getSignalQuality(p.rssi);
                return `
                    <tr>
                        <td><span class="codename" style="font-size:0.9rem;">${p.neighbor}</span></td>
                        <td><span class="rssi">${p.rssi || 'N/A'}</span></td>
                        <td><span class="signal ${signal.class}">${signal.icon} ${signal.text}</span></td>
                    </tr>
                `;
            }).join('');
        } else {
            peersBody.innerHTML = `<tr><td colspan="3" style="text-align:center; padding: 2rem; color: var(--text-muted);">No direct mesh neighbors registered</td></tr>`;
        }
    }
}

window.closeNodeInspector = function() {
    const card = document.getElementById("nodeInspectCard");
    if (card) card.classList.remove("active");
};

async function updateTables() {
    try {
        await fetchBatteryStats();

        const [activeListRes, neighborsRes] = await Promise.all([
            fetch('/api/active_list'),
            fetch('/api/neighbors')
        ]);
        const activeList = await activeListRes.json();
        const neighbors  = await neighborsRes.json();

        const activeCount   = activeList.nodes ? activeList.nodes.length : 0;
        const neighborCount = neighbors.neighbors ? neighbors.neighbors.length : 0;
        
        // Calculate average RSSI of active links
        const validRssiNodes = (activeList.nodes || []).filter(n => n.rssi && n.rssi !== 'N/A');
        const avgRssi = validRssiNodes.length > 0 
            ? Math.round(validRssiNodes.reduce((acc, curr) => acc + parseInt(curr.rssi), 0) / validRssiNodes.length)
            : -85;

        // Update statistics counters
        animateValue('active-count',   0, activeCount,   800);
        animateValue('neighbor-count', 0, neighborCount, 800);
        
        const healthEl = document.getElementById('network-health');
        if (healthEl) {
            healthEl.textContent = `${avgRssi} dBm`;
        }

        // Active registry counts
        const registryCountEl = document.getElementById('registryCount');
        if (registryCountEl) registryCountEl.textContent = `${activeCount} nodes active`;
        
        const neighborCountEl = document.getElementById('neighborCount');
        if (neighborCountEl) neighborCountEl.textContent = `${neighborCount} link vectors`;

        // Active list table
        const activeTable = document.querySelector('#active-list');
        if (activeTable) {
            if (activeList.nodes && activeList.nodes.length > 0) {
                activeTable.innerHTML = activeList.nodes.map((node, index) => {
                    const signal = getSignalQuality(node.rssi);
                    return `
                    <tr style="animation-delay:${index * 0.05}s">
                        <td><span class="codename">${node.codename}</span></td>
                        <td><span class="status-badge ${getStatusClass(node.status)}"><span class="status-dot"></span>${node.status}</span></td>
                        <td><span class="time-display">${formatTime(node.last_seen)}</span></td>
                        <td><span class="hops-badge">${node.hops !== undefined && node.hops !== 'N/A' ? node.hops : 'N/A'}</span></td>
                        <td><span class="rssi">${node.rssi || 'N/A'}</span></td>
                        <td><span class="signal ${signal.class}">${signal.icon} ${signal.text}</span></td>
                    </tr>`;
                }).join('');
            } else {
                activeTable.innerHTML = `<tr><td colspan="6"><div class="empty-state"><div class="empty-state-icon"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg></div><p class="empty-text">No active nodes detected</p></div></td></tr>`;
            }
        }

        // Neighbor table
        const neighborTable = document.querySelector('#neighbor-table');
        if (neighborTable) {
            const neighborsList = neighbors.neighbors || [];
            if (neighborsList.length > 0) {
                neighborTable.innerHTML = neighborsList.map((node, index) => {
                    const signal = getSignalQuality(node.rssi);
                    return `
                    <tr style="animation-delay:${index * 0.05}s">
                        <td><span class="codename">${node.codename}</span></td>
                        <td><span class="codename" style="background:var(--bg-app); font-size:0.9rem;">${node.neighbor || 'BASE'}</span></td>
                        <td><span class="time-display">${formatTime(node.last_seen)}</span></td>
                        <td><span class="rssi">${node.rssi || 'N/A'}</span></td>
                        <td><span class="rssi" style="background:var(--primary-light); color:var(--primary);">${node.snr !== undefined ? node.snr + ' dB' : 'N/A'}</span></td>
                        <td>
                            ${node.last_direct 
                                ? `<span class="direct-icon direct-yes" title="Direct Hop"><svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" style="color:var(--success);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></span>`
                                : `<span class="direct-icon direct-no" title="Multi-hop Relay"><svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" style="color:var(--danger);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></span>`
                            }
                        </td>
                    </tr>`;
                }).join('');
            } else {
                neighborTable.innerHTML = `<tr><td colspan="6"><div class="empty-state"><div class="empty-state-icon"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/></svg></div><p class="empty-text">No neighbor mesh data received</p></div></td></tr>`;
            }
        }

        // Render D3 Topology
        renderTopologyGraph(activeList.nodes || [], neighbors.neighbors || []);

    } catch (error) {
        console.error('Error updating networks:', error);
    }
}

// Initial fetch
updateTables();

// Poll topology data every 10 seconds
setInterval(updateTables, 10000);
