"""
Per-clip choice between the original audio and an enhanced version (EXPERIMENTAL): keep the version under which the
TRANSCRIPT is more probable for the letter model (HuBERT CTC forward-backward log-likelihood per frame, the same
lexical model the aligner uses). Enhancement then only replaces clips where it makes the words clearer to the model.
Uses the cached predictions of aligner2/preprocess_eval.py and signals downloaded by aligner2/hybrid_eval.py.

    python -m aligner2.select_eval --variant e_dns64 --conds clean,noise20,noise10,reverb,band4k
"""
import argparse
import json
import os

import numpy as np

from aligner2 import lexical
from aligner2.benchmark import BENCH, load_sets
from aligner2.hybrid_eval import LOCAL, _suffix, fetch
from aligner2.signals import clip_key


def ctc_score(z, texts):
    """mean log-likelihood per frame of the transcript's letter sequence (4 frame phases averaged)"""
    labels, _, _ = lexical.label_sequence(texts)
    out = []
    for k in ("ctc_logp", "ctc_logp_s80", "ctc_logp_s160", "ctc_logp_s240"):
        if k in z:
            lp = z[k].astype(float)
            _, logZ = lexical.forward_backward(lp, labels)
            out.append(logZ / len(lp))
    return float(np.mean(out))


def load(c, variant, deg):
    if variant == "none" and deg == "clean":
        from aligner2.local_coarse import load_z
        return load_z(c)
    zf = np.load(os.path.join(LOCAL, f"{clip_key(c['wav'])}{_suffix(variant, deg)}.npz"))
    return {k: zf[k] for k in ("ctc_logp", "ctc_logp_s80", "ctc_logp_s160", "ctc_logp_s240") if k in zf.files}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="e_dns64")
    ap.add_argument("--conds", default="clean,noise20,noise10,reverb,band4k")
    ap.add_argument("--sets", default="026,049"); ap.add_argument("--margin", type=float, default=0.0)
    args = ap.parse_args()
    from aligner2.preprocess_eval import run_variant, score
    from aligner2.verify import ear_items
    clips = load_sets(tuple(args.sets.split(","))); J = ear_items()
    for deg in args.conds.split(","):
        fetch(args.variant, clips, deg)
        if deg != "clean":
            fetch("none", clips, deg)
        A, B = run_variant("none", clips, deg), run_variant(args.variant, clips, deg)
        pick, n_enh = {}, 0
        for c in clips:
            texts = [t["text"] for t in c["tokens"]]
            sa, sb = ctc_score(load(c, "none", deg), texts), ctc_score(load(c, args.variant, deg), texts)
            k = (c["set"], str(c["clip"]))
            use = sb > sa + args.margin
            pick[k] = B[k] if use else A[k]; n_enh += use
        ra, rb, rs = score(A, clips, J), score(B, clips, J), score(pick, clips, J)
        line = " | ".join(f"{s} MAE {ra[s]['mae']:5.2f} / {rb[s]['mae']:5.2f} / {rs[s]['mae']:5.2f}  H {ra[s]['h']:5.2f} / {rb[s]['h']:5.2f} / {rs[s]['h']:5.2f}"
                          f"  acc {ra[s]['acc']}/{rb[s]['acc']}/{rs[s]['acc']} rej {ra[s]['rej']}/{rb[s]['rej']}/{rs[s]['rej']}" for s in ra)
        print(f"{deg:8} enhanced chosen for {n_enh:2}/{len(clips)} clips | never / always / chosen: {line}", flush=True)


if __name__ == "__main__":
    main()
