"""
Run aligner2 on the GPU engine over every gold clip and score it (aligner2/benchmark.py).

The two global parameters are never tuned on the set being scored: for each gold set, the grid
setting with the lowest MAE on the OTHER sets is applied to it (leave-one-set-out). The held-out set
(049) is scored but never part of any selection pool.

    python -m aligner2.run_bench [--tag NAME]
"""
import argparse
import itertools
import json
import os
import time

from aligner2 import remote
from aligner2.benchmark import BENCH, evaluate, load_sets, report
from aligner2.signals import clip_key

BASE = {"min_pause": 0.03, "pause_model": "word_ref", "lam": 1000.0, "cont_model": "class", "radius_ms": 20,
        "onset_ms": 10, "ref_mode": "word", "theta_db": 20.0, "clip_anchor_ms": 150,                     # v11
        # noise-robust pauses (2026-09-25): in a clip whose speech peaks are < 40 dB over the background, a pause may
        # also be a >= 90 ms stretch within 6 dB of the local floor (noise fills pauses, so the 20 dB-under-the-words
        # test fails). Clean clips (all benchmark clips: >= 44 dB) are unchanged; 20 dB noise: 026 33.7 -> 20.0 ms,
        # 049 39.9 -> 26.6 ms; 10 dB noise: 44.0 -> 25.0, 48.4 -> 29.8 (aligner2/pause_robust_eval.py)
        "pause_floor_db": 6.0, "pause_floor_min_ms": 90, "pause_floor_snr_max": 40.0}
GRID = [dict(BASE, unit="letter4", radius_ms=10, soft=sm) for sm in ("off", "wild", "wild+cut")]
GRID += [dict(BASE, unit="letter4", radius_ms=10, soft="off", refine=True)]     # + the rule stage (aligner2/refine.py)
SETS = ("009", "026", "049", "old14")
HELD_OUT = ("049",)              # scored, but never in the pool that picks a setting for any set


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tag", default="v1"); args = ap.parse_args()
    C = load_sets()
    t = time.time()
    n = remote.ensure_signals([(clip_key(c["wav"]), c["wav"]) for c in C])
    print(f"signals: {n} clips computed on the GPU ({time.time() - t:.0f}s)")
    t = time.time()
    keys = {(c["set"], c["clip"]): clip_key(c["wav"]) for c in C}
    res = remote.align_many([(keys[(c["set"], c["clip"])], [tk["text"] for tk in c["tokens"]]) for c in C], GRID)
    print(f"aligned {len(C)} clips x {len(GRID)} settings on the GPU ({time.time() - t:.0f}s)")
    preds_at = lambda gi: {(c["set"], c["clip"]): res[keys[(c["set"], c["clip"])]][gi] for c in C}
    scores = []
    for gi in range(len(GRID)):
        S, _ = evaluate(C, preds_at(gi))
        scores.append(S)
    loso, chosen = {}, {}
    for s in SETS:
        others = [o for o in SETS if o != s and o not in HELD_OUT]
        def mae_others(gi):
            num = sum(scores[gi][o]["all"]["mae"] * scores[gi][o]["all"]["n"] for o in others)
            return num / sum(scores[gi][o]["all"]["n"] for o in others)
        gi = min(range(len(GRID)), key=mae_others)
        chosen[s] = GRID[gi]
        for c in C:
            if c["set"] == s:
                loso[(c["set"], c["clip"])] = preds_at(gi)[(c["set"], c["clip"])]
    S, rows = evaluate(C, loso)
    txt = report(S, f"aligner2 {args.tag} -- leave-one-set-out; params per held-out set: {chosen}")
    print(txt)
    best_all = min(range(len(GRID)), key=lambda gi: scores[gi]["ALL"]["all"]["mae"])
    print(f"\n(best single setting on everything, for reference: {GRID[best_all]} -> MAE "
          f"{scores[best_all]['ALL']['all']['mae']:.1f}, w5 {scores[best_all]['ALL']['all']['w5']:.0f}%)")
    out = os.path.join(BENCH, "prov_runs", f"aligner2_{args.tag}.json")
    json.dump({"arpabet": {f"{c['set']}|{c['clip']}": remote.ARPA.get(keys[(c["set"], c["clip"])]) for c in C},
               "phones": {f"{c['set']}|{c['clip']}": remote.PHONES.get(keys[(c["set"], c["clip"])]) for c in C},
               "chosen": chosen, "summary": S, "preds": {f"{k[0]}|{k[1]}": v for k, v in loso.items()},
               "grid": GRID, "grid_summary": [sc["ALL"] for sc in scores],
               "grid_preds": ([{f"{c['set']}|{c['clip']}": res[keys[(c["set"], c["clip"])]][gi] for c in C} for gi in range(len(GRID))]
                              if len(GRID) <= 6 else None)}, open(out, "w"))
    open(out.replace(".json", ".txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
