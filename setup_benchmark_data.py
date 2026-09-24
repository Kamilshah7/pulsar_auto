import os
import json

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")

manifest_path = os.path.join(OUTPUT_DIR, "bundle_manifest.json")
with open(manifest_path, "r", encoding="utf-8") as f:
    wav_files = json.load(f)

# Sort them based on the standard pattern if needed, but manifest is usually in order.
# Build ordered_clips.json
ordered_clips = []
cur_time = 0.0

import wave
for i, wav_file in enumerate(wav_files):
    wpath = os.path.join(AUDIO_DIR, wav_file)
    with wave.open(wpath, "rb") as wf:
        dur = wf.getnframes() / wf.getframerate()
        
    ordered_clips.append({
        "id": f"clip_{i}",
        "index": i,
        "filename": wav_file,
        "duration_sec": dur,
        "start_sec": cur_time,
        "end_sec": cur_time + dur
    })
    cur_time += dur

with open(os.path.join(OUTPUT_DIR, "ordered_clips.json"), "w", encoding="utf-8") as f:
    json.dump(ordered_clips, f, indent=2)
    
print(f"Generated ordered_clips.json with {len(ordered_clips)} clips.")
