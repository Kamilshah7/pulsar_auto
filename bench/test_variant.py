"""A/B test a forced_aligner variant module against gt_per_clip.json on a clip subset."""
import importlib.util
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_gold_bench import find_wav  # gold clips live in ../pulsar_auto_audio_restore, not audio/

VARIANT_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "forced_aligner.py")
CLIPS = sys.argv[2] if len(sys.argv) > 2 else "0,1,9,10"

spec = importlib.util.spec_from_file_location("fa_variant", VARIANT_PATH)
fa_variant = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fa_variant)

aligner = fa_variant.ForcedAligner()

gt = json.load(open(os.path.join(ROOT, "bench", "gt_per_clip.json"), encoding="utf-8"))


def score_clip(gt_tokens, pred_tokens):
    rows = []
    for g, pr in zip(gt_tokens, pred_tokens):
        rows.append({
            "text": g["text"],
            "start_err_ms": round((pr["start"] - g["start"]) * 1000.0, 2),
            "end_err_ms": round((pr["end"] - g["end"]) * 1000.0, 2),
        })
    return rows


def summarize(all_rows, tol_ms=(5, 7, 10, 20)):
    abs_errs = []
    for r in all_rows:
        abs_errs.append(abs(r["start_err_ms"]))
        abs_errs.append(abs(r["end_err_ms"]))
    abs_errs = np.array(abs_errs)
    out = {
        "mae_ms": round(float(np.mean(abs_errs)), 3),
        "median_ms": round(float(np.median(abs_errs)), 3),
        "p90_ms": round(float(np.percentile(abs_errs, 90)), 3),
    }
    for t in tol_ms:
        out[f"pct_within_{t}ms"] = round(float(np.mean(abs_errs <= t) * 100), 2)
    return out


clip_ids = CLIPS.split(",")
all_rows = []
for ci in clip_ids:
    entry = gt[ci]
    wav_path = find_wav(entry["filename"])
    words = [t["text"] for t in entry["tokens"]]
    t1 = time.time()
    pred = aligner.align(wav_path, words, hybrid=True)
    dt = time.time() - t1
    rows = score_clip(entry["tokens"], pred)
    all_rows.extend(rows)
    s = summarize(rows)
    print(f"clip {ci:>2}: n={len(rows):3d} MAE={s['mae_ms']:6.2f}ms median={s['median_ms']:6.2f}ms "
          f"p90={s['p90_ms']:6.2f}ms within5ms={s['pct_within_5ms']:5.1f}% within7ms={s['pct_within_7ms']:5.1f}% ({dt:.1f}s)")

overall = summarize(all_rows)
print(f"\n=== OVERALL ({VARIANT_PATH}) ===")
for k, v in overall.items():
    print(f"  {k}: {v}")
