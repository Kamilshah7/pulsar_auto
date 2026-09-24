"""
Numeric table per word boundary for the deep full-read (bench/cache/aligner2/fullread/NOTES.md).

Reads the cached signals (bench/cache/aligner2/<key>_98e63a51.npz, mapped to clips by
bench/tools/clip_cache_map.json) -- no GPU, no torch. Gold = bench/gold_sets, system = aligner2 v16.

    python bench/tools/joins.py 026_01 23 31          # joins 23..31 (token j | token j+1)
    python bench/tools/joins.py 026_01 tok            # token table (gold / system / H flags)
    python bench/tools/joins.py 026_01 win 6.40 6.70 4   # free window, 4 ms rows

Columns: t, dB99 = loudness re clip p99, dBfl = dB over the local floor (min of 50 ms-smoothed loudness
within +-1 s), per = periodicity, flat = log spectral flatness, cent = log centroid (ln Hz), hi / lo =
dB share above 4 kHz / below 400 Hz, zcr, trn = >2 kHz 3 ms jump (dB), glo = LPC-residual crest (dB),
mfc = mfcc_change, fvel = formant_vel, sep = P(word separator), blk = P(blank), ctc = letter argmax of
the 20 ms HuBERT frame (second candidate when >= .10; '.' blank, '_' separator). Markers: G:/S: =
gold / system token edges falling in the row's bin [t, t+step).
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.path.join(ROOT, "bench", "cache", "aligner2")
SYS_RUN = os.path.join(ROOT, "bench", "prov_runs", "aligner2_v16.json")
HOP = 0.002
FRAME = 0.020
CONT_MAX_GAP = 0.005
LETTERS = ["<pad>", "<s>", "</s>", "<unk>", "|", "E", "T", "A", "O", "N", "I", "H", "S", "R", "D", "L", "U", "M", "W",
           "C", "F", "G", "Y", "P", "B", "V", "K", "'", "X", "J", "Q", "Z"]
SHOW = {0: ".", 4: "_"}
_CLIPS = {}


def load(clip_id):
    """clip_id '026_01' -> dict(z=signals, gold=[tokens], sys=[{start,end}], extra series)"""
    if clip_id in _CLIPS:
        return _CLIPS[clip_id]
    sys.path.insert(0, ROOT)
    from aligner2.benchmark import load_sets
    set_name, clip = clip_id.split("_")
    m = json.load(open(os.path.join(HERE, "clip_cache_map.json")))[clip_id]
    zf = np.load(os.path.join(CACHE, m["npz"]))
    z = {k: zf[k] for k in zf.files}
    c = [c for c in load_sets((set_name,)) if int(c["clip"]) == int(clip)][0]
    R = json.load(open(SYS_RUN))
    sp = (R["grid_preds"][0] if R.get("grid_preds") else R["preds"])[f"{set_name}|{int(clip)}"]
    L = z["loudness"].astype(float)
    Ls = np.convolve(L, np.ones(25) / 25, "same")           # 50 ms boxcar on the 2 ms grid
    w = int(1.0 / HOP)
    floor = np.array([Ls[max(0, i - w): i + w + 1].min() for i in range(len(L))])
    D = {"z": z, "gold": c["tokens"], "sys": sp, "p99": np.percentile(L, 99), "floor": floor,
         "p": np.exp(z["ctc_logp"].astype(float))}
    _CLIPS[clip_id] = D
    return D


def ctc_str(D, t):
    p = D["p"]
    k = min(len(p) - 1, max(0, int(t / FRAME)))
    o = np.argsort(p[k])[::-1]
    s = f"{SHOW.get(o[0], LETTERS[o[0]])}{p[k][o[0]]:.2f}"
    if p[k][o[1]] >= 0.10:
        s += f"/{SHOW.get(o[1], LETTERS[o[1]])}{p[k][o[1]]:.2f}"
    return s


def table(D, t0, t1, step_ms=None, marks=()):
    z = D["z"]
    span = t1 - t0
    if step_ms is None:
        step_ms = 6 if span <= 0.150 else 2 * int(np.ceil(span * 1000 / 25 / 2))
    st = int(round(step_ms / 2))
    a = int(t0 / HOP); b = int(t1 / HOP)
    T = len(z["loudness"])
    out = ["      t dB99 dBfl  per  flat cent    hi    lo  zcr  trn  glo  mfc fvel  sep  blk ctc"]
    for i in range(a, min(b, T), st):
        t = i * HOP
        L = z["loudness"][i]
        row = (f"{t:7.3f} {L - D['p99']:4.0f} {L - D['floor'][i]:4.0f} {z['periodicity'][i]:4.2f} {z['flatness'][i]:5.1f}"
               f" {z['centroid'][i]:4.1f} {z['high_ratio'][i]:5.1f} {z['low_ratio'][i]:5.1f} {z['zcr'][i]:4.2f}"
               f" {z['transient'][i]:4.1f} {z['glottal'][i]:4.1f} {z['mfcc_change'][i]:4.1f} {z['formant_vel'][i]:4.1f}"
               f" {z['ctc_wordsep'][i]:4.2f} {z['ctc_blank'][i]:4.2f} ")
        ctc = ctc_str(D, t)
        mk = [lab for (tm, lab) in marks if t - 1e-9 <= tm < t + st * HOP - 1e-9]
        out.append(row + f"{ctc:<13}" + (" " + " ".join(mk) if mk else ""))
    return "\n".join(out)


def fmt(t):
    return f"{t:.3f}"


def hflag(g, side):
    return "H" if g[f"{side}_human"] else ""


def joins(clip_id, j0, j1):
    D = load(clip_id)
    G, S = D["gold"], D["sys"]
    out = []
    for j in range(j0, j1 + 1):
        if j >= len(G):
            break
        last = j == len(G) - 1
        a, bb = G[j], (None if last else G[j + 1])
        sa, sb = S[j], (None if last else S[j + 1])
        marks = [(a["end"], f"G:{a['text']}.e"), (sa["end"], f"S:{a['text']}.e")]
        if last:
            name = f"END {a['text']}"
            hdr = f"end g {fmt(a['end'])}{hflag(a, 'end')} s {fmt(sa['end'])} ({(sa['end'] - a['end']) * 1000:+.0f})"
            lo, hi = min(a["end"], sa["end"]) - 0.030, max(a["end"], sa["end"]) + 0.080
            out.append(f"--- {name}  {hdr}  [{lo:.3f}-{hi:.3f}]")
            out.append(table(D, lo, hi, marks=marks))
            continue
        marks += [(bb["start"], f"G:{bb['text']}.s"), (sb["start"], f"S:{bb['text']}.s")]
        name = f"{a['text']}|{bb['text']}"
        hdr = (f"end g {fmt(a['end'])}{hflag(a, 'end')} s {fmt(sa['end'])} ({(sa['end'] - a['end']) * 1000:+.0f})  "
               f"start g {fmt(bb['start'])}{hflag(bb, 'start')} s {fmt(sb['start'])} ({(sb['start'] - bb['start']) * 1000:+.0f})")
        if j == 0:
            lo, hi = max(0.0, min(a["start"], sa["start"]) - 0.070), max(a["start"], sa["start"]) + 0.030
            out.append(f"--- START {a['text']}  start g {fmt(a['start'])}{hflag(a, 'start')} s {fmt(sa['start'])}"
                       f" ({(sa['start'] - a['start']) * 1000:+.0f})  [{lo:.3f}-{hi:.3f}]")
            out.append(table(D, lo, hi, marks=[(a["start"], f"G:{a['text']}.s"), (sa["start"], f"S:{a['text']}.s")]))
        gap = bb["start"] - a["end"]
        sgap = sb["start"] - sa["end"]
        e_lo, e_hi = min(a["end"], sa["end"]) - 0.030, max(a["end"], sa["end"]) + 0.030
        s_lo, s_hi = min(bb["start"], sb["start"]) - 0.030, max(bb["start"], sb["start"]) + 0.030
        if (gap > CONT_MAX_GAP or sgap > CONT_MAX_GAP) and s_lo > e_hi:
            # pause: longer look past the end (tails) and before the start (pre-onset events)
            e_hi = min(e_hi + 0.050, s_lo - 0.010)
            s_lo = max(s_lo - 0.040, e_hi + 0.010)
            out.append(f"--- END {name}  {hdr}  [{e_lo:.3f}-{e_hi:.3f}]")
            out.append(table(D, e_lo, e_hi, marks=marks))
            out.append(f"--- START {name}  {hdr}  [{s_lo:.3f}-{s_hi:.3f}]")
            out.append(table(D, s_lo, s_hi, marks=marks))
        else:
            lo, hi = min(e_lo, s_lo), max(e_hi, s_hi)
            out.append(f"--- {name}  {hdr}  [{lo:.3f}-{hi:.3f}]")
            out.append(table(D, lo, hi, marks=marks))
    return "\n".join(out)


def toktab(clip_id):
    D = load(clip_id)
    out = [f"{'j':>3} {'text':<14} {'g.start':>8} {'s.start':>8} {'err':>5}   {'g.end':>8} {'s.end':>8} {'err':>5}  gap"]
    for j, (g, s) in enumerate(zip(D["gold"], D["sys"])):
        gap = "" if j == len(D["gold"]) - 1 else f"{(D['gold'][j + 1]['start'] - g['end']) * 1000:.0f}"
        out.append(f"{j:>3} {g['text']:<14} {g['start']:8.3f}{hflag(g, 'start'):1} {s['start']:7.3f} "
                   f"{(s['start'] - g['start']) * 1000:+5.0f}   {g['end']:8.3f}{hflag(g, 'end'):1} {s['end']:7.3f} "
                   f"{(s['end'] - g['end']) * 1000:+5.0f}  {gap}")
    return "\n".join(out)


if __name__ == "__main__":
    cid = sys.argv[1]
    if sys.argv[2] == "tok":
        print(toktab(cid))
    elif sys.argv[2] == "win":
        D = load(cid)
        t0, t1 = float(sys.argv[3]), float(sys.argv[4])
        step = float(sys.argv[5]) if len(sys.argv) > 5 else None
        mk = [(g["start"], f"G:{g['text']}.s") for g in D["gold"]] + [(g["end"], f"G:{g['text']}.e") for g in D["gold"]]
        mk += [(s["start"], f"S:{g['text']}.s") for g, s in zip(D["gold"], D["sys"])]
        mk += [(s["end"], f"S:{g['text']}.e") for g, s in zip(D["gold"], D["sys"])]
        print(table(D, t0, t1, step, mk))
    else:
        print(joins(cid, int(sys.argv[2]), int(sys.argv[3])))
