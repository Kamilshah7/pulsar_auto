"""
EXPERIMENT (2026-09-27; the user: "other ways to simulate the ear than training -- a score that is higher for 'rabbit'
than for 'rabbit-uh'"). Which training-free cue prefers the cut the user ACCEPTED by ear over the one they REJECTED
at the same junction -- above all when the two are only 0-20 ms apart, where the user's micro corrections are?

Cues, all from the cached signals (aligner2/signals.py, 2 ms grid; no GPU): point cues read at the cut (a loudness
dip, spectral change, bursts, glottal pulses, weak voicing, HuBERT's in-context word-gap probability, ...), a
two-sided spectral contrast, and the 10 ms phone detector (charsiu): how well the frames before the cut sound like
word 1's last phone and the frames after it like word 2's first phone. Pairs as in aligner2/listen_eval.py; choices on
026 only, 049 (held out) and old14 are checks.

    python -m aligner2.cue_ear_eval
"""
import json
import os

import numpy as np

from aligner2 import fc_align
from aligner2.benchmark import BENCH
from aligner2.listen_eval import SETS, cuts, judged
from aligner2.verify import CACHE, MAP

HOP = 0.002
GAPS = ((0, 10), (10, 20), (20, 40), (40, 1e9))


def load_z(set_, clip, wav):
    M = json.load(open(MAP)); mk = f"{set_}_{int(clip):02d}"
    if mk in M:
        zf = np.load(os.path.join(CACHE, M[mk]["npz"]))
    else:
        from aligner2.signals import clip_key
        zf = np.load(os.path.join(CACHE, clip_key(wav) + "_98e63a51.npz"))
    return {k: zf[k] for k in zf.files}


def fc_on_grid(z):
    fc = z["fc_logp"].astype(float); T = len(z["t"])
    centres = np.arange(len(fc)) * fc_align.FRAME + fc_align.FRAME_OFF
    g = np.arange(T) * HOP
    return np.stack([np.interp(g, centres, fc[:, j]) for j in range(fc.shape[1])], 1)


def cue_scores(z, fcg, t, ph1, ph2):
    i = int(round(t / HOP)); T = len(z["t"])
    i = min(max(i, 10), T - 11)
    sc = {}
    for name, key, sign in (("loudness dip", "loudness", -1), ("spectral flux", "flux", 1),
                            ("MFCC change", "mfcc_change", 1), ("SSL change", "ssl_change", 1),
                            ("CTC change", "ctc_change", 1), ("burst/transient", "transient", 1),
                            ("glottal pulse", "glottal", 1), ("formant velocity", "formant_vel", 1),
                            ("weak voicing", "periodicity", -1), ("low speech prob", "speech_prob", -1),
                            ("HuBERT word-gap prob", "ctc_wordsep", 1), ("HuBERT blank prob", "ctc_blank", 1)):
        if key in z:
            sc[name] = sign * float(z[key][i])
    m = z["mfcc"].astype(float); w = 10                           # 20 ms each side
    sc["spectral contrast +-20 ms"] = float(np.linalg.norm(m[i:i + w].mean(0) - m[i - w:i].mean(0)))
    if ph1 is not None and ph2 is not None:
        w = 20                                                     # 40 ms each side
        sc["10 ms phone detector"] = float(fcg[max(0, i - w):i, ph1].mean() + fcg[i:i + w, ph2].mean())
    return sc


def main():
    rows = judged()
    arp = json.load(open(os.path.join(BENCH, "prov_runs", "aligner2_v16.json")))["arpabet"]
    v25 = json.load(open(os.path.join(BENCH, "prov_runs", "aligner2_v25.json")))["grid_preds"][3]
    Z, FCG, T = {}, {}, {}
    for rnd, a, pub, prv in rows:
        ck = (prv["set"], int(prv["clip"])); k = int(prv["pair"])
        if ck not in Z:
            Z[ck] = load_z(prv["set"], prv["clip"], prv["wav"]); FCG[ck] = fc_on_grid(Z[ck])
        ar = arp.get(f"{ck[0]}|{ck[1]}")
        p1 = ar[k].split()[-1] if ar and ar[k].strip() else None
        p2 = ar[k + 1].split()[0] if ar and ar[k + 1].strip() else None
        ph1 = fc_align.VOCAB.get(p1) if p1 else None; ph2 = fc_align.VOCAB.get(p2) if p2 else None
        p = v25[f"{ck[0]}|{ck[1]}"]; ours = (p[k]["end"] + p[k + 1]["start"]) / 2
        for t, ok in cuts(a):
            sc = cue_scores(Z[ck], FCG[ck], t, ph1, ph2)
            sc["closer to our cut (baseline)"] = -abs(t - ours)
            T.setdefault(a["id"], []).append((t, ok, sc))
    names = list(dict.fromkeys(n for lst in T.values() for _, _, sc in lst for n in sc))

    def acc(s, f, lo=0, hi=1e9):
        win = tot = 0.0
        for iid, lst in T.items():
            if not iid.startswith(s + "-"):
                continue
            A = [x for x in lst if x[1]]; R = [x for x in lst if not x[1]]
            for ta, _, sa in A:
                for tr, _, sr in R:
                    if lo < abs(ta - tr) * 1000 <= hi:
                        va, vr = f(sa), f(sr)
                        if va is None or vr is None:
                            continue
                        tot += 1; win += 1 if va > vr else .5 if va == vr else 0
        return (win / tot if tot else float("nan")), int(tot)

    print("pairwise accuracy (prefers the cut you accepted over one you rejected; chance 50 %), by how far apart the two "
          "cuts are:  0-10 ms | 10-20 | 20-40 | > 40 | all")
    for s in SETS:
        print(f"\n{s}  (pairs: " + ", ".join(str(acc(s, lambda sc: 0, lo, hi)[1]) for lo, hi in GAPS) + ")")
        for n in names:
            f = lambda sc, n=n: sc.get(n)
            print(f"  {n:30} " + " | ".join(f"{acc(s, f, lo, hi)[0]:5.0%}" for lo, hi in GAPS) + f" | {acc(s, f)[0]:5.1%}")
    # each cue on top of our cut: baseline + w * standardised cue, w chosen on 026
    print("\nour cut + w * cue (w chosen on 026; all pairs): 026 / 049 / old14, best w")
    std = {n: np.std([sc[n] for lst in T.values() for _, _, sc in lst if n in sc]) or 1.0 for n in names}
    base = "closer to our cut (baseline)"
    b = [acc(s, lambda sc: sc[base])[0] for s in SETS]
    print(f"  {'(our cut alone)':30} " + " / ".join(f"{x:.1%}" for x in b))
    for n in names:
        if n == base:
            continue
        best = max((acc("026", lambda sc, w=w: sc[base] + w * sc[n] / std[n] if n in sc else None)[0], w)
                   for w in (0.001, 0.002, 0.004, 0.008, 0.016))
        w = best[1]
        r = [acc(s, lambda sc: sc[base] + w * sc[n] / std[n] if n in sc else None)[0] for s in SETS]
        print(f"  {n:30} " + " / ".join(f"{x:.1%}" for x in r) + f"   (w {w})")


if __name__ == "__main__":
    main()
