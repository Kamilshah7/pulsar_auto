"""
Landmark lab for the captured golden bundles (aligner2/PERFECTION_WORKFLOW.md step 2): for every junction of a class,
compute candidate acoustic landmarks between the two words' letter peaks and score each against the golden cut --
separately on the junctions the user corrected and those they left alone (both are gold). A landmark worth a rule
matches the corrected ones AND keeps the left-alone ones.

    python -m aligner2.landmark_lab "stop>V"
"""
import collections
import contextlib
import io
import sys

import numpy as np

from aligner2 import cap_bench as CB, refine as R
from aligner2.captures import load_captures
from aligner2.micro_eval import junction_type

H = 0.002


def landmarks(S, pa, pb, ours):
    """candidate cut indices in the window between word k's last-letter peak and word k+1's first-letter peak"""
    a, b = max(1, min(pa, ours) - R.MS(20)), min(S.T - 2, max(pb, ours) + R.MS(20))
    out = {"ours": ours}
    if b - a < 6:
        return out
    m = a + int(np.argmin(S.Ls[a:b]))                                    # the closure / dip minimum
    out["dip minimum"] = m
    for x in (3, 5, 8, 12):
        idx = np.where(S.Ls[m:b] >= S.Ls[m] + x)[0]
        if len(idx):
            out[f"rise +{x} dB from the dip"] = m + int(idx[0])
    top = S.Ls[m:b].max()
    for q in (0.2, 0.35, 0.5):
        idx = np.where(S.Ls[m:b] >= S.Ls[m] + q * (top - S.Ls[m]))[0]
        if len(idx):
            out[f"rise {int(q * 100)}% of dip->peak"] = m + int(idx[0])
    sl = S.slope[m:b]
    if len(sl):
        out["steepest rise after dip"] = m + int(np.argmax(sl))
    bu = R.burst_onset(S, a, b, prefer="max")
    if bu is not None:
        out["burst onset"] = bu
        vo = R.voicing_onset(S, bu, b)
        if vo is not None:
            out["voicing onset (J1)"] = vo
    fr = R.first_rise(S, m, b)
    if fr is not None:
        out["first_rise (halfway)"] = fr
    return out


def main(cls):
    clips = load_captures()
    prep = CB.load_prepared(clips)
    res = CB.run(prep, set(R.RULES))
    score = {"corrected": collections.defaultdict(list), "left alone": collections.defaultdict(list)}
    n = collections.Counter()
    for (c, m, z), (_, _, p, tr) in zip(prep, res):
        texts = m["texts"]
        S = R.Sig(z)
        lex = R.lexical_peaks(z, texts)
        for k in range(len(p) - 1):
            if junction_type(m["arpabet"], k) != cls:
                continue
            g = c["tokens"]
            if g[k + 1]["start"] - g[k]["end"] > 0.010 or p[k + 1]["start"] - p[k]["end"] > 0.005:
                continue                                                  # touching words only
            gold = (g[k]["end"] + g[k + 1]["start"]) / 2
            ours = int(round((p[k]["end"] + p[k + 1]["start"]) / 2 / H))
            grp = "corrected" if (g[k]["end_changed"] or g[k + 1]["start_changed"]) else "left alone"
            n[grp] += 1
            L = landmarks(S, lex["last"][k], lex["first"][k + 1], ours)
            for name, i in L.items():
                score[grp][name].append((i * H - gold) * 1000)
    names = sorted({x for g in score.values() for x in g}, key=lambda x: (x != "ours", x))
    print(f"{cls}: touching junctions -- corrected {n['corrected']}, left alone {n['left alone']}")
    print(f"{'landmark':30} | {'corrected: <=2 / <=5 / <=10 ms, median':40} | {'left alone: <=2 / <=5 ms, median':34}")
    for nm in names:
        parts = []
        for grp in ("corrected", "left alone"):
            e = np.array(score[grp].get(nm, []))
            if len(e):
                a = np.abs(e)
                parts.append(f"{np.mean(a <= 2):4.0%} {np.mean(a <= 5):4.0%} {np.mean(a <= 10):4.0%} {np.median(e):+5.0f} (n {len(e)})")
            else:
                parts.append(" " * 30)
        print(f"{nm:30} | {parts[0]:40} | {parts[1]:34}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "stop>V")
