"""
Gated denoising for production (2026-09-25; the user: "wire it in").

Every clip is run through DNS64 (modal_denoise.py). The denoised audio is used only when it clearly removed background
noise: the 10th percentile of the loudness track (aligner2/signals.py's definition: log RMS, 10 ms frames, 2 ms hop)
fell by >= GATE_DB, or by >= GATE_DB_NOISY in a clip whose background is loud (snr() < SNR_MAX). Measured
(aligner2/preprocess_eval.py, NOTES.md "NOISE-ROBUST PAUSES + ENHANCEMENT"): clean clips drop 0-13 dB (median 1.8),
20 dB-SNR noise 12-50 (median 36), 10 dB-SNR 29-58 (49), reverb 6-17 (11.5). On 026 / 049 (MAE all, ms, without ->
gated): clean 0 / 24 clips denoised (identical), 20 dB noise 24 / 24 (33.7 / 39.9 -> 17.5 / 20.2), 10 dB noise 24 / 24
(44.0 / 48.4 -> 19.7 / 22.2), reverb 16 / 24 (24.4 / 27.2 -> 20.0 / 23.1; always 18.0 / 21.4), 4 kHz band 0 / 24
(identical). None of the 50 clean benchmark clips is denoised.
"""
import numpy as np

GATE_DB = 15.0          # floor drop that alone proves real background noise
GATE_DB_NOISY = 5.0     # ... enough when the clip's background is loud (speech peaks < SNR_MAX over it)
SNR_MAX = 40.0          # the same "loud background" test as the pause model (run_bench.BASE pause_floor_snr_max)


def floor_level(x):
    """10th percentile of the loudness track (the same computation as aligner2/signals.py, loudness)"""
    from aligner2.signals import SR, _frames
    f10 = _frames(np.asarray(x, dtype=np.float64), int(0.010 * SR))
    return float(np.percentile(10 * np.log10(np.mean(f10 ** 2, 1) + 1e-10), 10))


def floor_drop(x, y):
    """how far denoising lowered the background (dB): original floor - denoised floor"""
    return floor_level(x) - floor_level(y)


def snr(x):
    """speech peaks over the background (dB): 99th percentile of the loudness track minus the median local floor (the
    minimum of the 50 ms-smoothed loudness within +-1 s) -- aligner2/segment.py Prepared.snr on the same track"""
    from aligner2.signals import SR, _frames
    L = 10 * np.log10(np.mean(_frames(np.asarray(x, dtype=np.float64), int(0.010 * SR)) ** 2, 1) + 1e-10)
    sm = np.convolve(L, np.ones(25) / 25, "same")
    fl = np.lib.stride_tricks.sliding_window_view(np.pad(sm, 500, mode="edge"), 1001).min(axis=1)[:len(L)]
    return float(np.percentile(L, 99) - np.median(fl))


def use_denoised(x, y):
    """denoise when it removed >= 15 dB of background, or >= 5 dB in a clip with a loud background (< 40 dB under the
    speech peaks). On 026 / 049 x (clean, 20 / 10 dB noise, reverb, 4 kHz band): clean 0 / 24 clips, noise 48 / 48,
    reverb 16 / 24, band-limited 0 / 24 (the 15 dB gate alone missed one noisy clip, 11.7 dB)"""
    drop = floor_drop(x, y)
    return drop >= GATE_DB or (drop >= GATE_DB_NOISY and snr(x) < SNR_MAX)
