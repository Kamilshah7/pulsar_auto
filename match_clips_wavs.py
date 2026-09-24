import json
import glob
import wave
import os

clip_list = json.load(open('f:/BB/ETN-SC/pulsar_auto/output/clip_list.json'))
audio_dir = 'f:/BB/ETN-SC/pulsar_auto/audio'
wavs = glob.glob(os.path.join(audio_dir, '*.wav'))

wav_durs = {}
for w in wavs:
    with wave.open(w, 'rb') as wf:
        wav_durs[os.path.basename(w)] = wf.getnframes() / wf.getframerate()

d_tokens = json.load(open('f:/BB/ETN-SC/pulsar_auto/output/clip_tokens.json'))
key = list(d_tokens.keys())[0]
tokens = d_tokens[key]['tokens']

ordered_clips = []
cur_time_sec = 0.0
used_wavs = set()
for c in clip_list:
    idx = c['index']
    toks = [t for t in tokens if t.get('clipIndex') == idx]
    # Extract wav from tokens or match duration
    wav_from_tok = None
    for t in toks:
        tid = t.get('id', '')
        for wname in wav_durs.keys():
            if wname in tid:
                wav_from_tok = wname
                break
        if wav_from_tok:
            break
        import re
        m = re.search(r't_([a-zA-Z0-9_\-\.]+\.wav)', tid) or re.search(r'([a-zA-Z0-9_\-\.]+\.wav)', tid)
        if m and m.group(1) in wav_durs:
            wav_from_tok = m.group(1)
            break
            
    parts = c['time'].split('·')
    dur_target = float(parts[1].strip().replace('s',''))
    
    if not wav_from_tok:
        # Match by duration (strictly unused wavs)
        for wname, wdur in wav_durs.items():
            if wname not in used_wavs and abs(wdur - dur_target) < 0.05:
                wav_from_tok = wname
                break
                
    if wav_from_tok:
        used_wavs.add(wav_from_tok)
                
    actual_dur = wav_durs.get(wav_from_tok, 0)
    wpath = os.path.join(audio_dir, wav_from_tok)
    with wave.open(wpath, 'rb') as wf:
        nframes = wf.getnframes()
        sr = wf.getframerate()
    
    dur_sec = nframes / sr
    dom_start = None
    try:
        t_str = c["time"].split("·")[0].strip()
        t_parts = t_str.split(":")
        if len(t_parts) == 2:
            dom_start = float(t_parts[0]) * 60 + float(t_parts[1])
        elif len(t_parts) == 3:
            dom_start = float(t_parts[0]) * 3600 + float(t_parts[1]) * 60 + float(t_parts[2])
    except Exception:
        pass

    start_sec = dom_start if dom_start is not None else cur_time_sec
    end_sec = start_sec + dur_sec
    cur_time_sec = end_sec

    ordered_clips.append({
        'index': idx,
        'id': f'clip_{idx}',
        'filename': wav_from_tok,
        'duration_sec': dur_sec,
        'start_sec': start_sec,
        'end_sec': end_sec,
        'token_count': len(toks)
    })
    print(f"Clip {idx:02d}: {wav_from_tok} (start={start_sec:.2f}s, dur={dur_sec:.2f}s, tokens={len(toks)})")

with open('f:/BB/ETN-SC/pulsar_auto/output/ordered_clips.json', 'w', encoding='utf-8') as f:
    json.dump(ordered_clips, f, indent=2)

print("\nSaved ordered_clips.json!")
