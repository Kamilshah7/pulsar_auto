// Content Script: Labelbox Task Sniper & Siren (Non-blocking, isolated Shadow DOM)

(function () {
    'use strict';

    // Strictly run ONLY on project overview pages where the Start button exists
    function isOverviewPage() {
        return window.location.href.includes('/projects/') && 
               (window.location.href.includes('/overview') || window.location.pathname.endsWith('/overview'));
    }

    // Prevent double execution
    if (window.__LB_SNIPER_INITIALIZED__) return;
    window.__LB_SNIPER_INITIALIZED__ = true;

    console.log('[Labelbox Sniper] Extension loaded. Checking page context...');

    let settings = {
        enabled: true,
        autoReloadSeconds: 12,
        enableAutoReload: true,
        sirenDurationSec: 45
    };

    let checkCount = 0;
    let reloadCountdown = 12;
    let taskSnagged = false;
    let shadowRoot = null;
    let monitorTimer = null;
    let reloadTimer = null;

    // Load persisted settings
    try {
        chrome.storage.local.get(['sniper_settings'], (res) => {
            if (res && res.sniper_settings) {
                settings = { ...settings, ...res.sniper_settings };
            }
            reloadCountdown = settings.autoReloadSeconds;
            // Wait 2.5s for Labelbox SPA/React to finish hydrating before mounting sniper
            setTimeout(bootSniper, 2500);
        });
    } catch (e) {
        setTimeout(bootSniper, 2500);
    }

    function findStartButton() {
        // Labelbox's Start button is in the top right header
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const txt = (btn.innerText || btn.textContent || '').trim();
            if (/^start/i.test(txt)) {
                return btn;
            }
        }
        return null;
    }

    function isButtonActive(btn) {
        if (!btn) return false;

        const isDisabled = btn.disabled ||
                           btn.hasAttribute('disabled') ||
                           btn.classList.contains('Mui-disabled') ||
                           btn.getAttribute('aria-disabled') === 'true';

        if (isDisabled) return false;

        const style = window.getComputedStyle(btn);
        return style.pointerEvents !== 'none' && style.cursor !== 'not-allowed';
    }

    function snagTask(btn) {
        if (taskSnagged) return;
        taskSnagged = true;

        // 🛑 PERMANENTLY STOP AUTO-RELOAD IMMEDIATELY
        if (reloadTimer) {
            clearInterval(reloadTimer);
            reloadTimer = null;
        }
        if (monitorTimer) {
            clearInterval(monitorTimer);
            monitorTimer = null;
        }
        settings.enableAutoReload = false;

        console.log('%c [SNIPER] 🎯 TASK AVAILABLE! SNAGGING NOW!', 'background: #00dd55; color: #000; font-size: 16px; font-weight: bold; padding: 4px 8px;');

        // Dispatch synthetic events
        try {
            btn.scrollIntoView({ behavior: 'instant', block: 'center' });
            btn.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, cancelable: true }));
            btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
            btn.dispatchEvent(new MouseEvent('pointerup', { bubbles: true, cancelable: true }));
            btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
            btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            if (typeof btn.click === 'function') btn.click();
        } catch (e) {
            console.error('[Sniper] Click error:', e);
        }

        // Check for dropdown split menuitem
        setTimeout(() => {
            const menuItems = document.querySelectorAll('[role="menuitem"], .MuiMenuItem-root');
            if (menuItems.length > 0) {
                menuItems[0].click();
            }
        }, 150);

        // Notify background for offscreen loud siren + notification
        try {
            chrome.runtime.sendMessage({
                action: 'TASK_SNAGGED',
                duration: settings.sirenDurationSec
            });
        } catch (e) {
            console.error('[Sniper] Message error:', e);
        }

        // Visual alert on page
        triggerFlashingBorder();

        // Update HUD
        if (shadowRoot) {
            const st = shadowRoot.getElementById('hud-status');
            if (st) st.innerHTML = '<span style="color: #00ff88; font-weight: bold;">🎉 TASK SNAGGED!</span>';
            const btnSt = shadowRoot.getElementById('hud-btn-state');
            if (btnSt) btnSt.innerHTML = '<span style="color: #00ff88; font-weight: bold;">ACTIVE (CLICKED!)</span>';
            const timerEl = shadowRoot.getElementById('hud-timer');
            if (timerEl) timerEl.innerHTML = '<span style="color: #ff3366; font-weight: bold;">🛑 STOPPED</span>';
            const cb = shadowRoot.getElementById('cb-autoreload');
            if (cb) {
                cb.checked = false;
                cb.disabled = true;
            }
        }

        document.title = '🚨🚨 TASK READY! SNAGGED! 🚨🚨';
    }

    function triggerFlashingBorder() {
        if (document.getElementById('lb-sniper-alert-overlay')) return;
        const overlay = document.createElement('div');
        overlay.id = 'lb-sniper-alert-overlay';
        overlay.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            border: 14px solid #ff0055; box-sizing: border-box;
            z-index: 2147483646; pointer-events: none;
            animation: lbSniperPulse 0.35s infinite alternate;
        `;
        document.body.appendChild(overlay);
    }

    // Build HUD inside isolated Shadow DOM so it NEVER interferes with React
    function buildIsolatedHud() {
        if (document.getElementById('lb-sniper-host')) return;

        const host = document.createElement('div');
        host.id = 'lb-sniper-host';
        host.style.cssText = 'position: fixed; top: 14px; right: 14px; z-index: 2147483647;';
        document.documentElement.appendChild(host);

        shadowRoot = host.attachShadow({ mode: 'open' });

        shadowRoot.innerHTML = `
            <style>
                * { box-sizing: border-box; margin: 0; padding: 0; }
                .hud-box {
                    background: rgba(14, 18, 28, 0.95);
                    border: 1px solid rgba(0, 195, 255, 0.4);
                    border-radius: 12px;
                    padding: 12px 16px;
                    color: #e0e8ff;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    font-size: 13px;
                    box-shadow: 0 10px 35px rgba(0, 0, 0, 0.65), 0 0 15px rgba(0, 195, 255, 0.15);
                    backdrop-filter: blur(10px);
                    min-width: 250px;
                    user-select: none;
                }
                .hud-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    font-weight: 700;
                    color: #00d4ff;
                    margin-bottom: 8px;
                    padding-bottom: 6px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
                    cursor: move;
                }
                .hud-badge {
                    font-size: 10px;
                    background: rgba(0, 212, 255, 0.15);
                    color: #00d4ff;
                    padding: 2px 6px;
                    border-radius: 4px;
                    border: 1px solid rgba(0, 212, 255, 0.3);
                }
                .hud-row {
                    margin: 5px 0;
                    display: flex;
                    justify-content: space-between;
                    font-size: 12px;
                }
                .hud-label { color: #94a3b8; }
                .hud-val { font-weight: 600; color: #ffffff; }
                .hud-btn {
                    background: #1e2438;
                    border: 1px solid #3c466b;
                    color: #ffffff;
                    padding: 5px 10px;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.15s ease;
                }
                .hud-btn:hover {
                    background: #2e3857;
                    border-color: #00d4ff;
                    color: #00d4ff;
                }
                .hud-btn-danger {
                    background: #441822;
                    border-color: #ff3366;
                    color: #ff99aa;
                }
                .hud-btn-danger:hover {
                    background: #662033;
                    border-color: #ff6688;
                    color: #ffffff;
                }
            </style>
            <div class="hud-box" id="hud-box">
                <div class="hud-header" id="hud-header">
                    <span>🎯 Labelbox Sniper</span>
                    <span class="hud-badge">ARMED</span>
                </div>
                <div class="hud-row">
                    <span class="hud-label">Status:</span>
                    <span class="hud-val" id="hud-status" style="color: #ffaa00;">Monitoring</span>
                </div>
                <div class="hud-row">
                    <span class="hud-label">Start button:</span>
                    <span class="hud-val" id="hud-btn-state" style="color: #94a3b8;">Checking...</span>
                </div>
                <div class="hud-row">
                    <span class="hud-label">Next reload:</span>
                    <span class="hud-val" id="hud-timer" style="color: #00d4ff;">${reloadCountdown}s</span>
                </div>
                <div class="hud-row">
                    <span class="hud-label">Checks:</span>
                    <span class="hud-val" id="hud-scans">0</span>
                </div>
                <div style="display: flex; gap: 6px; margin-top: 8px;">
                    <button id="btn-test-siren" class="hud-btn" style="flex: 1;">🔊 Test Siren</button>
                    <button id="btn-stop-siren" class="hud-btn hud-btn-danger" style="flex: 1;">⏹️ Stop Alarm</button>
                </div>
                <div style="margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px;">
                    <label style="font-size: 11px; color: #94a3b8; display: flex; align-items: center; gap: 6px; cursor: pointer;">
                        <input type="checkbox" id="cb-autoreload" ${settings.enableAutoReload ? 'checked' : ''}>
                        Auto-reload page
                    </label>
                </div>
            </div>
        `;

        // Event listeners inside shadowRoot
        shadowRoot.getElementById('btn-test-siren').addEventListener('click', () => {
            chrome.runtime.sendMessage({ action: 'TEST_SIREN' });
        });

        shadowRoot.getElementById('btn-stop-siren').addEventListener('click', () => {
            chrome.runtime.sendMessage({ action: 'STOP_SIREN' });
            const ov = document.getElementById('lb-sniper-alert-overlay');
            if (ov) ov.remove();
        });

        shadowRoot.getElementById('cb-autoreload').addEventListener('change', (e) => {
            settings.enableAutoReload = e.target.checked;
            chrome.storage.local.set({ sniper_settings: settings });
        });

        // Draggable HUD
        const header = shadowRoot.getElementById('hud-header');
        let isDragging = false, startX, startY, origX, origY;
        header.addEventListener('mousedown', (e) => {
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            const rect = host.getBoundingClientRect();
            origX = rect.left;
            origY = rect.top;
            e.preventDefault();
        });
        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            host.style.right = 'auto';
            host.style.left = (origX + (e.clientX - startX)) + 'px';
            host.style.top = (origY + (e.clientY - startY)) + 'px';
        });
        window.addEventListener('mouseup', () => { isDragging = false; });
    }

    function checkStartButton() {
        if (taskSnagged || !settings.enabled) return;

        checkCount++;
        if (shadowRoot) {
            const scansEl = shadowRoot.getElementById('hud-scans');
            if (scansEl) scansEl.innerText = checkCount;
        }

        const btn = findStartButton();
        if (!btn) {
            if (shadowRoot) {
                const btnSt = shadowRoot.getElementById('hud-btn-state');
                if (btnSt) btnSt.innerHTML = '<span style="color: #64748b;">Waiting for render...</span>';
            }
            return;
        }

        const active = isButtonActive(btn);
        if (active) {
            // Immediately freeze reload before anything else
            if (reloadTimer) {
                clearInterval(reloadTimer);
                reloadTimer = null;
            }
            settings.enableAutoReload = false;

            if (shadowRoot) {
                const btnSt = shadowRoot.getElementById('hud-btn-state');
                if (btnSt) btnSt.innerHTML = '<span style="color: #00ff88; font-weight: bold;">ACTIVE (BLUE)!</span>';
            }
            snagTask(btn);
        } else {
            if (shadowRoot) {
                const btnSt = shadowRoot.getElementById('hud-btn-state');
                if (btnSt) btnSt.innerHTML = '<span style="color: #94a3b8;">Disabled (Grey)</span>';
            }
        }
    }

    function bootSniper() {
        if (!isOverviewPage()) {
            console.log('[Labelbox Sniper] Not on an overview page. Standing by.');
            return;
        }

        console.log('[Labelbox Sniper] Starting safe monitoring engine...');
        buildIsolatedHud();

        // Safe polling every 450ms (Zero DOM mutation feedback, 0% CPU impact)
        monitorTimer = setInterval(checkStartButton, 450);

        // Safe Auto-Reload Timer (every 1s)
        reloadTimer = setInterval(() => {
            if (taskSnagged || !settings.enableAutoReload) return;

            // If user navigated into a task or away from overview, abort reload immediately
            if (!isOverviewPage()) {
                clearInterval(reloadTimer);
                reloadTimer = null;
                return;
            }

            reloadCountdown--;
            if (shadowRoot) {
                const timerEl = shadowRoot.getElementById('hud-timer');
                if (timerEl) timerEl.innerText = `${reloadCountdown}s`;
            }

            if (reloadCountdown <= 0) {
                console.log('[Labelbox Sniper] Auto-refresh interval reached. Reloading...');
                window.location.reload();
            }
        }, 1000);
    }

    // Handle SPA navigation
    window.addEventListener('popstate', () => {
        setTimeout(() => {
            if (isOverviewPage() && !document.getElementById('lb-sniper-host')) {
                bootSniper();
            }
        }, 1000);
    });

})();
