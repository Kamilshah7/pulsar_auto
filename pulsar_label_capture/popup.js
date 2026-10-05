// Pulsar Label Capture -- aligner2/PERFECTION_WORKFLOW.md
const SERVER = 'http://127.0.0.1:7860/api/capture-labels';
const out = document.getElementById('out');

function show(text, cls) { out.className = cls || ''; out.textContent = text; }

// Runs IN THE PAGE (world MAIN, every frame): the editor keeps its labels in state.tokens
function readEditor() {
  let tokens = null;
  try { if (typeof state !== 'undefined' && state && Array.isArray(state.tokens)) tokens = state.tokens; } catch (e) {}
  if (!tokens && window.state && Array.isArray(window.state.tokens)) tokens = window.state.tokens;
  if (!tokens || !tokens.length) return null;
  const clean = tokens.map(t => ({
    id: t.id, speaker: t.speaker || 'S1', start: Number(t.start), end: Number(t.end), text: t.text || t.word || '',
    type: t.type || 'lexical', clipId: t.clipId, clipIndex: t.clipIndex, wrapOpen: t.wrapOpen || [], wrapClose: t.wrapClose || []
  }));
  const clips = [];
  try {
    document.querySelectorAll('.clip-item').forEach((el, i) => clips.push({
      index: i, label: (el.querySelector('.clip-label')?.textContent || el.textContent || '').trim().split('\n')[0],
      time: (el.querySelector('.clip-time')?.textContent || '').trim()
    }));
  } catch (e) {}
  let url = location.href;
  try { url = window.top.location.href; } catch (e) {}      // the task URL carries ?bundle=
  return { tokens: clean, clips, url, frame: location.href, extracted_at: new Date().toISOString() };
}

function downloadFallback(payload) {
  const name = `pulsar_${payload.kind}_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(payload)], { type: 'application/json' }));
  a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  return name;
}

async function capture(kind) {
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  show(`Reading the editor's labels (${kind.toUpperCase()})...`);
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const results = await chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, world: 'MAIN', func: readEditor });
    const hit = results.map(r => r && r.result).find(r => r && r.tokens && r.tokens.length);
    if (!hit) {
      show('No labels found on this tab.\nOpen the Pulsar editor (the page where you edit the word boundaries) and try again.', 'err');
      return;
    }
    const payload = { kind, ...hit };
    let res;
    try {
      const r = await fetch(SERVER, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      res = await r.json();
      if (!r.ok || !res.ok) throw new Error(res.error || ('HTTP ' + r.status));
    } catch (e) {
      const f = downloadFallback(payload);
      show(`Could not save to the app (${e.message}).\nIs app.py running?\nNothing is lost: downloaded ${f} -- import it later with:\npython label_capture.py import <that file>`, 'warn');
      return;
    }
    let msg = `Saved ${kind.toUpperCase()} for\n${res.bundle}\n${res.tokens} tokens, ${res.clips} clips, audio saved ${res.wavs_found}/${res.wavs}`;
    if (res.diff) {
      const d = res.diff;
      msg += `\nvs ${res.compared_to}: ${d.boundaries_moved} boundaries moved, ${d.tokens_added} tokens added, ${d.tokens_removed} removed`;
    }
    let cls = 'ok';
    if (kind === 'current' && res.wavs === 0) {
      msg += '\nWARNING: these labels do not carry the system\'s injected token ids -- this looks like the PRELABELS. ' +
             'Inject the system\'s labels first, then save CURRENT again.'; cls = 'err';
    } else if (kind === 'current' && res.diff && res.diff.boundaries_moved > 0) {
      msg += '\nNote: CURRENT already differs from the system\'s injected labels -- was something edited already?'; cls = 'warn';
    }
    if (kind === 'golden' && res.diff && res.diff.boundaries_moved === 0 && !res.diff.tokens_added && !res.diff.tokens_removed) {
      msg += '\nNote: nothing differs from the starting labels -- is this really after your corrections?'; cls = 'warn';
    }
    if (res.wavs_found < res.wavs) { msg += '\nWarning: some clips\' audio is not saved yet (run the bundle through the app).'; cls = 'warn'; }
    if (res.notes_file) msg += `\nChange notes: ${res.notes_file}${res.notes_created ? ' (created -- open it in Notepad)' : ''}`;
    show(msg, cls);
  } catch (e) {
    show('Error: ' + e.message, 'err');
  } finally {
    document.querySelectorAll('button').forEach(b => b.disabled = false);
  }
}

document.getElementById('current').onclick = () => capture('current');
document.getElementById('golden').onclick = () => capture('golden');
