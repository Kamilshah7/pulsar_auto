"""
Benchmark ForcedAligner.align() against golden labels (bench/gt_per_clip.json).

For each clip we feed the GOLDEN words (in golden order) as the transcript into
align(), so this isolates ACOUSTIC ALIGNMENT quality from transcription/text
correctness -- i.e. "if the aligner is told the exact right words, how close do
its predicted boundaries land to the human's boundaries?"

Usage:
    python bench/run_align_benchmark.py [--clips 0,1,2] [--out bench/results.json]
"""
import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_gold_bench import find_wav  # gold clips live in ../pulsar_auto_audio_restore, not audio/

from forced_aligner import ForcedAligner  # noqa: E402


def load_gt():
    with open(os.path.join(ROOT, "bench", "gt_per_clip.json"), encoding="utf-8") as f:
        return json.load(f)


def score_clip(gt_tokens, pred_tokens):
    """gt_tokens and pred_tokens are same length, same order (1:1 by construction)."""
    rows = []
    for gt, pr in zip(gt_tokens, pred_tokens):
        s_err = (pr["start"] - gt["start"]) * 1000.0
        e_err = (pr["end"] - gt["end"]) * 1000.0
        rows.append({
            "text": gt["text"],
            "gt_start": gt["start"], "gt_end": gt["end"],
            "pred_start": pr["start"], "pred_end": pr["end"],
            "start_err_ms": round(s_err, 2),
            "end_err_ms": round(e_err, 2),
        })
    return rows


def summarize(all_rows, tol_ms=(5, 7, 10, 20)):
    abs_errs = []
    signed_errs = []
    for r in all_rows:
        abs_errs.append(abs(r["start_err_ms"]))
        abs_errs.append(abs(r["end_err_ms"]))
        signed_errs.append(r["start_err_ms"])
        signed_errs.append(r["end_err_ms"])
    abs_errs = np.array(abs_errs)
    signed_errs = np.array(signed_errs)
    out = {
        "n_boundaries": len(abs_errs),
        "mae_ms": round(float(np.mean(abs_errs)), 3),
        "median_ms": round(float(np.median(abs_errs)), 3),
        "p90_ms": round(float(np.percentile(abs_errs, 90)), 3),
        "p99_ms": round(float(np.percentile(abs_errs, 99)), 3),
        "max_ms": round(float(np.max(abs_errs)), 3),
        "mean_signed_bias_ms": round(float(np.mean(signed_errs)), 3),
    }
    for t in tol_ms:
        out[f"pct_within_{t}ms"] = round(float(np.mean(abs_errs <= t) * 100), 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", type=str, default=None, help="comma-separated clip indices, default = all")
    ap.add_argument("--out", type=str, default=os.path.join(ROOT, "bench", "results.json"))
    ap.add_argument("--hybrid", action="store_true", default=True)
    ap.add_argument("--no-hybrid", dest="hybrid", action="store_false")
    ap.add_argument("--prelabels", action="store_true", default=True,
                     help="pass each clip's audio/*.json sidecar 'lexical' segments as a prelabel corroboration signal (matches production pipeline.py behavior). Default on.")
    ap.add_argument("--no-prelabels", dest="prelabels", action="store_false",
                     help="disable prelabels, to benchmark the prelabel-independent path")
    args = ap.parse_args()

    gt = load_gt()
    clip_ids = sorted(gt.keys(), key=lambda x: int(x))
    if args.clips:
        wanted = set(args.clips.split(","))
        clip_ids = [c for c in clip_ids if c in wanted]

    aligner = ForcedAligner()

    per_clip_results = {}
    all_rows = []
    t0 = time.time()
    for ci in clip_ids:
        entry = gt[ci]
        wav_path = find_wav(entry["filename"]) or os.path.join(ROOT, "audio", entry["filename"])
        if not os.path.exists(wav_path):
            print(f"[skip] clip {ci}: {wav_path} not found")
            continue
        words = [t["text"] for t in entry["tokens"]]

        prelabel_segments = None
        if args.prelabels:
            sidecar_path = (find_wav(entry["filename"][:-4] + ".json") or "")
            if os.path.exists(sidecar_path):
                sidecar = json.load(open(sidecar_path, encoding="utf-8"))
                prelabel_segments = [s for s in sidecar["segments"] if s["type"] == "lexical"]

        t1 = time.time()
        pred = aligner.align(wav_path, words, hybrid=args.hybrid, prelabel_segments=prelabel_segments)
        dt = time.time() - t1
        if len(pred) != len(entry["tokens"]):
            print(f"[WARN] clip {ci}: pred len {len(pred)} != gt len {len(entry['tokens'])}")
        rows = score_clip(entry["tokens"], pred)
        per_clip_results[ci] = {
            "filename": entry["filename"],
            "n_tokens": len(rows),
            "align_time_sec": round(dt, 2),
            "summary": summarize(rows),
            "rows": rows,
        }
        all_rows.extend(rows)
        s = per_clip_results[ci]["summary"]
        print(f"clip {ci:>2} ({entry['filename']}): n={len(rows):3d} "
              f"MAE={s['mae_ms']:6.2f}ms median={s['median_ms']:6.2f}ms "
              f"p90={s['p90_ms']:6.2f}ms  within5ms={s['pct_within_5ms']:5.1f}% "
              f"within7ms={s['pct_within_7ms']:5.1f}%  ({dt:.1f}s)")

    overall = summarize(all_rows)
    print("\n=== OVERALL ===")
    for k, v in overall.items():
        print(f"  {k}: {v}")
    print(f"\nTotal time: {time.time()-t0:.1f}s")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"overall": overall, "per_clip": per_clip_results}, f, indent=2)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
