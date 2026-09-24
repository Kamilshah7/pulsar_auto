import json

d = json.load(open('f:/BB/ETN-SC/pulsar_auto/output/clip_tokens.json'))
key = list(d.keys())[0]
tokens = d[key]['tokens']

for cid in ['clip_' + str(i) for i in range(11)]:
    ct = [t for t in tokens if t['clipId'] == cid]
    if ct:
        f = ct[0]
        tid = f['id']
        wav = tid.replace('t_', '').rsplit('_', 1)[0] + '.wav'
        print(f'{cid}: offset={f["start"]:.3f}s, end={ct[-1]["end"]:.3f}s, tokens={len(ct)}, wav={wav}')
