"""
Run the coarse stage (segment.align_two_pass, the engine's `align`) on the CPU from the locally cached signals,
so coarse-stage changes can be developed without a Modal deploy. Mirrors modal_aligner2.Engine.align.

    python -m aligner2.local_coarse 026_04          # one clip: v16 setting, compared with the stored v16 run
    python -m aligner2.local_coarse --check 009 026 # every clip of these sets vs the stored v16 run
"""
import argparse
import json
import os
import time

import numpy as np

from aligner2 import fc_align, phones, segment
from aligner2.benchmark import BENCH, load_sets
from aligner2.run_bench import GRID

CACHE = os.path.join(BENCH, "cache", "aligner2")
MAP = os.path.join(BENCH, "tools", "clip_cache_map.json")
V16 = os.path.join(BENCH, "prov_runs", "aligner2_v16.json")


def load_z(c):
    M = json.load(open(MAP))
    zf = np.load(os.path.join(CACHE, M[f"{c['set']}_{int(c['clip']):02d}"]["npz"]))
    return {k: zf[k] for k in zf.files}


_STORED = {}


def stored_phones(c):
    """(espeak phone strings, ARPAbet strings) per token, recorded by the last engine run
    (bench/prov_runs/aligner2_v17.json): phonemizer / espeak / g2p_en are only installed in the Modal image, and
    both strings depend on the transcript alone"""
    if not _STORED:
        R = json.load(open(os.path.join(BENCH, "prov_runs", "aligner2_v17.json"), encoding="utf-8"))
        _STORED.update({k: (R["phones"][k], R["arpabet"][k]) for k in R["phones"]})
    return _STORED[f"{c['set']}|{c['clip']}"]


def prepare(z, texts, device="cpu", stored=None):
    """stored: (espeak strings, ARPAbet strings) per token instead of phonemizing (see stored_phones)"""
    if stored is None:
        units, strs = phones.token_units(texts)
        fc_ids, fc_strs = fc_align.token_phones(texts)
    else:
        strs, fc_strs = stored
        units = [[phones.WILD] if s == "*" else phones._ids(s) for s in strs]
        fc_ids = [[fc_align.WILD] if s == "*" else [fc_align.VOCAB[p] for p in s.split()] for s in fc_strs]
    preps = {"full": segment.Prepared(z, texts, device=device, phone_units=units, phone_strs=strs, fc_ids=fc_ids)}
    for name, cut in (("wild", False), ("wild+cut", True)):
        soft = [segment.is_soft(t, cut) for t in texts]
        if any(soft):
            preps[name] = segment.Prepared(z, ["(())" if s_ else t for t, s_ in zip(texts, soft)], device=device,
                                           phone_units=[[-1] if s_ else u for u, s_ in zip(units, soft)],
                                           phone_strs=["*" if s_ else x for x, s_ in zip(strs, soft)],
                                           fc_ids=[[-1] if s_ else f for f, s_ in zip(fc_ids, soft)])
    return preps, fc_strs


def coarse(c, setting=None, z=None):
    """v16 coarse word times for one gold clip (setting: a run_bench GRID entry without 'refine')"""
    z = load_z(c) if z is None else z
    texts = [t["text"] for t in c["tokens"]]
    try:
        import g2p_en, phonemizer  # noqa: F401  (available -> phonemize like the engine)
        stored = None
    except ImportError:
        stored = stored_phones(c)
    preps, fc_strs = prepare(z, texts, stored=stored)
    g = dict(GRID[0] if setting is None else setting); g.pop("refine", None)
    return segment.align_two_pass(preps, texts, **g), fc_strs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="*")
    ap.add_argument("--check", nargs="*")
    args = ap.parse_args()
    R = json.load(open(V16))
    C = load_sets()
    if args.check is not None:
        todo = [c for c in C if c["set"][:3] in (args.check or ["009", "026"])]
    else:
        todo = [c for c in C if f"{c['set'][:3]}_{int(c['clip']):02d}" in args.clips]
    worst = 0.0
    for c in todo:
        t = time.time()
        p, _ = coarse(c)
        ref = R["grid_preds"][0][f"{c['set']}|{c['clip']}"]
        d = np.array([abs(a[s] - b[s]) * 1000 for a, b in zip(p, ref) for s in ("start", "end")])
        worst = max(worst, d.max())
        print(f"{c['set']}-{int(c['clip']):02d}  {len(p)} tokens  max|d| {d.max():6.1f} ms  identical {np.mean(d <= 1) * 100:5.1f}%"
              f"  ({time.time() - t:.0f}s)", flush=True)
    print(f"worst max|d| {worst:.1f} ms")


if __name__ == "__main__":
    main()
