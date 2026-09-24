"""
Filler detector study (dev 009 + 026 only): candidate definitions of a filler's extent ('uh' = a sustained central
vowel, 'um' = that vowel + a nasal murmur) compared with the gold edges of every filler token, start and end,
continuous / pause, all and H.

    python -m aligner2.filler_eval            # summary per candidate
    python -m aligner2.filler_eval --list     # per filler token
"""
import argparse
import collections

import numpy as np

from aligner2 import fc_align, refine as R
from aligner2.gross import tclass
from aligner2.local_bench import clip_inputs

HOP, MS = R.HOP, R.MS
V = fc_align.VOCAB
VOWEL_IDS = [V[p] for p in ("AH", "ER", "UH", "AA", "AO")]       # central / back vowels a filler is heard as
NASAL_IDS = [V[p] for p in ("M", "N")]


def _runs(mask, merge=MS(20), min_len=MS(40)):
    idx = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0]))
    runs = [[a, b] for a, b in zip(idx[::2], idx[1::2])]
    out = []
    for r in runs:
        if out and r[0] - out[-1][1] <= merge:
            out[-1][1] = r[1]
        else:
            out.append(r)
    return [(a, b) for a, b in out if b - a >= min_len]


def fc_grid(z, T):
    """charsiu frame posteriors on the 2 ms grid: P(vowel class), P(nasal), P(silence)"""
    P = np.exp(z["fc_logp"].astype(float))
    tf = np.array([fc_align.frame_time(f) + fc_align.FRAME / 2 for f in range(len(P))])
    g = np.arange(T) * HOP
    return (np.interp(g, tf, P[:, VOWEL_IDS].sum(1)), np.interp(g, tf, P[:, NASAL_IDS].sum(1)),
            np.interp(g, tf, P[:, fc_align.SIL]))


def islands(S, pv, pn, a, b, kind, p99, is_um):
    """candidate islands in [a, b) -> list of (start, end) grid indices"""
    a, b = S.clip(a), S.clip(b)
    if b - a < MS(40):
        return []
    if kind == "fc":
        m = pv[a:b] >= 0.5
    elif kind == "fc_loud":
        m = (pv[a:b] >= 0.5) & (S.Ls[a:b] >= p99 - 35.0)
    elif kind == "dsp":
        ch = R._box(S.mfcc_change[a:b], MS(30))
        m = (S.per[a:b] >= 0.45) & (S.Ls[a:b] >= p99 - 30.0) & (ch <= np.median(S.mfcc_change))
    else:
        raise ValueError(kind)
    out = [(a + x, a + y) for x, y in _runs(m)]
    if is_um:                                    # 'um': extend each vowel island by a contiguous nasal murmur
        ext = []
        for x, y in out:
            e = y
            while e < b and (pn[e] >= 0.4 or (S.lo[e] >= -1.0 and S.per[e] >= 0.4)):
                e += 1
            ext.append((x, e))
        out = ext
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    res = collections.defaultdict(list); listing = []
    for c, z, ar, coarse, lx in clip_inputs(("009", "026")):
        S = R.Sig(z); p99 = np.percentile(S.L, 99); toks = c["tokens"]; n = len(toks)
        pv, pn, ps = fc_grid(z, S.T)
        new = R.refine(z, [t["text"] for t in toks], ar, coarse, lex=lx)
        j = 0
        while j < n:
            if tclass(toks[j]["text"]) != "filler":
                j += 1; continue
            j1 = j
            while j1 + 1 < n and tclass(toks[j1 + 1]["text"]) == "filler":
                j1 += 1                                      # a run of fillers j..j1 ('uh uh')
            m = j1 - j + 1
            # search window: from the previous word's last letter to the next word's first letter (reliable)
            a = lx["last"][j - 1] if j > 0 else R.MS(0)
            b = lx["first"][j1 + 1] if j1 + 1 < n else S.T - 1
            a = max(a, int(round(coarse[j]["start"] / HOP)) - MS(300))
            b = min(b, int(round(coarse[j1]["end"] / HOP)) + MS(300))
            is_um = [toks[q]["text"].lower().startswith(("um", "uhm")) for q in range(j, j1 + 1)]
            for kind in ("fc", "fc_loud", "dsp"):
                isl = islands(S, pv, pn, a, b, kind, p99, any(is_um))
                if len(isl) >= m:
                    isl = sorted(sorted(isl, key=lambda r: -(r[1] - r[0]))[:m])    # the m longest, in order
                    for q, (x, y) in zip(range(j, j1 + 1), isl):
                        for side, t in (("start", x), ("end", y)):
                            res[kind].append((side, q, c, t * HOP))
            for q in range(j, j1 + 1):
                for side in ("start", "end"):
                    res["refined"].append((side, q, c, new[q][side]))
                    res["v16"].append((side, q, c, coarse[q][side]))
                listing.append((c, q, toks, coarse, new))
            j = j1 + 1
    # score
    def kind_of(c, q, side):
        from aligner2.benchmark import _kind
        return _kind(c["tokens"], q, side)
    print(f"{'candidate':10} {'side':5} {'kind':5} {'n':>4} {'MAE':>6} {'med':>6} | {'H n':>4} {'H MAE':>6}")
    for name, rows in res.items():
        for side in ("start", "end"):
            for kd in ("cont", "pause", "edge"):
                E = [(t - c["tokens"][q][side]) * 1000 for s, q, c, t in rows if s == side and kind_of(c, q, side) == kd]
                H = [(t - c["tokens"][q][side]) * 1000 for s, q, c, t in rows
                     if s == side and kind_of(c, q, side) == kd and c["tokens"][q][f"{side}_human"]]
                if E:
                    print(f"{name:10} {side:5} {kd:5} {len(E):4} {np.abs(E).mean():6.1f} {np.median(E):+6.1f} | "
                          f"{len(H):4} {np.abs(H).mean() if H else 0:6.1f}")
    if args.list:
        idx = {name: {(id(c), q, s): t for s, q, c, t in rows} for name, rows in res.items()}
        for c, q, toks, coarse, new in listing:
            g = toks[q]
            line = f"{c['set']}-{int(c['clip']):02d} j{q:3} {g['text']:5} gold {g['start']:.3f}{'H' if g['start_human'] else ' '}-{g['end']:.3f}{'H' if g['end_human'] else ' '}"
            for name in ("refined", "fc", "dsp"):
                s_, e_ = idx[name].get((id(c), q, "start")), idx[name].get((id(c), q, "end"))
                line += f" | {name} " + (f"{(s_ - g['start']) * 1000:+5.0f}/{(e_ - g['end']) * 1000:+5.0f}" if s_ is not None else "   -  /  -  ")
            print(line)


if __name__ == "__main__":
    main()
