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
    try {
        chrome.storage.onChanged.addListener((changes, area) => {
            if (area === 'local' && changes.sniper_settings && changes.sniper_settings.newValue) {
                settings = { ...settings, ...changes.sniper_settings.newValue };
            }
        });
    } catch (e) { /* ignore */ }

    function findStartButton() {
        // Labelbox's Start button is in the top right header. The page also has a second, permanently disabled
        // "Start" button (seen 2026-09-28): prefer the active one.
        const starts = [...document.querySelectorAll('button')]
            .filter(btn => /^start$/i.test((btn.innerText || btn.textContent || '').trim()));
        return starts.find(isButtonActive) || starts[0] || null;
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

    function snagTask(btn, autoClick) {
        // btn = the control that proves a task is there (since 2026-09: the labelling button, not Start)
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

        // mode: 'clicked' (labelling button clicked for you), 'alert' (auto-click off: you click it), 'opened'
        // (pressing Start went straight into a task, btn = null)
        const mode = !btn ? 'opened' : autoClick ? 'clicked' : 'alert';
        const TXT = {
            clicked: { status: '🎉 TASK SNAGGED!', state: 'LABELLING CLICKED!', title: '🚨🚨 TASK READY! SNAGGED! 🚨🚨' },
            alert:   { status: '🎉 TASK AVAILABLE: CLICK LABELLING!', state: 'LABELLING ACTIVE (not clicked)', title: '🚨🚨 TASK READY! CLICK LABELLING! 🚨🚨' },
            opened:  { status: '🎉 TASK OPENED!', state: 'START OPENED A TASK', title: '🚨🚨 TASK OPENED! 🚨🚨' }
        }[mode];
        console.log('%c [SNIPER] 🎯 TASK AVAILABLE! (' + mode + ')',
                    'background: #00dd55; color: #000; font-size: 16px; font-weight: bold; padding: 4px 8px;');

        // Click it (auto-click on). btn may be null when pressing Start already opened a task.
        if (mode === 'clicked') {
            try { clickLikeUser(btn); } catch (e) { console.error('[Sniper] Click error:', e); }
        }

        // Notify background for offscreen loud siren + notification
        try {
            chrome.runtime.sendMessage({
                action: 'TASK_SNAGGED',
                duration: settings.sirenDurationSec,
                clicked: mode !== 'alert',
                mode: mode
            });
        } catch (e) {
            console.error('[Sniper] Message error:', e);
        }

        // Visual alert on page
        triggerFlashingBorder();

        // Update HUD
        if (shadowRoot) {
            const st = shadowRoot.getElementById('hud-status');
            if (st) st.innerHTML = `<span style="color: #00ff88; font-weight: bold;">${TXT.status}</span>`;
            const btnSt = shadowRoot.getElementById('hud-btn-state');
            if (btnSt) btnSt.innerHTML = `<span style="color: #00ff88; font-weight: bold;">${TXT.state}</span>`;
            const timerEl = shadowRoot.getElementById('hud-timer');
            if (timerEl) timerEl.innerHTML = '<span style="color: #ff3366; font-weight: bold;">🛑 STOPPED</span>';
            const cb = shadowRoot.getElementById('cb-autoreload');
            if (cb) {
                cb.checked = false;
                cb.disabled = true;
            }
        }

        document.title = TXT.title;
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
                    <span class="hud-label">Labelling:</span>
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

    // ---- Detection (2026-09-28): Labelbox now keeps the Start button blue at all times, so "Start is active" no
    // longer means a task is waiting. Instead: press Start, then look at the "Start labeling" item of the menu it
    // opens -- greyed out (Mui-disabled, aria-disabled, opacity .38) = no task (close the menu, try again after the
    // next reload); not greyed out = a task is there. Only that MENU ITEM counts: pressing Start also shows a "Read
    // labeling instructions" link-button outside the menu, which the first version wrongly took for it.
    const LABEL_ITEM_RE = /^start\s+label(l)?ing\b/i;
    let probing = false;
    let lastProbe = 0;

    const sleep = (ms) => new Promise(r => setTimeout(r, ms));

    function clickLikeUser(el) {
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) {
            el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true }));
        }
        if (typeof el.click === 'function') el.click();
        else el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    }

    function isVisible(el) {
        return el.getClientRects().length > 0 && window.getComputedStyle(el).visibility !== 'hidden';
    }

    function menuItems() {
        return [...document.querySelectorAll('[role="menuitem"], .MuiMenuItem-root')].filter(isVisible);
    }

    // the visible "Start labeling" menu item, or null
    function labellingItem() {
        return menuItems().find(el => LABEL_ITEM_RE.test((el.innerText || el.textContent || '').trim())) || null;
    }

    function isGreyedOut(el) {
        // the element and its two nearest ancestors: MUI puts Mui-disabled / aria-disabled / opacity .38 on the item
        for (let e = el, d = 0; e && e !== document.body && d < 3; e = e.parentElement, d++) {
            if (e.disabled || e.hasAttribute('disabled') || e.getAttribute('aria-disabled') === 'true' ||
                e.classList.contains('Mui-disabled') || e.classList.contains('disabled')) return true;
            const st = window.getComputedStyle(e);
            if (st.pointerEvents === 'none' || st.cursor === 'not-allowed') return true;
            if (d === 0 && parseFloat(st.opacity) < 0.6) return true;      // only the item itself: menus fade in
        }
        return false;
    }

    function closeMenu() {
        const esc = { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true };
        (document.activeElement || document.body).dispatchEvent(new KeyboardEvent('keydown', esc));
        document.dispatchEvent(new KeyboardEvent('keydown', esc));
        setTimeout(() => {
            const bd = document.querySelector('.MuiPopover-root .MuiBackdrop-root, .MuiMenu-root .MuiBackdrop-root');
            if (bd) bd.click();
        }, 150);
    }

    function hudState(html) {
        if (!shadowRoot) return;
        const el = shadowRoot.getElementById('hud-btn-state');
        if (el) el.innerHTML = html;
    }

    async function probe() {
        if (probing || taskSnagged || !isOverviewPage()) return;
        const start = findStartButton();
        if (!start) { hudState('<span style="color: #64748b;">Waiting for Start...</span>'); return; }
        if (!isButtonActive(start)) { hudState('<span style="color: #94a3b8;">Start disabled</span>'); return; }

        probing = true;
        lastProbe = Date.now();
        checkCount++;
        if (shadowRoot) {
            const scansEl = shadowRoot.getElementById('hud-scans');
            if (scansEl) scansEl.innerText = checkCount;
        }
        hudState('<span style="color: #00d4ff;">Pressing Start...</span>');
        try {
            let found = labellingItem();                        // the menu may already be open
            if (!found) {
                const url0 = location.href;
                clickLikeUser(start);
                // wait (<= 4 s) for the "Start labeling" menu item, or for Start to open a task directly
                for (let i = 0; i < 40 && !found; i++) {
                    await sleep(100);
                    if (location.href !== url0 && !isOverviewPage()) {
                        hudState('<span style="color: #00ff88; font-weight: bold;">Start opened a task!</span>');
                        snagTask(null, false);
                        return;
                    }
                    found = labellingItem();
                }
            }
            if (!found) {
                hudState('<span style="color: #ffaa00;">"Start labeling" not found</span>');
                console.log('[Labelbox Sniper] After Start: no "Start labeling" menu item. Visible menu items:',
                            menuItems().map(el => (el.innerText || '').trim()));
                closeMenu();
                return;
            }
            await sleep(700);                                   // let the menu finish opening before judging
            if (!document.contains(found)) found = labellingItem() || found;
            if (isGreyedOut(found)) {
                hudState('<span style="color: #94a3b8;">Labelling greyed out (no task)</span>');
                closeMenu();
            } else {
                hudState('<span style="color: #00ff88; font-weight: bold;">LABELLING AVAILABLE!</span>');
                snagTask(found, settings.enabled !== false);
            }
        } catch (e) {
            console.error('[Sniper] Probe error:', e);
        } finally {
            probing = false;
        }
    }

    function bootSniper() {
        if (!isOverviewPage()) {
            console.log('[Labelbox Sniper] Not on an overview page. Standing by.');
            return;
        }

        console.log('[Labelbox Sniper] Starting safe monitoring engine...');
        buildIsolatedHud();

        // First probe as soon as Start has rendered; after that one probe per auto-reload (the page reloads), or,
        // with auto-reload off, one probe every autoReloadSeconds
        monitorTimer = setInterval(() => {
            if (taskSnagged || probing) return;
            const every = Math.max(5, settings.autoReloadSeconds || 12) * 1000;
            if (lastProbe === 0 || (!settings.enableAutoReload && Date.now() - lastProbe >= every)) probe();
        }, 450);

        // Safe Auto-Reload Timer (every 1s)
        reloadTimer = setInterval(() => {
            if (taskSnagged || !settings.enableAutoReload) return;

            // If user navigated into a task or away from overview, abort reload immediately
            if (!isOverviewPage()) {
                clearInterval(reloadTimer);
                reloadTimer = null;
                return;
            }

            if (probing) return;                                // never reload in the middle of a probe
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
