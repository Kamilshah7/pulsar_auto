import json
d = json.load(open('output/clip_tokens.json'))
clip0_key = list(d.keys())[0]
clip0 = d[clip0_key]['tokens']
for t in clip0:
    if 11 <= t['start'] and t['end'] <= 26:
        print(f"{t['text']}: {t['start']:.3f} - {t['end']:.3f}")
