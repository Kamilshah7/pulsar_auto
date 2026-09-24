"""
Fast benchmark: apply BoundaryRefiner (pure numpy, no model inference) to the cached
raw-CTC output for all 14 clips and score against golden labels. Runs in ~1-2s total,
so it's suitable for grid search / iteration.
"""
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from boundary_refiner import BoundaryRefiner, RefinerConfig  # noqa: E402


def load_cache():
    cache = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "bench", "raw_cache", "*.npz")), key=lambda p: int(os.path.basename(p)[:-4])):
        ci = os.path.basename(path)[:-4]
        d = np.load(path, allow_pickle=True)
        words = [{"text": str(d["word_text"][i]), "start": float(d["word_start"][i]),
                  "end": float(d["word_end"][i]), "score": float(d["word_score"][i])}
                 for i in range(len(d["word_text"]))]
        pipes = [{"start": float(d["pipe_start"][i]), "end": float(d["pipe_end"][i])}
                 for i in range(len(d["pipe_start"]))]
        cache[ci] = {"data": d["data"], "sr": int(d["sr"]), "words": words, "pipes": pipes}
    return cache


def load_gt():
    with open(os.path.join(ROOT, "bench", "gt_per_clip.json"), encoding="utf-8") as f:
        return json.load(f)


def summarize(all_rows, tol_ms=(5, 7, 10, 20)):
    abs_errs = []
    signed = []
    for r in all_rows:
        abs_errs.append(abs(r[0]))
        abs_errs.append(abs(r[1]))
        signed.append(r[0])
        signed.append(r[1])
    abs_errs = np.array(abs_errs)
    out = {
        "mae_ms": round(float(np.mean(abs_errs)), 3),
        "median_ms": round(float(np.median(abs_errs)), 3),
        "p90_ms": round(float(np.percentile(abs_errs, 90)), 3),
        "p99_ms": round(float(np.percentile(abs_errs, 99)), 3),
        "max_ms": round(float(np.max(abs_errs)), 3),
        "bias_ms": round(float(np.mean(signed)), 3),
    }
    for t in tol_ms:
        out[f"pct_within_{t}ms"] = round(float(np.mean(abs_errs <= t) * 100), 2)
    return out


def run_bench(cache, gt, cfg: RefinerConfig, clips=None, per_clip=False):
    refiner = BoundaryRefiner(cfg)
    all_rows = []
    per_clip_out = {}
    clip_ids = clips if clips else sorted(cache.keys(), key=lambda x: int(x))
    for ci in clip_ids:
        c = cache[ci]
        pred = refiner.refine(c["data"], c["sr"], c["words"], c["pipes"])
        gt_toks = gt[ci]["tokens"]
        rows = []
        for g, p in zip(gt_toks, pred):
            rows.append(((p["start"] - g["start"]) * 1000.0, (p["end"] - g["end"]) * 1000.0))
        all_rows.extend(rows)
        if per_clip:
            per_clip_out[ci] = summarize(rows)
    overall = summarize(all_rows)
    if per_clip:
        return overall, per_clip_out
    return overall


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="combined")
    ap.add_argument("--per-clip", action="store_true")
    args = ap.parse_args()

    cache = load_cache()
    gt = load_gt()
    cfg = RefinerConfig(method=args.method)
    if args.per_clip:
        overall, per_clip = run_bench(cache, gt, cfg, per_clip=True)
        for ci, s in per_clip.items():
            print(f"clip {ci:>2}: MAE={s['mae_ms']:6.2f} median={s['median_ms']:6.2f} "
                  f"p90={s['p90_ms']:6.2f} within5={s['pct_within_5ms']:5.1f}% within7={s['pct_within_7ms']:5.1f}%")
        print()
    else:
        overall = run_bench(cache, gt, cfg)
    print(f"=== method={args.method} ===")
    for k, v in overall.items():
        print(f"  {k}: {v}")
