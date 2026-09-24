"""
End-to-end A/B of a COARSE-stage change, locally on the CPU (aligner2/local_coarse.py): for every clip of the given
sets, B = coarse stage with the change -> letter peaks recomputed -> rule stage -> scored; A = the current pipeline
(the stored v16 run + cached letter peaks, identical to the engine). Prints MAE all / H per set for v16 and refined,
and the per-boundary changes > --show ms.

    python -m aligner2.coarse_ab respell_fillers                  # dev 009 + 026
    python -m aligner2.coarse_ab respell_fillers --sets 049       # held-out: reject only
"""
import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

CHANGES = ("respell_fillers", "softblank_fillers")


def _apply(change):
    from aligner2 import lexical
    if change == "respell_fillers":
        lexical.RESPELL_FILLERS = True
    elif change == "softblank_fillers":
        lexical.SOFTBLANK_FILLERS = True


def _run_clip(args):
    change, set_name, clip_id = args
    import torch
    torch.set_num_threads(1)
    _apply(change)
    from aligner2 import refine, local_coarse
    from aligner2.benchmark import load_sets
    c = [c for c in load_sets((set_name,)) if c["clip"] == clip_id][0]
    z = local_coarse.load_z(c)
    coarse, fc_strs = local_coarse.coarse(c, z=z)
    texts = [t["text"] for t in c["tokens"]]
    lx = refine.lexical_peaks(z, texts)
    new = refine.refine(z, texts, fc_strs, coarse, lex=lx)
    return (set_name, clip_id), coarse, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("change", choices=CHANGES)
    ap.add_argument("--sets", default="009,026")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--show", type=float, default=40.0)
    args = ap.parse_args()
    from aligner2 import refine
    from aligner2.benchmark import evaluate, load_sets
    from aligner2.local_bench import clip_inputs
    sets = tuple(args.sets.split(","))
    data = clip_inputs(sets)
    C = [c for c, *_ in data]
    A16 = {(c["set"], c["clip"]): co for c, z, ar, co, lx in data}
    AR = {(c["set"], c["clip"]): refine.refine(z, [t["text"] for t in c["tokens"]], ar, co, lex=lx) for c, z, ar, co, lx in data}
    with ProcessPoolExecutor(args.workers) as ex:
        out = list(ex.map(_run_clip, [(args.change, c["set"], c["clip"]) for c in C]))
    B16 = {k: co for k, co, _ in out}
    BR = {k: nw for k, _, nw in out}
    for name, P in (("A v16", A16), ("B v16", B16), ("A refined", AR), ("B refined", BR)):
        S, _ = evaluate(C, P, ear={})
        print(f"{name:10} " + "  ".join(f"{s}: {S[s]['all']['mae']:5.2f} (H {S[s]['human']['mae']:5.2f})" for s in list(sets) + ["ALL"]))
    tot = 0.0
    for c in C:
        key = (c["set"], c["clip"])
        for j, g in enumerate(c["tokens"]):
            for side in ("start", "end"):
                ea, eb = (AR[key][j][side] - g[side]) * 1000, (BR[key][j][side] - g[side]) * 1000
                tot += abs(ea) - abs(eb)
                if abs(ea - eb) >= args.show:
                    print(f"  {c['set']}-{int(c['clip']):02d} j{j:3} {side:5} {'H' if g[side + '_human'] else '.'} [{g['text']}]"
                          f"  A {ea:+6.0f}  B {eb:+6.0f}")
    print(f"total gain (refined, B vs A): {tot / 1000:+.2f} s")


if __name__ == "__main__":
    main()
