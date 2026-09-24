// ==========================================================================
// Pulsar Golden Labels Extractor — Run in Browser Console (F12) on the editor
// ==========================================================================
(function() {
    console.log('%c[Golden Extractor] Searching for tokens...', 'color: #00bcd4; font-weight: bold;');

    let tokens = null;

    // 1. window.state.tokens
    if (typeof state !== 'undefined' && state && Array.isArray(state.tokens)) {
        tokens = state.tokens;
    } else if (window.state && Array.isArray(window.state.tokens)) {
        tokens = window.state.tokens;
    }

    // 2. Check iframes
    if (!tokens || tokens.length === 0) {
        for (const ifr of document.querySelectorAll('iframe')) {
            try {
                if (ifr.contentWindow?.state?.tokens?.length) {
                    tokens = ifr.contentWindow.state.tokens;
                    break;
                }
            } catch(e) {}
        }
    }

    if (!tokens || tokens.length === 0) {
        console.error('%c[Golden Extractor] ❌ No tokens found!', 'color:red; font-weight:bold;');
        alert('No tokens found! Make sure you are on the Pulsar editor page.');
        return;
    }

    // Clean tokens
    const clean = tokens.map(t => ({
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

    // Also grab clip list from the DOM
    let clips = [];
    try {
        const clipEls = document.querySelectorAll('.clip-item');
        clipEls.forEach((el, i) => {
            const label = el.querySelector('.clip-label')?.textContent?.trim() || el.textContent?.trim().split('\n')[0] || '';
            const time = el.querySelector('.clip-time')?.textContent?.trim() || '';
            clips.push({ index: i, label, time, classes: el.className });
        });
    } catch(e) {}

    // Summary
    const byClip = {};
    clean.forEach(t => {
        const c = t.clipIndex ?? '?';
        if (!byClip[c]) byClip[c] = 0;
        byClip[c]++;
    });
    console.log('%c[Golden Extractor] ✅ ' + clean.length + ' tokens across ' + Object.keys(byClip).length + ' clips', 'color:#4caf50; font-weight:bold;');
    console.table(Object.entries(byClip).map(([k,v]) => ({ Clip: k, Tokens: v })));

    // Build payload
    const payload = { tokens: clean, clips: clips, extracted_at: new Date().toISOString(), total_tokens: clean.length, total_clips: Object.keys(byClip).length };
    const jsonStr = JSON.stringify(payload, null, 2);

    // Copy to clipboard
    try { if (typeof copy === 'function') copy(jsonStr); else navigator.clipboard.writeText(jsonStr); } catch(e) {}

    // Download
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'golden_labels.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    console.log('%c[Golden Extractor] 💾 Downloaded golden_labels.json (' + clean.length + ' tokens)', 'color:#ff9800; font-weight:bold;');
})();
