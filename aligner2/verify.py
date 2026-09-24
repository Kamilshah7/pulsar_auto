"""
System-wide check of one rule change (the user: fix errors one by one, verify no regression after each; listening wins).

A = the current refine.RULES, B = A + --add - --drop. Scored on
  gold:  009, 026 (dev), 049 (held-out: reject only), old14 -- MAE all / H (reviewer-moved), plain gold
  ear:   the listening review (bench/review/*/answers.jsonl) per set: judged junctions where the cut lands on an
         accepted option (<= 5 ms), on a rejected one only, mean distance to the nearest accepted time, and the MAE to
         the user's manual placements. When gold and ear disagree, the ear decides (the user, 2026-09-25).

    python -m aligner2.verify --add P3a
    python -m aligner2.verify --add X --list          # also every boundary / ear item that moved (>= 1 ms)
"""
import argparse
import collections
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from aligner2 import refine as R
from aligner2.benchmark import BENCH, REVIEW_ROUNDS, load_sets
from aligner2.local_bench import CACHE, LEX_CACHE, MAP, V16

SETS = ("009", "026", "049", "old14")


def ear_items():
    """{id: {"acc": [t], "rej": [t], "man": [t]}} over every review round ('disregard' notes skipped)"""
    J = collections.defaultdict(lambda: {"acc": [], "rej": [], "man": []})
    for r in REVIEW_ROUNDS:
        p = os.path.join(BENCH, "review", r, "answers.jsonl")
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            a = json.loads(line)
            if "disregard" in a.get("note", "").lower():
                continue
            for o in a["options"].values():
                (J[a["id"]]["acc"] if o["ok"] else J[a["id"]]["rej"]).append(o["t"])
            if a.get("manual") is not None:
                J[a["id"]]["man"].append(a["manual"])
                J[a["id"]]["acc"].append(a["manual"])
    return dict(J)


def _run_clip(args):
    c, rules_a, rules_b = args
    run = json.load(open(V16)); M = json.load(open(MAP))
    key = f"{c['set']}|{int(c['clip'])}"
    mk = f"{c['set']}_{int(c['clip']):02d}"
    if mk in M:
        zf = np.load(os.path.join(CACHE, M[mk]["npz"]))
    else:                                                  # old14: not in the map, found by its audio key
        from aligner2.signals import clip_key
        zf = np.load(os.path.join(CACHE, clip_key(c["wav"]) + "_98e63a51.npz"))
    z = {k: zf[k] for k in zf.files}
    lexc = json.load(open(LEX_CACHE))
    texts = [t["text"] for t in c["tokens"]]
    lx = lexc.get(key) or R.lexical_peaks(z, texts)
    ar, coarse = run["arpabet"][key], run["grid_preds"][0][key]
    out = []
    for rules in (rules_a, rules_b):
        R.RULES.clear(); R.RULES.update(rules); tr = {}
        out.append((R.refine(z, texts, ar, coarse, tr, lex=lx), tr))
    return c, ar, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", default=""); ap.add_argument("--drop", default="")
    ap.add_argument("--list", action="store_true"); ap.add_argument("--workers", type=int, default=7)
    args = ap.parse_args()
    A = set(R.RULES); B = (A | {x for x in args.add.split(",") if x}) - {x for x in args.drop.split(",") if x}
    clips = load_sets(SETS)
    J = ear_items()
    with ProcessPoolExecutor(args.workers) as ex:
        res = list(ex.map(_run_clip, [(c, A, B) for c in clips]))
    gold = {s: {"A": [], "B": [], "h": []} for s in SETS}
    ear = {s: {v: {"acc": 0, "rej": 0, "dist": [], "man": []} for v in "AB"} for s in SETS}
    moved, ear_moved = [], []
    for c, ar, ((pa, ta), (pb, tb)) in res:
        s, toks = c["set"], c["tokens"]
        for j, g in enumerate(toks):
            for side in ("start", "end"):
                ea, eb = (pa[j][side] - g[side]) * 1000, (pb[j][side] - g[side]) * 1000
                gold[s]["A"].append(ea); gold[s]["B"].append(eb); gold[s]["h"].append(g[f"{side}_human"])
                if abs(ea - eb) >= 1.0:
                    k = j if side == "end" else j - 1
                    moved.append((abs(ea) - abs(eb), f"{s}-{int(c['clip']):02d} j{j:<3} {side:5} {'H' if g[f'{side}_human'] else '.'} "
                                  f"[{g['text']}] A {ea:+5.0f} B {eb:+5.0f}  :: {tb.get(k, '') if k >= 0 else ''}"))
        for k in range(len(toks) - 1):
            iid = f"{s}-{int(c['clip'])}-{k}"
            if iid not in J or not J[iid]["acc"]:
                continue
            it = J[iid]
            cuts = {}
            for v, p in (("A", pa), ("B", pb)):
                t = (p[k]["end"] + p[k + 1]["start"]) / 2
                cuts[v] = t
                na = any(abs(t - x) <= 0.005 for x in it["acc"])
                nr = any(abs(t - x) <= 0.005 for x in it["rej"]) and not na
                E = ear[s][v]; E["acc"] += na; E["rej"] += nr
                E["dist"].append(min(abs(t - x) for x in it["acc"]) * 1000)
                if it["man"]:
                    E["man"].append(abs(t - float(np.median(it["man"]))) * 1000)
            if abs(cuts["A"] - cuts["B"]) >= 0.001:
                da = min(abs(cuts["A"] - x) for x in it["acc"]) * 1000; db = min(abs(cuts["B"] - x) for x in it["acc"]) * 1000
                ear_moved.append((da - db, f"{iid:11} [{toks[k]['text']}|{toks[k + 1]['text']}] dist-to-accepted A {da:5.1f} B {db:5.1f}"))
    print(f"B = A {'+ ' + args.add if args.add else ''}{' - ' + args.drop if args.drop else ''}")
    print(f"{'set':6} {'gold MAE A -> B':>18} {'H A -> B':>16} | {'ear n':>5} {'acc A->B':>9} {'rej A->B':>9} {'dist A->B':>13} {'manual A->B':>13}")
    for s in SETS:
        a = np.abs(gold[s]["A"]); b = np.abs(gold[s]["B"]); h = np.array(gold[s]["h"])
        EA, EB = ear[s]["A"], ear[s]["B"]
        n = len(EA["dist"])
        ear_txt = (f"{n:5} {EA['acc']:4}->{EB['acc']:<4} {EA['rej']:4}->{EB['rej']:<4} {np.mean(EA['dist']):5.1f}->{np.mean(EB['dist']):<5.1f}"
                   f"   {np.mean(EA['man']) if EA['man'] else 0:5.1f}->{np.mean(EB['man']) if EB['man'] else 0:<5.1f}") if n else ""
        print(f"{s:6} {a.mean():7.2f} -> {b.mean():6.2f}  {a[h].mean():6.2f} -> {b[h].mean():5.2f} | {ear_txt}")
    tot = sum(x[0] for x in moved) / 1000
    print(f"gold boundaries moved: {len(moved)}, total gain {tot:+.3f} s; ear items moved: {len(ear_moved)}, "
          f"total dist gain {sum(x[0] for x in ear_moved):+.1f} ms")
    if args.list:
        for d, r in sorted(moved, key=lambda x: x[0]):
            print("  " + r + f"  gain {d:+.0f}")
        for d, r in sorted(ear_moved, key=lambda x: x[0]):
            print("  ear " + r + f"  gain {d:+.1f}")


if __name__ == "__main__":
    main()
