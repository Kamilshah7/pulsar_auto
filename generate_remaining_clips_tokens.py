import os
import sys
import json
import numpy as np

BASE_DIR = r"f:\BB\ETN-SC\pulsar_auto"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from forced_aligner import ForcedAligner

aligner = ForcedAligner()

clips_file = os.path.join(BASE_DIR, "output", "ordered_clips.json")
clips = json.load(open(clips_file, encoding="utf-8"))
clip_map = {c["index"]: c for c in clips}

llm_d = json.load(open(os.path.join(BASE_DIR, "output", "llm_corrected_tokens.json"), encoding="utf-8"))

new_tokens_6_15 = []
total_violations = 0
min_gap = 999.0
min_dur = 999.0

print("=" * 85)
print("RUNNING GOLD-STANDARD ACOUSTIC ENGINE ON REMAINING CLIPS (CLIPS 6 TO 15)")
print("=" * 85)

for c_idx in range(6, 16):
    c_info = clip_map[c_idx]
    fname = c_info["filename"]
    offset = c_info["start_sec"]
    wpath = os.path.join(BASE_DIR, "audio", fname)
    raw_words = llm_d[str(c_idx)]

    aligned = aligner.align(wpath, raw_words, hybrid=True)

    print(f"Clip {c_idx:2d} ({c_info['id']}, offset={offset:.3f}s, dur={c_info['duration_sec']:.3f}s): {len(aligned)} / {len(raw_words)} tokens aligned.")

    # Validate gaps and durations
    for i in range(len(aligned)):
        dur = aligned[i]["end"] - aligned[i]["start"]
        if dur < min_dur:
            min_dur = dur
        if i < len(aligned) - 1:
            gap = aligned[i+1]["start"] - aligned[i]["end"]
            if gap < min_gap:
                min_gap = gap
            if gap < 0.0019:
                total_violations += 1
                print(f"  [VIOLATION] Clip {c_idx}: {aligned[i]['text']} [{aligned[i]['start']:.4f}, {aligned[i]['end']:.4f}] and {aligned[i+1]['text']} [{aligned[i+1]['start']:.4f}, {aligned[i+1]['end']:.4f}] gap={gap*1000:.2f}ms")

    for t_idx, t in enumerate(aligned, 1):
        new_tokens_6_15.append({
            "id": f"t_{fname}_{t_idx}",
            "speaker": "S1",
            "start": round(offset + t["start"], 4),
            "end": round(offset + t["end"], 4),
            "text": t["text"],
            "type": "lexical",
            "clipId": f"clip_{c_idx}",
            "clipIndex": c_idx,
            "wrapOpen": [],
            "wrapClose": []
        })

print("-" * 85)
print(f"Total tokens generated for Clips 6-15: {len(new_tokens_6_15)}")
print(f"Minimum token duration: {min_dur*1000:.1f} ms")
print(f"Minimum inter-token gap: {min_gap*1000:.1f} ms")
print(f"Total overlap violations (< 2.0 ms): {total_violations}")
print("=" * 85)

# Save intermediate JSON
out_json_path = os.path.join(BASE_DIR, "output", "tokens_clips_6_15.json")
with open(out_json_path, "w", encoding="utf-8") as f:
    json.dump(new_tokens_6_15, f, indent=2)
print(f"Saved: {out_json_path}")
