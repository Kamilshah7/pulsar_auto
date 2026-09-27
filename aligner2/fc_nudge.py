"""
EXPERIMENT (2026-09-27; the user: "2 sounds good" -- the 10 ms phone detector as an aligner step; the corrections
the user makes by ear are "at least 3-11 ms"). A final micro step after the rule stage, continuous junctions only:
the cut moves within +-radius of the rules' cut to where the 10 ms phone detector (charsiu frame classifier, the
engine's fc_logp) hears word 1's LAST phone before the cut and word 2's FIRST phone after it, minus a cost for moving
(|move| / tau: tau = seconds of move one nat of evidence buys). Training-free: a pretrained model + two numbers.
Evidence (aligner2/cue_ear_eval.py): on top of our cut it picks the user's accepted cut ~2.5 points more often in
every set. Evaluated with aligner2/fc_nudge_eval.py (verify.py's gold + ear scoring).
"""
import numpy as np

from aligner2 import fc_align

HOP = 0.002


def fc_on_grid(z):
    """charsiu log-probs (10 ms frames) interpolated onto the 2 ms signal grid: (T, 40) float32"""
    fc = z["fc_logp"].astype(np.float64); T = len(z["t"])
    centres = np.arange(len(fc)) * fc_align.FRAME + fc_align.FRAME_OFF
    g = np.arange(T) * HOP
    return np.stack([np.interp(g, centres, fc[:, j]) for j in range(fc.shape[1])], 1).astype(np.float32)


def _edge_phones(arpa, k):
    a, b = (arpa[k] or "").split(), (arpa[k + 1] or "").split()
    if not a or not b:
        return None, None
    return fc_align.VOCAB.get(a[-1]), fc_align.VOCAB.get(b[0])


def nudge(z, preds, arpa, radius=0.020, tau=0.004, win=0.040, clip_to_words=True, min_dur=0.020, fcg=None,
          trace=None):
    """preds: [{start, end}] after the rule stage -> the same with continuous junctions nudged"""
    fcg = fc_on_grid(z) if fcg is None else fcg
    T = len(fcg); R, W, M = int(round(radius / HOP)), int(round(win / HOP)), int(round(min_dur / HOP))
    out = [dict(p) for p in preds]
    for k in range(len(preds) - 1):
        e, s = preds[k]["end"], preds[k + 1]["start"]
        if abs(s - e) > 0.001:                              # a pause: not this step
            continue
        ph1, ph2 = _edge_phones(arpa, k)
        if ph1 is None or ph2 is None:
            continue
        i0 = int(round((e + s) / 2 / HOP))
        a0, b1 = int(round(preds[k]["start"] / HOP)), int(round(preds[k + 1]["end"] / HOP))
        lo, hi = max(i0 - R, a0 + M, 1), min(i0 + R, b1 - M, T - 2)
        if hi < lo:
            continue
        best, bi = -np.inf, i0
        for i in range(lo, hi + 1):
            l0 = max(i - W, a0) if clip_to_words else max(i - W, 0)
            r1 = min(i + W, b1) if clip_to_words else min(i + W, T)
            sc = fcg[l0:i, ph1].mean() + fcg[i:r1, ph2].mean() - abs(i - i0) * HOP / tau
            if sc > best:
                best, bi = sc, i
        if bi != i0:
            out[k]["end"] = out[k + 1]["start"] = bi * HOP
            if trace is not None:
                trace[k] = f"FCN {(bi - i0) * HOP * 1000:+.0f} ms"
    return out
