"""
Candidate definitions for the END of a word before a pause (dev sets 009 + 026 only), compared with the gold:
MAE / median signed error, all and H (reviewer-moved), per set. The pause-end counterpart of landmark_eval.py.

    python -m aligner2.pause_eval stop        # words ending in a stop
    python -m aligner2.pause_eval fric        # words ending in a fricative / affricate
"""
import argparse
import collections

import numpy as np

from aligner2 import refine as R
from aligner2.local_bench import clip_inputs

HOP, MS = R.HOP, R.MS


def release_end(S, bu, lim, p99, mode):
    """where a released stop's burst / aspiration / affrication dies (index), from its onset bu"""
    resid = S.Ls[bu:min(lim, bu + MS(200))].min()
    j = bu + MS(6)
    if mode == "resid":                                   # the current P1(b): back to the residual + 6 dB, <= 80 ms
        while j < min(lim, bu + MS(80)) and S.Ls[j] >= resid + R.BG_DB:
            j += 1
    elif mode == "resid200":                              # same, the tail may last 200 ms
        while j < min(lim, bu + MS(200)) and S.Ls[j] >= resid + R.BG_DB:
            j += 1
    elif mode == "db40":                                  # the ear convention: until it falls under -40 dB re p99
        while j < min(lim, bu + MS(200)) and (S.Ls[j] >= p99 - 40.0 and S.Ls[j] >= S.floor[j] + 6.0):
            j += 1
    elif mode == "fric":                                  # frication-led: while zcr >= 0.15 and over floor + 6
        while j < min(lim, bu + MS(200)) and ((S.zcr[j] >= 0.15 and S.Ls[j] >= S.floor[j] + 6.0)
                                               or S.Ls[j] >= p99 - 40.0):
            j += 1
    return j


def candidates(S, clip, k, coarse, p99, nxt):
    i_end, lim = int(round(coarse[k]["end"] / HOP)), S.clip(int(round(nxt / HOP)) - MS(10))
    c = {"v16": i_end}
    wpk = S.Ls[int(round(coarse[k]["start"] / HOP)):i_end + 1].max()
    for win in (60, 100, 140):
        for thr_name, trn in (("t3", 3.0), ("t2", 2.0)):
            S_trn = S.trn
            if trn != 3.0:                                # a weaker transient threshold
                S.trn = np.where(S_trn >= trn, np.maximum(S_trn, 3.0), S_trn)
            bu = R.burst_onset(S, i_end, min(lim, i_end + MS(win)), prefer="first")
            S.trn = S_trn
            if bu is None or S.Ls[bu:bu + MS(20)].max() < wpk - 30.0:
                continue
            for mode in ("resid", "resid200", "db40", "fric"):
                c[f"w{win}_{thr_name}_{mode}"] = release_end(S, bu, lim, p99, mode)
    # audibility: the word lasts until its sound falls under the ear threshold (p99 - X dB, and floor + 6 dB); a stop-
    # final word may re-rise out of its closure (<= 100 ms) with its release; never into the next word's letters
    stop_final = R.pclass(R.last_phone(clip["_arpa"][k])) == "stop"
    cap = min(lim, clip["_first"][k + 1] - MS(20)) if k + 1 < len(clip["_first"]) else lim
    for X in (40, 43, 46):
        thr = lambda i: max(p99 - X, S.floor[i] + 6.0)
        j = i_end
        while j < cap:
            if S.Ls[j] >= thr(j):
                j += 1; continue
            if stop_final:                                    # a closure: does the release come back within 100 ms?
                q = j
                while q < min(cap, j + MS(100)) and S.Ls[q] < thr(q):
                    q += 1
                if q < min(cap, j + MS(100)) and q - j <= MS(100) and S.trn[q:q + MS(10)].max() >= 2.0:
                    j = q; continue
            break
        c[f"aud{X}"] = max(i_end, j)
    # R7 for any final phone: a frication tail sounding at / right after the coarse end runs on until it dies
    zr = max(float(np.median(S.zcr[max(0, i_end - MS(20)):i_end])), float(np.median(S.zcr[i_end:i_end + MS(10)])))
    if zr >= 0.25:
        j, low = i_end, S.Ls[i_end]
        while j < min(cap, i_end + MS(200)) and S.zcr[j] >= max(0.15, 0.5 * zr) and S.Ls[j] >= S.floor[j] + 6.0 \
                and S.Ls[j] <= low + 3.0:
            low = min(low, S.Ls[j]); j += 1
        if j > i_end:
            c["fric_run"] = j
    # R6: a smooth voiced / breathy decay continuing from the coarse end ends near -40 dB re p99 (no re-rise, <= 150 ms)
    for X in (38, 40, 43):
        j, low = i_end, S.Ls[i_end]
        while j < min(cap, i_end + MS(150)) and S.Ls[j] >= max(p99 - X, S.floor[j] + 6.0) and S.Ls[j] <= low + 3.0:
            low = min(low, S.Ls[j]); j += 1
        c[f"decay{X}"] = j
    # no release found: a fricated / aspirated tail right after the coarse end
    j = i_end
    while j < min(lim, i_end + MS(200)) and S.zcr[j] >= 0.2 and S.Ls[j] >= S.floor[j] + 6.0:
        j += 1
    if j - i_end >= MS(20):
        c["hiss_tail"] = j
    return c


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cls", choices=("stop", "fric", "nas", "V", "any"))
    ap.add_argument("--top", type=int, default=20); ap.add_argument("--cascade", action="append", default=[])
    args = ap.parse_args()
    res = collections.defaultdict(list); rows = []
    for c, z, ar, coarse, lx in clip_inputs(("009", "026")):
        S = R.Sig(z); p99 = np.percentile(S.L, 99); toks = c["tokens"]
        refined = R.refine(z, [t["text"] for t in toks], ar, coarse, lex=lx)
        for k in range(len(toks) - 1):
            if toks[k + 1]["start"] - toks[k]["end"] <= 0.005:            # gold pause after word k
                continue
            if coarse[k + 1]["start"] - coarse[k]["end"] <= 0.005:          # the coarse stage saw it too
                continue
            cls = R.pclass(R.last_phone(ar[k]))
            if args.cls != "any" and cls != args.cls and not (args.cls == "fric" and cls == "aff"):
                continue
            g = toks[k]["end"]; h = toks[k]["end_human"]
            c["_arpa"], c["_first"] = ar, lx["first"]
            cd = candidates(S, c, k, coarse, p99, coarse[k + 1]["start"])
            cd["refined"] = int(round(refined[k]["end"] / HOP))
            rows.append((c["set"], h, g, cd))
            for name, i in cd.items():
                res[name].append((c["set"], h, (i * HOP - g) * 1000))
    n = len(rows)
    for spec in args.cascade:
        names = spec.split(",")
        for st, h, g, cd in rows:
            i = next((cd[nm] for nm in names if nm in cd), cd["refined"])
            res["CASCADE " + spec].append((st, h, (i * HOP - g) * 1000))
    print(f"{args.cls}-final pause ends (gold and coarse pause): n={n}, H n={sum(r[1] for r in rows)}")
    print(f"{'candidate':22} {'cover':>5} {'MAE':>6} {'med':>6} | {'H MAE':>6} {'H med':>6} | {'009':>6} {'026':>6}")
    keys = sorted(res, key=lambda kk: np.mean(np.abs([x[2] for x in res[kk]])))[:args.top]
    keys += [kk for kk in ("v16", "refined") if kk not in keys] + [kk for kk in res if kk.startswith("CASCADE")]
    for name in keys:
        v = res[name]; e = np.array([x[2] for x in v]); h = np.array([x[1] for x in v]); st = np.array([x[0] for x in v])
        print(f"{name:22} {len(v) / n * 100:4.0f}% {np.abs(e).mean():6.1f} {np.median(e):+6.1f} | "
              f"{np.abs(e[h]).mean() if h.any() else 0:6.1f} {np.median(e[h]) if h.any() else 0:+6.1f} | "
              f"{np.abs(e[st == '009']).mean() if (st == '009').any() else 0:6.1f} "
              f"{np.abs(e[st == '026']).mean() if (st == '026').any() else 0:6.1f}")


if __name__ == "__main__":
    main()
