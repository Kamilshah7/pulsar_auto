// Offscreen Audio Synthesizer for High-Volume Siren Alert

let audioCtx = null;
let sirenInterval = null;
let stopTimeout = null;

function getAudioContext() {
    if (!audioCtx) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AudioContextClass();
    }
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    return audioCtx;
}

function startSiren(durationSec = 45) {
    stopSiren();
    const ctx = getAudioContext();

    let isHigh = false;

    const playBeep = () => {
        try {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            // Sawtooth wave carries highest acoustic penetration
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(isHigh ? 1350 : 800, ctx.currentTime);
            isHigh = !isHigh;

            // Punchy gain envelope
            gain.gain.setValueAtTime(0.5, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.02, ctx.currentTime + 0.22);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start();
            osc.stop(ctx.currentTime + 0.23);
        } catch (e) {
            console.error('[Offscreen Audio] Error generating tone:', e);
        }
    };

    playBeep();
    sirenInterval = setInterval(playBeep, 240);

    stopTimeout = setTimeout(() => {
        stopSiren();
    }, durationSec * 1000);
}

function stopSiren() {
    if (sirenInterval) {
        clearInterval(sirenInterval);
        sirenInterval = null;
    }
    if (stopTimeout) {
        clearTimeout(stopTimeout);
        stopTimeout = null;
    }
}

chrome.runtime.onMessage.addListener((message) => {
    if (message.action === 'PLAY_SIREN') {
        startSiren(message.duration || 45);
    } else if (message.action === 'OFFSCREEN_STOP') {
        stopSiren();
    }
});
