import json
d = json.load(open('output/injected_tokens.json'))
clip0 = [t for t in d if t['clipIndex']==0]
for t in clip0:
    if 11 <= t['start'] and t['end'] <= 26:
        print(f"{t['text']}: {t['start']:.3f} - {t['end']:.3f}")
