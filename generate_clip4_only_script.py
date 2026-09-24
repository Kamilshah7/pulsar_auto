import json, os, wave
from groq import Groq
from dotenv import load_dotenv
load_dotenv()
import pipeline
from reconciler import AcousticReconciler
from vad_trimmer import VadTrimmer

OUTPUT_DIR = 'f:/BB/ETN-SC/pulsar_auto/output'
AUDIO_DIR = 'f:/BB/ETN-SC/pulsar_auto/audio'

# Target WAV and JSON for Clip 4 (index 3)
wname = 'syndigate_podcasts_3d2a82fa260c5c4799f5cb0e2f0a48b0_2110.0_2250.0-sortformer-8.wav'
jname = 'syndigate_podcasts_3d2a82fa260c5c4799f5cb0e2f0a48b0_2110.0_2250.0-sortformer-8.json'
wpath = os.path.join(AUDIO_DIR, wname)
jpath = os.path.join(AUDIO_DIR, jname)

# Clip 4 timeline offset
clip_offset = 70.08
clip_dur = 28.39

print(f"Transcribing {wname} with Groq Whisper...")
client = Groq(api_key=pipeline.GROQ_API_KEY)
with open(wpath, 'rb') as f:
    resp = client.audio.transcriptions.create(
        file=(wname, f.read()),
        model='whisper-large-v3',
        response_format='verbose_json',
        timestamp_granularities=['word']
    )

print("Groq transcript:", resp.text[:120], "...")
groq_words = resp.words

# Load canonical pre-labels from server JSON
jd = json.load(open(jpath, encoding='utf-8'))
pre_segs = []
for s in jd.get('segments', []):
    tstr_s = s.get('startTime', '0:0:0')
    tstr_e = s.get('endTime', '0:0:0')
    def parse_time(ts):
        parts = ts.split(':')
        return float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
    pre_segs.append({
        'text': s.get('refTranscript', s.get('text', '')),
        'start': parse_time(tstr_s),
        'end': parse_time(tstr_e),
        'speaker': s.get('speaker', 'S1')
    })

print(f"Loaded {len(pre_segs)} pre-label segments from server JSON.")

# Run Acoustic Reconciler & VAD Trimmer
trimmer = VadTrimmer(wpath)
reconciler = AcousticReconciler(trimmer)
reconciled, stats = reconciler.reconcile_clip(pre_segs, groq_words, clip_dur)

print(f"Acoustic reconciliation complete: {len(reconciled)} tokens.")
print(f"Silence trimmed: {stats.get('silence_trimmed_ms', 0):.1f}ms | False starts preserved: {stats.get('false_starts_preserved', 0)}")

# Map to global timeline offsets and create final token objects for clip 4
clip4_tokens = []
for t_idx, t in enumerate(reconciled, 1):
    st = float(t["start"])
    en = float(t["end"])
    g_start = round(clip_offset + st, 4)
    g_end = round(clip_offset + en, 4)
    
    clip4_tokens.append({
        "id": f"t_{wname}_{t_idx}",
        "speaker": t.get("speaker", "S1"),
        "start": g_start,
        "end": g_end,
        "text": t["text"].strip(),
        "type": "lexical",
        "clipId": "clip_3",
        "clipIndex": 3,
        "wrapOpen": t.get("wrapOpen", []),
        "wrapClose": t.get("wrapClose", [])
    })

# Save to output/clip4_only_tokens.json
out_tokens_path = os.path.join(OUTPUT_DIR, "clip4_only_tokens.json")
with open(out_tokens_path, "w", encoding="utf-8") as f:
    json.dump(clip4_tokens, f, indent=2)

print(f"Saved {len(clip4_tokens)} tokens to {out_tokens_path}")

# Build Standalone JS script that ONLY updates Clip #4 (leaving all other clips completely untouched)
tokens_json = json.dumps(clip4_tokens)
js_script = f"""// === PULSAR CLIP #4 ONLY INJECTION SCRIPT ===
// Updates ONLY Clip #4 (index 3), leaving all other 10 clips 100% untouched!
(function() {{
    const clip4Tokens = {tokens_json};
    
    if (!window.state || !Array.isArray(window.state.tokens)) {{
        console.error('[Pulsar Injector] window.state.tokens not found! Make sure the task is loaded.');
        return;
    }}
    
    // 1. Keep all tokens from all other clips (index !== 3)
    const otherTokens = window.state.tokens.filter(t => t.clipIndex !== 3 && t.clipId !== 'clip_3');
    
    // 2. Combine with new Clip 4 tokens and sort chronologically
    const allTokens = otherTokens.concat(clip4Tokens);
    allTokens.sort((a, b) => a.start - b.start);
    
    window.state.tokens = allTokens;
    
    // 3. Update tokenStats
    if (!window.state.tokenStats) window.state.tokenStats = {{}};
    for (const t of clip4Tokens) {{
        if (!window.state.tokenStats[t.id]) {{
            window.state.tokenStats[t.id] = {{ played: false, selectedCount: 0 }};
        }}
    }}
    
    // 4. Trigger UI render
    if (typeof renderAll === 'function') {{
        renderAll();
    }}
    
    console.log('%c [Pulsar Injector] SUCCESS! Updated Clip #4 with ' + clip4Tokens.length + ' perfected tokens. All other clips are 100% untouched!', 'background: #00bb44; color: #fff; font-weight: bold; font-size: 14px; padding: 4px 8px;');
}})();
"""

out_js_path = os.path.join(OUTPUT_DIR, "inject_clip4_only.js")
with open(out_js_path, "w", encoding="utf-8") as f:
    f.write(js_script)

print(f"Generated standalone JS script: {out_js_path} ({len(js_script)} bytes)")
