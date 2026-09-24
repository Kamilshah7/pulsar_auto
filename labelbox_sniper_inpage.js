// ==UserScript==
// @name         Labelbox Task Sniper & Siren Alert
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Snipes the "Start" button as soon as it turns blue (active) and plays a loud siren
// @match        https://app.labelbox.com/projects/*/overview*
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    // Prevent double injection
    if (window.__LABELBOX_SNIPER_RUNNING__) {
        console.log('[Sniper] Already active!');
        return;
    }
    window.__LABELBOX_SNIPER_RUNNING__ = true;

    // Config
    const CONFIG = {
        checkIntervalMs: 250,       // DOM scan frequency (4x per second)
        autoReloadSeconds: 12,      // Auto-refresh if page doesn't live-update
        enableAutoReload: true,     // Toggle auto-refresh
        sirenDurationSec: 45        // How long the siren blares
    };

    let checkCount = 0;
    let reloadCountdown = CONFIG.autoReloadSeconds;
    let taskSnagged = false;
    let audioCtx = null;
    let sirenInterval = null;

    // Save active state to sessionStorage so it automatically persists through page reloads
    sessionStorage.setItem('lb_sniper_auto_run', 'true');

    // --- Audio Siren Engine (Web Audio API) ---
    function initAudio() {
        if (!audioCtx) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            audioCtx = new AudioContextClass();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
    }

    function playSiren() {
        initAudio();
        if (sirenInterval) return;

        let toneHigh = false;
        const playTone = () => {
            if (!audioCtx) return;
            try {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();

                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(toneHigh ? 1300 : 750, audioCtx.currentTime);
                toneHigh = !toneHigh;

                gain.gain.setValueAtTime(0.35, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.22);

                osc.connect(gain);
                gain.connect(audioCtx.destination);

                osc.start();
                osc.stop(audioCtx.currentTime + 0.23);
            } catch (e) {
                console.error('[Sniper Audio Error]', e);
            }
        };

        playTone();
        sirenInterval = setInterval(playTone, 240);

        // Flash screen background
        document.body.classList.add('sniper-alarm-active');

        // Stop siren after configured duration
        setTimeout(() => {
            stopSiren();
        }, CONFIG.sirenDurationSec * 1000);
    }

    function stopSiren() {
        if (sirenInterval) {
            clearInterval(sirenInterval);
            sirenInterval = null;
        }
        document.body.classList.remove('sniper-alarm-active');
        const alertBorder = document.getElementById('lb-sniper-alert-overlay');
        if (alertBorder) alertBorder.remove();
    }

    // --- Helper: Find the Start Button ---
    function findStartButton() {
        const buttons = Array.from(document.querySelectorAll('button, a[role="button"]'));
        for (const btn of buttons) {
            const txt = (btn.textContent || '').trim();
            // Look for button that starts with or contains "Start"
            if (/^start/i.test(txt) || txt === 'Start') {
                return btn;
            }
        }
        return null;
    }

    // --- Helper: Check if Button is Enabled / Blue ---
    function isButtonActive(btn) {
        if (!btn) return false;

        // Check disabled attributes and classes
        const isDisabled = btn.disabled ||
                           btn.hasAttribute('disabled') ||
                           btn.classList.contains('Mui-disabled') ||
                           btn.getAttribute('aria-disabled') === 'true';

        if (isDisabled) return false;

        // Optional check for blue styling / primary color
        const style = window.getComputedStyle(btn);
        const isClickable = style.pointerEvents !== 'none' && style.cursor !== 'not-allowed';

        return isClickable;
    }

    // --- Snag Action ---
    function snagTask(btn) {
        if (taskSnagged) return;
        taskSnagged = true;

        console.log('%c [SNIPER] 🎯 BUTTON IS BLUE & ACTIVE! SNAGGING TASK NOW!', 'background: #00aa00; color: #ffffff; font-size: 16px; font-weight: bold; padding: 4px 8px;');

        // 1. Dispatch full click suite
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

        // 2. Check if a dropdown menu opened (e.g. "Start labeling")
        setTimeout(() => {
            const menuItems = document.querySelectorAll('[role="menuitem"], .MuiMenuItem-root, [class*="MenuItem"]');
            if (menuItems.length > 0) {
                console.log('[Sniper] Found dropdown menuitem, clicking first option...');
                menuItems[0].click();
            }
        }, 150);

        // 3. Start loud siren & visual alarm
        playSiren();
        triggerVisualOverlay();

        // 4. Update HUD
        const statusEl = document.getElementById('lb-sniper-status');
        if (statusEl) {
            statusEl.innerHTML = '<span style="color: #00ff66; font-weight: bold;">🎉 TASK SNAGGED! SIREN BLARING!</span>';
        }
        document.title = '🚨🚨 TASK READY! SNAGGED! 🚨🚨';
    }

    // --- Fullscreen Flash Overlay ---
    function triggerVisualOverlay() {
        let overlay = document.getElementById('lb-sniper-alert-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'lb-sniper-alert-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0; left: 0; width: 100vw; height: 100vh;
                border: 14px solid #ff0055;
                box-sizing: border-box;
                z-index: 2147483647;
                pointer-events: none;
                animation: lbSniperPulse 0.4s infinite alternate;
            `;
            document.body.appendChild(overlay);
        }
    }

    // --- Inject Styles ---
    const styleSheet = document.createElement('style');
    styleSheet.textContent = `
        @keyframes lbSniperPulse {
            0% { border-color: #ff0055; box-shadow: inset 0 0 50px rgba(255, 0, 85, 0.6); }
            100% { border-color: #00ff88; box-shadow: inset 0 0 50px rgba(0, 255, 136, 0.6); }
        }
        #lb-sniper-hud {
            position: fixed;
            top: 14px;
            right: 14px;
            z-index: 9999999;
            background: rgba(18, 22, 34, 0.94);
            border: 1px solid rgba(0, 195, 255, 0.4);
            border-radius: 10px;
            padding: 12px 16px;
            color: #e0e8ff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace, sans-serif;
            font-size: 13px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(8px);
            min-width: 250px;
            user-select: none;
        }
        #lb-sniper-hud .hud-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-weight: bold;
            font-size: 14px;
            color: #00d4ff;
            margin-bottom: 8px;
            padding-bottom: 6px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        #lb-sniper-hud .hud-row {
            margin: 4px 0;
            display: flex;
            justify-content: space-between;
        }
        #lb-sniper-hud .hud-btn {
            background: #252b42;
            border: 1px solid #3c466b;
            color: #fff;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
            margin-top: 6px;
            transition: all 0.2s;
        }
        #lb-sniper-hud .hud-btn:hover {
            background: #394368;
            border-color: #00d4ff;
        }
    `;
    document.head.appendChild(styleSheet);

    // --- Build Modern HUD Element ---
    const hud = document.createElement('div');
    hud.id = 'lb-sniper-hud';
    hud.innerHTML = `
        <div class="hud-title">
            <span>🎯 Labelbox Sniper</span>
            <span style="font-size: 10px; background: #00d4ff22; color: #00d4ff; padding: 2px 6px; border-radius: 4px;">ACTIVE</span>
        </div>
        <div class="hud-row">
            <span>Status:</span>
            <span id="lb-sniper-status" style="color: #ffaa00; font-weight: bold;">Waiting for tasks...</span>
        </div>
        <div class="hud-row">
            <span>Button state:</span>
            <span id="lb-sniper-btn-state">Disabled (Grey)</span>
        </div>
        <div class="hud-row">
            <span>Next Refresh:</span>
            <span id="lb-sniper-timer">${CONFIG.autoReloadSeconds}s</span>
        </div>
        <div class="hud-row">
            <span>Scans:</span>
            <span id="lb-sniper-scans">0</span>
        </div>
        <div style="display: flex; gap: 6px; margin-top: 8px;">
            <button id="lb-test-siren-btn" class="hud-btn" style="flex: 1;">🔊 Test Siren</button>
            <button id="lb-stop-siren-btn" class="hud-btn" style="flex: 1;">⏹️ Stop Sound</button>
        </div>
        <div style="margin-top: 6px;">
            <label style="font-size: 11px; color: #a0aec0; display: flex; align-items: center; gap: 6px; cursor: pointer;">
                <input type="checkbox" id="lb-autoreload-toggle" ${CONFIG.enableAutoReload ? 'checked' : ''}>
                Auto-refresh page
            </label>
        </div>
    `;
    document.body.appendChild(hud);

    // Wire up HUD Buttons
    document.getElementById('lb-test-siren-btn').addEventListener('click', () => {
        initAudio();
        playSiren();
        setTimeout(stopSiren, 2500);
    });
    document.getElementById('lb-stop-siren-btn').addEventListener('click', () => {
        stopSiren();
    });
    document.getElementById('lb-autoreload-toggle').addEventListener('change', (e) => {
        CONFIG.enableAutoReload = e.target.checked;
    });

    // Make HUD Draggable
    let isDragging = false, startX, startY, origX, origY;
    hud.addEventListener('mousedown', (e) => {
        if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') return;
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = hud.getBoundingClientRect();
        origX = rect.left;
        origY = rect.top;
        e.preventDefault();
    });
    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        hud.style.right = 'auto';
        hud.style.left = (origX + (e.clientX - startX)) + 'px';
        hud.style.top = (origY + (e.clientY - startY)) + 'px';
    });
    window.addEventListener('mouseup', () => { isDragging = false; });

    // Enable Audio on any user click anywhere on page (browser policy)
    window.addEventListener('click', () => {
        initAudio();
    }, { once: true });

    // --- Main Monitor Loop ---
    const scanLoop = setInterval(() => {
        if (taskSnagged) return;

        checkCount++;
        const scanEl = document.getElementById('lb-sniper-scans');
        if (scanEl) scanEl.innerText = checkCount;

        const btn = findStartButton();
        const stateEl = document.getElementById('lb-sniper-btn-state');

        if (!btn) {
            if (stateEl) stateEl.innerHTML = '<span style="color: #ff6666;">Not found</span>';
            return;
        }

        const active = isButtonActive(btn);

        if (active) {
            if (stateEl) stateEl.innerHTML = '<span style="color: #00ff88; font-weight: bold;">ENABLED (BLUE)!</span>';
            snagTask(btn);
        } else {
            if (stateEl) stateEl.innerHTML = '<span style="color: #999999;">Disabled (Grey)</span>';
        }
    }, CONFIG.checkIntervalMs);

    // --- Auto-Refresh Countdown ---
    const timerLoop = setInterval(() => {
        if (taskSnagged) return;
        if (!CONFIG.enableAutoReload) return;

        reloadCountdown--;
        const timerEl = document.getElementById('lb-sniper-timer');
        if (timerEl) timerEl.innerText = `${reloadCountdown}s`;

        if (reloadCountdown <= 0) {
            console.log('[Sniper] Auto-refreshing page to check for new tasks...');
            window.location.reload();
        }
    }, 1000);

    console.log('%c [SNIPER] Labelbox Start-Button Sniper Initialized! Monitoring top-right Start button.', 'color: #00d4ff; font-weight: bold;');
})();
