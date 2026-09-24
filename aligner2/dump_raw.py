"""
Dump the raw signals around every gold boundary, so the real behaviour can be read directly.

For every gold timestamp (continuous joins as one cut at the midpoint of end/start; pause edges as
two separate points), all 20 raw signals (un-normalised) in a +-100 ms window on the 2 ms grid.

    python -m aligner2.dump_raw     -> bench/cache/aligner2/raw_dump.npz  (X: [N, 20, 101], meta rows)
                                       bench/cache/aligner2/raw_dump_meta.json
"""
import json
import os
import re

import numpy as np

from aligner2.benchmark import CONT_MAX_GAP_MS, ear_judgments, load_sets
from aligner2.signals import CACHE, HOP, NAMES, compute

HALF = 50  # frames either side (100 ms)
VOWELS = set("aeiouy")


def sound(word, side):
    w = re.sub(r"[^a-z']", "", word.lower())
    if not w:
        return "?"
    ch = w[-1] if side == "coda" else w[0]
    if side == "coda" and w.endswith(("ng", "m", "n")):
        return "nasal"
    if ch in VOWELS or (side == "coda" and w.endswith(("w",))):
        return "vowel"
    if ch in "pbtdkgcq":
        return "stop"
    if ch in "fvszxj" or w[-2:] in ("sh", "ch", "th") if side == "coda" else w[:2] in ("sh", "ch", "th"):
        return "fric"
    if ch in "mn":
        return "nasal"
    if ch in "lr":
        return "liquid"
    if ch in "wh":
        return "glide/h"
    return "other"


def main():
    ear = ear_judgments()
    X, meta = [], []
    for c in load_sets():
        z = compute(c["wav"]); T = len(z["t"]); toks = c["tokens"]
        sig = np.stack([z[n] for n in NAMES]).astype(np.float32)
        pad = np.pad(sig, ((0, 0), (HALF, HALF)), mode="edge")
        pts = []
        for j in range(len(toks) - 1):
            gap = (toks[j + 1]["start"] - toks[j]["end"]) * 1000
            base = {"set": c["set"], "clip": c["clip"], "pair": j, "w1": toks[j]["text"], "w2": toks[j + 1]["text"],
                    "coda": sound(toks[j]["text"], "coda"), "onset": sound(toks[j + 1]["text"], "onset"), "gap_ms": gap}
            if gap <= CONT_MAX_GAP_MS:
                acc = ear.get(f"{c['set']}-{c['clip']}-{j}")
                pts.append(dict(base, kind="cont", t=(toks[j]["end"] + toks[j + 1]["start"]) / 2,
                                human=toks[j]["end_human"] or toks[j + 1]["start_human"], ear_acc=acc))
            else:
                pts.append(dict(base, kind="pause_end", t=toks[j]["end"], human=toks[j]["end_human"], ear_acc=None))
                pts.append(dict(base, kind="pause_start", t=toks[j + 1]["start"], human=toks[j + 1]["start_human"], ear_acc=None))
        pts.append({"set": c["set"], "clip": c["clip"], "pair": -1, "w1": "", "w2": toks[0]["text"], "coda": "", "onset":
                    sound(toks[0]["text"], "onset"), "gap_ms": None, "kind": "clip_start", "t": toks[0]["start"],
                    "human": toks[0]["start_human"], "ear_acc": None})
        pts.append({"set": c["set"], "clip": c["clip"], "pair": len(toks) - 1, "w1": toks[-1]["text"], "w2": "",
                    "coda": sound(toks[-1]["text"], "coda"), "onset": "", "gap_ms": None, "kind": "clip_end",
                    "t": toks[-1]["end"], "human": toks[-1]["end_human"], "ear_acc": None})
        for p in pts:
            k = int(round(p["t"] / HOP))
            if 0 <= k < T:
                X.append(pad[:, k:k + 2 * HALF + 1]); p["frame_offset_ms"] = (p["t"] - k * HOP) * 1000; meta.append(p)
    X = np.stack(X)
    np.savez_compressed(os.path.join(CACHE, "raw_dump.npz"), X=X, names=np.array(NAMES))
    json.dump(meta, open(os.path.join(CACHE, "raw_dump_meta.json"), "w", encoding="utf-8"))
    from collections import Counter
    print(X.shape, Counter(m["kind"] for m in meta))


if __name__ == "__main__":
    main()
