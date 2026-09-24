import json
try:
    data = json.load(open('output/wav2vec2_acoustic_transcriptions.json'))
    if isinstance(data, list) and len(data) > 0:
        c0 = data[0]
        if isinstance(c0, dict) and 'tokens' in c0:
            c0 = c0['tokens']
        elif isinstance(c0, dict) and 'words' in c0:
            c0 = c0['words']
        for t in c0:
            if isinstance(t, dict):
                if 11 <= t['start'] and t['end'] <= 26:
                    print(f"{t.get('word', t.get('text'))}: {t['start']:.3f} - {t['end']:.3f}")
except Exception as e:
    print(e)
