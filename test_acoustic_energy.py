"""
Diagnostic: Measure speech energy vs Whisper timestamps to detect silence padding.
"""
import wave
import numpy as np
import json
import os

AUDIO_DIR = "f:/BB/ETN-SC/pulsar_auto/audio"
OUTPUT_DIR = "f:/BB/ETN-SC/pulsar_auto/output"

# Find first wav in audio dir
wav_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(".wav")]
if not wav_files:
    print("No wav files found.")
    exit()

target_wav = wav_files[0]
target_path = os.path.join(AUDIO_DIR, target_wav)

with wave.open(target_path, "rb") as wf:
    sr = wf.getframerate()
    n_frames = wf.getnframes()
    raw = wf.readframes(n_frames)
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

print(f"Loaded {target_wav}: sample_rate={sr}, duration={n_frames/sr:.3f}s")

# Check corresponding JSON if available
json_file = target_wav.replace(".wav", ".json")
json_path = os.path.join(AUDIO_DIR, json_file)

if os.path.exists(json_path):
    d = json.load(open(json_path))
    segs = d.get("segments", [])
    print(f"Pre-label segments in {json_file}: {len(segs)}")
    for s in segs[:8]:
        text = s.get("refTranscript", s.get("text", ""))
        st_str = s.get("startTime", "0")
        en_str = s.get("endTime", "0")
        print(f"  [{s.get('segmentId')}] {text:15s} start={st_str} end={en_str}")
