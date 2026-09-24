from secrets_loader import get_secret
"""
Transcribe all clips in the current Pulsar task using Groq Whisper-large-v3 with word-level timestamps.
Reads the clip list dynamically from output/ordered_clips.json.
"""
import os
import json
import wave
from groq import Groq

GROQ_API_KEY = get_secret("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

AUDIO_DIR = "f:/BB/ETN-SC/pulsar_auto/audio"
OUTPUT_DIR = "f:/BB/ETN-SC/pulsar_auto/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

clips_file = os.path.join(OUTPUT_DIR, "ordered_clips.json")
if not os.path.exists(clips_file):
    raise FileNotFoundError("ordered_clips.json not found! Run match_clips_wavs.py first.")

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
    else:
        cur_time_sec = max(cur_time_sec, clip.get("end_sec", cur_time_sec))

print(f"Total task duration: {cur_time_sec:.3f}s across {len(CLIPS)} clips.\n")

results = []

for clip in CLIPS:
    idx = clip["index"]
    fname = clip["filename"]
    path = os.path.join(AUDIO_DIR, fname)
    print(f"[{idx+1}/{len(CLIPS)}] Transcribing {fname} ({clip['duration_sec']:.2f}s)...")

    with open(path, "rb") as audio_file:
        resp = client.audio.transcriptions.create(
            file=(fname, audio_file.read()),
            model="whisper-large-v3",
            response_format="verbose_json",
            timestamp_granularities=["word"]
        )

    clip_result = {
        "clip_index": idx,
        "clip_id": clip["id"],
        "filename": fname,
        "global_offset_sec": clip["start_sec"],
        "duration_sec": clip["duration_sec"],
        "full_text": resp.text.strip(),
        "words": resp.words or []
    }
    results.append(clip_result)
    print(f"    Words: {len(clip_result['words'])}, Text: \"{clip_result['full_text'][:70]}...\"")

out_file = os.path.join(OUTPUT_DIR, "groq_transcriptions.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"\nAll {len(CLIPS)} clips transcribed successfully! Saved to {out_file}")
