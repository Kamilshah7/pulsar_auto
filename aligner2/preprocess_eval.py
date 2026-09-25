"""
Does pre-processing the audio (aligner2/preprocess.py) improve the production aligner? For each variant: signals on the
Modal GPU engine under a separate cache key (<clip key>_pp_<variant>: the production cache is untouched), then the
production setting (run_bench.GRID[3] = v16 + rules) on those signals, then the same scoring as aligner2/verify.py:
gold MAE all / H per set and the listening review per set.

    python -m aligner2.preprocess_eval                 # every variant (predictions cached in bench/prov_runs/preproc_*.json)
    python -m aligner2.preprocess_eval --variants hpf80,denoise
    python -m aligner2.preprocess_eval --score-only    # re-score the cached predictions
    python -m aligner2.preprocess_eval --degrade noise10 --variants none,denoise --sets 026,049
                                                       # degrade the clean audio first (aligner2/degrade.py)
"""
import argparse
import json
import os
import time

import numpy as np

from aligner2 import degrade, preprocess, remote
from aligner2.benchmark import BENCH, load_sets
from aligner2.run_bench import GRID
from aligner2.signals import clip_key, load_audio
from aligner2.verify import ear_items

SETS = ("009", "026", "049", "old14")
OUT = os.path.join(BENCH, "prov_runs")


def _tag(variant, deg):
    return variant if deg == "clean" else f"{deg}_{variant}"


def run_variant(variant, clips, deg="clean"):
    path = os.path.join(OUT, f"preproc_{_tag(variant, deg)}.json")
    if os.path.exists(path):
        have = {tuple(k.split("|")): v for k, v in json.load(open(path)).items()}
        if all((c["set"], str(c["clip"])) in have for c in clips):
            return have
    if variant == "none" and deg == "clean":                # the production run itself
        g3 = json.load(open(os.path.join(OUT, "aligner2_v23.json")))["grid_preds"][3]
        preds = {(c["set"], str(c["clip"])): g3[f"{c['set']}|{c['clip']}"] for c in clips}
    else:
        suffix = f"_pp_{variant}" if deg == "clean" else f"_dg_{deg}_pp_{variant}"
        keys = {(c["set"], str(c["clip"])): f"{clip_key(c['wav'])}{suffix}" for c in clips}
        miss = set(remote._obj().missing.remote(list(keys.values())))
        need = [c for c in clips if keys[(c["set"], str(c["clip"]))] in miss]
        if variant.startswith("e_"):                        # a pretrained enhancer on Modal (modal_enhance.py)
            import modal
            fn = modal.Function.from_name("aligner2-enhance", variant[2:])
            src = [remote._bytes(degrade.apply(load_audio(c["wav"]), deg)) for c in need]
            enh = list(fn.map(src)) if src else []
            todo = [(keys[(c["set"], str(c["clip"]))], e, False) for c, e in zip(need, enh)]
        else:
            todo = [(keys[(c["set"], str(c["clip"]))],
                     remote._bytes(preprocess.apply(degrade.apply(load_audio(c["wav"]), deg), variant)), False)
                    for c in need]
        t0 = time.time()
        if todo:
            for i, _ in enumerate(remote._obj().signals.starmap(todo, order_outputs=False), 1):
                if i % 10 == 0 or i == len(todo):
                    remote.log(f"{_tag(variant, deg)}: signals {i}/{len(todo)} ({time.time() - t0:.0f}s)")
        res = remote.align_many([(keys[(c["set"], str(c["clip"]))], [t["text"] for t in c["tokens"]]) for c in clips], [GRID[3]])
        preds = {(c["set"], str(c["clip"])): res[keys[(c["set"], str(c["clip"]))]][0] for c in clips}
        f = preprocess.stretch_factor(variant)
        if f != 1.0:                                          # a time-stretched variant: back to the original timeline
            preds = {k: [dict(q, start=q["start"] / f, end=q["end"] / f) for q in v] for k, v in preds.items()}
    json.dump({"|".join(k): v for k, v in preds.items()}, open(path, "w"))
    return preds


def score(preds, clips, J):
    out = {}
    for s in sorted({c["set"] for c in clips}, key=SETS.index):
        e, eh, acc, rej, dist, man = [], [], 0, 0, [], []
        for c in [c for c in clips if c["set"] == s]:
            p, toks = preds[(s, str(c["clip"]))], c["tokens"]
            for j, g in enumerate(toks):
                for side in ("start", "end"):
                    d = abs(p[j][side] - g[side]) * 1000
                    e.append(d)
                    if g[f"{side}_human"]:
                        eh.append(d)
            for k in range(len(toks) - 1):
                it = J.get(f"{s}-{int(c['clip'])}-{k}")
                if not it or not it["acc"]:
                    continue
                t = (p[k]["end"] + p[k + 1]["start"]) / 2
                na = any(abs(t - x) <= 0.005 for x in it["acc"])
                acc += na; rej += (any(abs(t - x) <= 0.005 for x in it["rej"]) and not na)
                dist.append(min(abs(t - x) for x in it["acc"]) * 1000)
                if it["man"]:
                    man.append(abs(t - float(np.median(it["man"]))) * 1000)
        out[s] = dict(mae=np.mean(e), h=np.mean(eh), n_ear=len(dist), acc=acc, rej=rej,
                      dist=np.mean(dist) if dist else np.nan, man=np.mean(man) if man else np.nan)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default=",".join(preprocess.VARIANTS))   # + e_<method> (modal_enhance.py)
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--degrade", default="clean", choices=degrade.DEGRADATIONS)
    ap.add_argument("--sets", default=",".join(SETS))
    args = ap.parse_args()
    sets = tuple(args.sets.split(","))
    clips = load_sets(sets)
    J = ear_items()
    variants = args.variants.split(",")
    results = {}
    try:
        for v in variants:
            if args.score_only and not os.path.exists(os.path.join(OUT, f"preproc_{_tag(v, args.degrade)}.json"))                     and not (v == "none" and args.degrade == "clean"):
                continue
            results[v] = score(run_variant(v, clips, args.degrade), clips, J)
    finally:
        if not args.score_only:
            remote.stop_containers("(pre-processing experiment done)")
    base = results.get("none")
    print(f"degradation: {args.degrade}")
    print(f"{'variant':8} | " + " | ".join(f"{s:^31}" for s in sets))
    print(f"{'':8} | " + " | ".join(f"{'MAE':>6} {'H':>6} {'acc':>4} {'rej':>4} {'dist':>6}" for _ in sets))
    for v, r in results.items():
        cells = []
        for s in sets:
            x = r[s]
            ear = f"{x['acc']:4d} {x['rej']:4d} {x['dist']:6.1f}" if x["n_ear"] else f"{'':4} {'':4} {'':6}"
            cells.append(f"{x['mae']:6.2f} {x['h']:6.2f} {ear}")
        print(f"{v:8} | " + " | ".join(cells))
    if base:
        print("\ndelta vs none (MAE / H: negative = better; acc: positive = better; rej: negative = better)")
        for v, r in results.items():
            if v == "none":
                continue
            print(f"{v:8} | " + " | ".join(
                f"{r[s]['mae'] - base[s]['mae']:+6.2f} {r[s]['h'] - base[s]['h']:+6.2f} "
                + (f"{r[s]['acc'] - base[s]['acc']:+4d} {r[s]['rej'] - base[s]['rej']:+4d} {r[s]['dist'] - base[s]['dist']:+6.1f}"
                   if r[s]['n_ear'] else f"{'':4} {'':4} {'':6}") for s in sets))


if __name__ == "__main__":
    main()
