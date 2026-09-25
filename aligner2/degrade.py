"""
Controlled degradations of clean benchmark audio (16 kHz mono float64), to test how alignment depends on recording
quality and whether pre-processing (aligner2/preprocess.py) recovers it. Deterministic (fixed seeds); zero-phase
filters, so no degradation shifts a boundary in time.

  noise20   pink-ish noise at 20 dB SNR (re the speech RMS)
  noise10   the same at 10 dB SNR
  band4k    8th-order low-pass at 4 kHz, forward-backward (a phone / narrow-band codec)
  quiet     -30 dB gain, then 16-bit quantisation (a very low recording level)
  reverb    synthetic room: exponentially decaying noise impulse response, RT60 0.5 s, 30 % wet
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt, fftconvolve

SR = 16000
DEGRADATIONS = ("clean", "noise20", "noise10", "band4k", "quiet", "reverb")


def _pink(n, seed):
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    X = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1 / SR)
    X /= np.sqrt(np.maximum(f, 50.0))                        # ~1/f power above 50 Hz
    p = np.fft.irfft(X, n)
    return p / np.sqrt(np.mean(p ** 2))


def _speech_rms(x):
    e = np.convolve(x ** 2, np.ones(800) / 800, "same")      # 50 ms energy
    return np.sqrt(np.mean(e[e >= np.percentile(e, 50)]))    # the louder half = speech


def apply(x, deg, seed=0):
    if deg == "clean":
        return x
    if deg in ("noise20", "noise10"):
        snr = 20.0 if deg == "noise20" else 10.0
        return x + _pink(len(x), seed) * _speech_rms(x) * 10 ** (-snr / 20)
    if deg == "band4k":
        return sosfiltfilt(butter(8, 4000, "lowpass", fs=SR, output="sos"), x)
    if deg == "quiet":
        y = x * 10 ** (-30 / 20)
        return np.round(y * 32767) / 32767
    if deg == "reverb":
        rng = np.random.default_rng(seed + 1)
        n = int(0.6 * SR)
        t = np.arange(n) / SR
        h = rng.standard_normal(n) * np.exp(-6.9 * t / 0.5)  # -60 dB at 0.5 s
        h[0] = 0.0
        h /= np.sqrt(np.sum(h ** 2))
        wet = fftconvolve(x, h)[:len(x)]
        return 0.7 * x + 0.3 * wet * (np.sqrt(np.mean(x ** 2)) / max(np.sqrt(np.mean(wet ** 2)), 1e-12))
    raise ValueError(deg)
