"""
Learn boundary rules against the LISTENER'S EAR instead of editor labels.

Target per reviewed pair = every cut the listener judged acceptable (accepted blind options +
their own hand-placed cut). A predicted cut is a HIT if it lies within TOL_MS of any of them.
(Measured on 769 reviewed pairs: accepted zones span a median 11ms, and 20% of rejected cuts sat
within 10ms of an acceptable one -- the ear's window is about +/-5ms.)

Rules considered: a per-group constant shift of the live output (group = sound class, or leaf).
Leave-one-set-out: fit the shift on two gold sets, score hit rate on the third; bundle_026's
VERIFIED sample is weighted to its population (546/200) so collateral on already-right cuts counts.
A rule is kept only if it raises the hit rate in every fold where it can be scored.
"""
import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_review as AR  # noqa: E402

TOL_MS = 5.0
SHIFTS_MS = np.arange(-60, 31, 1.0)
W = {("026", "verified"): 546 / 200}
SETS = ("026", "049", "old14")


def targets(a):
    t = [o["t"] for o in a["options"].values() if o["ok"]]
    if a["manual"] is not None:
        t.append(a["manual"])
    return t


def hit(pred, a):
    return any(abs(pred - t) * 1000 <= TOL_MS for t in a["_tg"])


def wrate(items, shift_ms):
    num = den = 0.0
    for a in items:
        w = W.get((a["set"], a["kind"]), 1.0)
        num += w * hit(a["live"] + shift_ms / 1000, a); den += w
    return num / den if den else float("nan"), den


def best_shift(items):
    rates = [wrate(items, s)[0] for s in SHIFTS_MS]
    return float(SHIFTS_MS[int(np.nanargmax(rates))])


def run(group_of, label, min_items=12):
    A = [a for a in AR.load() if "disregard" not in a["note"].lower()]
    for a in A:
        a["_tg"] = targets(a)
    A = [a for a in A if a["_tg"]]
    G = collections.defaultdict(list)
    for a in A:
        G[group_of(a)].append(a)
    print(f"\n=== LOSO shift rules by {label} (hit = within {TOL_MS:.0f}ms of a cut you accepted) ===")
    print(f"{'group':<22}{'n':>4} | " + " | ".join(f"{s:^22}" for s in SETS) + " | shift  | 026 verified hit")
    kept = []
    for g, items in sorted(G.items(), key=lambda kv: -len(kv[1])):
        if len(items) < min_items:
            continue
        cells, wins, scored = [], 0, 0
        for s in SETS:
            test = [a for a in items if a["set"] == s]; train = [a for a in items if a["set"] != s]
            if len(test) < 3 or len(train) < 8:
                cells.append(f"{'-':^22}"); continue
            sh = best_shift(train)
            b, n = wrate(test, 0.0); r, _ = wrate(test, sh)
            cells.append(f"{100*b:3.0f}->{100*r:3.0f}% ({sh:+4.0f}ms)")
            scored += 1; wins += r > b
        sh_all = best_shift(items)
        ver = [a for a in items if a["kind"] == "verified"]
        vb, vn = wrate(ver, 0.0); vr, _ = wrate(ver, sh_all)
        ok = scored >= 2 and wins == scored and (not ver or vr >= vb)
        if ok:
            kept.append((g, sh_all))
        vtxt = f"{100*vb:3.0f}->{100*vr:3.0f}% (n={len(ver)})" if ver else "-"
        print(f"{str(g)[:21]:<22}{len(items):>4} | " + " | ".join(cells) + f" | {sh_all:+4.0f}ms | {vtxt}{'   <- KEEP' if ok else ''}")
    return kept


if __name__ == "__main__":
    run(lambda a: a["class"], "SOUND CLASS (w1 coda > w2 onset)")
    run(lambda a: f'{a["branch"]}|{a["leaf_line"]}', "LEAF")
