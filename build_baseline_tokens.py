"""
Build rule-compliant baseline tokens from Groq Whisper transcriptions and exact audio offsets.
Serves as an immediate baseline and validates the injection pipeline.
"""
import os
import json
import re
import wave

AUDIO_DIR = "f:/BB/ETN-SC/pulsar_auto/audio"
OUTPUT_DIR = "f:/BB/ETN-SC/pulsar_auto/output"

groq_data = json.load(open(os.path.join(OUTPUT_DIR, "groq_transcriptions.json"), encoding="utf-8"))

# Standard informal contractions allowed by Pulsar
ALLOWED_CONTRACTIONS = {
    "gonna", "wanna", "gotta", "gimme", "lemme", "whatcha", "dunno", 
    "gotcha", "kinda", "y'all", "'til", "'er", "'em", "c'mon", "'cause"
}

# Standard backchannel mappings
BACKCHANNEL_MAP = {
    "uh-huh": ["uh", "huh"],
    "mm-hm": ["mm", "hm"],
    "mm-mm": ["mm", "mm"],
    "nuh-huh": ["nuh", "huh"],
    "mmm": ["hmm"],
}

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

def clean_word(raw_word):
    """Normalize word per Pulsar rules: lowercase, strip punctuation except apostrophes."""
    w = raw_word.strip().lower()
    # Remove surrounding punctuation like quotes, commas, periods, etc.
    w = re.sub(r"^[^\w'<>\(\)\-]+", "", w)
    w = re.sub(r"[^\w'<>\(\)\-]+$", "", w)
    # Remove internal commas, periods, etc.
    w = w.replace(",", "").replace(".", "").replace("?", "").replace("!", "")
    w = w.replace("\"", "").replace(":", "").replace(";", "")
    return w

all_tokens = []

for clip_data in groq_data:
    c_idx = clip_data["clip_index"]
    c_info = CLIP_MAP[c_idx]
    offset = c_info["start_sec"]
    clip_dur = c_info["duration_sec"]
    fname = c_info["filename"]
    
    words = clip_data["words"]
    clip_tokens = []
    
    for w_entry in words:
        raw_w = w_entry["word"]
        start_local = float(w_entry["start"])
        end_local = float(w_entry["end"])
        
        # Clamp local times
        start_local = max(0.001, min(start_local, clip_dur - 0.002))
        end_local = max(start_local + 0.050, min(end_local, clip_dur - 0.001))
        
        cleaned = clean_word(raw_w)
        if not cleaned:
            continue
            
        # Check for hyphenated words: e.g. "eighty-seven" -> "eighty", "seven"
        # but keep truncations like "de-" or "elev-"
        if "-" in cleaned and not cleaned.endswith("-") and not cleaned.startswith("-"):
            parts = cleaned.split("-")
            n = len(parts)
            span = (end_local - start_local) / n
            for i, p in enumerate(parts):
                p_clean = clean_word(p)
                if p_clean:
                    st = round(start_local + i * span, 3)
                    en = round(start_local + (i + 1) * span, 3)
                    clip_tokens.append({
                        "text": p_clean,
                        "start": st,
                        "end": en,
                        "start_local": st,
                        "end_local": en
                    })
        else:
            st = round(start_local, 3)
            en = round(end_local, 3)
            clip_tokens.append({
                "text": cleaned,
                "start": st,
                "end": en,
                "start_local": st,
                "end_local": en
            })
            
    # Check for pre-labeled JSON
    jpath = os.path.join(AUDIO_DIR, fname.replace(".wav", ".json"))
    wpath = os.path.join(AUDIO_DIR, fname)
    pre_segs = []
    if os.path.exists(jpath):
        try:
            jd = json.load(open(jpath, encoding="utf-8"))
            for s in jd.get("segments", []):
                tstr_s = s.get("startTime", "0:0:0")
                tstr_e = s.get("endTime", "0:0:0")
                def parse_time(ts):
                    parts = ts.split(":")
                    return float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
                pre_segs.append({
                    "text": s.get("refTranscript", s.get("text", "")),
                    "start": parse_time(tstr_s),
                    "end": parse_time(tstr_e)
                })
        except Exception:
            pass

    from vad_trimmer import VadTrimmer
    from reconciler import AcousticReconciler

    trimmer = VadTrimmer(wpath) if os.path.exists(wpath) else None
    reconciler = AcousticReconciler(trimmer)
    reconciled = reconciler.reconcile_clip(pre_segs, clip_tokens, clip_dur)

    # Build final token objects with global timeline coordinates
    for t_idx, t in enumerate(reconciled, 1):
        global_start = round(offset + t["start"], 4)
        global_end = round(offset + t["end"], 4)
        
        token_obj = {
            "id": f"t_{fname}_{t_idx}",
            "speaker": "S1",
            "start": global_start,
            "end": global_end,
            "text": t["text"],
            "type": "lexical",
            "clipId": f"clip_{c_idx}",
            "clipIndex": c_idx,
            "wrapOpen": [],
            "wrapClose": []
        }
        all_tokens.append(token_obj)

out_file = os.path.join(OUTPUT_DIR, "baseline_tokens.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(all_tokens, f, indent=2)

print(f"Generated {len(all_tokens)} baseline tokens across all 11 clips!")
print(f"Saved to {out_file}")
