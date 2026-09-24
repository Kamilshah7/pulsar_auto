"""
Where do reviewers put a junction of a given class pair, relative to candidate landmark definitions?
Dev sets only (009 + 026). For each continuous gold join of the pair, candidates are computed inside the
lexical region (word k's last-letter peak .. word k+1's first-letter peak, +-10 ms) and compared with the
gold: MAE and median signed error, all / H (reviewer-moved) / per set. Used to CHOOSE among a few
principled definitions (no fitted parameters).

    python -m aligner2.landmark_eval "V>fric"
"""
import argparse
import collections

import numpy as np

from aligner2 import refine as R
from aligner2.local_bench import clip_inputs

HOP, MS = R.HOP, R.MS


def transition_marks(S, pa, pb, feats=R.FEATS):
    """progress of the joint change from the 10 ms around pa (phone A) to the 10 ms around pb (phone B):
    the frames where it reaches 0.2 / 0.5 / 0.8"""
    if pb - pa < MS(12):
        return {}
    ra, rb = (pa - MS(5), pa + MS(5)), (pb - MS(5), pb + MS(5))
    p = R.progress(S, pa, pb, ra, rb, feats)
    out = {}
    for q in (0.2, 0.5, 0.8):
        i = R.crossing(p, q)
        if i is not None:
            out[f"prog{int(q * 100)}"] = pa + i
    return out


def candidates(S, pa, pb, cut, pair):
    a, b = S.clip(min(pa, cut) - MS(10)), S.clip(max(pb, cut) + MS(10))
    c = {"v16": cut, "mid_peaks": (pa + pb) // 2}
    c.update(transition_marks(S, pa, pb))
    for name, feats in (("zh", ("zcr", "hi")), ("z", ("zcr",)), ("lo_cent", ("lo", "cent")), ("loud", ("Ls",))):
        for q, i in transition_marks(S, pa, pb, feats).items():
            c[f"{name}_{q}"] = i
    cA, cB = pair.split(">")
    if "?" in (cA, cB):
        return c
    for q in (0.2, 0.5, 0.8):
        for name, feats in (("self", None), ("self_zh", ("zcr", "hi")), ("self_z", ("zcr",)), ("self_loud", ("Ls",)),
                            ("self_lo", ("lo", "cent"))):
            i = R.transition(S, cA, cB, a, cut, b, q, feats)
            if i is not None:
                c[f"{name}{int(q * 100)}"] = i
    m = R.loud_min(S, a, b)
    if m is not None:
        c["loud_min"] = m
    hm = a + int(np.argmin(S.hi[a:b])) if b > a else None
    if hm is not None:
        c["hi_min"] = hm
    bu = R.burst_onset(S, a, b, prefer="last")
    if bu is not None:
        c["burst_last"] = bu
    for cdb in (6.0, 10.0):
        at = R.burst_onset(S, a, b, prefer="max", closure_db=cdb)
        if at is not None:
            c[f"attack{int(cdb)}"] = at
    if cB in ("stop", "aff"):
        bm = R.burst_onset(S, a, b, prefer="max")
        if bm is not None:
            c["burst_max"] = bm
            off = closure_onset(S, pa, bm, a)
            if off is not None:
                c["clos_on"] = off
                c["clos_mid"] = (off + bm) // 2
    return c


def mfcc_marks(z, S, pa, pb, a, b):
    """spectral-envelope candidates: progress in MFCC space (c1..c12) from the 10 ms around pa to the 10 ms
    around pb (distance ratio d_A / (d_A + d_B), 6 ms smoothed); the steepest MFCC / formant change"""
    out = {}
    if pb - pa < MS(12) or b - a < 3:
        return out
    M = z["mfcc"][:, 1:].astype(float)
    mA = np.median(M[pa - MS(5):pa + MS(5)], 0); mB = np.median(M[pb - MS(5):pb + MS(5)], 0)
    Ms = np.column_stack([R._box(M[:, j], 3) for j in range(M.shape[1])])
    dA = np.linalg.norm(Ms[pa:pb] - mA, axis=1); dB = np.linalg.norm(Ms[pa:pb] - mB, axis=1)
    p = dA / (dA + dB + 1e-9)
    for q in (0.2, 0.35, 0.5, 0.65, 0.8):
        i = R.crossing(p, q)
        if i is not None:
            out[f"mfcc{int(q * 100)}"] = pa + i
    out["mfcc_vel"] = a + int(np.argmax(R._box(z["mfcc_change"][a:b].astype(float), 3)))
    out["fvel"] = a + int(np.argmax(R._box(z["formant_vel"][a:b].astype(float), 3)))
    return out


def closure_onset(S, pa, bu, a):
    """where the loudness falls halfway (in dB) from the sound before the closure to the closure minimum"""
    lo = S.clip(min(pa, bu - MS(10)))
    if bu - lo < 3:
        return None
    mi = lo + int(np.argmin(S.Ls[lo:bu]))
    va = S.Ls[S.clip(min(pa, mi) - MS(30)):S.clip(min(pa, mi) + MS(10))].max()
    m = S.Ls[mi]
    off = mi
    while off > a and S.Ls[off] < m + (va - m) / 2:
        off -= 1
    return off


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pair"); ap.add_argument("--cascade", action="append", default=[])
    ap.add_argument("--top", type=int, default=15); ap.add_argument("--b-phone"); ap.add_argument("--a-phone")
    args = ap.parse_args()
    res = collections.defaultdict(list); rows = []
    for c, z, ar, coarse, lx in clip_inputs(("009", "026")):
        S = R.Sig(z); toks = c["tokens"]
        for k in range(len(toks) - 1):
            if toks[k + 1]["start"] - toks[k]["end"] > 0.005:
                continue
            pair = f"{R.pclass(R.last_phone(ar[k]))}>{R.pclass(R.first_phone(ar[k + 1]))}"
            if args.pair != "*" and pair != args.pair:
                continue
            if args.b_phone and R.first_phone(ar[k + 1]) != args.b_phone:
                continue
            if args.a_phone and R.last_phone(ar[k]) != args.a_phone:
                continue
            g = (toks[k]["end"] + toks[k + 1]["start"]) / 2
            cut = int(round((coarse[k]["end"] + coarse[k + 1]["start"]) / 2 / HOP))
            h = toks[k]["end_human"] or toks[k + 1]["start_human"]
            cd = candidates(S, lx["last"][k], lx["first"][k + 1], cut, pair)
            a_, b_ = S.clip(min(lx["last"][k], cut) - MS(10)), S.clip(max(lx["first"][k + 1], cut) + MS(10))
            mid = (lx["last"][k] + lx["first"][k + 1]) // 2
            for r in (10, 20):
                w0, w1 = S.clip(mid - MS(r)), S.clip(mid + MS(r))
                if w1 > w0 + 2:
                    cd[f"mid_loudmin{r}"] = w0 + int(np.argmin(S.Ls[w0:w1]))
                    cd[f"mid_himin{r}"] = w0 + int(np.argmin(S.hi[w0:w1]))
                    cd[f"mid_glo{r}"] = w0 + int(np.argmax(S.glottal[w0:w1]))
            pa_, pb_ = lx["last"][k], lx["first"][k + 1]
            if pb_ > pa_:
                # the closure precedes word k+1's first-letter peak: from 20 ms before the letter midpoint up to it
                w0, w1 = S.clip(mid - MS(20)), S.clip(max(pb_, mid + MS(20)))
                cd["mid_to_b_loudmin"] = w0 + int(np.argmin(S.Ls[w0:w1]))
                # the +-20 ms window only when it holds a real dip (>= 6 dB under the louder of its edges' 10 ms)
                v0, v1 = S.clip(mid - MS(20)), S.clip(mid + MS(20))
                wm = v0 + int(np.argmin(S.Ls[v0:v1]))
                edge = max(S.Ls[S.clip(v0 - MS(10)):v0 + 1].max(), S.Ls[v1:S.clip(v1 + MS(10)) + 1].max())
                cd["mid20_guard"] = wm if edge - S.Ls[wm] >= 6.0 else cd["mid_to_b_loudmin"]
                # no closure in the window = its quietest frame is still within 10 dB of the loudest frame between
                # the two letter peaks (e.g. inside a spelled letter's vowel) -> extend up to word k+1's first letter
                top = S.Ls[S.clip(pa_):S.clip(pb_) + 1].max()
                cd["mid20_vguard"] = wm if top - S.Ls[wm] >= 10.0 else cd["mid_to_b_loudmin"]
            cd.update(mfcc_marks(z, S, lx["last"][k], lx["first"][k + 1], a_, b_))
            if b_ > a_ + 2:
                cd["hi_min_region"] = a_ + int(np.argmin(S.hi[a_:b_]))
                lm = a_ + int(np.argmin(S.Ls[a_:b_]))
                cd["loud_min_region"] = lm
            rows.append((c["set"], h, g, cd))
            for name, i in cd.items():
                res[name].append((c["set"], h, (i * HOP - g) * 1000))
    n = len(res["v16"])
    print(f"{args.pair}: n={n}")
    print(f"{'candidate':14} {'cover':>5} {'MAE':>6} {'med':>6} | {'H MAE':>6} {'H med':>6} | {'009':>6} {'026':>6}")
    for spec in args.cascade:
        names = spec.split(",")
        for st, h, g, cd in rows:
            i = next((cd[nm] for nm in names if nm in cd), cd["v16"])
            res["CASCADE " + spec].append((st, h, (i * HOP - g) * 1000))
    for name, v in sorted(res.items(), key=lambda kv: np.mean(np.abs([x[2] for x in kv[1]])))[:args.top] + \
            [kv for kv in res.items() if kv[0] == "v16" or kv[0].startswith("CASCADE")]:
        e = np.array([x[2] for x in v]); h = np.array([x[1] for x in v]); st = np.array([x[0] for x in v])
        print(f"{name:14} {len(v) / n * 100:4.0f}% {np.abs(e).mean():6.1f} {np.median(e):+6.1f} | "
              f"{np.abs(e[h]).mean() if h.any() else 0:6.1f} {np.median(e[h]) if h.any() else 0:+6.1f} | "
              f"{np.abs(e[st == '009']).mean():6.1f} {np.abs(e[st == '026']).mean():6.1f}")


if __name__ == "__main__":
    main()
