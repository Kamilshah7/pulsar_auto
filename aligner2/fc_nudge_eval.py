"""
Scores aligner2/fc_nudge.py the way aligner2/verify.py scores a rule: A = the current rule stage (refine.RULES),
B = A + the nudge; gold MAE all / H per set and the listening review per set (accepted / rejected / distance to
the nearest accepted cut / MAE to the user's manual cuts). Settings are chosen on 009 + 026 (ear: 026); 049 is
held out (reject only), old14 a check.

    python -m aligner2.fc_nudge_eval                     # the settings grid (A computed once, cached)
    python -m aligner2.fc_nudge_eval --only 0.020,0.004,0.040,1 --list
"""
import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from aligner2 import fc_nudge
from aligner2 import refine as R
from aligner2.benchmark import BENCH, load_sets
from aligner2.cue_ear_eval import load_z
from aligner2.verify import SETS, _run_clip, ear_items

BASE = os.path.join(BENCH, "cache", "aligner2", "fc_nudge_base.json")


def base_preds(clips):
    """the current rule stage's output per clip (+ ARPAbet), cached by the rule set"""
    rules = sorted(R.RULES)
    if os.path.exists(BASE):
        d = json.load(open(BASE))
        if d["rules"] == rules and all(f"{c['set']}|{c['clip']}" in d["preds"] for c in clips):
            return d["preds"], d["arpa"]
    A = set(R.RULES)
    with ProcessPoolExecutor(7) as ex:
        res = list(ex.map(_run_clip, [(c, A, A) for c in clips]))
    preds = {f"{c['set']}|{c['clip']}": pa for c, ar, ((pa, _), _) in res}
    arpa = {f"{c['set']}|{c['clip']}": ar for c, ar, _ in res}
    json.dump({"rules": rules, "preds": preds, "arpa": arpa}, open(BASE, "w"))
    return preds, arpa


def score(P, clips, J):
    out = {}
    for s in SETS:
        e, h, acc, rej, dist, man = [], [], 0, 0, [], []
        for c in [c for c in clips if c["set"] == s]:
            p, toks = P[f"{s}|{c['clip']}"], c["tokens"]
            for j, g in enumerate(toks):
                for side in ("start", "end"):
                    d = abs(p[j][side] - g[side]) * 1000; e.append(d)
                    if g[f"{side}_human"]:
                        h.append(d)
            for k in range(len(toks) - 1):
                it = J.get(f"{s}-{int(c['clip'])}-{k}")
                if not it or not it["acc"]:
                    continue
                t = (p[k]["end"] + p[k + 1]["start"]) / 2
                na = any(abs(t - x) <= 0.005 for x in it["acc"])
                acc += na; rej += any(abs(t - x) <= 0.005 for x in it["rej"]) and not na
                dist.append(min(abs(t - x) for x in it["acc"]) * 1000)
                if it["man"]:
                    man.append(abs(t - float(np.median(it["man"]))) * 1000)
        out[s] = dict(mae=np.mean(e), h=np.mean(h), acc=acc, rej=rej, n=len(dist),
                      dist=np.mean(dist) if dist else np.nan, man=np.mean(man) if man else np.nan)
    return out


def line(tag, sA, sB):
    parts = []
    for s in SETS:
        a, b = sA[s], sB[s]
        t = f"{s} {b['mae'] - a['mae']:+.2f}/{b['h'] - a['h']:+.2f}"
        if a["n"]:
            t += f" ear {b['acc'] - a['acc']:+d}/{b['rej'] - a['rej']:+d} d{b['dist'] - a['dist']:+.1f} m{b['man'] - a['man']:+.1f}"
        parts.append(t)
    return f"{tag:24} " + " | ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=""); ap.add_argument("--list", action="store_true")
    ap.add_argument("--wide", action="store_true")
    args = ap.parse_args()
    clips = load_sets(SETS); J = ear_items()
    base, arpa = base_preds(clips)
    Z = {}
    for c in clips:
        k = f"{c['set']}|{c['clip']}"
        z = load_z(c["set"], c["clip"], c["wav"]); Z[k] = (z, fc_nudge.fc_on_grid(z))
    sA = score(base, clips, J)
    print("A = the current rule stage: " + " | ".join(
        f"{s} MAE {sA[s]['mae']:.2f} H {sA[s]['h']:.2f}" + (f" ear acc {sA[s]['acc']} rej {sA[s]['rej']} dist {sA[s]['dist']:.1f} man {sA[s]['man']:.1f}" if sA[s]["n"] else "")
        for s in SETS))
    print("B - A per set: gold MAE all/H (ms, lower = better) | ear accepted/rejected (+/-), mean distance to an "
          "accepted cut (d), MAE to your manual cuts (m)")
    if args.only:
        r, tau, w, cw = args.only.split(","); grid = [(float(r), float(tau), float(w), cw == "1")]
    else:
        grid = [(r, tau, w, cw) for r in (0.010, 0.020) for tau in (0.002, 0.004, 0.008, 0.016)
                for w in (0.020, 0.040) for cw in (True, False)]
        if args.wide:                                   # round 2: larger radius / stronger evidence weight
            grid = [(r, tau, w, True) for r in (0.020, 0.030, 0.040) for tau in (0.016, 0.032, 0.064) for w in (0.020, 0.040)]
    for r, tau, w, cw in grid:
        P, moves = {}, []
        for c in clips:
            k = f"{c['set']}|{c['clip']}"; z, g = Z[k]
            P[k] = fc_nudge.nudge(z, base[k], arpa[k], radius=r, tau=tau, win=w, clip_to_words=cw, fcg=g)
            moves += [abs(a["end"] - b["end"]) * 1000 for a, b in zip(base[k][:-1], P[k][:-1]) if abs(a["end"] - b["end"]) >= 0.001]
        mv = np.array(moves) if moves else np.zeros(1)
        print(line(f"r{r * 1000:.0f} tau{tau * 1000:.0f} w{w * 1000:.0f} {'clip' if cw else 'free'}", sA, score(P, clips, J))
              + f" || moved {len(moves)} (median {np.median(mv):.0f} ms)", flush=True)
        if args.list:
            for c in clips:
                k = f"{c['set']}|{c['clip']}"; toks = c["tokens"]
                for j in range(len(toks) - 1):
                    a, b = base[k][j]["end"], P[k][j]["end"]
                    if abs(a - b) >= 0.001:
                        g = toks[j]["end"]
                        print(f"   {c['set']}-{int(c['clip']):02d} [{toks[j]['text']}|{toks[j + 1]['text']}] "
                              f"move {(b - a) * 1000:+.0f} ms, gold err {(a - g) * 1000:+.0f} -> {(b - g) * 1000:+.0f}")


if __name__ == "__main__":
    main()
