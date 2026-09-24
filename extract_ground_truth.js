// =========================================================================
// Pulsar Ground Truth Extractor (Run in Browser DevTools Console on Pulsar)
// =========================================================================
(function() {
    console.log('%c[Pulsar Ground Truth Extractor] Searching for perfected tokens...', 'color: #00bcd4; font-weight: bold;');

    let tokens = null;

    // 1. Check window.state.tokens
    if (typeof state !== 'undefined' && state && Array.isArray(state.tokens)) {
        tokens = state.tokens;
    } else if (typeof window !== 'undefined' && window.state && Array.isArray(window.state.tokens)) {
        tokens = window.state.tokens;
    }

    // 2. Check iframes if embedded
    if (!tokens || tokens.length === 0) {
        const iframes = document.querySelectorAll('iframe');
        for (const ifr of iframes) {
            try {
                if (ifr.contentWindow && ifr.contentWindow.state && Array.isArray(ifr.contentWindow.state.tokens)) {
                    tokens = ifr.contentWindow.state.tokens;
                    break;
                }
            } catch(e) {}
        }
    }

    // 3. Fallback to localStorage (pulsar_align_clip_*)
    if (!tokens || tokens.length === 0) {
        console.log('[Pulsar Ground Truth Extractor] Checking localStorage keys...');
        const clipKeys = [];
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            if (k && k.startsWith('pulsar_align_clip_')) {
                clipKeys.push(k);
            }
        }
        if (clipKeys.length > 0) {
            let collected = [];
            clipKeys.sort().forEach(k => {
                try {
                    const parsed = JSON.parse(localStorage.getItem(k));
                    if (Array.isArray(parsed)) collected.push(...parsed);
                    else if (parsed && Array.isArray(parsed.tokens)) collected.push(...parsed.tokens);
                } catch(e) {}
            });
            if (collected.length > 0) {
                tokens = collected;
            }
        }
    }

    if (!tokens || tokens.length === 0) {
        console.error('%c[Pulsar Ground Truth Extractor] ❌ Could not find tokens in window.state or localStorage!', 'color: red; font-weight: bold;');
        alert('Could not find tokens in window.state or localStorage! Make sure you are on the Pulsar editor tab.');
        return;
    }

    console.log('%c[Pulsar Ground Truth Extractor] ✅ Found ' + tokens.length + ' perfected tokens!', 'color: #4caf50; font-weight: bold;');

    // Clean & standardize token structure
    const cleanTokens = tokens.map(t => ({
        id: t.id,
        speaker: t.speaker || 'S1',
        start: Number(t.start),
        end: Number(t.end),
        text: t.text || t.word || '',
        type: t.type || 'lexical',
        clipId: t.clipId,
        clipIndex: t.clipIndex,
        wrapOpen: t.wrapOpen || [],
        wrapClose: t.wrapClose || []
    }));

    // Group by clip for a clean summary table
    const clipSummary = {};
    cleanTokens.forEach(t => {
        const c = t.clipIndex !== undefined ? t.clipIndex : (t.clipId || 'unknown');
        if (!clipSummary[c]) clipSummary[c] = { count: 0, words: [] };
        clipSummary[c].count++;
        if (clipSummary[c].words.length < 6) clipSummary[c].words.push(t.text);
    });
    console.table(Object.keys(clipSummary).map(k => ({
        Clip: k,
        Tokens: clipSummary[k].count,
        Preview: clipSummary[k].words.join(' ') + '...'
    })));

    const jsonStr = JSON.stringify(cleanTokens, null, 2);

    // 1. Copy JSON directly to clipboard
    try {
        if (typeof copy === 'function') {
            copy(jsonStr);
            console.log('%c[Pulsar Ground Truth Extractor] 📋 Copied JSON to clipboard!', 'color: #2196f3;');
        } else {
            navigator.clipboard.writeText(jsonStr).then(() => {
                console.log('%c[Pulsar Ground Truth Extractor] 📋 Copied JSON to clipboard!', 'color: #2196f3;');
            });
        }
    } catch(e) {}

    // 2. Download baseline_ground_truth.json directly
    try {
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'baseline_ground_truth.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        console.log('%c[Pulsar Ground Truth Extractor] 💾 Downloaded baseline_ground_truth.json!', 'color: #ff9800;');
    } catch(e) {}

    console.log('%c[Pulsar Ground Truth Extractor] 🚀 ALL DONE! Just drop the downloaded file into pulsar_auto/output/ or paste into chat.', 'color: #4caf50; font-weight: bold;');
})();