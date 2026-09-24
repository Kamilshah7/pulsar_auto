import json, wave, os, zipfile

OUTPUT_DIR = 'f:/BB/ETN-SC/pulsar_auto/output'
AUDIO_DIR = 'f:/BB/ETN-SC/pulsar_auto/audio'

zip_path = os.path.join(AUDIO_DIR, 'bundle.zip')
with zipfile.ZipFile(zip_path, 'r') as zf:
    bundle_wavs = [f for f in zf.namelist() if f.endswith('.wav')]

clip_list = json.load(open(os.path.join(OUTPUT_DIR, 'clip_list.json'), encoding='utf-8'))

for idx, c in enumerate(clip_list):
    parts = c['time'].split('·')
    dur_target = float(parts[1].strip().replace('s', ''))
    matched = bundle_wavs[idx]
    wpath = os.path.join(AUDIO_DIR, matched)
    with wave.open(wpath, 'rb') as wf:
        dur = wf.getnframes() / wf.getframerate()
    jpath = os.path.join(AUDIO_DIR, matched.replace('.wav', '.json'))
    jd = json.load(open(jpath, encoding='utf-8'))
    print(f"Clip {idx} ({c['label']}) -> {matched[:35]}... | dur={dur:.2f}s vs target={dur_target:.2f}s | server words={len(jd.get('segments', []))}")
