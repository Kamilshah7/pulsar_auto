"""
Hybrid pre-processing test: the NEURAL signals (HuBERT CTC letters, xlsr phones, charsiu phones, CTC-derived tracks,
SSL change, speech probability) from pre-processed audio, the DSP signals (loudness, zcr, periodicity, spectra,
transients...) from the ORIGINAL audio -- so the rule stage's floor / p99-relative thresholds keep their calibration.
The coarse stage runs locally (aligner2/local_coarse.py), then the rules; scored like aligner2/verify.py.

    python -m aligner2.hybrid_eval --variant denoise          # fetches <clip key>_pp_denoise from the Modal volume
    python -m aligner2.hybrid_eval --variant denoise --degrade noise20 --sets 026,049
                          # DSP from the degraded audio (<key>_dg_noise20_pp_none), neural from _dg_noise20_pp_denoise
"""
import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from aligner2.benchmark import BENCH, load_sets

NEURAL = ("ctc_logp", "ctc_logp_s80", "ctc_logp_s160", "ctc_logp_s240", "phone_logp", "fc_logp", "ctc_blank",
          "ctc_wordsep", "ctc_change", "ssl_change", "speech_prob")
SETS = ("009", "026", "049", "old14")
LOCAL = os.path.join(BENCH, "cache", "aligner2", "preproc")


def _suffix(variant, deg):
    return f"_pp_{variant}" if deg == "clean" else f"_dg_{deg}_pp_{variant}"


def fetch(variant, clips, deg="clean"):
    """download the pre-processed signals once (np.savez next to the production cache, in preproc/)"""
    from aligner2 import remote
    from aligner2.signals import clip_key
    os.makedirs(LOCAL, exist_ok=True)
    todo = [c for c in clips if not os.path.exists(os.path.join(LOCAL, f"{clip_key(c['wav'])}{_suffix(variant, deg)}.npz"))]
    try:
        for c in todo:
            key = f"{clip_key(c['wav'])}{_suffix(variant, deg)}"
            z = remote._obj().signals.remote(key, b"", True)
            np.savez_compressed(os.path.join(LOCAL, key + ".npz"), **{k: np.asarray(v) for k, v in z.items()})
    finally:
        if todo:
            remote.stop_containers("(hybrid fetch done)")


def _clip(args):
    c, variant, deg, swap = args
    import torch
    torch.set_num_threads(1)
    from aligner2 import local_coarse, refine
    from aligner2.signals import clip_key
    if deg == "clean":
        z0 = local_coarse.load_z(c) if c["set"] != "old14" else _load_old14(c)
    else:
        zb = np.load(os.path.join(LOCAL, f"{clip_key(c['wav'])}{_suffix('none', deg)}.npz"))
        z0 = {k: zb[k] for k in zb.files}
    z = dict(z0)
    if swap:
        zf = np.load(os.path.join(LOCAL, f"{clip_key(c['wav'])}{_suffix(variant, deg)}.npz"))
        for k in NEURAL:
            if k in zf.files:
                z[k] = zf[k]
    coarse, fc_strs = local_coarse.coarse(c, z=z)
    texts = [t["text"] for t in c["tokens"]]
    lx = refine.lexical_peaks(z, texts)
    return (c["set"], str(c["clip"])), refine.refine(z, texts, fc_strs, coarse, lex=lx)


def _load_old14(c):
    from aligner2.local_bench import CACHE
    from aligner2.signals import clip_key
    zf = np.load(os.path.join(CACHE, clip_key(c["wav"]) + "_98e63a51.npz"))
    return {k: zf[k] for k in zf.files}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="denoise"); ap.add_argument("--sets", default=",".join(SETS))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--degrade", default="clean")
    args = ap.parse_args()
    sets = tuple(args.sets.split(","))
    clips = load_sets(sets)
    fetch(args.variant, clips, args.degrade)
    if args.degrade != "clean":
        fetch("none", clips, args.degrade)
    tag = args.variant if args.degrade == "clean" else f"{args.degrade}_{args.variant}"
    with ProcessPoolExecutor(args.workers) as ex:
        preds = dict(ex.map(_clip, [(c, args.variant, args.degrade, True) for c in clips]))
    out = os.path.join(BENCH, "prov_runs", f"preproc_hybrid_{tag}.json")
    json.dump({"|".join(k): v for k, v in preds.items()}, open(out, "w"))
    from aligner2.preprocess_eval import run_variant, score
    from aligner2.verify import ear_items
    J = ear_items()
    base = score(run_variant("none", clips, args.degrade), clips, J)
    full = score(run_variant(args.variant, clips, args.degrade), clips, J)
    hyb = score(preds, clips, J)
    print(f"[{args.degrade}] none -> full {args.variant} / hybrid ({args.variant} neural + unprocessed DSP)")
    for s in sets:
        b, f, h = base[s], full[s], hyb[s]
        ear = (f"| ear acc {b['acc']} / {f['acc']} / {h['acc']}  rej {b['rej']} / {f['rej']} / {h['rej']}  "
               f"dist {b['dist']:.1f} / {f['dist']:.1f} / {h['dist']:.1f}" if b["n_ear"] else "")
        print(f"  {s:6} MAE {b['mae']:.2f} / {f['mae']:.2f} / {h['mae']:.2f}   H {b['h']:.2f} / {f['h']:.2f} / {h['h']:.2f} {ear}")
    return
    for s in sets:
        b, h = base[s], hyb[s]
        ear = (f"| ear acc {b['acc']}->{h['acc']} rej {b['rej']}->{h['rej']} dist {b['dist']:.1f}->{h['dist']:.1f}"
               if b["n_ear"] else "")
        print(f"  {s:6} MAE {b['mae']:.2f} -> {h['mae']:.2f}  H {b['h']:.2f} -> {h['h']:.2f} {ear}")


if __name__ == "__main__":
    main()
