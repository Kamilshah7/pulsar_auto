"""
Candidate signals for word segmentation, all on one 2 ms grid (frame k centred at k * HOP).

Every signal is a generic property of speech audio -- nothing here knows about words, sound
classes or any particular recording. Audio is resampled to 16 kHz mono first.

  acoustic (DSP)
    loudness      log RMS energy, 10 ms window                                  (how loud)
    periodicity   normalised autocorrelation peak, 70-400 Hz, 30 ms window      (how voiced)
    log_f0        log pitch at that peak, unvoiced frames interpolated          (which pitch)
    zcr           zero-crossing rate, 10 ms                                     (noisiness, time domain)
    centroid      log spectral centroid, 20 ms                                  (brightness)
    flatness      log spectral flatness (geometric / arithmetic mean power)     (tone vs noise)
    low_ratio     dB share of power below 400 Hz                                (murmur / voice bar)
    high_ratio    dB share of power above 4 kHz                                 (frication)
    tilt          slope of the log spectrum vs log frequency                    (source/vocal effort)
    flux          positive spectral flux of the normalised spectrum             (onset of new energy)
    mfcc_change   distance between mean MFCCs of the 20 ms left / right of k   (spectral shape change)
    formant_vel   speed of F1/F2 movement (LPC), 10 ms                          (articulator movement)
    syllabic      300-3000 Hz envelope low-passed to 10 Hz, dB                  (syllable nuclei vs troughs)
    transient     largest 3 ms jump of >2 kHz energy                            (bursts, clicks)
    glottal       crest factor (dB) of the LPC residual, 25 ms                  (creak / glottal stops)
  pretrained models, used as-is (no training)
    ctc_blank     P(blank) from HuBERT-large CTC                                (between letters)
    ctc_wordsep   P(word separator '|') from HuBERT-large CTC                   (between words, lexical)
    ctc_change    Jensen-Shannon divergence of the CTC posterior (blank + letters), t-1 vs t+1
    ssl_change    cosine distance of HuBERT layer-18 states, t-1 vs t+1         (learned phonetic change)
    speech_prob   pyannote segmentation-3.0 speech probability                  (speech vs non-speech)

    from aligner2.signals import compute
    S = compute(wav_path)   # {"t": times, name: values, ..., "ctc_logp": (T20, V) log posteriors}

Model outputs come from the GPU engine (modal_aligner2.py); everything else is plain numpy so the same
code runs locally and in the Modal containers.
"""
import hashlib
import os

import numpy as np
import soundfile as sf
import torch
import torchaudio

SR = 16000
HOP = 0.002
HOP_N = int(SR * HOP)
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench", "cache", "aligner2")
SSL_LAYER = 18
NAMES = ["loudness", "periodicity", "log_f0", "zcr", "centroid", "flatness", "low_ratio", "high_ratio", "tilt", "flux",
         "mfcc_change", "formant_vel", "syllabic", "transient", "glottal", "ctc_blank", "ctc_wordsep", "ctc_change", "ssl_change",
         "speech_prob"]


def load_audio(path):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = torch.from_numpy(x.mean(1))
    if sr != SR:
        x = torchaudio.functional.resample(x, sr, SR)
    return x.numpy().astype(np.float64)


def _frames(x, win):
    """(T, win) frames centred at k * HOP_N, zero padded at the edges"""
    T = len(x) // HOP_N + 1
    pad = np.pad(x, (win // 2, win // 2 + HOP_N))
    idx = np.arange(win)[None, :] + (np.arange(T) * HOP_N)[:, None]
    return pad[idx]


def _interp(t_src, v_src, T):
    return np.interp(np.arange(T) * HOP, t_src, v_src)


# ── acoustic ──────────────────────────────────────────────────────────────────────────────────────

def _acoustic(x):
    out = {}
    f10 = _frames(x, int(0.010 * SR))
    T = len(f10)
    out["loudness"] = 10 * np.log10(np.mean(f10 ** 2, 1) + 1e-10)
    out["zcr"] = np.mean(np.abs(np.diff(np.sign(f10), axis=1)) > 0, 1)

    # periodicity + f0: normalised autocorrelation over 30 ms
    f30 = _frames(x, int(0.030 * SR)); f30 = f30 - f30.mean(1, keepdims=True)
    n = f30.shape[1]; nfft = 1 << (2 * n - 1).bit_length()
    F = np.fft.rfft(f30, nfft, axis=1); ac = np.fft.irfft(np.abs(F) ** 2, nfft, axis=1)[:, :n]
    lo, hi = SR // 400, SR // 70
    ac_n = ac[:, lo:hi] / np.maximum(ac[:, :1], 1e-12)
    k = np.argmax(ac_n, 1)
    out["periodicity"] = np.clip(ac_n[np.arange(T), k], 0, 1)
    f0 = np.log(SR / (k + lo))
    voiced = out["periodicity"] > 0.5
    out["log_f0"] = np.interp(np.arange(T), np.where(voiced)[0], f0[voiced]) if voiced.sum() > 2 else f0

    # spectrum-based: 20 ms Hann, 512-point
    f20 = _frames(x, int(0.020 * SR)) * np.hanning(int(0.020 * SR))[None, :]
    P = np.abs(np.fft.rfft(f20, 512, axis=1)) ** 2 + 1e-12
    fr = np.fft.rfftfreq(512, 1 / SR)
    tot = P.sum(1)
    out["centroid"] = np.log((P * fr).sum(1) / tot + 1)
    out["flatness"] = np.mean(np.log(P), 1) - np.log(np.mean(P, 1))
    out["low_ratio"] = 10 * np.log10(P[:, fr < 400].sum(1) / tot)
    out["high_ratio"] = 10 * np.log10(P[:, fr >= 4000].sum(1) / tot)
    band = (fr > 100) & (fr < 7000); lf = np.log(fr[band]); lf = lf - lf.mean()
    out["tilt"] = (np.log(P[:, band]) @ lf) / (lf @ lf)
    S = np.sqrt(P); Sn = S / S.sum(1, keepdims=True)
    out["flux"] = np.r_[0, np.sqrt((np.maximum(np.diff(Sn, axis=0), 0) ** 2).sum(1))]

    # MFCC change: left vs right 20 ms means
    mel = torchaudio.functional.melscale_fbanks(257, 0, SR / 2, 40, SR, norm="slaney", mel_scale="slaney").numpy()
    mfcc = torchaudio.functional.create_dct(13, 40, "ortho").numpy()
    C = np.log(P @ mel + 1e-10) @ mfcc; C = (C - C.mean(0)) / (C.std(0) + 1e-9)
    w = 10; cs = np.cumsum(np.vstack([np.zeros((1, 13)), C]), 0)
    left = np.zeros_like(C); right = np.zeros_like(C)
    ks = np.arange(T); a = np.clip(ks - w, 0, T); b = np.clip(ks + w, 0, T)
    left = (cs[ks] - cs[a]) / np.maximum(ks - a, 1)[:, None]; right = (cs[b] - cs[ks]) / np.maximum(b - ks, 1)[:, None]
    out["mfcc_change"] = np.linalg.norm(left - right, axis=1)
    out["mfcc"] = C                                            # (T, 13) per-clip standardised: spectral identity

    # syllabic envelope: 300-3000 Hz band energy, low-passed at 10 Hz (on the 2 ms grid)
    env = np.log(P[:, (fr >= 300) & (fr <= 3000)].sum(1))
    kern = np.hanning(51); kern /= kern.sum()                 # ~100 ms Hann ~ 10 Hz low-pass
    out["syllabic"] = 10 / np.log(10) * np.convolve(env, kern, "same")

    # transient: >2 kHz energy jump over 3 ms
    hf = 10 * np.log10(P[:, fr >= 2000].sum(1))
    d = np.r_[np.zeros(2), hf[2:] - hf[:-2]]
    out["transient"] = np.maximum(d, 0)

    out["formant_vel"], out["glottal"] = _formant_velocity(x, T)
    return out


def _formant_velocity(x, T, hop_s=0.005, win_s=0.025, order=18):
    from scipy.linalg import solve_toeplitz
    step = int(hop_s * SR); wl = int(win_s * SR); win = np.hamming(wl)
    from scipy.signal import lfilter
    ts, F, G = [], [], []
    xe = np.append(x[0], x[1:] - 0.97 * x[:-1])
    last = np.array([500.0, 1500.0])
    for a in range(0, max(1, len(x) - wl), step):
        fr = xe[a:a + wl] * win
        r = np.correlate(fr, fr, "full")[wl - 1:wl + order]
        f12 = last
        crest = 0.0
        if r[0] > 1e-8:
            try:
                c = solve_toeplitz(r[:order], -r[1:order + 1])
                e = lfilter(np.r_[1, c], [1], xe[a:a + wl])[order:]
                crest = 20 * np.log10(np.max(np.abs(e)) / (np.sqrt(np.mean(e ** 2)) + 1e-12) + 1e-12)
                rt = np.roots(np.r_[1, c]); rt = rt[np.imag(rt) > 0]
                f = np.angle(rt) * SR / (2 * np.pi); bw = -np.log(np.abs(rt)) * SR / np.pi
                f = np.sort(f[(f > 150) & (f < 4000) & (bw < 500)])
                if len(f) >= 2:
                    f12 = f[:2]
            except (np.linalg.LinAlgError, ValueError):
                pass
        last = f12; ts.append((a + wl / 2) / SR); F.append(np.log(f12)); G.append(crest)
    ts, F = np.array(ts), np.array(F)
    k = 2  # 10 ms at 5 ms hop
    v = np.zeros(len(F)); v[k:-k] = np.abs(F[2 * k:] - F[:-2 * k]).sum(1)
    return _interp(ts, v, T), _interp(ts, np.array(G), T)


# ── model outputs -> signals (pure numpy: runs wherever the model outputs are) ───────────────────

def model_signals(r, T):
    """signals 13-15 + ssl_change + speech_prob from the GPU model outputs (modal_aligner2.Engine)"""
    lg = r["logits"].astype(np.float64)
    logp = lg - np.logaddexp.reduce(lg, axis=1, keepdims=True)
    p = np.exp(logp)
    tf = np.arange(len(lg)) * 0.020 + 0.0125
    out = {"ctc_blank": _interp(tf, p[:, 0], T), "ctc_wordsep": _interp(tf, p[:, 4], T)}
    m = 0.5 * (p[2:] + p[:-2])
    kl = lambda a, b: (a * (np.log(a + 1e-12) - np.log(b + 1e-12))).sum(1)
    out["ctc_change"] = _interp(tf, np.r_[0, 0.5 * kl(p[2:], m) + 0.5 * kl(p[:-2], m), 0], T)
    out["ssl_change"] = _interp(tf, r[f"ssl_change_{SSL_LAYER}"], T)
    out["speech_prob"] = _aggregate_pyannote(r["pya"], r["pya_starts"], 5.0, T)
    for sh in (80, 160, 240):                   # HuBERT on the audio advanced by sh samples (5/10/15 ms)
        if f"logits_s{sh}" in r:
            ls = r[f"logits_s{sh}"].astype(np.float64)
            out[f"ctc_logp_s{sh}"] = (ls - np.logaddexp.reduce(ls, axis=1, keepdims=True)).astype(np.float32)
    if "fc_logits" in r:                       # charsiu frame classifier, 10 ms frames
        fl = r["fc_logits"].astype(np.float64)
        out["fc_logp"] = (fl - np.logaddexp.reduce(fl, axis=1, keepdims=True)).astype(np.float32)
    if "phone_logits" in r:                    # xlsr-53 espeak phoneme CTC (same 20 ms frames)
        pl = r["phone_logits"].astype(np.float64)
        out["phone_logp"] = (pl - np.logaddexp.reduce(pl, axis=1, keepdims=True)).astype(np.float32)
    return out, logp


def _aggregate_pyannote(data, starts, duration, T):
    """speech probability = max speaker activity; segmentation-3.0 is permutation-invariant so its
    5 s windows come back un-aggregated -- Hann-weighted average on the 2 ms grid."""
    nc, nf, _ = data.shape
    acc, wsum = np.zeros(T), np.zeros(T)
    grid = np.arange(T) * HOP
    w = np.hanning(nf + 2)[1:-1]
    for i in range(nc):
        tf = starts[i] + (np.arange(nf) + 0.5) * duration / nf
        sel = (grid >= tf[0]) & (grid <= tf[-1])
        acc[sel] += np.interp(grid[sel], tf, data[i].max(1) * w)
        wsum[sel] += np.interp(grid[sel], tf, w)
    return acc / np.maximum(wsum, 1e-6)


def features(x, model_out):
    """every signal for one clip: x = 16 kHz mono samples, model_out = GPU model outputs"""
    out = _acoustic(x)
    T = len(out["loudness"])
    ms, logp = model_signals(model_out, T)
    out.update(ms)
    out = {k: v.astype(np.float32) for k, v in out.items()}   # includes phone_logp (T20, 392) when present
    out["t"] = np.arange(T) * HOP
    out["ctc_logp"] = logp.astype(np.float32)
    return out


# ── entry point (local) ───────────────────────────────────────────────────────────────────────────

def version():
    """cache tag: changes whenever this file changes, so local and GPU caches never go stale"""
    return hashlib.sha1(open(__file__, "rb").read()).hexdigest()[:8]


def clip_key(path):
    st = os.stat(path)
    return hashlib.sha1(f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()[:16]


def compute(path, use_cache=True):
    """all signals for a local WAV: local cache, else computed on the GPU engine (modal_aligner2.py)"""
    key = clip_key(path)
    cp = os.path.join(CACHE, f"{key}_{version()}.npz")
    if use_cache and os.path.exists(cp):
        z = np.load(cp)
        return {k: z[k] for k in z.files}
    from aligner2 import remote
    out = remote.signals(key, load_audio(path))
    os.makedirs(CACHE, exist_ok=True)
    np.savez_compressed(cp, **out)
    return out
