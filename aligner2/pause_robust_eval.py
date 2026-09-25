"""
Noise-robust pause model (aligner2/segment.py: pause_floor_db / pause_vad) on clean and degraded audio. The coarse stage
runs locally (aligner2/local_coarse.py) on the cached signals (clean: the production cache; degraded: the downloads of
aligner2/hybrid_eval.py in bench/cache/aligner2/preproc/), then the current rules; scored like aligner2/verify.py.

    python -m aligner2.pause_robust_eval --conds clean,noise20 --settings base,floor6,vad50
"""
import argparse
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from aligner2.benchmark import load_sets

SETTINGS = {"base": {}, "floor6": {"pause_floor_db": 6.0}, "floor10": {"pause_floor_db": 10.0},
            "vad50": {"pause_vad": 0.5}, "vad30": {"pause_vad": 0.3},
            "floor6+vad50": {"pause_floor_db": 6.0, "pause_vad": 0.5},
            "floor6&vad50": {"pause_floor_db": 6.0, "pause_floor_vad": 0.5},
            "floor10&vad50": {"pause_floor_db": 10.0, "pause_floor_vad": 0.5},
            "floor6&vad30": {"pause_floor_db": 6.0, "pause_floor_vad": 0.3},
            "floor6min60": {"pause_floor_db": 6.0, "_floor_min_ms": 60}, "floor6min90": {"pause_floor_db": 6.0, "_floor_min_ms": 90},
            "floor6min120": {"pause_floor_db": 6.0, "_floor_min_ms": 120},
            "gated": {"pause_floor_db": 6.0, "pause_floor_min_ms": 90, "pause_floor_snr_max": 40.0}}
LOCAL = os.path.join("bench", "cache", "aligner2", "preproc")


def _floor_min_patch(min_ms):
    """TEST-ONLY override of segment._word_quiet_run: a floor-only silence must last >= min_ms (a silence the word-
    referenced test finds keeps the usual min_pause); in noise, weak consonants near the floor are short, pauses long"""
    from aligner2 import segment
    from aligner2.signals import HOP
    orig = segment._word_quiet_run

    def patched(prep, k, delta_db, ref_mode="edge", floor_db=None, vad=None, floor_vad=None):
        run = orig(prep, k, delta_db, ref_mode)                       # the word-referenced silence alone
        if floor_db is None:
            return run
        both = orig(prep, k, delta_db, ref_mode, floor_db, vad, floor_vad)
        if run and (run[1] - run[0]) * HOP >= 0.03:
            return run if both is None or (both[1] - both[0]) <= (run[1] - run[0]) else both
        return both if both and (both[1] - both[0]) * HOP >= min_ms / 1000 else run
    segment._word_quiet_run = patched


def _clip(args):
    c, cond, setting = args
    import torch
    torch.set_num_threads(1)
    fm = SETTINGS[setting].get("_floor_min_ms")
    if fm:
        _floor_min_patch(fm)
    from aligner2 import local_coarse, refine
    from aligner2.run_bench import GRID
    from aligner2.signals import clip_key
    if cond == "clean":
        z = local_coarse.load_z(c)
    else:
        zf = np.load(os.path.join(LOCAL, f"{clip_key(c['wav'])}_dg_{cond}_pp_none.npz"))
        z = {k: zf[k] for k in zf.files}
    g = dict(GRID[0]); g.pop("refine", None); g.update({k: v for k, v in SETTINGS[setting].items() if not k.startswith("_")})
    coarse, fc = local_coarse.coarse(c, setting=g, z=z)
    texts = [t["text"] for t in c["tokens"]]
    return (c["set"], str(c["clip"])), refine.refine(z, texts, fc, coarse, lex=refine.lexical_peaks(z, texts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", default="clean,noise20,noise10,reverb")
    ap.add_argument("--settings", default=",".join(SETTINGS))
    ap.add_argument("--sets", default="026,049"); ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    from aligner2.preprocess_eval import score
    from aligner2.verify import ear_items
    sets = tuple(args.sets.split(","))
    clips = load_sets(sets); J = ear_items()
    res = {}
    with ProcessPoolExecutor(args.workers) as ex:
        for cond in args.conds.split(","):
            for st in args.settings.split(","):
                preds = dict(ex.map(_clip, [(c, cond, st) for c in clips]))
                res[(cond, st)] = score(preds, clips, J)
                r = res[(cond, st)]
                print(f"{cond:8} {st:13} " + " | ".join(
                    f"{s} MAE {r[s]['mae']:6.2f} H {r[s]['h']:6.2f}" + (f" acc {r[s]['acc']:3d} rej {r[s]['rej']:3d} dist {r[s]['dist']:5.1f}" if r[s]["n_ear"] else "")
                    for s in sets), flush=True)


if __name__ == "__main__":
    main()
