import json

data = json.load(open("f:/BB/ETN-SC/pulsar_auto/output/groq_transcriptions.json", encoding="utf-8"))
for d in data:
    print(f"=== Clip {d['clip_index']} ({d['filename']}) ===")
    print(f"Text: {d['full_text']}")
    print(f"Word count: {len(d['words'])}")
    sample = " | ".join(f"{w['word']} ({w['start']:.2f}-{w['end']:.2f})" for w in d['words'][:6])
    print(f"First words: {sample}\n")
