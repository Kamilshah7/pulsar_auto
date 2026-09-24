// Popup logic for Labelbox Sniper Settings

document.addEventListener('DOMContentLoaded', () => {
    const slider = document.getElementById('reload-slider');
    const sliderVal = document.getElementById('reload-val');
    const autoReloadToggle = document.getElementById('autoreload-toggle');
    const sniperToggle = document.getElementById('sniper-toggle');
    const testBtn = document.getElementById('test-siren-btn');
    const stopBtn = document.getElementById('stop-siren-btn');

    // Load settings from storage
    chrome.storage.local.get(['sniper_settings'], (res) => {
        const settings = res.sniper_settings || {
            enabled: true,
            autoReloadSeconds: 10,
            enableAutoReload: true,
            sirenDurationSec: 45
        };

        slider.value = settings.autoReloadSeconds;
        sliderVal.innerText = `${settings.autoReloadSeconds}s`;
        autoReloadToggle.checked = settings.enableAutoReload;
        sniperToggle.checked = settings.enabled;
    });

    // Save helper
    function saveSettings() {
        const settings = {
            enabled: sniperToggle.checked,
            autoReloadSeconds: parseInt(slider.value, 10),
            enableAutoReload: autoReloadToggle.checked,
            sirenDurationSec: 45
        };
        chrome.storage.local.set({ sniper_settings: settings });
    }

    slider.addEventListener('input', () => {
        sliderVal.innerText = `${slider.value}s`;
        saveSettings();
    });

    autoReloadToggle.addEventListener('change', saveSettings);
    sniperToggle.addEventListener('change', saveSettings);

    testBtn.addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'TEST_SIREN' });
    });

    stopBtn.addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'STOP_SIREN' });
    });
});
