import json, os, wave
from reconciler import AcousticReconciler
from vad_trimmer import VadTrimmer
from pipeline import pipeline as p

OUTPUT_DIR = 'f:/BB/ETN-SC/pulsar_auto/output'
AUDIO_DIR = 'f:/BB/ETN-SC/pulsar_auto/audio'

# 1. Ensure ordered_clips is correct
clips = json.load(open(os.path.join(OUTPUT_DIR, 'ordered_clips.json'), encoding='utf-8'))
clip3_info = [c for c in clips if c['index'] == 3][0]
print(f"Clip 3 file: {clip3_info['filename']} (start={clip3_info['start_sec']}, dur={clip3_info['duration_sec']})")

# 2. Get Groq Whisper words for Clip 3
groq_data = json.load(open(os.path.join(OUTPUT_DIR, 'groq_transcriptions.json'), encoding='utf-8'))
g3 = [g for g in groq_data if g['clip_index'] == 3][0]

# 3. Load pre-labels for Clip 3
jpath = os.path.join(AUDIO_DIR, clip3_info['filename'].replace('.wav', '.json'))
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

# 4. Reconcile with acoustic engine
wpath = os.path.join(AUDIO_DIR, clip3_info['filename'])
trimmer = VadTrimmer(wpath)
reconciler = AcousticReconciler(trimmer)
reconciled, stats = reconciler.reconcile_clip(pre_segs, g3.get('words', []), clip3_info['duration_sec'])

print(f"Reconciled Clip 3: {len(reconciled)} tokens. Shaved {stats.get('silence_trimmed_ms', 0):.1f}ms silence.")

# Format as LLM corrected tokens format
clip3_llm_tokens = []
for t in reconciled:
    clip3_llm_tokens.append({
        "text": t["text"].lower().strip(".,!?:;\"'()"),
        "start": round(float(t["start"]), 3),
        "end": round(float(t["end"]), 3)
    })

# Clean up contractions and hyphens per rules
for t in clip3_llm_tokens:
    if t["text"] in ["didnt", "dont", "cant", "wont"]:
        t["text"] = t["text"][:-2] + "'t"
    elif t["text"] in ["youve", "theyve", "weve"]:
        t["text"] = t["text"][:-2] + "'ve"
    elif t["text"] in ["youre", "theyre", "were"] and t["text"] != "were":
        t["text"] = t["text"][:-2] + "'re"

# 5. Update llm_corrected_tokens.json
llm_file = os.path.join(OUTPUT_DIR, 'llm_corrected_tokens.json')
llm_data = json.load(open(llm_file, encoding='utf-8'))
llm_data['3'] = clip3_llm_tokens

with open(llm_file, 'w', encoding='utf-8') as f:
    json.dump(llm_data, f, indent=2)

print("Updated key '3' in llm_corrected_tokens.json!")

# 6. Run pipeline generator to rebuild inject_console.js and injected_tokens.json
js_code = p.process_llm_output_and_generate_injection(json.dumps(llm_data))
print(f"Successfully generated inject_console.js ({len(js_code)} bytes)!")
