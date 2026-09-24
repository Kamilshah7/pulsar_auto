"""
Compare pre-labeled JSON segments vs Groq Whisper transcription for all 11 clips.
"""
import os
import json

AUDIO_DIR = "f:/BB/ETN-SC/pulsar_auto/audio"
OUTPUT_DIR = "f:/BB/ETN-SC/pulsar_auto/output"

groq_data = json.load(open(os.path.join(OUTPUT_DIR, "groq_transcriptions.json"), encoding="utf-8"))

comparisons = []

for clip in groq_data:
    idx = clip["clip_index"]
    fname = clip["filename"]
    json_name = fname.replace(".wav", ".json")
    json_path = os.path.join(AUDIO_DIR, json_name)
    
    pre_words = []
    if os.path.exists(json_path):
        with open(json_path, encoding="utf-8") as jf:
            jd = json.load(jf)
            pre_words = [s.get("refTranscript", s.get("text", "")) for s in jd.get("segments", [])]
    
    comp = {
        "clip_index": idx,
        "clip_id": clip["clip_id"],
        "filename": fname,
        "pre_label_word_count": len(pre_words),
        "pre_label_text": " ".join(pre_words),
        "groq_word_count": len(clip["words"]),
        "groq_text": clip["full_text"],
        "groq_words_with_timing": [
            {"word": w["word"], "start": round(w["start"], 3), "end": round(w["end"], 3)}
            for w in clip["words"]
        ]
    }
    comparisons.append(comp)

out_path = os.path.join(OUTPUT_DIR, "clip_comparisons.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(comparisons, f, indent=2)

print(f"Comparisons saved to {out_path}")
for c in comparisons:
    print(f"\n--- Clip {c['clip_index']} ({c['filename']}) ---")
    print(f"Pre-label ({c['pre_label_word_count']} words): {c['pre_label_text'][:100]}...")
    print(f"Groq      ({c['groq_word_count']} words): {c['groq_text'][:100]}...")
