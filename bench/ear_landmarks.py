"""
Landmark rules scored against the listener's ear (bench/review/answers.jsonl).

For every reviewed pair, compute the acoustic landmarks (landmark_search.landmarks: energy dips/
rises at 3/10/20ms, voicing/HF on-offsets, spectral change, burst end, closure start, CTC anchors).
Rule = landmark + offset, optionally GATED: only replace the live cut when the landmark lands
within G ms of it. Offsets are fitted on two gold sets, hit rate scored on the third (hit = within
5ms of a cut the listener accepted). bundle_026's verified sample is weighted to its population.
A rule is kept only if it raises the hit rate in every scorable fold and does not lower it on
verified pairs.
"""
import collections
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_review as AR  # noqa: E402
import ear_rules as ER  # noqa: E402
import landmark_loso as LL  # noqa: E402
import landmark_search as LS  # noqa: E402
import run_gold_bench as RGB  # noqa: E402

GATES_MS = (10, 20, 40, None)
SETS = ("026", "049", "old14")


def load_items():
    rows, gts = {}, {}
    for name, set_dir, rows_p in LL.sets():
        if set_dir:
            RGB.AUDIO_DIRS.insert(0, os.path.join(set_dir, "audio"))
            gts[name] = json.load(open(os.path.join(set_dir, "gt_per_clip.json"), encoding="utf-8"))
        else:
            gts[name] = json.load(open(os.path.join(HERE, "gt_per_clip.json"), encoding="utf-8"))
        for r in json.load(open(rows_p, encoding="utf-8")):
            rows[(name, r["clip"], r["i"])] = r
    A = [a for a in AR.load() if "disregard" not in a["note"].lower()]
    out = []
    for a in A:
        a["_tg"] = ER.targets(a)
        if not a["_tg"]:
            continue
        s, clip, pair = a["id"].split("-", 2)
        r = rows.get((s, clip, int(pair)))
        if r is None or r.get("p_start") is None:
            continue
        a["_lm"] = LS.landmarks(r, LS.feats(RGB.find_wav(gts[s][clip]["filename"])))
        out.append(a)
    return out


def rule(lm, off, gate):
    def f(a):
        if lm not in a["_lm"]:
            return a["live"]
        t = a["_lm"][lm] + off
        return t if gate is None or abs(t - a["live"]) * 1000 <= gate else a["live"]
    return f


def wrate(items, f):
    num = den = 0.0
    for a in items:
        w = ER.W.get((a["set"], a["kind"]), 1.0)
        num += w * ER.hit(f(a), a); den += w
    return num / den if den else float("nan")


def fit_offset(train, lm):
    """offset maximising hit rate on train, searched around the median target-landmark gap"""
    gaps = [min(a["_tg"], key=lambda t: abs(t - a["live"])) - a["_lm"][lm] for a in train if lm in a["_lm"]]
    if len(gaps) < 6:
        return None
    c = float(np.median(gaps)); grid = c + np.arange(-0.030, 0.0301, 0.002)
    return float(grid[int(np.argmax([wrate([a for a in train if lm in a["_lm"]], rule(lm, o, None)) for o in grid]))])


def main(group_of, label, min_items=15):
    items = load_items()
    lms = sorted({k for a in items for k in a["_lm"]} - {"current"})
    G = collections.defaultdict(list)
    for a in items:
        G[group_of(a)].append(a)
    print(f"\n=== ear-target landmark rules by {label} ({len(items)} reviewed pairs) ===")
    kept = []
    for g, I in sorted(G.items(), key=lambda kv: -len(kv[1])):
        if len(I) < min_items:
            continue
        best = None
        for lm in lms:
            for gate in GATES_MS:
                folds, ok = {}, True
                for s in SETS:
                    test = [a for a in I if a["set"] == s]; train = [a for a in I if a["set"] != s]
                    if len(test) < 4 or len(train) < 10:
                        continue
                    off = fit_offset(train, lm)
                    if off is None:
                        ok = False; break
                    b = wrate(test, lambda a: a["live"]); r = wrate(test, rule(lm, off, gate))
                    folds[s] = (b, r)
                    ok &= r > b
                if not ok or len(folds) < 2:
                    continue
                off_all = fit_offset(I, lm)
                ver = [a for a in I if a["kind"] == "verified"]
                vb = wrate(ver, lambda a: a["live"]) if ver else None
                vr = wrate(ver, rule(lm, off_all, gate)) if ver else None
                if ver and vr < vb:
                    continue
                gain = np.mean([r - b for b, r in folds.values()])
                if best is None or gain > best[0]:
                    best = (gain, lm, gate, off_all, folds, vb, vr, len(ver))
        if best:
            gain, lm, gate, off, folds, vb, vr, nv = best
            ft = "  ".join(f"{s}:{100*b:.0f}->{100*r:.0f}%" for s, (b, r) in folds.items())
            vt = f"verified {100*vb:.0f}->{100*vr:.0f}% (n={nv})" if nv else "verified -"
            print(f"  {str(g)[:26]:<27} n={len(I):>3}  {lm}{'' if gate is None else f' gated {gate}ms'} {off*1000:+.1f}ms  | {ft} | {vt}   <- KEEP")
            kept.append((g, lm, gate, off))
        else:
            print(f"  {str(g)[:26]:<27} n={len(I):>3}  (no landmark rule wins every fold)")
    return kept


if __name__ == "__main__":
    main(lambda a: f'{a["branch"]}|{a["leaf_line"]}', "LEAF")
    main(lambda a: a["class"], "SOUND CLASS")
