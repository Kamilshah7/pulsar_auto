// Background Service Worker for Labelbox Task Sniper

let creatingOffscreenPromise = null;

async function hasOffscreenDocument() {
    try {
        if ('getContexts' in chrome.runtime) {
            const contexts = await chrome.runtime.getContexts({
                contextTypes: ['OFFSCREEN_DOCUMENT'],
                documentUrls: [chrome.runtime.getURL('offscreen.html')]
            });
            return contexts.length > 0;
        } else if (chrome.offscreen && 'hasDocument' in chrome.offscreen) {
            return await chrome.offscreen.hasDocument();
        }
    } catch (e) {
        // Fallback
    }
    return false;
}

async function setupOffscreen() {
    if (await hasOffscreenDocument()) return;

    if (creatingOffscreenPromise) {
        await creatingOffscreenPromise;
    } else {
        creatingOffscreenPromise = chrome.offscreen.createDocument({
            url: 'offscreen.html',
            reasons: ['AUDIO_PLAYBACK'],
            justification: 'Audible loud siren alert when new task is available'
        }).catch(err => {
            if (!err.message.includes('Only a single offscreen document may be created')) {
                console.error('[Sniper BG] createDocument error:', err);
            }
        });
        await creatingOffscreenPromise;
        creatingOffscreenPromise = null;
    }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    (async () => {
        try {
            if (message.action === 'TASK_SNAGGED') {
                // 1. Show high-priority desktop notification
                try {
                    chrome.notifications.create('task_snagged_' + Date.now(), {
                        type: 'basic',
                        iconUrl: 'icon128.png',
                        title: '🚨 TASK READY & SNAGGED! 🚨',
                        message: 'Labelbox Start button became active and was automatically clicked! Jump to your tab now.',
                        priority: 2,
                        requireInteraction: true
                    });
                } catch (e) {
                    console.error('[Notification error]', e);
                }

                // 2. Set action badge
                chrome.action.setBadgeText({ text: 'GO!' });
                chrome.action.setBadgeBackgroundColor({ color: '#00cc44' });

                // 3. Play loud siren via offscreen document
                await setupOffscreen();
                chrome.runtime.sendMessage({ action: 'PLAY_SIREN', duration: message.duration || 45 });
                sendResponse({ status: 'ok' });
            } else if (message.action === 'STOP_SIREN') {
                chrome.action.setBadgeText({ text: '' });
                await setupOffscreen();
                chrome.runtime.sendMessage({ action: 'OFFSCREEN_STOP' });
                sendResponse({ status: 'ok' });
            } else if (message.action === 'TEST_SIREN') {
                await setupOffscreen();
                chrome.runtime.sendMessage({ action: 'PLAY_SIREN', duration: 3 });
                sendResponse({ status: 'ok' });
            }
        } catch (globalErr) {
            console.error('[Sniper BG message handler error]', globalErr);
            sendResponse({ error: globalErr.toString() });
        }
    })();
    return true; // Keep message channel open for async response
});
