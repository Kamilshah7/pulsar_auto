"""
Formant landmarks for sonorant joins (vowel/glide/liquid/nasal on both sides), where energy and
voicing run straight through the boundary and only the resonances move.

Per 25ms frame (2ms hop) in [p_start-80ms, p_end+40ms]: pre-emphasis, Hamming, LPC order 2+sr/1000
(autocorrelation / Levinson), formants = LPC root frequencies in 90-5000 Hz with bandwidth < 400 Hz,
median-smoothed over 5 frames. Landmarks:
  f1_min, f2_min, f2_max, f3_min      time of the extreme
  f1_rate, f2_rate, f3_rate           time of the fastest change over 10ms
  fmt_change                          time of the largest summed relative change of F1-F3 over 10ms
"""
import numpy as np
import soundfile as sf
from scipy.linalg import solve_toeplitz
from scipy.signal import medfilt

_WAV = {}


def _audio(path):
    if path not in _WAV:
        x, sr = sf.read(path, dtype="float64")
        _WAV[path] = (x.mean(1) if x.ndim > 1 else x, sr)
    return _WAV[path]


def tracks(path, t0, t1, hop_s=0.002, win_s=0.025):
    x, sr = _audio(path)
    order = 2 + sr // 1000
    wl = int(win_s * sr); win = np.hamming(wl)
    ts, F = [], []
    for t in np.arange(max(t0, win_s / 2), t1, hop_s):
        a = int(t * sr - wl / 2)
        if a < 0 or a + wl > len(x):
            continue
        fr = x[a:a + wl]; fr = np.append(fr[0], fr[1:] - 0.97 * fr[:-1]) * win
        r = np.correlate(fr, fr, "full")[wl - 1:wl + order]
        if r[0] <= 1e-10:
            continue
        try:
            c = solve_toeplitz(r[:order], -r[1:order + 1])
        except np.linalg.LinAlgError:
            continue
        roots = np.roots(np.r_[1, c]); roots = roots[np.imag(roots) > 0]
        f = np.angle(roots) * sr / (2 * np.pi); bw = -np.log(np.abs(roots)) * sr / np.pi
        f = np.sort(f[(f > 90) & (f < 5000) & (bw < 400)])
        if len(f) >= 3:
            ts.append(t); F.append(f[:3])
    if len(F) < 15:
        return None, None
    F = np.array(F)
    return np.array(ts), np.stack([medfilt(F[:, k], 5) for k in range(3)], 1)


def landmarks(path, p_start, p_end):
    ts, F = tracks(path, p_start - 0.080, p_end + 0.040)
    if ts is None:
        return {}
    out = {"f1_min": ts[np.argmin(F[:, 0])], "f2_min": ts[np.argmin(F[:, 1])], "f2_max": ts[np.argmax(F[:, 1])],
           "f3_min": ts[np.argmin(F[:, 2])]}
    k = 5  # 10ms at 2ms hop
    d = np.abs(F[k:] - F[:-k]) / np.maximum(F[:-k], 1)
    mid = lambda i: ts[i + k // 2]
    for j, n in enumerate(("f1_rate", "f2_rate", "f3_rate")):
        out[n] = mid(int(np.argmax(d[:, j])))
    out["fmt_change"] = mid(int(np.argmax(d.sum(1))))
    return {kk: float(v) for kk, v in out.items()}
