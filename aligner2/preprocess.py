"""
Audio pre-processing variants (experimental; aligner2/preprocess_eval.py measures them). Input and output: 16 kHz mono
float64 (as aligner2.signals.load_audio returns). Every filter is ZERO-PHASE (forward-backward or STFT with the same
analysis / synthesis window), so no variant shifts a boundary in time.

  peak     peak normalised to -1 dBFS
  rms20    RMS normalised to -20 dBFS
  hpf80    4th-order Butterworth high-pass at 80 Hz (rumble / hum), forward-backward
  agc      speech-only 2:1 compression toward -20 dBFS (50 ms RMS envelope, 200 ms smoothing, <= +20 / -10 dB);
           frames within 10 dB of the noise floor keep 0 dB (pauses are not amplified)
  denoise  spectral subtraction (32 ms STFT, 8 ms hop): noise power = mean of the 10 % quietest frames, 1.5x
           over-subtraction, gain floor -20 dB
  combo    hpf80 -> denoise -> peak
  slowNNN  time-stretch by NNN/100 by resampling (slower and lower-pitched; exact timing): more CTC frames per sound
           for fast / mumbled speech. The aligner's times are divided by the factor afterwards (preprocess_eval.py).
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt, stft, istft

SR = 16000
VARIANTS = ("none", "peak", "rms20", "hpf80", "agc", "denoise", "combo")


def stretch_factor(variant):
    return int(variant[4:]) / 100 if variant.startswith("slow") else 1.0


def slow(x, factor):
    """time stretch by RESAMPLING: the samples are stretched by `factor` (the speech is slower AND lower-pitched, 1/factor):
    an event at input time t is at factor * t exactly (a phase vocoder keeps the pitch but smears onsets by up to 14 ms)"""
    import torch
    import torchaudio
    num = int(round(factor * 100)); den = 100
    return torchaudio.functional.resample(torch.as_tensor(np.ascontiguousarray(x), dtype=torch.float64), den, num).numpy()


def _box(x, n):
    n = max(1, int(n))
    return np.convolve(x, np.ones(n) / n, "same")


def peak(x, db=-1.0):
    return x * (10 ** (db / 20) / max(np.abs(x).max(), 1e-9))


def rms(x, db=-20.0):
    return x * (10 ** (db / 20) / max(np.sqrt(np.mean(x ** 2)), 1e-9))


def hpf(x, fc=80.0):
    return sosfiltfilt(butter(4, fc, "highpass", fs=SR, output="sos"), x)


def agc(x, target=-20.0, ratio=2.0):
    env = 10 * np.log10(_box(x ** 2, 0.05 * SR) + 1e-12)
    floor = np.percentile(env, 10)
    g = np.clip((target - env) * (1 - 1 / ratio), -10.0, 20.0)
    g = np.where(env > floor + 10.0, g, 0.0)                      # pauses / background: untouched
    g = _box(g, 0.2 * SR)                                          # centred smoothing (zero-phase)
    return x * 10 ** (g / 20)


def denoise(x, over=1.5, floor_db=-20.0):
    f, t, X = stft(x, SR, nperseg=512, noverlap=384)
    P = np.abs(X) ** 2
    frame_e = P.sum(0)
    q = frame_e <= np.percentile(frame_e, 10)
    N = P[:, q].mean(1, keepdims=True)
    G = np.sqrt(np.maximum(1 - over * N / np.maximum(P, 1e-20), 10 ** (floor_db / 10)))
    _, y = istft(X * G, SR, nperseg=512, noverlap=384)
    y = y[:len(x)]
    return np.pad(y, (0, len(x) - len(y)))


def apply(x, variant):
    if variant == "none":
        return x
    if variant == "peak":
        return peak(x)
    if variant == "rms20":
        return rms(x)
    if variant == "hpf80":
        return hpf(x)
    if variant == "agc":
        return agc(x)
    if variant == "denoise":
        return denoise(x)
    if variant == "combo":
        return peak(denoise(hpf(x)))
    if variant.startswith("slow"):
        return slow(x, stretch_factor(variant))
    raise ValueError(variant)
