import zipfile, json, wave, io, os

OUTPUT_DIR = 'f:/BB/ETN-SC/pulsar_auto/output'
AUDIO_DIR = 'f:/BB/ETN-SC/pulsar_auto/audio'

z = zipfile.ZipFile(os.path.join(AUDIO_DIR, 'bundle.zip'), 'r')
wav_names = [n for n in z.namelist() if n.endswith('.wav')]
clip_list = json.load(open(os.path.join(OUTPUT_DIR, 'clip_list.json'), encoding='utf-8'))

print(f"Total clips in DOM: {len(clip_list)}, Total WAVs in bundle.zip: {len(wav_names)}")

for i in range(len(clip_list)):
    c = clip_list[i]
    wname = wav_names[i]
    jname = wname.replace('.wav', '.json')
    
    # Read duration
    wdata = z.read(wname)
    wf = wave.open(io.BytesIO(wdata), 'rb')
    dur = wf.getnframes() / wf.getframerate()
    
    # Read pre-labels
    jdata = json.loads(z.read(jname).decode('utf-8'))
    words = [s.get('refTranscript', s.get('text', '')) for s in jdata.get('segments', [])]
    
    parts = c['time'].split('·')
    dur_target = float(parts[1].strip().replace('s', ''))
    
    match_status = 'PERFECT' if abs(dur - dur_target) < 0.05 else 'MISMATCH'
    print(f"Clip {i:02d} ({c['label']}): {wname[:40]}... | dur={dur:.2f}s vs target={dur_target:.2f}s [{match_status}] | {len(words)} words")
