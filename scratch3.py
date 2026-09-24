import json
d = json.load(open('golden_labels_current_upto_6.json'))
for t in d['tokens']:
    if t.get('clipIndex', 0) == 0 and 11 <= t['start'] and t['end'] <= 26:
        print(f"{t['text']}: {t['start']:.3f} - {t['end']:.3f}")
