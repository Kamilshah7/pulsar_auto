"""
TRUE end-to-end benchmark: take the reconciled (LLM-corrected) word sequence for each
clip -- the same kind of input the live pipeline.process_llm_output_and_generate_injection()
would receive -- run it through the CURRENT LIVE ForcedAligner (hybrid=True, i.e. the
real snap_boundaries_hybrid heuristic engine as it stands in forced_aligner.py right now),
and score the result against golden labels using sequence alignment (so word insertions/
deletions/substitutions are correctly accounted for, not just index-aligned).

This is what a user of the system actually gets today: text errors AND boundary errors
together, not the idealized "given perfect text" number from bench/run_align_benchmark.py.
"""
import json
import os
import re
import sys
import difflib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_gold_bench import find_wav  # gold clips live in ../pulsar_auto_audio_restore, not audio/

from forced_aligner import ForcedAligner  # noqa: E402


def norm(w):
    return re.sub(r"[^a-z']", "", w.lower())


def main():
    gt = json.load(open(os.path.join(ROOT, "bench", "gt_per_clip.json"), encoding="utf-8"))
    ordered = json.load(open(os.path.join(ROOT, "output", "ordered_clips.json"), encoding="utf-8"))
    filename_by_idx = {c["index"]: c["filename"] for c in ordered}
    reconciled = json.load(open(os.path.join(ROOT, "output", "reconciled_transcript.json"), encoding="utf-8"))

    aligner = ForcedAligner()

    all_pairs = []  # (gt_row, pred_row) for matched (equal-text) tokens
    per_clip_summary = {}
    total_ref = 0
    total_err = 0

    for ci in sorted(reconciled.keys(), key=lambda x: int(x)):
        words = reconciled[ci]
        fname = filename_by_idx[int(ci)]
        wpath = find_wav(fname)
        pred = aligner.align(wpath, words, hybrid=True)
        # pred[i]["text"] == words[i] by construction of align()'s mapping loop

        ref_toks = gt[ci]["tokens"]
        ref_texts = [norm(t["text"]) for t in ref_toks]
        hyp_texts = [norm(w) for w in words]

        sm = difflib.SequenceMatcher(None, ref_texts, hyp_texts)
        errs = 0
        clip_pairs = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    g = ref_toks[i1 + k]
                    p = pred[j1 + k]
                    clip_pairs.append((g, p))
            else:
                errs += max(i2 - i1, j2 - j1)

        wer = errs / max(len(ref_texts), 1)
        total_ref += len(ref_texts)
        total_err += errs
        all_pairs.extend(clip_pairs)

        if clip_pairs:
            abs_errs = []
            for g, p in clip_pairs:
                abs_errs.append(abs((p["start"] - g["start"]) * 1000.0))
                abs_errs.append(abs((p["end"] - g["end"]) * 1000.0))
            abs_errs = np.array(abs_errs)
            per_clip_summary[ci] = {
                "wer_pct": round(wer * 100, 1),
                "matched_tokens": len(clip_pairs),
                "ref_tokens": len(ref_texts),
                "mae_ms": round(float(np.mean(abs_errs)), 2),
                "median_ms": round(float(np.median(abs_errs)), 2),
                "pct_within_5ms": round(float(np.mean(abs_errs <= 5) * 100), 1),
                "pct_within_7ms": round(float(np.mean(abs_errs <= 7) * 100), 1),
                "pct_within_20ms": round(float(np.mean(abs_errs <= 20) * 100), 1),
            }
        else:
            per_clip_summary[ci] = {"wer_pct": round(wer * 100, 1), "matched_tokens": 0, "ref_tokens": len(ref_texts)}

        print(f"clip {ci:>2}: WER={per_clip_summary[ci]['wer_pct']:5.1f}% "
              f"matched={len(clip_pairs)}/{len(ref_texts)} "
              f"MAE={per_clip_summary[ci].get('mae_ms','n/a')}")

    print(f"\nOVERALL WER (text): {100*total_err/total_ref:.2f}%")

    abs_errs = []
    for g, p in all_pairs:
        abs_errs.append(abs((p["start"] - g["start"]) * 1000.0))
        abs_errs.append(abs((p["end"] - g["end"]) * 1000.0))
    abs_errs = np.array(abs_errs)
    overall_timing = {
        "n_boundaries": len(abs_errs),
        "n_matched_tokens": len(all_pairs),
        "mae_ms": round(float(np.mean(abs_errs)), 3),
        "median_ms": round(float(np.median(abs_errs)), 3),
        "p90_ms": round(float(np.percentile(abs_errs, 90)), 3),
        "pct_within_5ms": round(float(np.mean(abs_errs <= 5) * 100), 2),
        "pct_within_7ms": round(float(np.mean(abs_errs <= 7) * 100), 2),
        "pct_within_10ms": round(float(np.mean(abs_errs <= 10) * 100), 2),
        "pct_within_20ms": round(float(np.mean(abs_errs <= 20) * 100), 2),
    }
    print("OVERALL TIMING (on correctly-matched tokens only):")
    for k, v in overall_timing.items():
        print(f"  {k}: {v}")

    out = {
        "overall_wer_pct": round(100 * total_err / total_ref, 2),
        "overall_timing": overall_timing,
        "per_clip": per_clip_summary,
    }
    with open(os.path.join(ROOT, "bench", "results_e2e.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\nWrote bench/results_e2e.json")


if __name__ == "__main__":
    main()
