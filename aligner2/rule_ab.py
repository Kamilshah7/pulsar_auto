"""
A/B one rule change on the local bench, per junction class: A = the rule set without the change, B = with it.
Continuous and pause joins, all and H (reviewer-moved), and the total gain in seconds of summed error (positive = B better).

    python -m aligner2.rule_ab --drop J13            # A = RULES - J13, B = RULES
    python -m aligner2.rule_ab --add J15             # A = RULES, B = RULES + J15 (a rule written but not enabled)
    python -m aligner2.rule_ab --drop J14 --sets 049 # held-out check (score only; never choose on it)
"""
import argparse
import collections

import numpy as np

from aligner2 import refine as R
from aligner2.local_bench import clip_inputs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", default="", help="rules removed in A (comma-separated)")
    ap.add_argument("--add", default="", help="rules added in B (comma-separated)")
    ap.add_argument("--sets", default="009,026")
    ap.add_argument("--min-gain", type=float, default=0.05, help="only print classes whose gain is >= this (s)")
    args = ap.parse_args()
    drop = {r for r in args.drop.split(",") if r}
    add = {r for r in args.add.split(",") if r}
    full = set(R.RULES)
    data = clip_inputs(tuple(args.sets.split(",")))
    res = collections.defaultdict(lambda: [[], [], []])
    for rules, slot in ((full - drop, 0), (full | add, 1)):
        R.RULES.clear(); R.RULES.update(rules)
        for c, z, ar, coarse, lx in data:
            toks = c["tokens"]
            p = R.refine(z, [t["text"] for t in toks], ar, coarse, lex=lx)
            for k in range(len(toks) - 1):
                cont = toks[k + 1]["start"] - toks[k]["end"] <= 0.005
                A, B = R.last_phone(ar[k]), R.first_phone(ar[k + 1])
                key = (f"{R.pclass(A)}>{'DH' if B == 'DH' else R.pclass(B)}", "cont" if cont else "pause")
                e = abs(p[k]["end"] - toks[k]["end"]) + abs(p[k + 1]["start"] - toks[k + 1]["start"])
                res[key][slot].append(e * 500)                       # mean of the two sides, ms
                if slot == 0:
                    res[key][2].append(toks[k]["end_human"] or toks[k + 1]["start_human"])
    R.RULES.clear(); R.RULES.update(full)
    tot = 0.0
    for key, (a, b, h) in sorted(res.items(), key=lambda kv: -abs(np.sum(kv[1][0]) - np.sum(kv[1][1]))):
        a, b, h = np.array(a), np.array(b), np.array(h, bool)
        d = (a.sum() - b.sum()) / 1000; tot += d
        if abs(d) < args.min_gain:
            continue
        print(f"{key[0]:10} {key[1]:5} n={len(a):4} A {a.mean():5.1f} B {b.mean():5.1f} | H n={h.sum():3} "
              f"A {a[h].mean() if h.any() else 0:5.1f} B {b[h].mean() if h.any() else 0:5.1f} | gain {d:+.2f}s")
    print(f"total gain {tot:+.2f}s")


if __name__ == "__main__":
    main()
