"""
Pick the 15 signals: informative at word boundaries AND not redundant with each other.

Two views of every signal, z-scored per clip:
    level   the signal itself
    change  |x(t + 5 ms) - x(t - 5 ms)| for level signals; the signal itself for signals that
            already measure change (flux, mfcc_change, formant_vel, transient, ctc_change, ssl_change)
Redundancy(i, j) = max(|Spearman rho| on level, on change) over frames of every clip.
Informativeness  = AUC of the change view AT gold boundaries vs 20-60 ms away from any boundary in
                   the same stretch of speech (does the signal move where words meet, more than
                   inside words?). Continuous-speech cuts and pause edges reported separately.
Selection: greedy by AUC, skipping a signal whose redundancy with one already chosen is >= MAX_R.

    python -m aligner2.select_signals
"""
import numpy as np
from scipy.stats import rankdata

from aligner2.benchmark import CONT_MAX_GAP_MS, load_sets
from aligner2.signals import HOP, NAMES, compute

CHANGE_TYPE = {"flux", "mfcc_change", "formant_vel", "transient", "ctc_change", "ssl_change"}
MAX_R = 0.70
N_PICK = 15
OFFS_MS = (20, 30, 40, 50, 60)


def views(z):
    lev, chg = {}, {}
    for n in NAMES:
        x = z[n].astype(float)
        zs = lambda v: (v - v.mean()) / (v.std() + 1e-9)
        lev[n] = zs(x)
        if n in CHANGE_TYPE:
            chg[n] = zs(x)
        else:
            d = np.zeros_like(x); d[5:-5] = np.abs(x[10:] - x[:-10]); chg[n] = zs(d)
    return lev, chg


def auc(pos, neg):
    pos, neg = np.asarray(pos), np.asarray(neg)
    r = rankdata(np.r_[pos, neg])
    return (r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def main():
    C = load_sets()
    L = {n: [] for n in NAMES}; D = {n: [] for n in NAMES}
    pos = {k: {n: [] for n in NAMES} for k in ("cont", "pause")}
    neg = {k: {n: [] for n in NAMES} for k in ("cont", "pause")}
    for c in C:
        z = compute(c["wav"]); lev, chg = views(z)
        for n in NAMES:
            L[n].append(lev[n][::5]); D[n].append(chg[n][::5])
        T = len(z["t"]); toks = c["tokens"]
        bpts = []
        for j in range(len(toks) - 1):
            gap = (toks[j + 1]["start"] - toks[j]["end"]) * 1000
            if gap <= CONT_MAX_GAP_MS:
                bpts.append(("cont", (toks[j]["end"] + toks[j + 1]["start"]) / 2))
            else:
                bpts += [("pause", toks[j]["end"]), ("pause", toks[j + 1]["start"])]
        allb = np.array([t for _, t in bpts])
        for kind, t in bpts:
            b = int(round(t / HOP))
            if not 0 <= b < T:
                continue
            for n in NAMES:
                pos[kind][n].append(chg[n][b])
            for o in OFFS_MS:
                for sgn in (-1, 1):
                    tt = t + sgn * o / 1000
                    k = int(round(tt / HOP))
                    if 0 <= k < T and np.min(np.abs(allb - tt)) > 0.015:
                        for n in NAMES:
                            neg[kind][n].append(chg[n][k])
    L = {n: np.concatenate(v) for n, v in L.items()}; D = {n: np.concatenate(v) for n, v in D.items()}
    RL = {n: rankdata(v) for n, v in L.items()}; RD = {n: rankdata(v) for n, v in D.items()}
    corr = lambda a, b: abs(np.corrcoef(a, b)[0, 1])
    R = {(a, b): max(corr(RL[a], RL[b]), corr(RD[a], RD[b])) for a in NAMES for b in NAMES if a != b}
    A = {n: {k: auc(pos[k][n], neg[k][n]) for k in ("cont", "pause")} for n in NAMES}
    ncont, npause = len(pos["cont"][NAMES[0]]), len(pos["pause"][NAMES[0]])
    score = {n: (ncont * A[n]["cont"] + npause * A[n]["pause"]) / (ncont + npause) for n in NAMES}

    print(f"{len(C)} clips, {ncont} continuous cuts, {npause} pause edges\n")
    print(f"{'signal':<13}{'AUC cont':>9}{'AUC pause':>10}{'AUC all':>8}   most similar (rho)")
    for n in sorted(NAMES, key=lambda n: -score[n]):
        m = max((b for b in NAMES if b != n), key=lambda b: R[(n, b)])
        print(f"{n:<13}{A[n]['cont']:>9.3f}{A[n]['pause']:>10.3f}{score[n]:>8.3f}   {m} ({R[(n, m)]:.2f})")
    picked, skipped = [], []
    for n in sorted(NAMES, key=lambda n: -score[n]):
        clash = [p for p in picked if R[(n, p)] >= MAX_R]
        (skipped.append((n, clash[0], R[(n, clash[0])])) if clash else picked.append(n))
    print(f"\nSELECTED ({min(len(picked), N_PICK)} of {len(NAMES)}), max pairwise redundancy < {MAX_R}:")
    for i, n in enumerate(picked[:N_PICK], 1):
        others = [p for p in picked[:N_PICK] if p != n]
        m = max(others, key=lambda b: R[(n, b)])
        print(f"  {i:>2}. {n:<13} AUC {score[n]:.3f}   closest selected: {m} ({R[(n, m)]:.2f})")
    for n, p, r in skipped:
        print(f"  dropped {n:<13} redundant with {p} ({r:.2f})")
    for n in picked[N_PICK:]:
        print(f"  dropped {n:<13} (least informative after the first {N_PICK})")
    print("\nredundancy matrix (selected):")
    sel = picked[:N_PICK]
    print(" " * 13 + "".join(f"{s[:5]:>6}" for s in sel))
    for a in sel:
        print(f"{a:<13}" + "".join(f"{'--' if a == b else f'{R[(a, b)]:.2f}':>6}" for b in sel))


if __name__ == "__main__":
    main()
