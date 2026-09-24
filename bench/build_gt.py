"""
Build clip-local ground-truth token lists from curr_proj_golden_labels.json,
using output/ordered_clips.json for clipIndex -> filename / global-offset mapping.

Output: bench/gt_per_clip.json
  { "<clipIndex>": {"filename": "...", "tokens": [{"text":..., "start":..., "end":...}, ...]} }
start/end are clip-LOCAL seconds (i.e. relative to that clip's own wav file).
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    golden = json.load(open(os.path.join(ROOT, "curr_proj_golden_labels.json"), encoding="utf-8"))
    ordered = json.load(open(os.path.join(ROOT, "output", "ordered_clips.json"), encoding="utf-8"))

    offset_by_idx = {c["index"]: c["start_sec"] for c in ordered}
    filename_by_idx = {c["index"]: c["filename"] for c in ordered}

    by_clip = {}
    for t in golden["tokens"]:
        ci = t["clipIndex"]
        by_clip.setdefault(ci, []).append(t)

    out = {}
    for ci, toks in sorted(by_clip.items()):
        offset = offset_by_idx.get(ci, 0.0)
        toks_sorted = sorted(toks, key=lambda t: t["start"])
        local_toks = []
        for t in toks_sorted:
            local_toks.append({
                "text": t["text"],
                "start": round(t["start"] - offset, 4),
                "end": round(t["end"] - offset, 4),
            })
        out[str(ci)] = {
            "filename": filename_by_idx.get(ci),
            "n_tokens": len(local_toks),
            "tokens": local_toks,
        }

    os.makedirs(os.path.join(ROOT, "bench"), exist_ok=True)
    with open(os.path.join(ROOT, "bench", "gt_per_clip.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    total = sum(v["n_tokens"] for v in out.values())
    print(f"Wrote bench/gt_per_clip.json: {len(out)} clips, {total} tokens total")
    for ci, v in out.items():
        neg = [t for t in v["tokens"] if t["start"] < -0.05 or t["end"] > 60]
        if neg:
            print(f"  WARNING clip {ci} ({v['filename']}): {len(neg)} tokens with suspicious local time (offset issue?)")

if __name__ == "__main__":
    main()
