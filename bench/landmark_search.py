"""
Per-leaf landmark search: which acoustic event do the human's boundaries sit at a
CONSISTENT offset from?

For every continuous-speech leaf with >= MIN_N human-corrected pairs on DEV, compute ~18
landmarks in a window around the CTC pipe, learn one offset per landmark = median(gold -
landmark) on DEV corrected pairs ONLY, then score:
  dev corrected   (in-sample: the offset was fitted here)
  test corrected  (out-of-sample: same frozen offset)
  dev accepted    how far the rule would move boundaries the human accepted (collateral)

    python bench/landmark_search.py --dev-rows R1 --dev-set DIR --test-rows R2 --out out.json
"""
import argparse
import collections
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_gold_bench as RGB  # noqa: E402

MIN_N = 5
FEAT = {}


def feats(path):
    """2ms RMS (per sample) + 20ms/2ms-hop frame features: HF ratio (>=4 kHz), voicing
    (normalised autocorrelation peak, 70-400 Hz), spectral flux, log spectrum."""
    if path in FEAT:
        return FEAT[path]
    d, sr = sf.read(path); d = d.mean(1) if d.ndim > 1 else d
    wr = max(1, int(sr * 0.002)); c = np.cumsum(np.pad(d.astype(float) ** 2, (0, wr)))
    rms = np.sqrt(np.maximum((c[wr:] - c[:-wr]) / wr, 0))
    fl = int(sr * 0.020); hop = wr; nf = max(1, (len(d) - fl) // hop + 1)
    fr = d[np.arange(fl)[None, :] + (np.arange(nf) * hop)[:, None]].astype(float)
    fr -= fr.mean(1, keepdims=True)
    spec = np.abs(np.fft.rfft(fr * np.hanning(fl)[None, :], axis=1)); freqs = np.fft.rfftfreq(fl, 1 / sr)
    p2 = spec ** 2
    hf = p2[:, freqs >= 4000].sum(1) / (p2.sum(1) + 1e-12)
    sn = spec / (spec.sum(1, keepdims=True) + 1e-12)
    flux = np.r_[0, np.sqrt(np.sum(np.maximum(np.diff(sn, axis=0), 0) ** 2, axis=1))]
    nfft = 1 << (2 * fl - 1).bit_length()
    F_ = np.fft.rfft(fr, n=nfft, axis=1); ac = np.fft.irfft((F_ * np.conj(F_)).real, n=nfft, axis=1)[:, :fl]
    lo, hi_ = max(1, int(sr / 400)), min(fl - 1, int(sr / 70))
    vox = np.clip(ac[:, lo:hi_].max(1) / np.maximum(ac[:, 0], 1e-9), 0, 1)
    FEAT[path] = dict(sr=sr, rms=rms, hop=hop, fl=fl, hf=hf, vox=vox, flux=flux, lspec=np.log(spec + 1e-9))
    return FEAT[path]


def cur(r): return (r["pred_w1end"] + r["pred_w2start"]) / 2
def gold(r): return (r["gold_w1end"] + r["gold_w2start"]) / 2


def landmarks(r, F):
    sr, hop, fl = F["sr"], F["hop"], F["fl"]
    t0, t1 = r["p_start"] - 0.080, r["p_end"] + 0.040
    a, b = max(0, int(t0 * sr)), min(len(F["rms"]), int(t1 * sr))
    fa, fb = max(0, int((t0 * sr - fl / 2) / hop)), min(len(F["hf"]), int((t1 * sr - fl / 2) / hop))
    ft = lambda k: (k * hop + fl / 2) / sr
    out = {"current": cur(r), "p_start": r["p_start"], "p_mid": r["p_mid"], "p_end": r["p_end"],
           "raw_w1_end": r.get("in_w1_end", cur(r)), "raw_w2_start": r.get("in_w2_start", cur(r))}
    if b - a < int(0.030 * sr) or fb - fa < 10:
        return out
    db = 20 * np.log10(F["rms"][a:b] + 1e-6)
    out["rms_dip"] = (a + int(np.argmin(db))) / sr
    for w_ms in (3, 10, 20):
        w = int(w_ms / 1000 * sr); d = db[w:] - db[:-w]
        out[f"rise{w_ms}"] = (a + int(np.argmax(d)) + w // 2) / sr
        out[f"fall{w_ms}"] = (a + int(np.argmin(d)) + w // 2) / sr
    for name, x in (("vox", F["vox"]), ("hf", F["hf"])):
        s = 5; seg = x[fa:fb]
        if len(seg) > 2 * s:
            d = seg[s:] - seg[:-s]
            out[f"{name}_on"] = ft(fa + int(np.argmax(d)) + s // 2)
            out[f"{name}_off"] = ft(fa + int(np.argmin(d)) + s // 2)
    out["flux_max"] = ft(fa + int(np.argmax(F["flux"][fa:fb])))

    # Stop-consonant cues (2026-09-23). Every remaining failure the listener described was a stop
    # on the wrong side of the cut ("proud di", "banged dup", "like ka"): the human keeps a stop's
    # closure AND release with the word it belongs to.
    #   burst_end     w1 ends in a stop: release = sharpest 3ms energy jump (>= 9 dB); its end = first
    #                 frame after it with voicing >= 0.5 (next sound voiced), else where HF energy
    #                 falls below half its post-release peak, capped 70ms (aspiration).
    #   closure_start w2 starts with a stop: steepest 10ms energy fall before the release (or in the
    #                 window if no release is found) = start of w2's closure silence.
    w3 = int(0.003 * sr); d3 = db[w3:] - db[:-w3]
    rel = None
    if len(d3) and float(np.max(d3)) >= 9.0:
        rel = a + int(np.argmax(d3)) + w3 // 2
        k0 = int((rel - fl / 2) / hop); k1 = min(len(F["vox"]), k0 + int(0.070 * sr / hop))
        end = None
        if k1 > k0:
            v = F["vox"][k0:k1]; hi = np.where(v >= 0.5)[0]
            if len(hi):
                end = ft(k0 + int(hi[0]))
            else:
                h = F["hf"][k0:k1]; pk = int(np.argmax(h[:max(1, int(0.015 * sr / hop))]))
                lo = np.where(h[pk:] < 0.5 * h[pk])[0]
                end = ft(k0 + pk + int(lo[0])) if len(lo) else ft(k1 - 1)
        if end is not None and end > rel / sr:
            out["burst_end"] = end
    w10 = int(0.010 * sr); stop_at = (rel - a) if rel is not None else len(db)
    seg = db[:max(0, stop_at)]
    if len(seg) > w10 + 2:
        dd = seg[w10:] - seg[:-w10]
        out["closure_start"] = (a + int(np.argmin(dd)) + w10 // 2) / sr
    s = 10; best, bi = -1, None
    for k in range(max(fa, s), min(fb, len(F["lspec"]) - s)):
        dd = np.linalg.norm(F["lspec"][k - s:k].mean(0) - F["lspec"][k:k + s].mean(0))
        if dd > best:
            best, bi = dd, k
    if bi is not None:
        out["spec_change"] = ft(bi)
    return out


def load(rows_p, gt, human_tag):
    R = [r for r in json.load(open(rows_p, encoding="utf-8")) if r["gold_gap_ms"] <= 5 and r.get("p_start") is not None]
    for r in R:
        r["_lm"] = landmarks(r, feats(RGB.find_wav(gt[r["clip"]]["filename"])))
        r["_fixed"] = r["prov_w1end"] == human_tag and r["prov_w2start"] == human_tag
        r["_kept"] = r["prov_w1end"] != human_tag and r["prov_w2start"] != human_tag and abs(cur(r) - gold(r)) * 1000 <= 2
        r["_key"] = f'{r["branch"]}|{r["leaf_line"]}'
    return R


def stats(e):
    e = np.abs(np.asarray(e)) * 1000
    return {"n": int(len(e)), "mae": float(e.mean()) if len(e) else None,
            "w5": float(np.mean(e <= 5) * 100) if len(e) else None, "w10": float(np.mean(e <= 10) * 100) if len(e) else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-rows", required=True); ap.add_argument("--dev-set", required=True)
    ap.add_argument("--test-rows", required=True); ap.add_argument("--out", required=True)
    args = ap.parse_args()
    RGB.AUDIO_DIRS.insert(0, os.path.join(args.dev_set, "audio"))
    gdev = json.load(open(os.path.join(args.dev_set, "gt_per_clip.json"), encoding="utf-8"))
    gtest = json.load(open(os.path.join(os.path.dirname(HERE), "bench", "gt_per_clip.json"), encoding="utf-8"))
    D = load(args.dev_rows, gdev, "human"); T = load(args.test_rows, gtest, "dragged")
    keys = [k for k, n in collections.Counter(r["_key"] for r in D if r["_fixed"]).most_common() if n >= MIN_N]
    report = {}
    for key in keys:
        dF = [r for r in D if r["_key"] == key and r["_fixed"]]; dK = [r for r in D if r["_key"] == key and r["_kept"]]
        tF = [r for r in T if r["_key"] == key and r["_fixed"]]
        rows = []
        for lm in sorted({k for r in dF for k in r["_lm"]}):
            off = [gold(r) - r["_lm"][lm] for r in dF if lm in r["_lm"]]
            if len(off) < MIN_N:
                continue
            o = float(np.median(off)); iqr = float(np.percentile(off, 75) - np.percentile(off, 25))
            pred = lambda r: (r["_lm"][lm] + o) if lm in r["_lm"] else cur(r)
            rows.append({"landmark": lm, "offset_ms": o * 1000, "iqr_ms": iqr * 1000,
                         "dev": stats([pred(r) - gold(r) for r in dF]), "test": stats([pred(r) - gold(r) for r in tF]),
                         "acc_move_med": float(np.median([abs(pred(r) - cur(r)) for r in dK]) * 1000) if dK else None,
                         "acc_move_gt10": int(sum(abs(pred(r) - cur(r)) > 0.010 for r in dK)), "acc_n": len(dK)})
        base = {"dev": stats([cur(r) - gold(r) for r in dF]), "test": stats([cur(r) - gold(r) for r in tF])}
        report[key] = {"src": dF[0]["leaf_src"], "base": base, "rows": rows}
        print(f"\n### {key}  {(dF[0]['leaf_src'] or 'no bnd=')[:60]}")
        print(f"   {'landmark':<14}{'offset':>8}{'IQR':>7} | {'DEV corr':^19} | {'TEST corr (held-out)':^20} | accepted move")
        f = lambda s: f"{s['mae']:5.1f} {s['w5']:3.0f}% {s['w10']:3.0f}%" if s["n"] else "   n/a         "
        print(f"   {'CURRENT':<14}{'':>8}{'':>7} | {f(base['dev'])} n={base['dev']['n']:<3}| {f(base['test'])} n={base['test']['n']:<3} |")
        for x in sorted(rows, key=lambda x: x["iqr_ms"])[:8]:
            better = (x["dev"]["mae"] < base["dev"]["mae"] and x["test"]["n"] and x["test"]["mae"] < base["test"]["mae"])
            print(f"   {x['landmark']:<14}{x['offset_ms']:+8.1f}{x['iqr_ms']:7.1f} | {f(x['dev'])}      | {f(x['test'])}      | "
                  f"med {x['acc_move_med'] or 0:5.1f} >10: {x['acc_move_gt10']}/{x['acc_n']}{'   <- both' if better else ''}")
    json.dump(report, open(args.out, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
