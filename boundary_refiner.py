"""
General-purpose acoustic boundary refiner for word-level forced alignment.

Design principle: no phoneme-specific or word-specific rules. Every boundary decision
reduces to two generic acoustic questions, evaluated in a small window bounded by the
CTC model's own uncertainty around its predicted word gap:

  1. Is there a genuine, sustained silence in this window? (absolute energy test)
     -> if yes, this is a real pause: place the two boundaries at the acoustic
        offset/onset (sustained threshold crossings) bracketing that silence.
  2. Otherwise the words are acoustically connected with no true gap.
     -> place the single shared boundary at the point of maximum local acoustic
        change ("novelty") in the window: a combination of the energy envelope
        dropping (fading between sounds) and spectral flux (timbral change,
        e.g. fricative->vowel, stop release, nasal->vowel) -- this one signal
        generalizes across all phone-to-phone transition types instead of
        enumerating them.

All decisions are governed by a handful of global, calibratable parameters (search
margin, silence-hold duration, sustain-hold duration, onset/offset buffers, thresholds).
None of them reference specific words, phonemes, or clips.
"""
import re
from dataclasses import dataclass

import numpy as np


def rolling_rms(data: np.ndarray, sr: int, win_ms: float = 2.0) -> np.ndarray:
    """Short-time RMS energy envelope, one value per audio sample."""
    win = max(1, int(sr * win_ms / 1000.0))
    sq = data.astype(np.float64) ** 2
    cumsum = np.cumsum(np.pad(sq, (0, win), mode="constant"))
    moving_mean = (cumsum[win:] - cumsum[:-win]) / win
    return np.sqrt(np.maximum(moving_mean, 0.0))


def spectral_flux(data: np.ndarray, sr: int, frame_ms: float = 20.0, hop_ms: float = 2.0) -> np.ndarray:
    """Half-wave-rectified spectral flux (frame-to-frame magnitude increase), upsampled
    to one value per audio sample so it can be indexed alongside rolling_rms(). This is
    a standard onset/novelty detection function: it responds to ANY acoustic transition
    (timbral or energy), not just energy dips, which is what lets it stand in for dozens
    of phone-class-specific transition rules."""
    frame_len = max(8, int(sr * frame_ms / 1000.0))
    hop_len = max(1, int(sr * hop_ms / 1000.0))
    n = len(data)
    n_frames = 1 + max(0, (n - frame_len) // hop_len)
    if n_frames <= 1:
        return np.zeros(n, dtype=np.float64)
    window = np.hanning(frame_len)
    flux = np.zeros(n_frames, dtype=np.float64)
    prev_mag = None
    for i in range(n_frames):
        s = i * hop_len
        frame = data[s:s + frame_len]
        if len(frame) < frame_len:
            frame = np.pad(frame, (0, frame_len - len(frame)))
        spec = np.abs(np.fft.rfft(frame * window))
        if prev_mag is not None:
            diff = spec - prev_mag
            flux[i] = float(np.sum(diff[diff > 0]))
        prev_mag = spec
    flux_persample = np.repeat(flux, hop_len)[:n]
    if len(flux_persample) < n:
        flux_persample = np.pad(flux_persample, (0, n - len(flux_persample)), mode="edge")
    return flux_persample


def nearest_zero_crossing(data: np.ndarray, sr: int, t: float, window_ms: float = 10.0) -> float:
    """Snap a boundary time to the nearest zero-crossing to avoid audible clicks."""
    idx = int(t * sr)
    radius = int(sr * (window_ms / 1000.0) / 2)
    start = max(0, idx - radius)
    end = min(len(data) - 1, idx + radius)
    if end <= start:
        return t
    seg = data[start:end]
    zc = np.where(np.diff(np.signbit(seg)))[0]
    if len(zc) == 0:
        return t
    best = zc[np.argmin(np.abs(zc - (idx - start)))]
    return (start + best) / sr


@dataclass
class RefinerConfig:
    method: str = "combined"          # "energy_valley" | "flux" | "combined"
    flux_weight: float = 0.5          # weight of flux vs energy in "combined"
    margin_ms: float = 60.0           # how far the search window may extend beyond the CTC pipe span
    sil_hold_ms: float = 15.0         # minimum sustained sub-threshold run to count as a real pause
    hold_ms: float = 6.0              # sustain duration required to confirm an onset/offset (rejects noise blips)
    attack_ms: float = 10.0           # buffer subtracted from a detected onset (word starts slightly before energy is clearly up)
    decay_ms: float = 10.0            # buffer added to a detected offset (word ends slightly after energy visibly drops)
    speech_mult: float = 0.08         # speech_thresh = noise_floor + speech_mult * (peak - noise_floor)
    trail_mult: float = 0.04          # trail_thresh  = noise_floor + trail_mult  * (peak - noise_floor)
    min_dur: float = 0.030            # minimum word duration
    min_gap: float = 0.002            # minimum silence enforced between adjacent words
    edge_lookback: float = 0.150      # how far before the first word / after the last word to search for true onset/offset
    onset_search_pad_ms: float = 100.0  # how far past the detected silence run's own edge to look for a confirmed onset/offset
    peak_zscore_min: float = 1.0      # a novelty peak must exceed the window's own mean by this many std-devs to override the CTC estimate; otherwise fall back to trusting the model (conservative correction, not blind search)
    min_plausible_word_ms: float = 70.0   # a run of words averaging less raw-CTC duration than this is treated as implausibly compressed and rescued (see _rescue_compressed_runs)
    rescue_lookback: float = 0.600    # how far outward from a compressed run's own raw edges to search for its true acoustic boundaries
    rescue_expand_min_ratio: float = 1.25  # only rescue if the true acoustic span is at least this much larger than the raw CTC span (avoids acting on noise)
    rescue_silence_hold_ms: float = 40.0   # sustained-silence requirement when tunnelling outward through a whole run to find its true edges (longer than the ordinary per-boundary hold_ms so an inter-word micro-dip doesn't stop the walk early)


class BoundaryRefiner:
    def __init__(self, config: RefinerConfig = None, **overrides):
        self.cfg = config or RefinerConfig()
        for k, v in overrides.items():
            setattr(self.cfg, k, v)

    def refine(self, data: np.ndarray, sr: int, words: list, pipes: list) -> list:
        cfg = self.cfg
        if not words:
            return words

        rms = rolling_rms(data, sr)
        flux = spectral_flux(data, sr) if cfg.method in ("flux", "combined") else None
        audio_dur = len(data) / sr

        noise_floor = float(np.percentile(rms, 10))
        peak_energy = float(np.percentile(rms, 95))
        speech_thresh = noise_floor + cfg.speech_mult * (peak_energy - noise_floor)
        trail_thresh = noise_floor + cfg.trail_mult * (peak_energy - noise_floor)

        def s2i(t):
            return max(0, min(len(rms) - 1, int(t * sr)))

        hold_samples = max(1, int(sr * cfg.hold_ms / 1000.0))

        def find_onset(from_i, to_i):
            """First sample >= from_i where energy sustains above speech_thresh for hold_ms."""
            for k in range(from_i, to_i):
                if rms[k] >= speech_thresh:
                    seg = rms[k: min(k + hold_samples, to_i)]
                    if len(seg) >= max(1, int(hold_samples * 0.6)) and np.mean(seg) >= speech_thresh * 0.7:
                        return k
            return None

        def find_offset(from_i, to_i):
            """Last sample < to_i where energy sustains above speech_thresh for hold_ms, scanning backward."""
            for k in range(to_i, from_i, -1):
                if rms[k] >= speech_thresh:
                    seg = rms[max(from_i, k - hold_samples): k + 1]
                    if len(seg) >= max(1, int(hold_samples * 0.6)) and np.mean(seg) >= speech_thresh * 0.7:
                        return k
            return None

        def scan_forward_to_silence(from_i, to_i, sustain_samples=None):
            """Starting at from_i (w1's own raw end -- presumed still speech), scan
            forward and return the index where a sustained below-threshold silence run
            begins. This finds where w1's OWN speech stops, independent of whatever else
            happens later in a possibly-long gap (e.g. unrelated noise near w2).
            `sustain_samples` controls how long the silence must hold to count -- callers
            tunnelling through several words' worth of audio need a longer sustain than a
            single word-adjacent gap check, or an ordinary micro-dip between two words
            (e.g. a stop-consonant closure) stops the scan almost immediately."""
            hs = sustain_samples if sustain_samples is not None else hold_samples
            i = from_i
            while i < to_i:
                if rms[i] < trail_thresh:
                    seg = rms[i: min(i + hs, to_i)]
                    if len(seg) >= max(1, int(hs * 0.6)) and np.mean(seg) < trail_thresh * 1.2:
                        return i
                i += 1
            return None

        def scan_backward_to_silence(from_i, to_i, sustain_samples=None):
            """Starting at from_i (w2's own raw start -- presumed still speech), scan
            backward and return the index where a sustained below-threshold silence run
            begins (i.e. the boundary between the immediately-preceding silence and w2's
            own onset), independent of whatever happens earlier in a long gap. See
            `scan_forward_to_silence` for `sustain_samples`."""
            hs = sustain_samples if sustain_samples is not None else hold_samples
            i = from_i
            while i > to_i:
                if rms[i] < trail_thresh:
                    seg = rms[max(to_i, i - hs): i + 1]
                    if len(seg) >= max(1, int(hs * 0.6)) and np.mean(seg) < trail_thresh * 1.2:
                        return i
                i -= 1
            return None

        refined = [dict(w) for w in words]
        margin = cfg.margin_ms / 1000.0

        # ---- Pre-pass: truncated/cut-off word ("...-") followed by a real pause ----
        # Per the Pulsar guidelines, a hyphen marks a word the speaker audibly cut off.
        # When the speaker hesitates right after cutting off (stumble, then a brief hold
        # before continuing), that trailing silence conventionally belongs to the cutoff
        # word's own span rather than being split down the middle with the next word. Use
        # a WIDE search (not the tight local margin used elsewhere) starting from the
        # cutoff word's own raw end, since CTC's own boundary estimate for a truncated
        # fragment is often unreliable and the true pause can sit well beyond it.
        trunc_hold_samples = max(1, int(sr * cfg.rescue_silence_hold_ms / 1000.0))
        for i in range(len(refined) - 1):
            w1, w2 = refined[i], refined[i + 1]
            if not w1["text"].rstrip().endswith("-"):
                continue
            search_from_i = s2i(w1["end"])
            search_to_i = s2i(min(audio_dur, w1["end"] + cfg.rescue_lookback))
            off_i = scan_forward_to_silence(search_from_i, search_to_i, trunc_hold_samples)
            if off_i is None:
                continue
            on_i = find_onset(off_i, s2i(min(audio_dur, w2["end"] + cfg.rescue_lookback)))
            if on_i is None:
                continue
            w1["end"] = round(off_i / sr + cfg.decay_ms / 1000.0, 4)
            w2["start"] = round(max(w1["end"] + cfg.min_gap, on_i / sr - cfg.attack_ms / 1000.0), 4)

        # ---- Pre-pass: rescue CTC-compressed runs via voicing-continuity walk ----
        # Forced CTC alignment must spread the ENTIRE given word list across the ENTIRE
        # audio; for a run of short/reduced/disfluent words it can end up cramming several
        # of them into an implausibly short span while stealing time from neighbours. When
        # that happens, none of the individual raw boundaries inside the run are trustworthy
        # anchors for local search -- so instead of searching near them, walk OUTWARD from
        # the run's own edges through continuous voicing until hitting genuine silence, to
        # find the run's true acoustic extent, then redistribute the run's words
        # proportionally into that corrected span (subsequent pairwise refinement still
        # polishes the internal boundaries from there via the novelty function).
        def _norm_txt(t):
            return re.sub(r"[^a-z]", "", str(t).lower())

        run_boundaries = [0]
        for i in range(len(refined) - 1):
            w1, w2 = refined[i], refined[i + 1]
            # Two adjacent occurrences of the SAME word (a repeat/stutter) are a known weak
            # point for CTC forced alignment: the DP has no acoustic way to tell which
            # frames belong to occurrence 1 vs 2 beyond an arbitrary split, so a "pause"
            # detected between them from the (possibly-arbitrary) raw boundaries is not
            # trustworthy evidence of a real gap. Always keep repeats in the same run so the
            # rescue below can re-derive their true combined span from real silence instead.
            if _norm_txt(w1["text"]) and _norm_txt(w1["text"]) == _norm_txt(w2["text"]):
                continue
            w1_anchor_i = s2i(w1["end"])
            w2_anchor_i = s2i(w2["start"])
            search_hi = s2i(min(audio_dur, w2["start"] + margin))
            search_lo = s2i(max(0.0, w1["end"] - margin))
            off_i = scan_forward_to_silence(w1_anchor_i, search_hi) if w1_anchor_i < search_hi else None
            on_i = scan_backward_to_silence(w2_anchor_i, search_lo) if w2_anchor_i > search_lo else None
            if off_i is not None and on_i is not None and off_i < on_i:
                run_boundaries.append(i + 1)
        run_boundaries.append(len(refined))

        for r in range(len(run_boundaries) - 1):
            ri, rj = run_boundaries[r], run_boundaries[r + 1]
            run = refined[ri:rj]
            if len(run) < 2:
                continue
            raw_span = run[-1]["end"] - run[0]["start"]
            if raw_span <= 0:
                continue
            # Trigger on the run's WORST (most compressed) adjacent sub-window rather than
            # the whole run's average, since one normal-length word early in a run (e.g. a
            # clearly-spoken word right before a fast disfluency cluster) would otherwise
            # dilute the average and hide a real compression problem later in the same run.
            worst_pair_ms = min(
                ((run[k + 1]["end"] - run[k]["start"]) / 2.0) * 1000.0
                for k in range(len(run) - 1)
            )
            if worst_pair_ms >= cfg.min_plausible_word_ms:
                continue

            rescue_hold_samples = max(1, int(sr * cfg.rescue_silence_hold_ms / 1000.0))
            end_i = s2i(run[-1]["end"])
            far_lo = s2i(max(0.0, run[0]["start"] - cfg.rescue_lookback))
            true_start_i = scan_backward_to_silence(end_i, far_lo, rescue_hold_samples) if end_i > far_lo else None

            start_i = s2i(run[0]["start"])
            far_hi = s2i(min(audio_dur, run[-1]["end"] + cfg.rescue_lookback))
            true_end_i = scan_forward_to_silence(start_i, far_hi, rescue_hold_samples) if start_i < far_hi else None

            if true_start_i is None or true_end_i is None:
                continue
            true_start_t = true_start_i / sr
            true_end_t = true_end_i / sr
            true_span = true_end_t - true_start_t
            if true_span <= raw_span * cfg.rescue_expand_min_ratio:
                continue

            for w in run:
                rel_s = (w["start"] - run[0]["start"]) / raw_span
                rel_e = (w["end"] - run[0]["start"]) / raw_span
                w["start"] = round(true_start_t + rel_s * true_span, 4)
                w["end"] = round(true_start_t + rel_e * true_span, 4)

        # ---- Edge: first word onset ----
        wf = refined[0]
        lo_i = s2i(max(0.0, wf["start"] - cfg.edge_lookback))
        hi_i = s2i(wf["end"])
        on = find_onset(lo_i, hi_i)
        if on is not None:
            wf["start"] = round(max(0.0, on / sr - cfg.attack_ms / 1000.0), 4)

        # ---- Edge: last word offset ----
        wl = refined[-1]
        lo_i = s2i(wl["start"])
        hi_i = s2i(min(audio_dur, wl["end"] + cfg.edge_lookback))
        off = find_offset(lo_i, hi_i)
        if off is not None:
            wl["end"] = round(min(audio_dur, off / sr + cfg.decay_ms / 1000.0), 4)

        # ---- Pairwise boundaries ----
        margin = cfg.margin_ms / 1000.0
        for i in range(len(refined) - 1):
            w1, w2 = refined[i], refined[i + 1]

            p_start = pipes[i]["start"] if i < len(pipes) else min(w1["end"], w2["start"])
            p_end = pipes[i]["end"] if i < len(pipes) else max(w1["end"], w2["start"])
            p_mid = (p_start + p_end) / 2.0

            lo_t = max(w1["start"] + cfg.min_dur, min(w1["end"], p_start) - margin)
            hi_t = min(w2["end"] - cfg.min_dur, max(w2["start"], p_end) + margin)

            if hi_t <= lo_t:
                bnd = p_mid
                w1["end"] = round(bnd - cfg.min_gap / 2, 4)
                w2["start"] = round(bnd + cfg.min_gap / 2, 4)
                continue

            lo_i, hi_i = s2i(lo_t), s2i(hi_t)

            # Try to resolve this as a genuine pause: walk forward from w1's own end to
            # find where its speech actually stops, and walk backward from w2's own start
            # to find where its speech actually begins. This is anchored to each word
            # individually, so it stays correct even when the raw CTC gap between them is
            # large and/or contains unrelated noise -- there is no "search the whole
            # window for the biggest quiet patch" step to be fooled by such noise.
            w1_anchor_i = s2i(w1["end"])
            w2_anchor_i = s2i(w2["start"])
            off_i = scan_forward_to_silence(w1_anchor_i, hi_i) if w1_anchor_i < hi_i else None
            on_i = scan_backward_to_silence(w2_anchor_i, lo_i) if w2_anchor_i > lo_i else None

            if off_i is not None and on_i is not None and off_i < on_i:
                w1_end = off_i / sr + cfg.decay_ms / 1000.0
                w2_start = on_i / sr - cfg.attack_ms / 1000.0
                w1_end = min(w1_end, w2_start - cfg.min_gap)
            else:
                # No genuine silence in this window: the words are acoustically connected.
                # Build a novelty signal (energy drop and/or spectral flux, z-scored against
                # this window's OWN local statistics) and only let a peak in it override the
                # CTC model's own boundary estimate (p_mid) if it stands out clearly from the
                # local background. This is a conservative-correction principle: search for
                # evidence of a transition, but don't force a pick out of noise when there
                # isn't one -- flat/ambiguous windows just keep the model's estimate.
                seg_rms = rms[lo_i:hi_i]
                seg_flux = flux[lo_i:hi_i] if flux is not None else None

                if cfg.method == "energy_valley":
                    novelty = -(seg_rms - seg_rms.mean())
                elif cfg.method == "flux":
                    novelty = seg_flux
                else:  # combined
                    r_std = seg_rms.std()
                    f_std = seg_flux.std()
                    e_z = -(seg_rms - seg_rms.mean()) / r_std if r_std > 1e-12 else np.zeros_like(seg_rms)
                    f_z = (seg_flux - seg_flux.mean()) / f_std if f_std > 1e-12 else np.zeros_like(seg_flux)
                    novelty = cfg.flux_weight * f_z + (1.0 - cfg.flux_weight) * e_z

                nstd = novelty.std()
                peak_i = int(np.argmax(novelty))
                peak_z = (novelty[peak_i] - novelty.mean()) / nstd if nstd > 1e-12 else 0.0

                if peak_z >= cfg.peak_zscore_min:
                    bnd = (lo_i + peak_i) / sr
                else:
                    bnd = p_mid
                bnd = max(lo_t, min(hi_t, bnd))
                w1_end = bnd - cfg.min_gap / 2
                w2_start = bnd + cfg.min_gap / 2

            w1["end"] = round(w1_end, 4)
            w2["start"] = round(w2_start, 4)

        # ---- Pass 2: monotonicity / min-gap / min-duration enforcement ----
        for i in range(len(refined) - 1):
            if refined[i + 1]["start"] - refined[i]["end"] < cfg.min_gap:
                refined[i]["end"] = round(refined[i + 1]["start"] - cfg.min_gap, 4)
        for i in range(len(refined)):
            if refined[i]["start"] < 0.0:
                refined[i]["start"] = 0.0
            if refined[i]["end"] <= refined[i]["start"]:
                refined[i]["end"] = round(refined[i]["start"] + cfg.min_dur, 4)
            if i > 0 and refined[i]["start"] <= refined[i - 1]["end"]:
                refined[i]["start"] = round(refined[i - 1]["end"] + cfg.min_gap, 4)
                if refined[i]["end"] <= refined[i]["start"]:
                    refined[i]["end"] = round(refined[i]["start"] + cfg.min_dur, 4)

        # ---- Zero-crossing snap (click-free cuts) ----
        for i in range(len(refined)):
            new_start = nearest_zero_crossing(data, sr, refined[i]["start"])
            new_end = nearest_zero_crossing(data, sr, refined[i]["end"])
            if new_end <= new_start:
                new_end = new_start + cfg.min_dur
            refined[i]["start"] = round(new_start, 4)
            refined[i]["end"] = round(new_end, 4)

        return refined
