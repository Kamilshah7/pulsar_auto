"""
EXPERIMENT (2026-09-27, step 3 of the micro-adjustment plan): junctions next to a STOP, which the phone-detector nudge
(aligner2/fc_nudge.py) skips -- a stop's closure is silence, the detector cannot place it. The ear's criterion there is
physical: word 2 must not start with the release burst of word 1's stop ("that|is": the burst and aspiration belong
to "that"), and a cut into a stop ("the|time") should sit in the closure's silence, not in word 1's audible decay or on
word 2's burst. Measured at 1 ms from the raw audio (3 ms windows): on the ear pairs 0-10 ms apart, "no high-band energy
in the 4 ms after the cut" prefers the accepted cut 69 % (stop>X, n 94) and "the quietest cut" 76 % (X>stop, n 21).

The cut moves within +-radius to minimise  hf_after(t) [+ level(t) for X>stop]  +  |move| * cost  (dB, dB per ms), where
hf_after = the loudest first-difference (high-band) energy in [t, t + 4 ms] above the local floor and level = the
loudest broadband energy in [t - 3, t + 3 ms] above the closure floor.
"""
import numpy as np

STOPS = {"P", "B", "T", "D", "K", "G"}
SR, HOPMS = 16000, 0.001


def envelopes(x):
    """broadband and high-band (first difference) energy in dB, 3 ms windows, 1 ms hop"""
    w = int(0.003 * SR); h = int(HOPMS * SR)
    n = len(x) // h
    d = np.diff(x, prepend=x[0])
    idx = np.clip(np.arange(n)[:, None] * h + np.arange(-w // 2, w // 2)[None, :], 0, len(x) - 1)
    E = 10 * np.log10(np.mean(x[idx] ** 2, 1) + 1e-12)
    H = 10 * np.log10(np.mean(d[idx] ** 2, 1) + 1e-12)
    return E, H


def nudge(x_or_env, preds, arpa, radius=0.008, cost=1.0, groups=("stop>X", "X>stop"), trace=None):
    E, H = envelopes(x_or_env) if not isinstance(x_or_env, tuple) else x_or_env
    n = len(E); R = int(round(radius / HOPMS))
    out = [dict(p) for p in preds]
    for k in range(len(preds) - 1):
        e, s = preds[k]["end"], preds[k + 1]["start"]
        if not -0.001 <= s - e <= 0.005:
            continue
        a, b = (arpa[k] or "").split(), (arpa[k + 1] or "").split()
        if not a or not b:
            continue
        s1, s2 = a[-1] in STOPS, b[0] in STOPS
        grp = "stop>X" if s1 and not s2 else "X>stop" if s2 and not s1 else "stop>stop" if s1 and s2 else None
        if grp not in groups:
            continue
        t0 = (e + s) / 2; i0 = int(round(t0 / HOPMS))
        lo, hi = max(i0 - R, 60, int(preds[k]["start"] / HOPMS) + 20), min(i0 + R, n - 70, int(preds[k + 1]["end"] / HOPMS) - 20)
        if hi < lo:
            continue
        floorE = E[max(0, i0 - 40):i0 + 60].min(); floorH = H[max(0, i0 - 40):i0 + 60].min()
        best, bi = np.inf, i0
        for i in range(lo, hi + 1):
            c = H[i:i + 5].max() - floorH
            if grp != "stop>X":
                c += E[i - 3:i + 4].max() - floorE
            c += abs(i - i0) * cost
            if c < best:
                best, bi = c, i
        if bi != i0:
            d = bi * HOPMS - t0
            out[k]["end"] = e + d; out[k + 1]["start"] = s + d
            if trace is not None:
                trace[k] = f"SN {d * 1000:+.0f} ms"
    return out
