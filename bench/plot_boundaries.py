"""
Side-by-side diagnostic plots of continuous-speech boundaries: ones the human corrected
vs ones they accepted, for a given dispatch branch.

Each panel: spectrogram (0-8 kHz), 2 ms RMS in dB, waveform. Lines:
  green  = gold boundary          red   = ours
  grey   = CTC pipe span (p_start..p_end, the separator the model emitted between words)

    python bench/plot_boundaries.py --rows bench/prov_runs/b049_branches.json \
        --set bench/gold_sets/<dir> --branch case4 --out bench/diagnostic_plots/b049_case4.png
"""
import argparse
import json
import os
import random
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_gold_bench as RGB  # noqa: E402


def rms_db(x, sr, win_ms=2.0):
    w = max(1, int(sr * win_ms / 1000))
    c = np.cumsum(np.pad(x.astype(np.float64) ** 2, (0, w)))
    r = np.sqrt(np.maximum((c[w:] - c[:-w]) / w, 0))
    return 20 * np.log10(r + 1e-6)


def panel(axs, audio, sr, r, title):
    G = (r["gold_w1end"] + r["gold_w2start"]) / 2
    P = (r["pred_w1end"] + r["pred_w2start"]) / 2
    lo = max(0.0, min(G, P, r["p_start"]) - 0.18)
    hi = min(len(audio) / sr, max(G, P, r["p_end"]) + 0.18)
    seg = audio[int(lo * sr):int(hi * sr)]
    t = np.arange(len(seg)) / sr + lo
    ax_s, ax_r, ax_w = axs
    ax_s.specgram(seg, NFFT=256, Fs=sr, noverlap=224, cmap="magma", xextent=(lo, hi))
    ax_s.set_ylim(0, 8000)
    ax_r.plot(t, rms_db(seg, sr)[:len(t)], lw=0.7, color="k")
    ax_w.plot(t, seg, lw=0.4, color="k")
    for ax in axs:
        ax.axvspan(r["p_start"], r["p_end"], color="grey", alpha=0.18)
        ax.axvline(G, color="limegreen", lw=1.6)
        ax.axvline(P, color="red", lw=1.2, ls="--")
        ax.set_xlim(lo, hi)
        ax.tick_params(labelsize=6)
    ax_s.set_title(title, fontsize=7)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--n", type=int, default=4, help="examples per group")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    gt = json.load(open(os.path.join(args.set, "gt_per_clip.json"), encoding="utf-8"))
    RGB.AUDIO_DIRS.insert(0, os.path.join(args.set, "audio"))
    R = [r for r in json.load(open(args.rows, encoding="utf-8"))
         if r["branch"] == args.branch and r["gold_gap_ms"] <= 5 and r.get("p_start") is not None]
    fixed = [r for r in R if r["prov_w1end"] == "human" and r["prov_w2start"] == "human"]
    kept = [r for r in R if r["prov_w1end"] != "human" and r["prov_w2start"] != "human"]
    rnd = random.Random(args.seed)
    fixed = rnd.sample(fixed, min(args.n, len(fixed)))
    kept = rnd.sample(kept, min(args.n, len(kept)))

    n = max(len(fixed), len(kept))
    fig, axes = plt.subplots(3 * n, 2, figsize=(11, 3.1 * n),
                             gridspec_kw={"height_ratios": [2, 1, 1] * n})
    audio_cache = {}
    for col, (group, name) in enumerate(((fixed, "CORRECTED by human"), (kept, "ACCEPTED by human"))):
        for k in range(n):
            axs = [axes[3 * k + j][col] for j in range(3)]
            if k >= len(group):
                for a in axs:
                    a.axis("off")
                continue
            r = group[k]
            fn = gt[r["clip"]]["filename"]
            if fn not in audio_cache:
                a, sr = sf.read(RGB.find_wav(fn))
                audio_cache[fn] = (a.mean(1) if a.ndim > 1 else a, sr)
            audio, sr = audio_cache[fn]
            G = (r["gold_w1end"] + r["gold_w2start"]) / 2
            P = (r["pred_w1end"] + r["pred_w2start"]) / 2
            panel(axs, audio, sr, r, f"{name} | clip {r['clip']} #{r['i']}  '{r['w1']}' -> '{r['w2']}'  "
                                      f"ours-gold {1000 * (P - G):+.0f}ms")
    fig.suptitle(f"{args.branch}: green=gold  red dashed=ours  grey=CTC pipe", fontsize=9)
    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=110)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
