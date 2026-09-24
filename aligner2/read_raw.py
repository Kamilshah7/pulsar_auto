"""Render raw boundary traces as text (one digit per 4 ms, 0 = row min .. 9 = row max, '|' = gold)."""
import json
import sys

import numpy as np

z = np.load("bench/cache/aligner2/raw_dump.npz"); X, names = z["X"], list(z["names"])
M = json.load(open("bench/cache/aligner2/raw_dump_meta.json", encoding="utf-8"))
ix = {n: i for i, n in enumerate(names)}
ROWS = ["loudness", "periodicity", "flatness", "centroid", "low_ratio", "transient", "formant_vel", "ctc_wordsep"]
COLS = list(range(20, 81, 2))   # -60..+60 ms in 4 ms steps; index 50 = gold


def render(i):
    m = M[i]
    ear = ""
    if m.get("ear_acc"):
        ear = "  ear-ok at " + ",".join(f"{(t - m['t']) * 1000:+.0f}" for t in sorted(set(round(a, 4) for a in m["ear_acc"])))
    out = [f"#{i} {m['set']}-{m['clip']}-{m['pair']} {m['kind']:<11} '{m['w1']}|{m['w2']}' ({m['coda']}>{m['onset']}) "
           f"{'HUMAN' if m['human'] else 'kept'}{ear}"]
    for n in ROWS:
        v = X[i, ix[n], COLS].astype(float)
        q = np.clip(((v - v.min()) / (v.max() - v.min() + 1e-12) * 9.999).astype(int), 0, 9)
        s = "".join(str(d) for d in q)
        s = s[:15] + "|" + s[15:]
        lo, hi = v.min(), v.max()
        out.append(f"   {n:<12}{s}   [{lo:.2f} .. {hi:.2f}]")
    return "\n".join(out)


if __name__ == "__main__":
    kind, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    only_human = len(sys.argv) > 4 and sys.argv[4] == "human"
    idx = [i for i, m in enumerate(M) if m["kind"] == kind and (m["human"] or not only_human)]
    rng = np.random.default_rng(seed)
    print(f"-60ms{' ' * 10}gold{' ' * 10}+60ms   ({len(idx)} {kind} points{' (human-placed)' if only_human else ''}, showing {n})")
    for i in sorted(rng.choice(idx, min(n, len(idx)), replace=False)):
        print(render(i))
