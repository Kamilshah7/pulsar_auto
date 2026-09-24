import json
d = json.load(open('output/full_localstorage.json'))
for k, v in d.items():
    if k.startswith('pulsar_align_clip_'):
        try:
            tokens = json.loads(v)
            if 'tokens' in tokens: tokens = tokens['tokens']
            for t in tokens:
                if 12 <= t['start'] and t['end'] <= 25:
                    print(f"{t['text']}: {t['start']:.3f} - {t['end']:.3f}")
        except Exception as e:
            pass
