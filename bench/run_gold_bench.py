"""
Provenance-aware gold benchmark for ForcedAligner.align().

Why this exists instead of bench/run_align_benchmark.py:
  1. That script reads clips from audio/, which is overwritten by every new bundle; the
     gold clips live in ../pulsar_auto_audio_restore/. It silently skips all 14 clips.
  2. The gold labels are a MIXTURE. They were captured from the Pulsar editor after our
     pipeline injected aligner output and a human corrected some boundaries. Timestamp
     forensics separate the two:
       - DRAGGED  : sub-millisecond value (e.g. 4.3884s). The editor's pixel->time drag
                    produces arbitrary sub-ms values; our injector rounds to whole ms and
                    the server pre-labels are whole ms. These are the only boundaries a
                    person positively placed.
       - ACCEPTED : whole-millisecond value. Mostly our own injected output that the
                    human looked at and left alone -- 27-32% of these match historical
                    aligner versions to within 0.5ms, versus 1.8% for raw CTC.
     Scoring against ACCEPTED boundaries partly rewards reproducing the old aligner, so a
     change that is genuinely better can look worse. DRAGGED is the primary metric; the
     ALL number is kept only for continuity with the old 12.491ms / 44.46% baseline.

Usage:
    python bench/run_gold_bench.py [--tag NAME] [--save PATH] [--clips 0,1,2]
Env knobs from forced_aligner.py (PULSAR_*) are honoured, so sweeps are:
    PULSAR_TRAIL_MULT=0.07 python bench/run_gold_bench.py --tag trail070
"""
import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
AUDIO_DIRS = [os.path.join(os.path.dirname(ROOT), "pulsar_auto_audio_restore"),
              os.path.join(ROOT, "audio")]


def find_wav(name):
    for d in AUDIO_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def provenance(t, status=None):
    """Recorded status from bench/snapshot_gold.py when available; otherwise the old
    timestamp-precision forensics for the original 14-clip set."""
    if status is not None:
        return {"moved": "human", "no_injection_match": "human",
                "reviewed_accepted": "verified", "unreviewed": "untouched"}[status]
    ms = t * 1000.0
    return "dragged" if abs(ms - round(ms)) > 1e-6 else "accepted"


CONT_MAX_GAP_MS = 5.0  # gold gap between two words at or below this = continuous speech


def continuity(toks, j, side):
    """'cont' if this timestamp is a boundary between two touching words in gold,
    'pause' if there is a real gap, 'edge' for the clip's first start / last end."""
    if side == "end":
        if j == len(toks) - 1:
            return "edge"
        gap = (toks[j + 1]["start"] - toks[j]["end"]) * 1000.0
    else:
        if j == 0:
            return "edge"
        gap = (toks[j]["start"] - toks[j - 1]["end"]) * 1000.0
    return "cont" if gap <= CONT_MAX_GAP_MS else "pause"


def summarize(errs):
    a = np.abs(np.asarray(errs, dtype=float))
    if a.size == 0:
        return {"n": 0}
    return {
        "n": int(a.size),
        "mae_ms": round(float(a.mean()), 3),
        "median_ms": round(float(np.median(a)), 3),
        "p90_ms": round(float(np.percentile(a, 90)), 3),
        "w5": round(float(np.mean(a <= 5) * 100), 2),
        "w7": round(float(np.mean(a <= 7) * 100), 2),
        "w10": round(float(np.mean(a <= 10) * 100), 2),
        "w20": round(float(np.mean(a <= 20) * 100), 2),
        "bias_ms": round(float(np.mean(errs)), 3),
    }


def fmt(name, s):
    if not s.get("n"):
        return f"{name:<16} n=0"
    return (f"{name:<16} n={s['n']:4d}  MAE={s['mae_ms']:7.3f}  med={s['median_ms']:6.2f}  "
            f"w5={s['w5']:5.2f}%  w10={s['w10']:5.2f}%  p90={s['p90_ms']:6.2f}")


def score(gt, preds):
    """preds: {clip: [{"start","end"}, ...]} aligned 1:1 with gold tokens."""
    rows = []
    for ci, toks in ((c, gt[c]["tokens"]) for c in gt):
        p = preds.get(ci)
        if p is None:
            continue
        for j, (g, pr) in enumerate(zip(toks, p)):
            for side in ("start", "end"):
                rows.append({"clip": ci, "tok": j, "side": side,
                             "prov": provenance(g[side], g.get(f"{side}_status")),
                             "cont": continuity(toks, j, side),
                             "err_ms": (pr[side] - g[side]) * 1000.0})
    out = {"all": summarize([r["err_ms"] for r in rows])}
    for k in sorted({r["prov"] for r in rows}):
        out[k] = summarize([r["err_ms"] for r in rows if r["prov"] == k])
    for c in ("cont", "pause", "edge"):
        out[c] = summarize([r["err_ms"] for r in rows if r["cont"] == c])
        for k in sorted({r["prov"] for r in rows}):
            out[f"{c}/{k}"] = summarize([r["err_ms"] for r in rows if r["cont"] == c and r["prov"] == k])
    return out, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=os.environ.get("SWEEP_TAG", "run"))
    ap.add_argument("--clips", default=None)
    ap.add_argument("--save", default=None, help="write predictions + per-boundary rows as JSON")
    ap.add_argument("--set", default=None,
                    help="a bench/gold_sets/<dir> snapshot (default: the original bench/gt_per_clip.json)")
    args = ap.parse_args()

    from forced_aligner import ForcedAligner

    if args.set:
        gt = json.load(open(os.path.join(args.set, "gt_per_clip.json"), encoding="utf-8"))
        AUDIO_DIRS.insert(0, os.path.join(args.set, "audio"))
    else:
        gt = json.load(open(os.path.join(ROOT, "bench", "gt_per_clip.json"), encoding="utf-8"))
    if args.clips:
        keep = set(args.clips.split(","))
        gt = {k: v for k, v in gt.items() if k in keep}

    aligner = ForcedAligner()
    preds = {}
    t0 = time.time()
    for ci in sorted(gt, key=int):
        wav = find_wav(gt[ci]["filename"])
        if wav is None:
            sys.exit(f"FATAL: clip {ci} audio {gt[ci]['filename']} not found in {AUDIO_DIRS}")
        out = aligner.align(wav, [t["text"] for t in gt[ci]["tokens"]], hybrid=True)
        if len(out) != len(gt[ci]["tokens"]):
            sys.exit(f"FATAL: clip {ci} returned {len(out)} tokens for {len(gt[ci]['tokens'])} gold")
        preds[ci] = [{"start": w["start"], "end": w["end"]} for w in out]

    res, rows = score(gt, preds)
    print(f"RESULT {args.tag}  ({time.time() - t0:.0f}s)")
    for k in [k for k in res if "/" not in k] + [k for k in res if "/" in k]:
        if res[k].get("n"):
            print("   " + fmt(k.upper(), res[k]))
    if args.save:
        json.dump({"tag": args.tag, "summary": res, "preds": preds, "rows": rows},
                  open(args.save, "w", encoding="utf-8"))


if __name__ == "__main__":
    main()
