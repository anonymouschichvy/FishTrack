/**
 * FishTrack Dark Mode Theme & Navigation Manager
 * Dynamically injects theme toggles, synchronizes preferences, and handles responsive menus.
 */

window.toggleMenu = function() {
    const sidebarNav = document.getElementById('sidebarNav');
    if (sidebarNav) sidebarNav.classList.toggle('active');
};

document.addEventListener('click', function(event) {
    const sidebarNav = document.getElementById('sidebarNav');
    const menuToggle = document.querySelector('.menu-toggle');
    if (sidebarNav && menuToggle && !sidebarNav.contains(event.target) && !menuToggle.contains(event.target)) {
        sidebarNav.classList.remove('active');
    }

    const notifDrawer = document.getElementById('notifDrawer');
    const notifBtn = document.getElementById('notifBtn');
    if (notifDrawer && notifBtn && !notifDrawer.contains(event.target) && !notifBtn.contains(event.target)) {
        notifDrawer.style.display = 'none';
    }
});

// Help drawer control with tab focusing support
window.toggleHelpDrawer = function(defaultTab) {
    const drawer = document.getElementById('helpDrawer');
    if (drawer) {
        const isActive = drawer.classList.toggle('active');
        if (isActive) {
            window.switchHelpTab(defaultTab || 'page');
        }
    }
};

window.switchHelpTab = function(tabName) {
    // Hide all tab contents
    const contents = document.querySelectorAll('.help-tab-content');
    contents.forEach(el => el.style.display = 'none');
    
    // Show target tab content container with flex-direction column gap spacing
    const target = document.getElementById(`helpTab-${tabName}`);
    if (target) {
        target.style.display = 'flex';
    }
    
    // Toggle active classes on tab buttons
    const buttons = document.querySelectorAll('.help-tab-btn');
    buttons.forEach(btn => btn.classList.remove('active'));
    
    const activeBtn = document.getElementById(`helpTabBtn-${tabName}`);
    if (activeBtn) activeBtn.classList.add('active');
};

// Operator Feedback Modal Control
window.openFeedbackModal = function() {
    const modal = document.getElementById('feedbackModal');
    if (modal) modal.showModal();
};

window.closeFeedbackModal = function() {
    const modal = document.getElementById('feedbackModal');
    if (modal) modal.close();
};

window.submitFeedbackForm = async function(event) {
    event.preventDefault();
    const operator = document.getElementById('feedbackOperator').value;
    const category = document.getElementById('feedbackCategory').value;
    const rating = parseInt(document.getElementById('feedbackRating').value);
    const message = document.getElementById('feedbackMessage').value;
    const page = window.location.pathname;

    try {
        const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ operator, category, rating, message, page })
        });
        const data = await response.json();
        if (data.success) {
            alert('Feedback log submitted successfully!');
            window.closeFeedbackModal();
            document.getElementById('feedbackForm').reset();
            
            // Add custom local audit event for submission
            await fetch('/api/audit_log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'feedback_submitted',
                    operator: operator || 'Operator',
                    details: `Submitted feedback category ${category} with severity rating ${rating}`,
                    status: 'info'
                })
            });
            window.loadNotifications();
        } else {
            alert('Error submitting feedback: ' + data.error);
        }
    } catch (error) {
        console.error('Error submitting feedback:', error);
        alert('Failed to submit feedback log.');
    }
};

// Notifications Drawer & Feed Control
window.loadNotifications = async function() {
    try {
        const response = await fetch('/api/audit_log');
        const data = await response.json();
        if (data.success) {
            const clearedAtStr = localStorage.getItem('notifications_cleared_at');
            const clearedAt = clearedAtStr ? new Date(clearedAtStr) : null;
            
            const activeLogs = data.logs.filter(log => {
                if (!clearedAt) return true;
                return new Date(log.timestamp) > clearedAt;
            });
            
            const notifFeed = document.getElementById('notifFeed');
            const badge = document.getElementById('notifBadge');
            
            if (activeLogs.length > 0) {
                if (badge) {
                    badge.textContent = activeLogs.length;
                    badge.style.display = 'flex';
                }
                if (notifFeed) {
                    notifFeed.innerHTML = activeLogs.map(log => {
                        const dateText = new Date(log.timestamp).toLocaleTimeString();
                        let statusColor = 'var(--text-primary)';
                        if (log.status === 'warning') statusColor = 'var(--warning)';
                        else if (log.status === 'error' || log.status === 'critical') statusColor = 'var(--danger)';
                        
                        return `
                            <div class="notif-item">
                                <div class="notif-item-title" style="color: ${statusColor}; font-weight:600;">${log.action.toUpperCase()}</div>
                                <div style="color: var(--text-secondary); margin: 2px 0 4px; font-size:0.75rem;">${log.details || ''}</div>
                                <div class="notif-item-time">${dateText} (${log.operator || 'System'})</div>
                            </div>
                        `;
                    }).join('');
                }
            } else {
                if (badge) {
                    badge.style.display = 'none';
                    badge.textContent = '0';
                }
                if (notifFeed) {
                    notifFeed.innerHTML = '<div class="notif-empty">No new events recorded.</div>';
                }
            }
        }
    } catch (error) {
        console.error('Error loading notifications:', error);
    }
};

window.toggleNotifications = function() {
    const drawer = document.getElementById('notifDrawer');
    if (!drawer) return;
    if (drawer.style.display === 'none' || !drawer.style.display) {
        window.loadNotifications();
        drawer.style.display = 'flex';
    } else {
        drawer.style.display = 'none';
    }
};

window.clearNotifications = function() {
    localStorage.setItem('notifications_cleared_at', new Date().toISOString());
    const notifFeed = document.getElementById('notifFeed');
    if (notifFeed) {
        notifFeed.innerHTML = '<div class="notif-empty">No new events recorded.</div>';
    }
    const badge = document.getElementById('notifBadge');
    if (badge) {
        badge.style.display = 'none';
        badge.textContent = '0';
    }
};


(function() {
    // 1. Prevent flash of unstyled content
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme = savedTheme || (systemPrefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', initialTheme);

    // 2. Inject toggle on DOM load
    document.addEventListener('DOMContentLoaded', () => {
        // Load notifications feed
        if (window.loadNotifications) window.loadNotifications();

        const navContainer = document.querySelector('.nav-container');
        if (!navContainer || document.getElementById('themeToggleBtn')) return;

        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

        const themeToggle = document.createElement('div');
        themeToggle.id = 'themeToggleBtn';
        themeToggle.innerHTML = `
            <button
                class="theme-pill${isDark ? ' dark' : ''}"
                aria-label="Toggle theme"
                aria-pressed="${isDark}"
            >
                <div class="theme-pill__icons">
                    <svg class="theme-pill__sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <circle cx="12" cy="12" r="5"/>
                        <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
                        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                        <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
                        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                    </svg>
                    <svg class="theme-pill__moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                    </svg>
                </div>
                <div class="theme-pill__knob"></div>
            </button>
        `;

        const menuToggle = navContainer.querySelector('.menu-toggle');
        if (menuToggle) {
            menuToggle.parentNode.insertBefore(themeToggle, menuToggle);
        } else {
            navContainer.appendChild(themeToggle);
        }

        const btn = themeToggle.querySelector('.theme-pill');
        btn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            const isDarkNow = newTheme === 'dark';

            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);

            btn.classList.toggle('dark', isDarkNow);
            btn.setAttribute('aria-pressed', isDarkNow);
        });
    });
})();