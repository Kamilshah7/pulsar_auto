import json

with open('output/baseline_ground_truth.json', 'r', encoding='utf-8') as f:
    ref = json.load(f)
with open('output/injected_tokens.json', 'r', encoding='utf-8') as f:
    hyp = json.load(f)

ref_by_clip = {}
for t in ref:
    c_idx = t.get('clipIndex', 0)
    ref_by_clip.setdefault(c_idx, []).append(t)
    
hyp_by_clip = {}
for t in hyp:
    c_idx = t.get('clipIndex', 0)
    hyp_by_clip.setdefault(c_idx, []).append(t)

for c_idx in sorted(ref_by_clip.keys()):
    r_toks = ref_by_clip[c_idx]
    h_toks = hyp_by_clip.get(c_idx, [])
    if len(r_toks) != len(h_toks):
        print(f'Clip {c_idx}: {len(h_toks)} hyp tokens vs {len(r_toks)} ref tokens')
        
    for i, (rt, ht) in enumerate(zip(r_toks, h_toks)):
        rtext = rt.get('text', rt.get('word', '')).strip().lower()
        htext = ht.get('text', ht.get('word', '')).strip().lower()
        if rtext != htext:
            print(f'  [TEXT] Clip {c_idx} Idx {i}: hyp "{htext}" vs ref "{rtext}"')
        else:
            diff_start = abs(rt['start'] - ht['start'])
            diff_end = abs(rt['end'] - ht['end'])
            if diff_start > 0.05 or diff_end > 0.05:
                print(f'  [TIME] Clip {c_idx} Idx {i} ({rtext}): hyp {ht["start"]:.3f}-{ht["end"]:.3f} vs ref {rt["start"]:.3f}-{rt["end"]:.3f} (S_diff: {diff_start*1000:.0f}ms, E_diff: {diff_end*1000:.0f}ms)')
