"""
Gross errors of the full pipeline (v16 coarse + rule stage) on the dev sets, grouped by what surrounds them.
Categories are fixed from the transcript alone (no audio): the token, or a neighbour within one token, is a
filler / a partial word ('s-') / unintelligible '(())' / a spelled letter; else 'other'.

    python -m aligner2.gross                 # dev 009 + 026: share of all error by category
    python -m aligner2.gross --list filler   # the boundaries of one category, worst first
"""
import argparse
import collections
import re

import numpy as np

from aligner2 import refine
from aligner2.benchmark import _kind
from aligner2.local_bench import clip_inputs

FILLERS = {"uh", "um", "uhm", "umm", "hmm", "hm", "mm", "mhm", "er", "erm", "ah", "eh", "oh", "uh-huh"}
LETTERS = set("bcdefghjklmnopqrstuvwxyz")                      # single-letter tokens other than 'a' / 'i'


def tclass(text):
    w = text.strip().lower()
    if w.startswith("((") and w.endswith("))"):
        return "unintel"
    if w.endswith("-"):
        return "partial"
    w = re.sub(r"[^a-z'-]", "", w)
    if w in FILLERS:
        return "filler"
    if len(w) == 1 and w in LETTERS:
        return "letter"
    return None


def category(toks, j):
    """the most specific class among token j and its immediate neighbours"""
    for order in ("unintel", "partial", "letter", "filler"):
        for k in (j, j - 1, j + 1):
            if 0 <= k < len(toks) and tclass(toks[k]["text"]) == order:
                return order
    return "other"


def rows(sets=("009", "026"), audit=False):
    out = []
    data = clip_inputs(sets)
    if audit:
        from aligner2 import gold_audit
        clips, _ = gold_audit.audited(data)
        data = [(cc,) + tuple(d[1:]) for cc, d in zip(clips, data)]
    for c, z, ar, coarse, lx in data:
        toks = c["tokens"]
        new = refine.refine(z, [t["text"] for t in toks], ar, coarse, lex=lx)
        for j, (g, q, v) in enumerate(zip(toks, new, coarse)):
            for side in ("start", "end"):
                out.append(dict(set=c["set"], clip=int(c["clip"]), j=j, text=g["text"], side=side,
                                kind=_kind(toks, j, side), h=g[f"{side}_human"], cat=category(toks, j),
                                err=(q[side] - g[side]) * 1000, err16=(v[side] - g[side]) * 1000,
                                ctx=" ".join(t["text"] for t in toks[max(0, j - 2):j + 3])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--min", type=float, default=80.0)
    ap.add_argument("--sets", default="009,026")
    ap.add_argument("--audit", action="store_true", help="score against the audited gold (aligner2/gold_audit.py)")
    ap.add_argument("--worse", type=float, help="list boundaries the rule stage made worse than v16 by >= this many ms")
    args = ap.parse_args()
    R = rows(tuple(args.sets.split(",")), args.audit)
    tot = sum(abs(r["err"]) for r in R); toth = sum(abs(r["err"]) for r in R if r["h"])
    g = collections.defaultdict(list)
    for r in R:
        g[r["cat"]].append(r)
    print(f"{len(R)} boundaries, total |err| {tot / 1000:.1f} s (H {toth / 1000:.1f} s)")
    print(f"{'category':9} {'n':>5} {'MAE':>6} {'share':>6} {'H share':>8} {'gross n':>8} {'gross share':>12}")
    for cat, rs in sorted(g.items(), key=lambda kv: -sum(abs(r["err"]) for r in kv[1])):
        e = np.array([abs(r["err"]) for r in rs]); eh = sum(abs(r["err"]) for r in rs if r["h"])
        gross = e[e > args.min]
        print(f"{cat:9} {len(rs):5} {e.mean():6.1f} {e.sum() / tot * 100:5.1f}% {eh / toth * 100:7.1f}%"
              f" {len(gross):8} {gross.sum() / tot * 100:11.1f}%")
    ga = [abs(r["err"]) for r in R if abs(r["err"]) > args.min]
    print(f"all gross (> {args.min:.0f} ms): n={len(ga)}, {sum(ga) / tot * 100:.1f}% of the error")
    if args.worse is not None:
        W = sorted((r for r in R if abs(r["err"]) - abs(r["err16"]) >= args.worse),
                   key=lambda r: abs(r["err16"]) - abs(r["err"]))
        lost = sum(abs(r["err"]) - abs(r["err16"]) for r in W)
        print(f"\nrule stage worse than v16 by >= {args.worse:.0f} ms: n={len(W)}, +{lost / 1000:.2f} s")
        for r in W[:args.n]:
            print(f"{r['set']}-{r['clip']:02d} j{r['j']:3} {r['side']:5} {r['kind']:5} {'H' if r['h'] else '.'}"
                  f" err {r['err']:+7.0f} (v16 {r['err16']:+7.0f})  [{r['text']}]  | {r['ctx']}")
    if args.list:
        L = sorted((r for r in R if r["cat"] == args.list and abs(r["err"]) > args.min), key=lambda r: -abs(r["err"]))
        for r in L[:args.n]:
            print(f"{r['set']}-{r['clip']:02d} j{r['j']:3} {r['side']:5} {r['kind']:5} {'H' if r['h'] else '.'}"
                  f" err {r['err']:+7.0f} (v16 {r['err16']:+7.0f})  [{r['text']}]  | {r['ctx']}")


if __name__ == "__main__":
    main()
