"""
One junction k|k+1, read at 2 ms (the case-by-case work: signal first, then the listening review, then the gold).

    python -m aligner2.case 026-5 28                 # current rules
    python -m aligner2.case 026-5 28 --add J1e       # also the cut with a candidate rule (marker X)
    python -m aligner2.case 026-5 28 --ms 80 --step 4

Markers in the table: G gold (e = word k's end, s = word k+1's start), S v16, N refined, X refined with --add,
L word k's last-letter peak, F word k+1's first-letter peak, A / R an option the user accepted / rejected in the
listening review, M the user's manual placement.
"""
import argparse
import os
import sys

from aligner2 import refine as R
from aligner2.verify import _run_clip, ear_items
from aligner2.benchmark import load_sets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip"); ap.add_argument("k", type=int)
    ap.add_argument("--add", default=""); ap.add_argument("--drop", default="")
    ap.add_argument("--ms", type=float, default=50); ap.add_argument("--step", type=int, default=2)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    st, cl = args.clip.split("-")
    c = [c for c in load_sets((st,)) if int(c["clip"]) == int(cl)][0]
    A = set(R.RULES); B = (A | {x for x in args.add.split(",") if x}) - {x for x in args.drop.split(",") if x}
    _, ar, ((pa, ta), (pb, tb)) = _run_clip((c, A, B))
    import json
    from aligner2.local_bench import V16, LEX_CACHE
    coarse = json.load(open(V16))["grid_preds"][0][f"{st}|{int(cl)}"]
    lx = json.load(open(LEX_CACHE)).get(f"{st}|{int(cl)}")
    toks, k = c["tokens"], args.k
    it = ear_items().get(f"{st}-{int(cl)}-{k}", {"acc": [], "rej": [], "man": []})
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench", "tools"))
    import joins
    D = joins.load(f"{st}_{int(cl):02d}")
    marks = [(toks[k]["end"], "G:e"), (toks[k + 1]["start"], "G:s"), (coarse[k]["end"], "S:e"), (coarse[k + 1]["start"], "S:s"),
             (pa[k]["end"], "N:e"), (pa[k + 1]["start"], "N:s")]
    if B != A:
        marks += [(pb[k]["end"], "X:e"), (pb[k + 1]["start"], "X:s")]
    if lx:
        marks += [(lx["last"][k] * R.HOP, "L"), (lx["first"][k + 1] * R.HOP, "F")]
    man = set(round(x, 4) for x in it["man"])
    marks += [(t, "M" if round(t, 4) in man else "A") for t in it["acc"]] + [(t, "R") for t in it["rej"]]
    times = [m[0] for m in marks]
    t0, t1 = min(times) - args.ms / 1000, max(times) + args.ms / 1000
    h = lambda side, j: "H" if toks[j][f"{side}_human"] else ""
    print(f"{args.clip} j{k} [{toks[k]['text']}|{toks[k + 1]['text']}]  {ar[k]} | {ar[k + 1]}")
    print(f"  gold {toks[k]['end']:.3f}{h('end', k)} / {toks[k + 1]['start']:.3f}{h('start', k + 1)}   v16 {coarse[k]['end']:.3f} / "
          f"{coarse[k + 1]['start']:.3f}   refined {pa[k]['end']:.3f} / {pa[k + 1]['start']:.3f}  [{ta.get(k, '')}]")
    if B != A:
        print(f"  with {args.add or ''}{' -' + args.drop if args.drop else ''}: {pb[k]['end']:.3f} / {pb[k + 1]['start']:.3f}  [{tb.get(k, '')}]")
    if it["acc"] or it["rej"]:
        print(f"  ear: accepted {sorted(round(x, 3) for x in it['acc'])}  rejected {sorted(round(x, 3) for x in it['rej'])}  "
              f"manual {sorted(round(x, 3) for x in it['man'])}")
    print(joins.table(D, t0, t1, args.step, marks))


if __name__ == "__main__":
    main()
