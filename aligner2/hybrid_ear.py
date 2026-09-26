"""
Old (forced_aligner, the "live" cut of every review) vs new (aligner2 v25) on the listening review, and the hybrid
question (2026-09-26; the user: "any way we can hybridize the old and new aligner ... especially on the ear test set").

    python -m aligner2.hybrid_ear            # the existing ear data: bias check, direct A/B, hybrid variants
    python -m aligner2.hybrid_ear --round    # score bench/review/confirm_hybrid (bench/build_confirm_hybrid.py)

Caveat on the existing data: the old cut was ALWAYS one of the options heard, the new cut often was not, so distance /
accepted counts favour the old aligner; the direct A/B (both cuts heard) favours the new one a little (its rules were
built on these judgments). The confirm_hybrid round plays both cuts blind where only the old one had been heard.
"""
import argparse
import collections
import json
import os

import numpy as np

from aligner2.benchmark import BENCH, REVIEW_ROUNDS
from aligner2.verify import ear_items

V25 = os.path.join(BENCH, "prov_runs", "aligner2_v25.json")
ROUND = os.path.join(BENCH, "review", "confirm_hybrid")
SETS = ("026", "049", "old14")


def _answers(rounds):
    for r in rounds:
        p = os.path.join(BENCH, "review", r, "answers.jsonl")
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                if line.strip():
                    yield json.loads(line)


def rows():
    """one row per ear item with an accepted time: old (live) cut, new (v25) cut, class, errors (ms)"""
    J, meta = ear_items(), {}
    for a in _answers(REVIEW_ROUNDS):
        meta.setdefault(a["id"], a)
    v25 = json.load(open(V25))["grid_preds"][3]
    out = []
    for i, it in J.items():
        if not it["acc"] or i not in meta:
            continue
        s, c, k = i.split("-")
        p = v25.get(f"{s}|{c}")
        if p is None:
            continue
        k = int(k)
        old, new = meta[i]["live"], (p[k]["end"] + p[k + 1]["start"]) / 2
        e = lambda t: min(abs(t - x) for x in it["acc"]) * 1000
        out.append(dict(id=i, set=s, cls=meta[i].get("class") or "?", old=old, new=new, gap=abs(old - new) * 1000,
                        eo=e(old), en=e(new)))
    return out


def verdicts():
    """{id: [(t, ok)]} every judged option and manual placement ('disregard' notes skipped)"""
    V = collections.defaultdict(list)
    for a in _answers(REVIEW_ROUNDS):
        if "disregard" in a.get("note", "").lower():
            continue
        V[a["id"]] += [(o["t"], o["ok"]) for o in a["options"].values()]
        if a.get("manual") is not None:
            V[a["id"]].append((a["manual"], True))
    return V


def verdict(V, i, t, tol=0.002):
    v = [ok for x, ok in V.get(i, []) if abs(x - t) <= tol]
    return None if not v else sum(v) / len(v) >= 0.5


def existing():
    R, V, J = rows(), verdicts(), ear_items()
    print(f"{len(R)} ear items with an accepted time\n")
    print("1. distance to the nearest accepted time (FAVOURS OLD: its cut was always an option heard)")
    for s in SETS:
        eo, en = (np.array([r[k] for r in R if r["set"] == s]) for k in ("eo", "en"))
        print(f"   {s:6} n={len(eo):3}  MAE old {eo.mean():5.1f}  new {en.mean():5.1f}  best-of-both {np.minimum(eo, en).mean():5.1f} ms")
    print("\n2. both cuts heard directly (an option within 2 ms of each), cuts > 2 ms apart")
    for s in SETS + (None,):
        c = collections.Counter((verdict(V, r["id"], r["old"]), verdict(V, r["id"], r["new"]))
                                for r in R if (s is None or r["set"] == s) and r["gap"] > 2)
        print(f"   {s or 'all':6} only old ok {c[(True, False)]:3}, only new ok {c[(False, True)]:3}, "
              f"both ok {c[(True, True)]:3}, both wrong {c[(False, False)]:3}")
    DH = lambda r: r["cls"].endswith(">dh/th")
    variants = {"new (v25)": lambda r: r["new"], "old": lambda r: r["old"],
                "old at X>dh/th": lambda r: r["old"] if DH(r) else r["new"],
                "old if |old-new| < 20 ms": lambda r: r["old"] if r["gap"] < 20 else r["new"],
                "midpoint if |old-new| < 20 ms": lambda r: (r["old"] + r["new"]) / 2 if r["gap"] < 20 else r["new"]}
    print("\n3. hybrid variants (verify.py ear metrics: lands on accepted / on rejected only, <= 5 ms; distance)")
    for name, f in variants.items():
        cells = []
        for s in SETS:
            acc = rej = 0; d = []
            for r in (r for r in R if r["set"] == s):
                it, t = J[r["id"]], f(r)
                na = any(abs(t - x) <= 0.005 for x in it["acc"])
                acc += na; rej += any(abs(t - x) <= 0.005 for x in it["rej"]) and not na
                d.append(min(abs(t - x) for x in it["acc"]) * 1000)
            cells.append(f"{s} acc {acc:3} rej {rej:3} dist {np.mean(d):5.1f}")
        print(f"   {name:30} " + " | ".join(cells))


def score_round():
    p = os.path.join(ROUND, "answers.jsonl")
    if not os.path.exists(p):
        print(f"no answers yet ({p})")
        return
    prv = json.load(open(os.path.join(ROUND, "items_private.json"), encoding="utf-8"))
    last = {}
    for line in open(p, encoding="utf-8"):
        if line.strip():
            a = json.loads(line)
            last[a["id"]] = a                                   # the latest answer per item counts
    C = collections.defaultdict(collections.Counter)
    for i, a in last.items():
        if "disregard" in a.get("note", "").lower():
            continue
        ok = {cue: o["ok"] for o in a["options"].values() for cue in o["cues"]}
        g = prv[i]["kind"]
        C[(g, prv[i]["set"])][(ok.get("old"), ok.get("new"))] += 1
    print(f"{len(last)} of {len(prv)} items answered\n")
    print(f"{'group':8} {'set':6} | only old ok | only new ok | both ok | both wrong")
    for g in ("dh/th", "stop", "control"):
        for s in SETS:
            c = C[(g, s)]
            print(f"{g:8} {s:6} | {c[(True, False)]:11} | {c[(False, True)]:11} | {c[(True, True)]:7} | {c[(False, False)]:10}")
        w = {s: C[(g, s)][(True, False)] - C[(g, s)][(False, True)] for s in SETS}
        switch = w["026"] > 0 and w["049"] >= 0 and w["old14"] >= 0
        print(f"   -> {g}: old - new wins per set {w}: {'SWITCH to the old cut' if switch else 'keep the new cut'}"
              f"{'' if g != 'control' else ' (control: the general case, not a candidate)'}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", action="store_true")
    args = ap.parse_args()
    score_round() if args.round else existing()
