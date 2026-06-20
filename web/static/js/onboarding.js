// FishTrack Operator Guided Onboarding Tour Wizard

const tourSteps = [
    {
        target: '#link-home',
        title: 'Operator Dashboard',
        icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>`,
        body: 'Welcome to FishTrack! This is your main dashboard showing active fleet node statuses, telemetry feeds, and live summaries.'
    },
    {
        target: '#link-networks',
        title: 'Mesh Routing Map',
        icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 15V9m-4 4H10M9 6h6"/></svg>`,
        body: 'Click here to inspect the active mesh topology. You can drag buoy nodes around in D3, view direct RF links (Hops = 1), and trace multi-hop relays.'
    },
    {
        target: '#link-commands',
        title: 'Command Center',
        icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
        body: 'Use this page to deploy preset scripts (such as a 60-second sonar profiler run or camera threshold recalibration) directly to buoys.'
    },
    {
        target: '#link-linux',
        title: 'Linux Shell Console',
        icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>`,
        body: 'Need low-level debug access? Open the Linux console to run raw shell commands (like disk space checks or system uptime checks) over LoRa packets.'
    },
    {
        target: '#link-scheduler',
        title: 'Job Scheduler',
        icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
        body: 'Automate tasks to run hourly, daily, weekly, or at custom minute intervals. Ideal for scheduling midnight scans and battery level aggregation.'
    },
    {
        target: '.search-trigger',
        title: 'Search & Command Palette',
        icon: `<svg xmlns="http://www.w3.org/2000/svg" class="inline-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
        body: 'Press Ctrl + K anywhere to open the fuzzy search palette. Quickly jump to pages, toggle dark/light theme, or search the offline glossary.'
    }
];

let currentTourStep = 0;

// Add highlight styles dynamically
const tourHighlightStyle = document.createElement('style');
tourHighlightStyle.textContent = `
    .tour-element-highlighted {
        position: relative !important;
        z-index: 10001 !important;
        box-shadow: 0 0 0 4px var(--primary), 0 10px 30px rgba(0,0,0,0.2) !important;
        background-color: var(--card-bg) !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
    }
`;
document.head.appendChild(tourHighlightStyle);

function startOnboardingTour() {
    currentTourStep = 0;
    const overlay = document.getElementById('tourOverlay');
    if (overlay) {
        overlay.style.display = 'flex';
        showTourStep(currentTourStep);
    }
}

function endOnboardingTour() {
    const overlay = document.getElementById('tourOverlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
    clearTourHighlights();
}

function clearTourHighlights() {
    document.querySelectorAll('.tour-element-highlighted').forEach(el => {
        el.classList.remove('tour-element-highlighted');
    });
}

function showTourStep(stepIndex) {
    clearTourHighlights();

    if (stepIndex < 0 || stepIndex >= tourSteps.length) {
        endOnboardingTour();
        return;
    }

    const step = tourSteps[stepIndex];
    
    // Update contents
    document.getElementById('tourTitle').innerHTML = `${step.icon || ''} <span>${step.title}</span>`;
    document.getElementById('tourBody').textContent = step.body;
    document.getElementById('tourStepIndicator').textContent = `${stepIndex + 1} / ${tourSteps.length}`;

    // Enable/disable buttons
    const prevBtn = document.getElementById('tourPrevBtn');
    const nextBtn = document.getElementById('tourNextBtn');
    
    if (prevBtn) prevBtn.disabled = stepIndex === 0;
    if (nextBtn) {
        nextBtn.textContent = stepIndex === tourSteps.length - 1 ? 'Finish' : 'Next';
    }

    // Scroll and highlight element
    const targetElement = document.querySelector(step.target);
    if (targetElement) {
        targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        targetElement.classList.add('tour-element-highlighted');
        
        // Reposition tour card near the highlighted element if not on mobile
        positionTourCard(targetElement);
    } else {
        // Fallback to center positioning
        const card = document.getElementById('tourCard');
        if (card) {
            card.style.position = 'relative';
            card.style.top = '0';
            card.style.left = '0';
            card.style.margin = 'auto';
        }
    }
}

function positionTourCard(targetEl) {
    const card = document.getElementById('tourCard');
    if (!card) return;

    if (window.innerWidth <= 768) {
        // Float in center on mobile
        card.style.position = 'relative';
        card.style.top = 'auto';
        card.style.left = 'auto';
        card.style.margin = 'auto';
        return;
    }

    const rect = targetEl.getBoundingClientRect();
    
    card.style.position = 'absolute';
    card.style.margin = '0';
    
    // Determine best position (below or to the right)
    const topSpace = rect.top;
    const bottomSpace = window.innerHeight - rect.bottom;
    const rightSpace = window.innerWidth - rect.right;
    
    if (rightSpace > 320) {
        card.style.left = `${rect.right + 20}px`;
        card.style.top = `${rect.top + window.scrollY}px`;
    } else if (bottomSpace > 250) {
        card.style.left = `${rect.left}px`;
        card.style.top = `${rect.bottom + 20 + window.scrollY}px`;
    } else {
        card.style.left = `${rect.left}px`;
        card.style.top = `${rect.top - 220 + window.scrollY}px`;
    }
}

function nextTourStep() {
    currentTourStep++;
    if (currentTourStep >= tourSteps.length) {
        endOnboardingTour();
    } else {
        showTourStep(currentTourStep);
    }
}

function prevTourStep() {
    if (currentTourStep > 0) {
        currentTourStep--;
        showTourStep(currentTourStep);
    }
}

// Adjust positioning on resize
window.addEventListener('resize', () => {
    const overlay = document.getElementById('tourOverlay');
    if (overlay && overlay.style.display !== 'none') {
        const step = tourSteps[currentTourStep];
        const targetElement = document.querySelector(step.target);
        if (targetElement) positionTourCard(targetElement);
    }
});
