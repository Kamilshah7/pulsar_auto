"""
Inject tokens into the Pulsar editor.
Can inject either:
  1. output/llm_corrected_tokens.json (if produced by LLM)
  2. output/baseline_tokens.json (Whisper-derived baseline)

Produces:
  - output/inject_console.js (for instant paste into browser DevTools console F12)
  - injects via Botasaurus directly into the editor session
"""
import os
import json
import wave

OUTPUT_DIR = "f:/BB/ETN-SC/pulsar_auto/output"
AUDIO_DIR = "f:/BB/ETN-SC/pulsar_auto/audio"

clips_file = os.path.join(OUTPUT_DIR, "ordered_clips.json")
CLIPS = json.load(open(clips_file, encoding="utf-8"))

cur_time_sec = 0.0
for clip in CLIPS:
    if "start_sec" not in clip:
        path = os.path.join(AUDIO_DIR, clip["filename"])
        with wave.open(path, "rb") as wf:
            nframes = wf.getnframes()
            sr = wf.getframerate()
            clip["duration_sec"] = nframes / sr
            clip["start_sec"] = cur_time_sec
            clip["end_sec"] = cur_time_sec + clip["duration_sec"]
            cur_time_sec = clip["end_sec"]

CLIP_MAP = {c["index"]: c for c in CLIPS}

def prepare_tokens():
    """Load tokens from LLM output or fallback to baseline tokens."""
    llm_file = os.path.join(OUTPUT_DIR, "llm_corrected_tokens.json")
    baseline_file = os.path.join(OUTPUT_DIR, "baseline_tokens.json")
    
    if os.path.exists(llm_file):
        print(f"Loading LLM corrected tokens from {llm_file}...")
        raw = json.load(open(llm_file, encoding="utf-8"))
        # If format is {"0": [...], "1": [...]}, convert to flat token list
        if isinstance(raw, dict):
            final_tokens = []
            for c_idx_str, toks in raw.items():
                c_idx = int(c_idx_str)
                c_info = CLIP_MAP[c_idx]
                offset = c_info["start_sec"]
                fname = c_info["filename"]
                for t_idx, t in enumerate(toks, 1):
                    # Check if times are local or global
                    st = float(t["start"])
                    en = float(t["end"])
                    # If start is smaller than offset, treat as local
                    if st < offset:
                        g_start = round(offset + st, 4)
                        g_end = round(offset + en, 4)
                    else:
                        g_start = round(st, 4)
                        g_end = round(en, 4)
                        
                    final_tokens.append({
                        "id": f"t_{fname}_{t_idx}",
                        "speaker": t.get("speaker", "S1"),
                        "start": g_start,
                        "end": g_end,
                        "text": t["text"].strip().lower(),
                        "type": "lexical",
                        "clipId": f"clip_{c_idx}",
                        "clipIndex": c_idx,
                        "wrapOpen": t.get("wrapOpen", []),
                        "wrapClose": t.get("wrapClose", [])
                    })
            return final_tokens
        elif isinstance(raw, list):
            return raw
    elif os.path.exists(baseline_file):
        print(f"Loading baseline tokens from {baseline_file}...")
        return json.load(open(baseline_file, encoding="utf-8"))
    else:
        raise FileNotFoundError("Neither llm_corrected_tokens.json nor baseline_tokens.json found!")

def generate_console_script(tokens):
    """Generate a JS snippet to paste into DevTools console (F12)."""
    js_code = f"""// === PULSAR INJECTION SCRIPT ===
// Paste this directly into the Chrome DevTools Console (F12) while viewing the editor.
(function() {{
    const newTokens = {json.dumps(tokens)};
    
    console.log('[Pulsar Injector] Updating state.tokens with ' + newTokens.length + ' tokens...');
    state.tokens = newTokens;
    
    if (!state.tokenStats) state.tokenStats = {{}};
    for (const t of state.tokens) {{
        if (!state.tokenStats[t.id]) {{
            state.tokenStats[t.id] = {{ played: false, selectedCount: 0 }};
        }}
    }}
    
    // Refresh all editor views and save to storage/server
    renderAll();
    
    console.log('[Pulsar Injector] SUCCESS! All 11 clips updated.');
    console.log('[Pulsar Injector] You can now review waveform boundaries, add tags (<ol>, <s*>, <ct>), and click Run QA.');
}})();
"""
    out_path = os.path.join(OUTPUT_DIR, "inject_console.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(js_code)
    print(f"Generated DevTools console script: {out_path}")
    return out_path


TASK_URL = (
    "https://pulsar-upload-portal.vercel.app/"
    "?bundle=word_alignment_production_2026-08-29_SO-70802-b04_bundle_048"
    "&dataRowId=cmte54vwkhrkn073238x10iwk"
    "&sig=-vg1jesPClcCgnXgGWXbF2uHS79hut0bMTKFTFagPqc"
)

def inject_via_browser(tokens):
    """Optionally inject directly using Botasaurus browser."""
    from botasaurus.browser import browser, Driver
    
    @browser(
        block_images=False,
        wait_for_complete_page_load=False,
    )
    def do_inject(driver: Driver, data):
        print("[1] Navigating to task URL...")
        driver.get(TASK_URL)
        driver.sleep(3)
        
        print("[2] If prompted for password/email, enter them now in the browser:")
        print("    Password: (see local_secrets.json)")
        print("    Email: kamilkhan1704@gmail.com")
        print("    When editor is visible, press ENTER in this terminal.")
        driver.prompt()
        driver.sleep(2)
        
        print("[3] Injecting tokens into editor state...")
        tokens_json = json.dumps(tokens)
        res = driver.run_js(f"""
            try {{
                const newTokens = {tokens_json};
                state.tokens = newTokens;
                if (!state.tokenStats) state.tokenStats = {{}};
                for (const t of state.tokens) {{
                    if (!state.tokenStats[t.id]) {{
                        state.tokenStats[t.id] = {{ played: false, selectedCount: 0 }};
                    }}
                }}
                renderAll();
                toast('Injected ' + newTokens.length + ' tokens successfully!', 'ok');
                return {{ ok: true, count: state.tokens.length }};
            }} catch(e) {{
                return {{ ok: false, error: e.message }};
            }}
        """)
        print(f"    Injection result: {res}")
        print("[4] Tokens injected! You can inspect the editor now.")
        driver.prompt("Press ENTER when done reviewing the editor in browser.")
        return res

    return do_inject()


if __name__ == "__main__":
    import sys
    tokens = prepare_tokens()
    print(f"Prepared {len(tokens)} tokens.")
    js_path = generate_console_script(tokens)
    print("\n" + "=" * 60)
    print("READY TO INJECT!")
    print(f"Option A (Instant - 0s): Open DevTools (F12) in your already-open browser,")
    print(f"         copy the contents of:\n         {js_path}\n         and paste into Console.")
    print(f"Option B (Automated): Run: python inject_tokens.py --browser")
    print("=" * 60)
    
    if "--browser" in sys.argv:
        inject_via_browser(tokens)

