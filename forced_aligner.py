import torch
import torchaudio
import torchaudio.functional as F
import soundfile as sf
import numpy as np
import os, sys, re, difflib
from dataclasses import dataclass
from scipy.signal import find_peaks

@dataclass
class Point:
    token_index: int
    time_index: int
    score: float

@dataclass
class Segment:
    label: str
    start: int
    end: int
    score: float

INITIALISMS = {
    # Media & Technology
    "dvd": ["d", "v", "d"],
    "tv": ["t", "v"],
    "vcr": ["v", "c", "r"],
    "vhs": ["v", "h", "s"],
    "cd": ["c", "d"],
    "pc": ["p", "c"],
    "hd": ["h", "d"],
    "cg": ["c", "g"],
    "cgi": ["c", "g", "i"],
    "vr": ["v", "r"],
    "ar": ["a", "r"],
    "ai": ["a", "i"],
    "ml": ["m", "l"],
    "ui": ["u", "i"],
    "ux": ["u", "x"],
    "api": ["a", "p", "i"],
    "url": ["u", "r", "l"],
    "ip": ["i", "p"],
    "vpn": ["v", "p", "n"],
    "cpu": ["c", "p", "u"],
    "gpu": ["g", "p", "u"],
    "ram": ["r", "a", "m"],
    "usb": ["u", "s", "b"],
    "html": ["h", "t", "m", "l"],
    "css": ["c", "s", "s"],
    "js": ["j", "s"],
    "fm": ["f", "m"],
    
    # Sports & Organizations
    "afc": ["a", "f", "c"],
    "nfc": ["n", "f", "c"],
    "nfl": ["n", "f", "l"],
    "nba": ["n", "b", "a"],
    "mlb": ["m", "l", "b"],
    "nhl": ["n", "h", "l"],
    "ufc": ["u", "f", "c"],
    "fbi": ["f", "b", "i"],
    "cia": ["c", "i", "a"],
    "nsa": ["n", "s", "a"],
    "irs": ["i", "r", "s"],
    "fda": ["f", "d", "a"],
    "cdc": ["c", "d", "c"],
    "epa": ["e", "p", "a"],
    "fcc": ["f", "c", "c"],
    "sec": ["s", "e", "c"],
    "usa": ["u", "s", "a"],
    "uk": ["u", "k"],
    "eu": ["e", "u"],
    "un": ["u", "n"],
    "uae": ["u", "a", "e"],
    
    # Medical & General
    "ptsd": ["p", "t", "s", "d"],
    "adhd": ["a", "d", "h", "d"],
    "ocd": ["o", "c", "d"],
    "dna": ["d", "n", "a"],
    "rna": ["r", "n", "a"],
    "er": ["e", "r"],
    "icu": ["i", "c", "u"],
    "cpr": ["c", "p", "r"],
    "iv": ["i", "v"],
    
    # Business & Finance
    "ceo": ["c", "e", "o"],
    "cto": ["c", "t", "o"],
    "cfo": ["c", "f", "o"],
    "coo": ["c", "o", "o"],
    "vp": ["v", "p"],
    "pr": ["p", "r"],
    "hr": ["h", "r"],
    "atm": ["a", "t", "m"],
    "pin": ["p", "i", "n"],
    "diy": ["d", "i", "y"],
    "faq": ["f", "a", "q"],
    "rsvp": ["r", "s", "v", "p"],
    "ps": ["p", "s"],
    "vip": ["v", "i", "p"],
    "id": ["i", "d"],
    "dj": ["d", "j"],
    "mc": ["m", "c"],
    "iq": ["i", "q"],
    "eq": ["e", "q"],
    "ac": ["a", "c"],
    "dc": ["d", "c"],
    "ev": ["e", "v"],
    "suv": ["s", "u", "v"],
    "atv": ["a", "t", "v"],
    "rv": ["r", "v"],
    "bmw": ["b", "m", "w"],
    "gmc": ["g", "m", "c"],
    "vw": ["v", "w"],
}

ACRONYMS_AS_WORDS = {"nasa", "nato", "laser", "radar", "scuba", "aids", "sonar", "sim", "gif"}

def split_abbreviations(words):
    result = []
    for w in words:
        if not w:
            continue
        w_clean = re.sub(r"[^\w\.]", "", str(w)).lower()
        if "." in w_clean:
            parts = [p for p in w_clean.strip(".").split(".") if p]
            if len(parts) > 1 and all(len(p) <= 2 for p in parts):
                letters = [c for c in w_clean if c.isalpha()]
                result.extend(letters)
                continue
        w_stripped = re.sub(r"[^\w]", "", str(w)).lower()
        if w_stripped in INITIALISMS:
            result.extend(INITIALISMS[w_stripped])
            continue
        if str(w).isupper() and 2 <= len(str(w)) <= 4 and str(w).isalpha() and w_stripped not in ACRONYMS_AS_WORDS:
            result.extend(list(w_stripped))
            continue
        result.append(w)
    return result

class ForcedAligner:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[ForcedAligner] Initializing on {self.device}...")
        self.bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
        self.model = self.bundle.get_model().to(self.device)
        self.labels = self.bundle.get_labels()
        self.dictionary = {c: i for i, c in enumerate(self.labels)}
        print("[ForcedAligner] Wav2Vec2 loaded successfully.")

    @staticmethod
    def _parse_hms(t):
        """'HH:MM:SS.mmm' -> seconds."""
        h, m, s = str(t).split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    def match_prelabel_segments(self, raw_words, segments):
        """Best-effort match of an externally-provided prelabel (a prior,
        independently-produced draft word-level transcript+timing -- e.g.
        an earlier automated pass over the same clip, NOT derived from this
        pipeline's own CTC/heuristic output) onto our own word sequence.

        Uses text-sequence alignment rather than positional indexing, since
        prelabel segmentation can legitimately differ from ours (different
        handling of repeated/truncated words) -- confirmed on this
        project's own audio/*.json sidecars: naive positional matching only
        found ~33% of words correctly paired, while sequence alignment
        finds ~91%. Returns {idx: (start_sec, end_sec)} only for words with
        a confident, exact-text match; words with no match (or no prelabel
        at all) simply aren't present in the returned dict, so sparse or
        entirely absent prelabel coverage degrades gracefully -- callers
        must not assume every index is present."""
        def _clean(t):
            t = str(t).strip().lower()
            if t == "(())":
                return ""
            m = re.fullmatch(r"\((.+)\)", t)
            if m:
                t = m.group(1)
            t = t.rstrip("-")
            t = re.sub(r"[^a-z']", "", t)
            return t

        g_norm = [_clean(w) for w in raw_words]
        p_norm = [_clean(s.get("refTranscript", "")) for s in segments]

        sm = difflib.SequenceMatcher(None, g_norm, p_norm, autojunk=False)
        lookup = {}
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op != "equal":
                continue
            for k in range(i2 - i1):
                gi, pj = i1 + k, j1 + k
                if not g_norm[gi]:
                    continue
                seg = segments[pj]
                try:
                    st = self._parse_hms(seg["startTime"])
                    en = self._parse_hms(seg["endTime"])
                except Exception:
                    continue
                if en > st:
                    lookup[gi] = (st, en)
        return lookup

    def get_emission(self, waveform):
        with torch.inference_mode():
            emission, _ = self.model(waveform.to(self.device))
            return emission[0].cpu()

    def get_trellis(self, emission, tokens, blank_id=0):
        num_frame = emission.size(0)
        num_tokens = len(tokens)

        trellis = torch.zeros((num_frame, num_tokens))
        trellis[1:, 0] = torch.cumsum(emission[1:, blank_id], 0)
        trellis[0, 1:] = -float("inf")
        trellis[-num_tokens + 1 :, 0] = float("inf")

        for t in range(num_frame - 1):
            trellis[t + 1, 1:] = torch.maximum(
                trellis[t, 1:] + emission[t, blank_id],
                trellis[t, :-1] + emission[t, tokens[1:]],
            )
        return trellis

    def backtrack(self, trellis, emission, tokens, blank_id=0):
        t, j = trellis.size(0) - 1, trellis.size(1) - 1
        path = [Point(j, t, emission[t, blank_id].exp().item())]
        while j > 0:
            assert t > 0
            p_stay = emission[t - 1, blank_id]
            p_change = emission[t - 1, tokens[j]]
            stayed = trellis[t - 1, j] + p_stay
            changed = trellis[t - 1, j - 1] + p_change
            t -= 1
            if changed > stayed:
                j -= 1
            prob = (p_change if changed > stayed else p_stay).exp().item()
            path.append(Point(j, t, prob))

        while t > 0:
            prob = emission[t - 1, blank_id].exp().item()
            path.append(Point(j, t - 1, prob))
            t -= 1

        return path[::-1]

    def merge_repeats(self, path, transcript):
        i1, i2 = 0, 0
        segments = []
        while i1 < len(path):
            while i2 < len(path) and path[i1].token_index == path[i2].token_index:
                i2 += 1
            if path[i1].token_index < len(transcript):
                score = sum(path[k].score for k in range(i1, i2)) / (i2 - i1)
                segments.append(
                    Segment(
                        transcript[path[i1].token_index],
                        path[i1].time_index,
                        path[i2 - 1].time_index + 1,
                        score,
                    )
                )
            i1 = i2
        return segments

    def merge_words(self, segments, separator="|"):
        words = []
        i1, i2 = 0, 0
        while i1 < len(segments):
            if i2 >= len(segments) or segments[i2].label == separator:
                if i1 != i2:
                    segs = segments[i1:i2]
                    word = "".join([seg.label for seg in segs])
                    score = sum(seg.score * seg.length for seg in segs) / sum(seg.length for seg in segs)
                    words.append(Segment(word, segments[i1].start, segments[i2 - 1].end, score))
                i1 = i2 + 1
                i2 = i1
            else:
                i2 += 1
        return words

    def snap_boundaries_hybrid(self, words, pipes_or_audio_path, audio_path=None, vad_spans=None, preloaded_audio=None, prelabel_segments=None):
        """
        Gold-calibrated boundary refinement (v9).

        Connected speech (<80ms CTC gap):
          - Find RMS valley in gap.
          - If valley is genuinely quiet (< trail_thresh): use valley as boundary.
          - Else (continuous voiced speech): use CTC pipe midpoint.

        True pause (>=80ms):
          - w1 end: last energy drop in gap.
          - w2 start: backward scan from CTC start (up to 500ms back).

        prelabel_segments: optional list of externally-provided draft
        word-level segments (e.g. this project's audio/*.json sidecar
        "lexical" entries -- {"refTranscript","startTime","endTime"}), used
        ONLY as a corroborating signal where our own acoustic heuristics
        have no case-specific evidence to go on (the plain CTC-midpoint
        default fallback), never to override a case that found real signal.
        Fully optional -- sparse, low-quality, or entirely absent prelabels
        just mean this corroboration never fires; nothing else changes.
        """
        import re as _re

        if not words:
            return words

        if audio_path is None:
            audio_path = pipes_or_audio_path

        if preloaded_audio is not None:
            data, sr = preloaded_audio
        else:
            data, sr = sf.read(audio_path)
            if data.ndim > 1:
                data = np.mean(data, axis=1)
        audio_dur = len(data) / sr

        # ── Acoustic features ─────────────────────────────────────────────────
        win_rms = max(1, int(sr * 0.002))   # 2ms RMS window; also the spectral-frame hop
        # EXPERIMENT (env-gated, default = the 2ms above, i.e. unchanged): smoothing the
        # envelope measured monotonically worse (see PULSAR_RMS_SMOOTH_MS below), so the
        # measured trend says SHARPER is better. This knob widens/narrows the RMS
        # integration window itself, independently of the spectral hop, to test whether
        # that trend continues below 2ms or whether 2ms is already the optimum.
        _rms_win_ms = float(os.environ.get("PULSAR_RMS_WIN_MS", "2.0"))
        win_env = max(1, int(sr * _rms_win_ms / 1000.0))
        sq = data.astype(np.float64) ** 2
        cumsum = np.cumsum(np.pad(sq, (0, win_env), mode="constant"))
        moving_mean = (cumsum[win_env:] - cumsum[:-win_env]) / win_env
        rms = np.sqrt(np.maximum(moving_mean, 0.0))

        # EXPERIMENT (env-gated, default OFF = exact previous behavior): the 2ms RMS
        # window above is extremely short, so argmin(rms[...]) -- which is how most of
        # the boundary cases below actually pick their point -- is choosing the single
        # noisiest local minimum sample inside its scan window. Smoothing the envelope
        # before the argmin trades a little temporal sharpness for a much lower-variance
        # valley location. bench/forced_aligner_smooth.py is an old snapshot that did
        # this at a fixed 6ms; this knob makes the width sweepable without a fork.
        # MEASURED (full corpus, 1716 boundaries): 0ms=12.491 MAE / 44.46% within 5ms,
        # 2ms=13.385 / 42.60%, 4ms=14.814 / 40.56% -- monotonically WORSE. The sharp 2ms
        # envelope is load-bearing, not noise; the argmin is not jitter-limited. Keep at 0.
        _rms_smooth_ms = float(os.environ.get("PULSAR_RMS_SMOOTH_MS", "0"))
        if _rms_smooth_ms > 0:
            _sm_k = max(1, int(sr * _rms_smooth_ms / 1000.0))
            rms = np.convolve(rms, np.ones(_sm_k) / _sm_k, mode="same")

        # EXPERIMENT (env-gated, default OFF = exact previous behavior): noise_floor and
        # peak_energy below are percentiles over the WHOLE clip, but every threshold
        # derived from them gates a LOCAL 50-100ms decision. On a clip with any loudness
        # drift (speaker leaning away, a quiet aside, a loud laugh) the local speech/
        # silence contrast is scaled against a global floor that doesn't describe the
        # audio at that instant. Setting the window (seconds) locally normalizes the
        # envelope so the same multipliers mean "this fraction of the contrast HERE".
        # Implemented as a normalization of rms itself rather than per-sample threshold
        # arrays so the 47 trail_thresh / 14 speech_thresh comparison sites stay untouched;
        # the window is wide relative to a scan window, so argmin behaviour is preserved.
        _local_win_s = float(os.environ.get("PULSAR_LOCAL_THRESH_WIN_S", "0"))
        _g_floor, _g_scale = 0.0, 1.0
        if _local_win_s > 0:
            _g_floor = float(np.percentile(rms, 10))
            _g_scale = max(float(np.percentile(rms, 95)) - _g_floor, 1e-9)
            _blk = max(1, int(sr * 0.100))
            _nb = max(1, len(rms) // _blk)
            _trim = _nb * _blk
            _blocks = rms[:_trim].reshape(_nb, _blk)
            _bf = np.percentile(_blocks, 10, axis=1)
            _bp = np.percentile(_blocks, 95, axis=1)
            _half = max(1, int(round(_local_win_s / 0.100 / 2)))
            _lf = np.empty(_nb)
            _lp = np.empty(_nb)
            for _b in range(_nb):
                _lo, _hi = max(0, _b - _half), min(_nb, _b + _half + 1)
                _lf[_b] = np.percentile(_bf[_lo:_hi], 25)
                _lp[_b] = np.percentile(_bp[_lo:_hi], 75)
            _xb = (np.arange(_nb) + 0.5) * _blk
            _xs = np.arange(len(rms))
            _lf_s = np.interp(_xs, _xb, _lf)
            _lp_s = np.interp(_xs, _xb, _lp)
            rms = (rms - _lf_s) / np.maximum(_lp_s - _lf_s, 1e-9)

        def _abs_rms(v: float) -> float:
            """Convert an absolute-RMS literal into whatever units `rms` is currently in
            (identity unless local normalization above is active)."""
            if _local_win_s <= 0:
                return v
            return (v - _g_floor) / _g_scale

        # Vectorized ZCR (5ms window)
        win_zcr = max(1, int(sr * 0.005))
        signs = np.sign(data)
        signs[signs == 0] = 1.0
        zc = (np.abs(np.diff(signs)) > 0).astype(np.float64)
        zc = np.pad(zc, (0, 1), mode="constant")
        cumsum_zc = np.cumsum(np.pad(zc, (0, win_zcr), mode="constant"))
        zcr = (cumsum_zc[win_zcr:] - cumsum_zc[:-win_zcr]) / (2.0 * win_zcr)

        # ── Spectral features (20ms frames, hop = win_rms so all signal arrays share
        # the same per-sample indexing convention as rms/zcr) ──────────────────────
        # RMS and ZCR are both blind in specific, complementary ways (RMS misses quiet-
        # but-real sounds; ZCR is unreliable at near-zero amplitude). These add signals
        # that fail in *different* places, so combining them is more robust than any
        # one alone: voicing (periodicity) separates real voiced speech from noise/
        # silence structurally rather than by energy; spectral flux flags any sudden
        # timbral change (onset) even when RMS rises gradually; HF-band ratio is a
        # cleaner, FFT-based alternative to ZCR for frication; spectral flatness flags
        # noise-like (breath, frication, room tone) vs. tonal (voiced) content.
        frame_len = int(sr * 0.020)
        hop = win_rms
        n_frames = max(1, (len(data) - frame_len) // hop + 1)
        frame_starts = (np.arange(n_frames) * hop).astype(int)
        raw_frames = np.stack([
            np.pad(data[s:s + frame_len].astype(np.float64), (0, max(0, frame_len - len(data[s:s + frame_len]))))
            for s in frame_starts
        ])
        raw_frames = raw_frames - raw_frames.mean(axis=1, keepdims=True)
        hann = np.hanning(frame_len)
        win_frames = raw_frames * hann[None, :]

        spec = np.abs(np.fft.rfft(win_frames, axis=1))
        freqs = np.fft.rfftfreq(frame_len, d=1.0 / sr)

        spec_sum = np.sum(spec, axis=1, keepdims=True) + 1e-12
        spec_norm = spec / spec_sum
        diff = np.diff(spec_norm, axis=0)
        diff = np.vstack([np.zeros((1, spec_norm.shape[1])), diff])
        spectral_flux_frames = np.sqrt(np.sum(np.maximum(diff, 0.0) ** 2, axis=1))

        hf_mask = freqs >= 4000.0
        hf_energy = np.sum(spec[:, hf_mask] ** 2, axis=1)
        total_energy = np.sum(spec ** 2, axis=1) + 1e-12
        hf_ratio_frames = hf_energy / total_energy

        _eps = 1e-12
        geo_mean = np.exp(np.mean(np.log(spec + _eps), axis=1))
        arith_mean = np.mean(spec, axis=1) + _eps
        spectral_flatness_frames = geo_mean / arith_mean

        # Voicing / periodicity via FFT-based autocorrelation in the human pitch range
        _nfft = frame_len
        while _nfft < 2 * frame_len:
            _nfft *= 2
        F_raw = np.fft.rfft(raw_frames, n=_nfft, axis=1)
        power = (F_raw * np.conj(F_raw)).real
        ac = np.fft.irfft(power, n=_nfft, axis=1)[:, :frame_len]
        ac0 = ac[:, 0]
        ac0_safe = np.where(ac0 > 1e-9, ac0, 1e-9)
        min_lag = max(1, int(sr / 400.0))
        max_lag = min(frame_len - 1, int(sr / 70.0))
        if max_lag > min_lag:
            voicing_frames = np.max(ac[:, min_lag:max_lag], axis=1) / ac0_safe
        else:
            voicing_frames = np.zeros(n_frames)
        voicing_frames = np.clip(voicing_frames, 0.0, 1.0)

        def _upsample_frames(frame_vals: np.ndarray) -> np.ndarray:
            out = np.empty(len(data), dtype=np.float64)
            for i in range(n_frames):
                s = frame_starts[i]
                e = frame_starts[i + 1] if i + 1 < n_frames else len(data)
                out[s:e] = frame_vals[i]
            if n_frames > 0:
                out[frame_starts[-1]:] = frame_vals[-1]
            return out

        spectral_flux      = _upsample_frames(spectral_flux_frames)
        hf_ratio            = _upsample_frames(hf_ratio_frames)
        spectral_flatness   = _upsample_frames(spectral_flatness_frames)
        voicing              = _upsample_frames(voicing_frames)

        prelabel_by_idx = self.match_prelabel_segments([w["text"] for w in words], prelabel_segments) if prelabel_segments else {}

        noise_floor    = float(np.percentile(rms, 10))
        peak_energy    = float(np.percentile(rms, 95))
        _speech_mult  = float(os.environ.get("PULSAR_SPEECH_MULT", "0.08"))
        _trail_mult   = float(os.environ.get("PULSAR_TRAIL_MULT", "0.055"))
        _whisper_mult = float(os.environ.get("PULSAR_WHISPER_MULT", "0.01"))
        speech_thresh  = noise_floor + _speech_mult * (peak_energy - noise_floor)
        trail_thresh   = noise_floor + _trail_mult * (peak_energy - noise_floor)
        whisper_thresh = noise_floor + _whisper_mult * (peak_energy - noise_floor)


        # ── Helpers ───────────────────────────────────────────────────────────
        def s2i(t: float) -> int:
            return max(0, min(len(rms) - 1, int(t * sr)))

        # ── Ear rules (2026-09-24) ─────────────────────────────────────────────
        # Learned from a blind listening review of 769 pairs (bench/review/answers.jsonl):
        # target = every cut the listener judged acceptable, hit = within 5ms of one. Each rule
        # won on every leave-one-set-out fold AND did not lower the hit rate on boundaries the
        # listener had verified. All are GATED: they only move a cut when the acoustic cue lands
        # close to the current one, which is what keeps already-right cuts intact.
        # A confirmation round then judged every boundary the rules move that had never been
        # heard (196 more pairs, bench/review/confirm_ear). Census over all moved boundaries in
        # the three gold sets: R3 11 fixed / 3 broken, R4 3/1, R5 5/2 -> ON. R2 7/8 (net loss)
        # and R1 15/9 but losing on the older clips 3/6 (a constant 3.6ms nudge, at the ear's
        # resolution) -> OFF by default, kept for re-testing with more data.
        # PULSAR_DISABLE_EAR_RULES="R3,R5" turns rules off, PULSAR_ENABLE_EAR_RULES="R1" opts in.
        _env_set = lambda k: {x.strip().upper() for x in os.environ.get(k, "").split(",") if x.strip()}
        _ear_off = ({"R1", "R2"} - _env_set("PULSAR_ENABLE_EAR_RULES")) | _env_set("PULSAR_DISABLE_EAR_RULES")

        def ear_rule(name):
            return name not in _ear_off

        def vowel_voicing_onset(ps, pe):
            """Steepest voicing rise in [ps-80ms, pe+40ms] (frame-centred), as used by G1."""
            fa = max(0, int(((ps - 0.080) * sr - frame_len / 2) / hop))
            fb = min(len(voicing_frames), int(((pe + 0.040) * sr - frame_len / 2) / hop))
            seg = voicing_frames[fa:fb]
            if len(seg) <= 10:
                return None
            return ((fa + int(np.argmax(seg[5:] - seg[:-5])) + 2) * hop + frame_len / 2) / sr

        def gated(cur, target, gate_s):
            return target if target is not None and abs(target - cur) <= gate_s else cur

        # RMS-only "silence" tests are blind to fricatives: a voiceless fricative onset
        # (s, f, sh, th...) is quiet (low RMS, easily under trail_thresh) but acoustically
        # active -- high-frequency turbulent noise gives it a markedly elevated zero-
        # crossing rate versus genuine silence or voiced speech. Confirmed concretely: at
        # a "signify" onset, ZCR jumps from ~0.02-0.03 (voiced-speech baseline) to
        # 0.08-0.23 exactly at the gold boundary, while RMS stays low throughout and a
        # pure-RMS backward scan walks straight past it. is_true_silence() is a drop-in
        # replacement for "rms[k] < trail_thresh" wherever that's used to mean "no speech
        # here" -- it additionally requires a low ZCR, consistent with the fricative/
        # sibilant ZCR thresholds (0.035-0.08) already used elsewhere in this file.
        ZCR_FRICATIVE_THRESH = 0.05
        # At very low RMS (near-total silence), ZCR itself becomes noisy and spuriously
        # elevated (near-zero-amplitude samples cross zero erratically), so it is only a
        # reliable frication indicator once there is some real signal present. Below this
        # fraction of trail_thresh, trust RMS alone; only consult ZCR in the "grey zone"
        # between that floor and trail_thresh, where a quiet-but-real fricative would sit.
        ZCR_GATE_RMS_FRAC = float(os.environ.get("PULSAR_ZCR_GATE_FRAC", "0.3"))

        def is_true_silence(k: int) -> bool:
            if rms[k] >= trail_thresh:
                return False
            if rms[k] < ZCR_GATE_RMS_FRAC * trail_thresh:
                return True
            return zcr[k] < ZCR_FRICATIVE_THRESH

        def first_onset(from_i: int, to_i: int) -> int:
            for k in range(from_i, to_i):
                if rms[k] > speech_thresh:
                    return k
            return to_i

        def sustained_onset(from_i: int, to_i: int, hold_ms: float = 10.0) -> int:
            """Find where speech becomes sustained (not just a single burst spike).
            Returns the sample where RMS exceeds speech_thresh and stays up for
            at least hold_ms ms within the next 20ms window."""
            hold_samples = max(1, int(hold_ms * sr / 1000))
            for k in range(from_i, to_i - hold_samples):
                if rms[k] > speech_thresh:
                    # Check if it sustains for hold_ms
                    window = rms[k: min(k + hold_samples * 2, to_i)]
                    if np.mean(window) > speech_thresh * 0.5:
                        return k
            return to_i

        def last_drop(from_i: int, to_i: int) -> int:
            for k in range(to_i, from_i, -1):
                if rms[k] > speech_thresh:
                    return k
            return from_i

        def last_drop_trail(from_i: int, to_i: int) -> int:
            """Last sample above trail_thresh scanning backward."""
            for k in range(to_i, from_i, -1):
                if rms[k] > trail_thresh:
                    return k
            return from_i

        def clean_txt(text: str) -> str:
            import re as _re2
            return _re2.sub(r"[^a-z]", "", text.lower())

        def ends_in_stop(text: str) -> bool:
            c = clean_txt(text)
            if not c or c.endswith("ing"): return False
            if c.endswith(("ke", "te", "pe", "de", "be", "ge", "ck")): return True
            return c[-1] in "ktpbdgc"

        def ends_in_velar_stop(text: str) -> bool:
            c = clean_txt(text)
            if not c or c.endswith("ing"): return False
            if c.endswith(("ke", "ck", "ge")): return True
            return c[-1] in "kgc"

        def starts_with_stop(text: str) -> bool:
            c = clean_txt(text)
            if not c or c.startswith("th") or c.startswith("ch") or c.startswith("sh"): return False
            return c[0] in "ktpbdgc"

        def ends_in_nasal(text: str) -> bool:
            c = clean_txt(text)
            if not c: return False
            if c.endswith(("me", "ne", "ng")): return True
            return c[-1] in "nm"

        def starts_with_nasal(text: str) -> bool:
            c = clean_txt(text)
            return bool(c) and c[0] in "nm"

        def ends_in_fricative(text: str) -> bool:
            c = clean_txt(text)
            if not c or c in ("the", "she", "he", "we", "be", "me"): return False
            if c.endswith(("se", "ze", "ve", "fe", "sh", "ch", "th", "ce")): return True
            return c[-1] in "fvsz"

        def ends_in_sibilant(text: str) -> bool:
            c = clean_txt(text)
            if not c: return False
            if c.endswith(("s", "z", "sh", "ch", "x", "ce", "se", "ze")): return True
            return False

        def ends_in_vowel(text: str) -> bool:
            c = clean_txt(text)
            if not c: return False
            if c in ("the", "she", "he", "we", "be", "me"): return True
            if ends_in_stop(c) or ends_in_nasal(c) or ends_in_fricative(c):
                return False
            return c[-1] in "aeiouy"

        def starts_with_sibilant(text: str) -> bool:
            c = clean_txt(text)
            return c.startswith("s") or c.startswith("sh") or c.startswith("ch") or c.startswith("z") or c.startswith("kh")

        def starts_with_vowel(text: str) -> bool:
            c = clean_txt(text)
            return bool(c) and (c[0] in "aeiou" or c.startswith("uh") or c.startswith("um"))

        def starts_with_liquid(text: str) -> bool:
            c = clean_txt(text)
            return bool(c) and c[0] in "rl"

        def starts_with_voiceless_th(text: str) -> bool:
            c = clean_txt(text)
            return c.startswith("th") and not c.startswith(("the", "that", "this", "there", "they", "their", "them", "then", "those", "these"))

        # ── Extract pipe starts, midpoints, and ends ──────────────────────────
        pipes_raw = pipes_or_audio_path
        pipe_mids   = []
        pipe_starts = []
        pipe_ends   = []
        if isinstance(pipes_raw, list) and pipes_raw and isinstance(pipes_raw[0], dict):
            pipe_mids   = [(p["start"] + p["end"]) / 2.0 for p in pipes_raw]
            pipe_starts = [p["start"] for p in pipes_raw]
            pipe_ends   = [p["end"] for p in pipes_raw]

        refined = [dict(w) for w in words]

        # ── Edge: first word onset ────────────────────────────────────────────
        if refined:
            wf = refined[0]
            wf_txt = wf["text"].strip().lower()
            is_whisper = wf_txt.startswith("((") or wf_txt == "(())"
            lookback = 0.400 if is_whisper else 0.150
            si = s2i(max(0.0, wf["start"] - lookback))
            ei = s2i(wf["end"])
            wf_st_i = s2i(wf["start"])
            # Walk backward for a SUSTAINED dip below trail_thresh, not just a single
            # sample -- a brief single-frame dip is common noise even inside a noisy
            # region (e.g. mumbled/unintelligible "(())" murmur), and stopping at the
            # first one badly undershoots the true onset by stopping inside that murmur
            # rather than continuing back through it to the real silence before it.
            sil_hold_i = max(1, int(0.015 * sr))
            for k in range(wf_st_i, si, -1):
                if rms[k] < trail_thresh:
                    window = rms[max(si, k - sil_hold_i):k + 1]
                    if len(window) >= max(1, int(sil_hold_i * 0.7)) and np.mean(window) < trail_thresh * 1.1:
                        si = k
                        break
            on = first_onset(si, ei)
            wf["start"] = round(max(0.0, on / sr - 0.010), 4)

        # ── Edge: last word drop ──────────────────────────────────────────────
        if refined:
            wl = refined[-1]
            si = s2i(wl["start"])
            ei = s2i(min(audio_dur, wl["end"] + 0.250))
            dp = last_drop(si, ei)
            wl["end"] = round(min(audio_dur, dp / sr + 0.010), 4)

        skip_pairs = set()
        # ── Pre-Pass: Consecutive Identical Fillers ('uh -> uh', 'um -> um') ──
        for i in range(len(refined) - 1):
            w1 = refined[i]
            w2 = refined[i + 1]
            c1_txt = clean_txt(w1["text"])
            c2_txt = clean_txt(w2["text"])
            if c1_txt in ("uh", "um") and c2_txt in ("uh", "um"):
                w2_core_i = s2i(min(w2["end"], max(w2["start"] + 0.040, (w2["start"] + w2["end"]) / 2.0)))
                sil_max = int(0.040 * sr)
                silence_count = 0
                min_scan_i = s2i(refined[i - 1]["end"] if i > 0 else 0.0)
                voiced_st_i = w2_core_i
                for k in range(w2_core_i, min_scan_i, -1):
                    is_voiced = (rms[k] >= trail_thresh * 0.8) and (zcr[k] < 0.06)
                    if not is_voiced:
                        silence_count += 1
                        if silence_count >= sil_max:
                            voiced_st_i = k + silence_count
                            break
                    else:
                        silence_count = 0
                        voiced_st_i = k

                v_st_t = round(voiced_st_i / sr, 4)
                if (w2["start"] - v_st_t) >= 0.060:
                    v_si = s2i(v_st_t + 0.060)
                    v_ei = s2i(w2["end"] - 0.030)
                    if v_ei > v_si:
                        valley_idx = v_si + np.argmin(rms[v_si:v_ei])
                        mid_bnd = round(valley_idx / sr, 4)
                        w1["start"] = v_st_t
                        w1["end"]   = round(mid_bnd - 0.001, 4)
                        w2["start"] = round(mid_bnd + 0.001, 4)
                        skip_pairs.add(i)

        # ── Pre-Pass B: Cutoffs Ending in '-' followed by Vowel / Word ──
        for i in range(len(refined) - 1):
            if i in skip_pairs:
                continue
            w1 = refined[i]
            w2 = refined[i + 1]
            if w1["text"].endswith("-") and (starts_with_vowel(w2["text"]) or w2["text"].startswith("uh") or w2["text"].startswith("um")):
                si = s2i(max(w1["start"] + 0.040, w1["end"] - 0.040))
                ei = s2i(min(audio_dur, w2["start"] + 0.010))
                if ei > si + int(0.020 * sr):
                    dip_i = si + int(np.argmin(rms[si:ei]))
                    dip_t = dip_i / sr
                    w1["end"]   = round(dip_t - 0.001, 4)
                    w2["start"] = round(dip_t + 0.001, 4)
                    skip_pairs.add(i)


        # ── Pass 1: Pairwise refinement ───────────────────────────────────────
        for i in range(len(refined) - 1):
            if i in skip_pairs:
                continue
            w1 = refined[i]
            w2 = refined[i + 1]

            p_start = pipe_starts[i] if (pipe_starts and i < len(pipe_starts)) else min(w1["end"], w2["start"])
            p_end   = pipe_ends[i]   if (pipe_ends   and i < len(pipe_ends))   else max(w1["end"], w2["start"])
            p_mid   = pipe_mids[i]   if (pipe_mids   and i < len(pipe_mids))   else (p_start + p_end) / 2.0

            pause_dur = w2["start"] - p_end
            pause_check_start = p_end
            if (w2["start"] - w1["end"]) >= 0.100 and pause_dur < 0.100:
                pause_dur = w2["start"] - w1["end"]
                pause_check_start = w1["end"] + 0.020
            is_hesitation = False
            is_true_pause = False

            if pause_dur >= 0.100:
                p_si = s2i(pause_check_start)
                p_ei = s2i(w2["start"])
                if p_ei > p_si:
                    min_gap_rms = float(np.min(rms[p_si:p_ei]))
                    mean_gap_rms = float(np.mean(rms[p_si:p_ei]))

                    # Check if this is a vocalized hesitation filler (e.g. "think -> uh" with high RMS)
                    if pause_dur < 0.150 and ends_in_stop(w1["text"]) and clean_txt(w2["text"]) in ("uh", "um") and mean_gap_rms >= trail_thresh:
                        is_hesitation = True

                    if not is_hesitation:
                        max_sil_samples = 0
                        cur_sil_samples = 0
                        for r_val in rms[p_si:p_ei]:
                            if r_val < trail_thresh:
                                cur_sil_samples += 1
                                if cur_sil_samples > max_sil_samples:
                                    max_sil_samples = cur_sil_samples
                            else:
                                cur_sil_samples = 0
                        max_sil_ms = (max_sil_samples / sr) * 1000.0

                        if max_sil_ms >= 15.0:
                            is_true_pause = True
                        elif mean_gap_rms < speech_thresh and min_gap_rms < trail_thresh * 1.5:
                            is_true_pause = True

            if is_true_pause:
                # ── TRUE PAUSE ───────────────────────────────────────────────
                gap_si = s2i(max(0.0, w1["end"] - 0.005))
                gap_ei = s2i(min(w2["start"], w1["end"] + 0.500))

                # Detect first continuous silence drop after w1 to avoid jumping over inter-clause inhales/noises
                sil_run = 0
                sil_lim = int(0.015 * sr)
                first_drop_i = gap_si
                found_drop = False
                for k in range(gap_si, gap_ei):
                    if rms[k] < trail_thresh:
                        sil_run += 1
                        if sil_run >= sil_lim:
                            first_drop_i = k - sil_run
                            found_drop = True
                            break
                    else:
                        sil_run = 0
                        first_drop_i = k

                if found_drop:
                    buf = 0.015 if ends_in_stop(w1["text"]) else 0.010
                    w1_end_t = first_drop_i / sr + buf
                    # If w1 ends in stop and pause before w2 is moderate (<400ms), verify that an early closure dip
                    # didn't truncate the plosive burst by checking backwards from w2 start across dead silence
                    if ends_in_stop(w1["text"]) and (w2["start"] - w1["end"]) < 0.450:
                        # Forward check across stop closure: a released stop can produce a
                        # "burst train" -- one or more energetic/voiced blips (release burst,
                        # brief re-voicing) separated by near-silence, not just a single burst.
                        # RMS alone under-detects the fainter later blips (some barely cross
                        # speech_thresh), so voicing (periodicity) corroborates marginal RMS:
                        # a sample counts as burst-like if EITHER signal indicates real content.
                        # Iterate burst-then-drop detection so a second (or third) blip within
                        # reach of w2's start also gets absorbed into w1's end, not just the first.
                        max_search_end_i = s2i(w2["start"] - 0.015)
                        search_from_i = first_drop_i
                        w1_end_t_burst = None
                        # Voicing (like ZCR) becomes noisy/spuriously elevated at near-zero RMS,
                        # so a single qualifying sample is not enough evidence of a real burst --
                        # require ~8ms of sustained qualification to filter isolated noise blips
                        # while still catching genuine (15-40ms) trailing bursts.
                        burst_sustain_lim = int(0.005 * sr)
                        while search_from_i < max_search_end_i:
                            burst_lim = min(max_search_end_i, search_from_i + int(0.130 * sr))
                            burst_k = None
                            burst_run = 0
                            for k in range(search_from_i, burst_lim):
                                if rms[k] >= speech_thresh or (voicing[k] >= 0.5 and rms[k] >= trail_thresh):
                                    burst_run += 1
                                    if burst_run >= burst_sustain_lim:
                                        burst_k = k
                                else:
                                    burst_run = 0
                            if burst_k is None:
                                break
                            # Plosive burst found! Find where it drops back into true silence
                            # (both RMS and voicing collapsed, not just a voiced-content dip).
                            # Voicing itself becomes spuriously elevated at near-total silence
                            # (same artifact as ZCR), so once RMS is deep enough below
                            # trail_thresh, trust it alone rather than waiting on voicing too.
                            drop_k = None
                            for k in range(burst_k, max_search_end_i):
                                if rms[k] < trail_thresh and (voicing[k] < 0.5 or rms[k] < 0.3 * trail_thresh):
                                    win_end = min(len(rms), k + int(0.012 * sr))
                                    if win_end >= len(rms) or np.mean(rms[k:win_end]) < trail_thresh:
                                        drop_k = k
                                        break
                            if drop_k is None:
                                break
                            w1_end_t_burst = drop_k / sr + 0.005
                            search_from_i = drop_k
                        if w1_end_t_burst is not None:
                            w1_end_t = w1_end_t_burst
                        else:
                            bk_ei = s2i(max(0.0, w2["start"] - 0.015))
                            bk_si = s2i(max(0.0, w1["start"] + 0.020))
                            found_bk_k = None
                            for k in range(bk_ei, bk_si, -1):
                                if rms[k] >= trail_thresh:
                                    found_bk_k = k
                                    break
                            if found_bk_k is not None:
                                bk_t = found_bk_k / sr
                                if 0 < bk_t - w1["end"] <= 0.080 and (w2["start"] - bk_t) >= 0.040:
                                    w1_end_t = bk_t
                    elif ends_in_sibilant(w1["text"]) and (clean_txt(w1["text"]).endswith(("ms", "ns", "ngs", "nds", "mes", "nes")) or ends_in_nasal(w1["text"])):
                        # Verify that an internal closure dip didn't truncate trailing sibilant frication (e.g. "comes -> we")
                        sib_lim = s2i(min(w2["start"], w1["end"] + 0.350))
                        start_k = s2i(w1["end"])
                        last_sib_k = start_k
                        for k in range(start_k, sib_lim):
                            if zcr[k] >= 0.080 and rms[k] >= _abs_rms(0.0003):
                                last_sib_k = k
                            elif rms[k] < _abs_rms(0.0002):
                                if (k - last_sib_k) > int(0.020 * sr):
                                    break
                        if last_sib_k > start_k:
                            w1_end_t = max(w1_end_t, last_sib_k / sr)
                else:
                    # Speech continues between w1 and w2 without sustained silence drop (connected speech)
                    if ends_in_sibilant(w1["text"]) and (clean_txt(w2["text"]) in ("uh", "um") or starts_with_vowel(w2["text"]) or starts_with_nasal(w2["text"])):
                        # Sibilant fricative into voiced murmur/vowel (e.g. "kids -> um"):
                        # High ZCR (sibilant) drops into low ZCR voiced speech
                        z_si = s2i(max(0.0, w1["start"] + 0.020))
                        z_ei = s2i(min(audio_dur, w2["start"] + 0.030))
                        z_drop_i = None
                        for k in range(z_ei, z_si, -1):
                            if zcr[k] >= 0.080:
                                z_drop_i = k + int(0.004 * sr)
                                break
                        if z_drop_i is not None:
                            bnd = z_drop_i / sr
                        else:
                            bnd = (w1["end"] + w2["start"]) / 2.0
                        w1_end_t = bnd - 0.001
                        w2["start"] = round(bnd + 0.001, 4)
                    else:
                        # Connected speech across gap without sustained silence:
                        # Locate the acoustic dip / syllable boundary between w1 and w2
                        scan_si = s2i(max(0.0, min(w1["end"], p_start) - 0.040))
                        scan_ei = s2i(min(audio_dur, max(w2["start"], p_end) + 0.020))
                        if scan_ei > scan_si + int(0.010 * sr):
                            dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                            bnd = dip_i / sr
                            w1_end_t = bnd - 0.001
                            w2["start"] = round(bnd + 0.001, 4)
                        else:
                            bnd = (w1["end"] + w2["start"]) / 2.0
                            w1_end_t = bnd - 0.001
                            w2["start"] = round(bnd + 0.001, 4)

                # In long pauses (>350ms) after vowel, detect true vowel offset before any inter-clause noise/laughter
                if (w2["start"] - w1["start"]) > 0.350 and ends_in_vowel(w1["text"]):
                    c1_clean = clean_txt(w1["text"])
                    if len(c1_clean) <= 3 and (w1["end"] - w1["start"]) > 0.300:
                        # Short monosyllable word over-extended by CTC into pause noise/laughter (e.g. "see ... haha")
                        w1_core_i = s2i(w1["start"] + 0.040)
                    else:
                        # Multi-syllabic or normal-length word: start scan near word end to avoid internal consonant closures
                        w1_core_i = s2i(max(w1["start"], w1["end"] - 0.040))
                    silence_run = 0
                    sil_lim = int(0.012 * sr)
                    drop_fwd_i = s2i(w1["end"])
                    for k in range(w1_core_i, s2i(w2["start"])):
                        if rms[k] < trail_thresh:
                            silence_run += 1
                            if silence_run >= sil_lim:
                                drop_fwd_i = k - silence_run
                                break
                        else:
                            silence_run = 0
                            drop_fwd_i = k
                    w1_end_t = min(w1_end_t, drop_fwd_i / sr)

                w1["end"] = round(min(w1_end_t, w2["start"] - 0.002), 4)

                # For w2 start:
                if found_drop:
                    c2_raw = w2["text"].strip().lower()
                    c2_clean = clean_txt(w2["text"])
                    is_whisper_w2 = c2_raw.startswith("((") or c2_raw == "(())"
                    # NOTE: tried a rule here attributing any short (<400ms) pause before a
                    # truncated retry attempt (w2 ending in "-") entirely to that attempt,
                    # on the theory that a hesitation-before-a-stutter is conventionally
                    # absorbed into the stutter's own span (this fixed clip 7's "pe-", a
                    # genuine near-zero-gap case in gold). Reverted: tested against the
                    # full benchmark per the one-fix-at-a-time regression methodology, and
                    # it net-regressed -- e.g. clip 5's "the-" has a genuine ~181ms pause
                    # in gold (NOT absorbed) despite matching the same "w2 ends in '-',
                    # gap < 400ms" trigger. The "pause before a truncation is absorbed
                    # into it" pattern is not actually general; it only coincidentally fit
                    # the one case it was derived from. No acoustic signal distinguishes
                    # the two cases without more information than is available here.
                    if is_whisper_w2:
                        # Low-energy whisper murmur scan backwards
                        w2_st_i = s2i(w2["start"])
                        min_back_i = s2i(w1["end"] + 0.002)
                        silence_run = 0
                        sil_lim = int(0.015 * sr)
                        onset_i = w2_st_i
                        for k in range(w2_st_i, min_back_i, -1):
                            if rms[k] < whisper_thresh:
                                silence_run += 1
                                if silence_run >= sil_lim:
                                    onset_i = k + silence_run
                                    break
                            else:
                                silence_run = 0
                                onset_i = k
                        w2_start_t = max(onset_i / sr - 0.010, w1["end"] + 0.002)
                    elif c2_clean in ("um", "uh", "ah", "er"):
                        # Scan backwards from w2 core (peak) across continuous murmur.
                        # A preceding voiceless-stop release (e.g. "think -> uh") produces
                        # noisy aspiration: brief, isolated RMS blips that randomly exceed
                        # trail_thresh (confirmed up to 0.014 vs trail_thresh ~0.008) but
                        # carry no real periodicity (voicing 0.09-0.17, well below genuine
                        # murmur/vowel voicing). Pure-RMS silence testing lets each blip
                        # reset the silence run, so the scan never accumulates a clean 75ms
                        # stretch and walks all the way back into what is really still w1's
                        # burst/aspiration. Require either a confidently loud sample
                        # (>=speech_thresh) or genuine periodicity (voicing) before treating
                        # it as real murmur content, not just any momentary RMS peak.
                        w2_core_i = s2i(min(w2["end"], max(w2["start"] + 0.040, (w2["start"] + w2["end"]) / 2.0)))
                        min_back_i = s2i(w1["end"] + 0.002)
                        silence_run = 0
                        sil_lim = int(0.075 * sr)
                        onset_i = w2_core_i
                        for k in range(w2_core_i, min_back_i, -1):
                            is_real_speech = rms[k] >= speech_thresh or (rms[k] >= trail_thresh and voicing[k] >= 0.35)
                            if not is_real_speech:
                                silence_run += 1
                                if silence_run >= sil_lim:
                                    onset_i = k + silence_run
                                    break
                            else:
                                silence_run = 0
                                onset_i = k
                        w2_start_t = max(onset_i / sr - 0.010, w1["end"] + 0.002)
                    elif starts_with_sibilant(w2["text"]):
                        # Sibilant words (s, sh, ch, z): scan backwards starting near w2["start"]
                        # looking for where the signal drops into true pause silence, avoiding
                        # internal stop closures in clusters (e.g. sp-, st-, sk-). RMS alone is
                        # blind here: sibilant frication (the /s/ itself) is often LOW ENERGY,
                        # indistinguishable from true silence by RMS, which made the scan stop
                        # almost immediately at w2_st_i instead of walking back through the
                        # frication to the real pre-word pause. ZCR resolves this: frication is
                        # high zero-crossing-rate noise, true silence is low.
                        # BUT: at very low RMS (near-total silence), ZCR itself becomes noisy and
                        # spuriously high (near-zero amplitude crossing zero erratically), so the
                        # ZCR override is only trusted within a bounded window close to w2_st_i --
                        # long enough to cover a sibilant's own frication (rarely >150ms) but not
                        # so long that it misreads deep background silence further back as speech.
                        # Beyond that window the scan falls back to the plain RMS test.
                        w2_st_i = s2i(min(w2["end"], w2["start"] + 0.030))
                        min_back_i = s2i(w1["end"] + 0.002)
                        zcr_trust_limit_i = max(min_back_i, w2_st_i - int(0.150 * sr))
                        silence_run = 0
                        sil_lim = int(0.015 * sr)
                        onset_i = s2i(w2["start"])
                        for k in range(w2_st_i, min_back_i, -1):
                            is_sil = is_true_silence(k) if k >= zcr_trust_limit_i else (rms[k] < trail_thresh)
                            if is_sil:
                                silence_run += 1
                                if silence_run >= sil_lim:
                                    onset_i = k + silence_run
                                    break
                            else:
                                silence_run = 0
                                onset_i = k
                        w2_start_t = max(onset_i / sr - 0.005, w1["end"] + 0.002)
                    else:
                        # Scan backwards from w2 across speech to find true acoustic onset
                        # without jumping over pre-pause inhales or noise
                        w2_st_i = s2i(min(w2["end"], w2["start"] + 0.035))
                        min_back_i = s2i(w1["end"] + 0.002)
                        silence_run = 0
                        sil_lim = int(0.030 * sr)
                        onset_i = s2i(w2["start"])
                        for k in range(w2_st_i, min_back_i, -1):
                            if rms[k] < trail_thresh:
                                silence_run += 1
                                if silence_run >= sil_lim:
                                    onset_i = k + silence_run
                                    break
                            else:
                                silence_run = 0
                                onset_i = k
                        w2_start_t = max(onset_i / sr - 0.005, w1["end"] + 0.002)

                    w2["start"] = round(w2_start_t, 4)

            else:
                # ── CONTINUOUS SPEECH ─────────────────────────────────────────
                # 0. Inter-word quiet gap inside pipe (e.g. "pretty -> cool")
                is_pipe_gap = False
                if ends_in_vowel(w1["text"]) and not is_hesitation and (p_end - p_start) >= 0.035 and (w2["start"] - p_start) >= 0.075:
                    p_si = s2i(p_start)
                    p_ei = s2i(p_end)
                    if p_ei > p_si:
                        min_pipe_rms = float(np.min(rms[p_si:p_ei]))
                        # A single very-low sample is not enough evidence that the WHOLE
                        # pipe span [p_start, p_end] is a genuine silence gap -- a brief
                        # coarticulation dip (e.g. vowel trailing into a nasal onset) can
                        # momentarily bottom out just as low while the span as a whole
                        # stays continuously voiced (confirmed on "i -> never": min dips
                        # to 0.0016, but the span's mean RMS is 0.02-0.03, well above
                        # trail_thresh, and blindly splitting at p_start/p_end put "i"
                        # 76ms early and "never" 35ms late). Require the span's mean RMS
                        # to also be low, confirming it is quiet throughout, not just at
                        # one narrow notch.
                        mean_pipe_rms = float(np.mean(rms[p_si:p_ei]))
                        if min_pipe_rms < _abs_rms(0.0025) and mean_pipe_rms < trail_thresh:
                            is_pipe_gap = True

                if is_pipe_gap:
                    w1["end"]   = round(p_start, 4)
                    w2["start"] = round(p_end, 4)
                    continue

                search_st = min(w1["end"], w2["start"], p_start)
                search_en = max(w1["end"], w2["start"], p_end)

                if search_en - search_st < 0.004:
                    mid_t = (search_st + search_en) / 2
                    search_st = mid_t - 0.002
                    search_en = mid_t + 0.002

                si = s2i(search_st)
                ei = s2i(search_en)

                if si >= ei:
                    bnd = p_mid
                    w1["end"]   = round(bnd - 0.001, 4)
                    w2["start"] = round(bnd + 0.001, 4)
                    continue

                valley_i   = si + int(np.argmin(rms[si:ei]))
                valley_rms = rms[valley_i]
                valley_t   = valley_i / sr

                c1 = clean_txt(w1["text"])
                c2 = clean_txt(w2["text"])
                w2_start_override = None

                # ABLATION (env-gated, default OFF = exact previous behavior): bypass the
                # entire 14-case continuous-speech dispatch below and just take the CTC
                # pipe midpoint, which is what case 14 (the do-nothing fallback) already
                # does. Full-corpus per-case attribution showed every case lands within
                # ~2ms MAE of that fallback, so this measures what the whole heuristic
                # layer is actually worth rather than arguing about it.
                if os.environ.get("PULSAR_FORCE_PMID") == "1":
                    bnd = max(w1["start"] + 0.001, min(w2["end"] - 0.001, p_mid))
                    w1["end"]   = round(bnd - 0.001, 4)
                    w2["start"] = round(bnd + 0.001, 4)
                    continue

                # 1. Sibilants (/s/, /sh/, /ch/, /z/, /kh/)
                if starts_with_sibilant(w2["text"]):
                    if ends_in_sibilant(w1["text"]) or ends_in_fricative(w1["text"]):
                        if w2["text"].endswith("-") and (w2["end"] - w1["start"]) >= 0.250:
                            # Full word into stuttered sibilant restart (e.g. "was -> s-"):
                            # w1 must span its natural syllable duration; find the articulator reset dip
                            dip_si = s2i(w1["start"] + 0.150)
                            dip_ei = s2i(min(audio_dur, min(w1["start"] + 0.240, w2["end"] - 0.040)))
                            if dip_ei > dip_si:
                                dip_i = dip_si + int(np.argmin(rms[dip_si:dip_ei]))
                                bnd = dip_i / sr
                            else:
                                bnd = (w1["start"] + w2["end"]) / 2.0
                        else:
                            # Both words are sibilants/fricatives ("is -> selling"):
                            # Pipe midpoint is exact boundary
                            bnd = p_mid
                    elif c1.endswith(("st", "sp", "sk")):
                        # w1 ends in stop after sibilant (e.g. "just -> still"):
                        # w2 start is the true sibilant onset after stop release
                        bnd = w2["start"]
                    else:
                        z_si = s2i(max(0.0, p_start - 0.060))
                        z_ei = s2i(p_end)
                        found_z = None
                        for k in range(z_si, z_ei):
                            if zcr[k] >= 0.035 and (k + int(0.006 * sr) < len(zcr) and zcr[k + int(0.006 * sr)] >= 0.08):
                                found_z = k / sr
                                break
                        bnd = found_z if found_z is not None else p_mid

                # 2. Hesitation filler ("think -> uh")
                elif is_hesitation:
                    # p_end (the raw CTC pipe's own end estimate) can include a long
                    # quiet-but-voiced stretch that's really still w1's own trailing
                    # closure/release, well past where w1 should truly end (confirmed:
                    # "that -> um", p_end lands 70ms after gold's "that" end, inside a
                    # quiet region with sustained voicing 0.36-0.73 that gold treats as
                    # neither "that" nor "um"). Scan forward from w1's own raw end for
                    # the first SUSTAINED (15ms) drop into near-total silence (well below
                    # trail_thresh), marking where w1's audible content truly stops;
                    # fall back to p_end if no such drop is found.
                    scan_si = s2i(w1["end"])
                    scan_ei = s2i(min(audio_dur, p_end))
                    found_i = None
                    if scan_ei > scan_si:
                        _run = 0
                        _sus = int(0.015 * sr)
                        for k in range(scan_si, scan_ei):
                            if rms[k] < 0.5 * trail_thresh:
                                _run += 1
                                if _run >= _sus:
                                    found_i = k - _run
                                    break
                            else:
                                _run = 0
                    if found_i is not None:
                        bnd = found_i / sr
                        # Pulling w1's end back to its true closure leaves a real gap
                        # before w2's own onset (the quiet lead-in belongs to neither
                        # word per gold) -- w1["end"] and w2["start"] must NOT be tied
                        # to the same split point here. Scan forward from the closure
                        # for w2's own confident (sustained >=15ms >=speech_thresh)
                        # onset and decouple w2["start"] from bnd via the override
                        # mechanism (confirmed: "that -> um", gold's "um" start sits at
                        # the filler's loud onset, ~100ms after "that"'s true end, not
                        # adjacent to it).
                        fwd_si = s2i(bnd)
                        fwd_ei = s2i(min(audio_dur, w2["end"]))
                        onset_i = None
                        if fwd_ei > fwd_si:
                            _run2 = 0
                            _sus2 = int(0.015 * sr)
                            for k in range(fwd_si, fwd_ei):
                                if rms[k] >= speech_thresh:
                                    _run2 += 1
                                    if _run2 >= _sus2:
                                        onset_i = k - _run2
                                        break
                                else:
                                    _run2 = 0
                        if onset_i is not None:
                            w2_start_override = max(onset_i / sr - 0.010, bnd + 0.002)
                    else:
                        bnd = p_end

                # 3. Glides (/w/ as in "wanna", "we-", /j/ as in "you", "used")
                elif c2.startswith("w") and ends_in_vowel(w1["text"]) and (w2["start"] - p_end) >= 0.015:
                    bnd = w2["start"]
                elif c2 == "you" and (c1.endswith(("t", "d", "te", "de")) or ends_in_nasal(w1["text"])):
                    # Alveolar stop/nasal releases into glide /j/ at p_start
                    bnd = p_start
                elif c2 == "you" and (ends_in_stop(w1["text"]) or ends_in_vowel(w1["text"])):
                    bnd = w2["start"]

                # 4. Fricative offset into liquid/vowel
                elif ends_in_fricative(w1["text"]) and not ends_in_stop(w1["text"]):
                    if starts_with_liquid(w2["text"]):
                        if ends_in_sibilant(w1["text"]):
                            scan_si = s2i(p_start)
                            scan_ei = s2i(max(p_end, w2["start"]))
                            if scan_ei > scan_si:
                                dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                                bnd = dip_i / sr
                            else:
                                bnd = p_mid
                        else:
                            bnd = p_mid
                    elif starts_with_vowel(w2["text"]):
                        if ends_in_sibilant(w1["text"]) or ends_in_fricative(w1["text"]):
                            # Sibilant or fricative into vowel: detect acoustic drop in ZCR where frication ends
                            z_si = s2i(max(0.0, p_start - 0.040))
                            z_ei = s2i(min(audio_dur, max(p_end, w2["start"] - 0.010)))
                            drop_z = None
                            if os.environ.get("PULSAR_LEGACY_CASE4_ZSCAN") == "1":
                                for k in range(z_ei, z_si, -1):
                                    if zcr[k] >= 0.055:
                                        drop_z = (k + int(0.005 * sr)) / sr
                                        break
                            else:
                                # Frication offset = end of the FIRST high-ZCR run in the window
                                # (w1's own fricative), bridging dips shorter than 10ms. The old
                                # backward scan took the LAST high-ZCR sample anywhere in the window,
                                # which often sits inside w2 (e.g. "of -> us" grabbed the /s/ of "us"),
                                # landing a median 49ms late; users corrected 64% of this leaf's
                                # boundaries. Capping the window at p_end instead fixed that but broke
                                # pairs whose frication runs past an early CTC pipe ("kids -> um"
                                # went 4ms -> 115ms early). Following the run handles both.
                                # Human-corrected boundaries on this leaf, 2026-09-23:
                                #   bundle_049 (dev)  62.1 -> 11.1ms MAE,  7% -> 41% within 5ms
                                #   old 14 (held-out) 13.8 -> 10.0ms MAE, 50% -> 57% within 5ms
                                # with no accepted boundary moved on either set.
                                # PULSAR_LEGACY_CASE4_ZSCAN=1 restores the old scan.
                                hi = np.where(zcr[z_si:z_ei + 1] >= 0.055)[0]
                                if len(hi):
                                    gap_max = int(0.010 * sr)
                                    run_end = hi[0]
                                    for k in hi[1:]:
                                        if k - run_end > gap_max:
                                            break
                                        run_end = k
                                    drop_z = (z_si + run_end + int(0.005 * sr)) / sr
                            bnd = drop_z if drop_z is not None else p_mid
                        elif (w2["start"] - p_end) >= 0.075:
                            bnd = w2["start"]
                        else:
                            bnd = p_start
                    else:
                        scan_si = s2i(p_start)
                        scan_ei = s2i(p_end)
                        if scan_ei > scan_si:
                            dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                            bnd = dip_i / sr
                            # R2 (ear): pipe start -5ms when within 20ms. Hit rate 026 67->71%,
                            # 049 27->36%, old14 17->50%; verified 71->75%.
                            if ear_rule("R2"):
                                bnd = gated(bnd, p_start - 0.005, 0.020)
                        else:
                            bnd = p_mid

                # 5. Dental fricative /th/ onset after rhotic/liquid (e.g. "fear -> that's")
                elif (c2.startswith("that") or c2.startswith("the") or c2.startswith("this")) and c1.endswith("r"):
                    scan_si = s2i(max(0.0, p_end - 0.030))
                    scan_ei = s2i(min(audio_dur, w2["start"] + 0.010))
                    if scan_ei > scan_si:
                        dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                        bnd = dip_i / sr
                    else:
                        bnd = p_end

                # 6. Delayed word onset in raw CTC
                elif (w2["start"] - p_end) >= 0.075 and starts_with_vowel(w2["text"]) and not ends_in_vowel(w1["text"]):
                    if ends_in_stop(w1["text"]) or ends_in_nasal(w1["text"]) or c1.endswith("r"):
                        scan_si = s2i(max(0.0, p_start - 0.045))
                        if (w2["start"] - p_end) >= 0.150:
                            scan_ei = s2i(min(audio_dur, w2["start"] + 0.010))
                        else:
                            scan_ei = s2i(min(audio_dur, p_end + 0.025))
                        if scan_ei > scan_si:
                            # A genuine stop closure is not just a momentary dip under
                            # trail_thresh -- confirmed by comparing "think -> uh" (real,
                            # sustained ~60ms closure at 5-25% of trail_thresh) against
                            # "it -> actually" / "fond -> of" (a brief 2-sample dip barely
                            # under trail_thresh within otherwise continuous voicing, from a
                            # weak/incomplete stop articulation) -- the latter is NOT a real
                            # closure and must not trigger the forward-rise search below.
                            # Require the dip to be both deep (<50% of trail_thresh) and
                            # sustained (>=10ms) near the window start.
                            closure_win = rms[scan_si:min(scan_ei, scan_si + int(0.060 * sr))]
                            closure_sustain = int(0.010 * sr)
                            has_closure = False
                            _run = 0
                            for _v in closure_win:
                                if _v < 0.5 * trail_thresh:
                                    _run += 1
                                    if _run >= closure_sustain:
                                        has_closure = True
                                        break
                                else:
                                    _run = 0
                            if ends_in_stop(w1["text"]) and has_closure:
                                # A stop's own closure is near-total silence, and over a wide
                                # window it is very often the deepest RMS point in the whole
                                # span -- a blind argmin then wrongly pulls bnd back into w1's
                                # own closure/aspiration release instead of w2's true onset
                                # (confirmed: "think -> uh", raw CTC gap 340ms, argmin landed
                                # at the /k/ closure, 64ms before gold's real "uh" onset).
                                # Search FORWARD instead for the first SUSTAINED rise into
                                # real voiced content, skipping past the closure/aspiration;
                                # fall back to the old argmin only if nothing qualifies. Only
                                # do this when the window genuinely STARTS in a closure
                                # (confirmed dip below trail_thresh near scan_si) -- otherwise
                                # (e.g. a weakly-released/unreleased stop with no real silence
                                # gap at all, "think -> it" elsewhere in this clip) there is no
                                # closure to skip past and the forward search just fires on w1's
                                # own still-loud trailing content instead, landing even earlier
                                # than the old argmin.
                                sustain = int(0.015 * sr)
                                rise_i = None
                                for k in range(scan_si, scan_ei):
                                    if rms[k] >= speech_thresh or (rms[k] >= trail_thresh and voicing[k] >= 0.35):
                                        chk_hi = min(scan_ei, k + sustain)
                                        if chk_hi > k and np.mean(rms[k:chk_hi]) >= trail_thresh and np.mean(voicing[k:chk_hi]) >= 0.30:
                                            rise_i = k
                                            break
                                if rise_i is not None:
                                    bnd = rise_i / sr
                                else:
                                    dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                                    bnd = dip_i / sr
                            else:
                                dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                                bnd = dip_i / sr
                                # R5 (ear): pipe start when within 40ms. Hit rate 026 19->45%,
                                # old14 43->57%; verified 0->50% (n=2 -- smallest rule, least evidence).
                                if ear_rule("R5"):
                                    bnd = gated(bnd, p_start - 0.0001, 0.040)
                    elif w1["text"].startswith("((") or w1["text"] == "(())" or not c1:
                        # Whisper / inaudible token into vowel speech ("(()) -> uh"): find vowel attack after valley
                        scan_si = s2i(p_start)
                        scan_ei = s2i(w2["start"])
                        if scan_ei > scan_si:
                            v_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                            diff_win = int(0.035 * sr)
                            if v_i + diff_win < len(rms):
                                diffs = np.diff(rms[v_i : v_i + diff_win])
                                max_rise_i = v_i + int(np.argmax(diffs))
                                bnd = max_rise_i / sr
                            else:
                                bnd = v_i / sr
                        else:
                            bnd = p_mid
                    else:
                        bnd = w2["start"]

                # 7. Stop plosive onset (/b/, /p/, /d/, /t/, /g/, /k/) after vowel ("you -> become")
                elif starts_with_stop(w2["text"]) and ends_in_vowel(w1["text"]):
                    if (p_start - w1["end"]) >= 0.030:
                        # Plosive closure drop before lips/tongue release ("you -> become")
                        scan_si = s2i(w1["end"])
                        scan_ei = s2i(p_start + 0.010)
                        dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                        bnd = dip_i / sr
                    else:
                        p_si = s2i(p_start)
                        p_ei = s2i(p_end)
                        if p_ei > p_si:
                            dip_i = p_si + int(np.argmin(rms[p_si:p_ei]))
                            bnd = dip_i / sr
                            # H3: vowel -> stop, dip inside a narrow pipe. The pipe midpoint -18.6ms is
                            # the better anchor (leave-one-set-out: 026 23.4->15.4ms, 049 35.2->30.4,
                            # old14 12.7->8.4). Approved by ear 2026-09-23: nothing got worse, incl.
                            # verified boundaries moved 19ms and 37ms.
                            # PULSAR_LEGACY_VOWEL_STOP_DIP=1 restores the plain dip.
                            if os.environ.get("PULSAR_LEGACY_VOWEL_STOP_DIP") != "1":
                                bnd = p_mid - 0.01861
                        elif w2["start"] > p_end:
                            bnd = (p_end + w2["start"]) / 2.0
                        else:
                            bnd = p_mid

                # 8. Voiceless dental fricative /th/ onset after vowel ("the -> thing", "i -> think")
                elif starts_with_voiceless_th(w2["text"]) and ends_in_vowel(w1["text"]):
                    if (w2["start"] - p_end) >= 0.015:
                        scan_si = s2i(max(0.0, p_start - 0.030))
                        scan_ei = s2i(min(audio_dur, p_end))
                        if scan_ei > scan_si:
                            dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                            bnd = dip_i / sr
                        else:
                            bnd = (p_end + w2["start"]) / 2.0
                    else:
                        bnd = p_end

                # 9. Liquid consonant onset after vowel ("go -> like", "i -> like")
                elif starts_with_liquid(w2["text"]) and ends_in_vowel(w1["text"]):
                    if c2.startswith("l"):
                        scan_si = s2i(max(0.0, p_start - 0.035))
                        scan_ei = s2i(min(audio_dur, p_end))
                        if scan_ei > scan_si:
                            dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                            bnd = dip_i / sr
                            # G2: vowel -> /l/ has no reliable energy dip, but w2's raw CTC start sits
                            # a consistent ~47ms after the human boundary (landmark search, IQR 20ms).
                            # Approved by ear 2026-09-23: 7/7 new-clip pairs improved or held, plus 3
                            # accepted pairs incl. 2 held-out ones it moves away. Corrected, this leaf:
                            # dev 35.9 -> 15.0ms, held-out 13.4 -> 10.5ms. PULSAR_LEGACY_LIQUID_DIP=1 undoes it.
                            if os.environ.get("PULSAR_LEGACY_LIQUID_DIP") != "1":
                                bnd = w2["start"] - 0.0473
                        else:
                            bnd = p_mid
                    else:
                        bnd = p_end

                # 10. Consonant (stop or nasal) into vowel
                elif (ends_in_stop(w1["text"]) or ends_in_nasal(w1["text"])) and starts_with_vowel(w2["text"]):
                    # Velar stops (/k/, /g/ as in "like", "take", "week", "specific"):
                    # Burst release aligns with pipe midpoint; for wide gaps scan within [p_start, p_start + 0.050]
                    if ends_in_velar_stop(w1["text"]):
                        if (p_end - p_start) <= 0.055:
                            bnd = p_mid
                            # G1: the vowel's voicing onset (-2.3ms), which lands AFTER the unvoiced
                            # /k g/ burst -- an energy-rise detector caught the burst instead and
                            # split "like -> ka". Earlier-only (this leaf's error is one-sided late),
                            # and skipped after "-nk": the voiced /ng/ before the stop leaves no clean
                            # voicing edge ("think -> it's" failed by ear +32ms and on held-out -80ms).
                            # Approved by ear 2026-09-23 (4/5, the 5th was think). Corrected, this
                            # leaf: dev 24.8 -> 9.8ms, held-out 26.9 -> 19.0ms. PULSAR_LEGACY_VELAR_PMID=1 undoes it.
                            if os.environ.get("PULSAR_LEGACY_VELAR_PMID") != "1" and                                     not re.sub(r"[^a-z]", "", w1["text"].lower()).endswith("nk"):
                                _fa = max(0, int(((p_start - 0.080) * sr - frame_len / 2) / hop))
                                _fb = min(len(voicing_frames), int(((p_end + 0.040) * sr - frame_len / 2) / hop))
                                _seg = voicing_frames[_fa:_fb]
                                if len(_seg) > 10:
                                    _k = _fa + int(np.argmax(_seg[5:] - _seg[:-5])) + 2
                                    bnd = min(bnd, (_k * hop + frame_len / 2) / sr - 0.0023)
                        else:
                            scan_si = s2i(p_start)
                            scan_ei = s2i(min(audio_dur, p_start + 0.050))
                            if scan_ei > scan_si:
                                dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                                bnd = dip_i / sr
                            else:
                                bnd = p_start + 0.020
                    elif ends_in_nasal(w1["text"]):
                        if c1.endswith(("me", "ne")):
                            scan_si = s2i(max(0.0, p_end - 0.035))
                            scan_ei = s2i(max(0.0, p_end - 0.005))
                            dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                            bnd = dip_i / sr
                        elif c1.endswith("ng") and not c1.endswith("ing"):
                            # Velar nasal /ŋ/ root into vowel ("thing -> is"): release into vowel at p_end
                            bnd = p_end
                        else:
                            scan_si = s2i(max(0.0, p_start - 0.045))
                            scan_ei = s2i(min(audio_dur, min(p_start + 0.035, max(p_end, w2["start"]))))
                            if scan_ei > scan_si:
                                dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                                bnd = dip_i / sr
                                # The dip sits inside the quieter nasal murmur, early of the
                                # nasal->vowel release (human corrections median -21ms). Halfway to
                                # the pipe start: approved by ear 2026-09-23 on all 4 samples
                                # (2 corrected, 2 accepted incl. the largest shift). Corrected, this
                                # leaf: dev 29.9 -> 18.2ms, held-out 16.0 -> 10.3ms.
                                # PULSAR_LEGACY_NASAL_DIP=1 restores the plain dip.
                                if os.environ.get("PULSAR_LEGACY_NASAL_DIP") != "1":
                                    bnd = (bnd + p_start) / 2.0
                            else:
                                bnd = p_mid
                    elif (p_end - p_start) <= 0.030:
                        # Compact pipe: stop closure entirely within window; p_mid is most reliable
                        bnd = p_mid
                        # H1: p_mid sits a consistent ~35ms late here (leave-one-set-out over 3 gold
                        # sets: 026 40.3->21.1ms, 049 63.5->42.3, old14 20.2->15.7). Approved by ear
                        # 2026-09-23 incl. both verified boundaries it moves ~35ms; the one miss,
                        # "end -> in", is a pair where even the human label sounds non-contiguous.
                        # A nasal+stop guard was rejected: it also drops "and -> if", rated perfect.
                        # PULSAR_LEGACY_COMPACT_STOP_PMID=1 restores the plain midpoint.
                        if os.environ.get("PULSAR_LEGACY_COMPACT_STOP_PMID") != "1":
                            bnd = p_mid - 0.03475
                        # R4 (ear): vowel voicing onset +1.7ms when within 10ms.
                        # Hit rate 026 38->50%, 049 20->40%.
                        if ear_rule("R4"):
                            _v = vowel_voicing_onset(p_start, p_end)
                            bnd = gated(bnd, None if _v is None else _v + 0.0017, 0.010)
                    else:
                        scan_si = s2i(max(0.0, p_start - 0.040))
                        scan_ei = s2i(min(audio_dur, min(p_start + 0.035, max(p_end, w2["start"]))))
                        if scan_ei > scan_si:
                            dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                            bnd = dip_i / sr + (0.015 if ends_in_stop(w1["text"]) else 0.0)
                            # R3 (ear): cut at the vowel's voicing onset (-2.3ms) when within 20ms --
                            # i.e. after the stop's release, which is what "proud di" / "just ta"
                            # were saying. Hit rate 026 51->59%, 049 10->50%, old14 29->47%;
                            # verified 75->88%. The gate keeps "proud -> i" where it was.
                            if ear_rule("R3"):
                                _v = vowel_voicing_onset(p_start, p_end)
                                bnd = gated(bnd, None if _v is None else _v - 0.0023, 0.020)
                        else:
                            bnd = p_mid

                # 11. Quiet valley in search window (< trail_thresh): plosive closure
                elif valley_rms < trail_thresh:
                    bnd = valley_t
                    # This generic argmin(rms) fallback can land *inside* a released/
                    # aspirated stop or fricative onset (HF-dominant even at low RMS,
                    # so RMS alone can't tell it apart from true silence) -- but only
                    # when w2 itself starts with a stop/sibilant, i.e. w2's own onset
                    # plausibly explains the frication (confirmed via "offered -> to").
                    # A fixed HF-ratio threshold was tried and reverted: the HF value
                    # AT gold's boundary varies wildly across cases (0.005 to 0.78) so
                    # no single threshold works. But the HF ramp's rising edge (from
                    # near-baseline ~0.02 to near-saturation ~0.5) is consistent in
                    # DURATION (~6-20ms), and gold consistently sits close to its
                    # TEMPORAL MIDPOINT regardless of the absolute HF values involved
                    # -- confirmed across "offered->to" (+2.1ms), "get->to" (-6.0ms),
                    # "travelling->to" (-8.3ms), all far tighter than any fixed-
                    # threshold attempt managed on this same trio.
                    if (starts_with_stop(w2["text"]) or starts_with_sibilant(w2["text"])) and \
                       (ends_in_stop(w1["text"]) or ends_in_nasal(w1["text"])) and \
                       hf_ratio[s2i(bnd)] >= 0.3:
                        # The extra hf_ratio[bnd] gate above is the key discriminator:
                        # only intervene when the CURRENT estimate is itself sitting
                        # inside high-HF territory (plausibly "stuck in frication", the
                        # actual failure mode being fixed). When the current estimate
                        # already sits in genuine low-HF silence (e.g. "start -> to",
                        # where the natural /t/ VOT closure is long and the current
                        # estimate already lands inside it correctly), leave it alone --
                        # confirmed this case regressed 1.7ms->21.3ms without this gate,
                        # because the onset/plateau search would find the (unrelated,
                        # much later) frication ramp regardless of whether the current
                        # estimate needed correcting at all.
                        bnd_i = s2i(bnd)
                        win_lo = max(s2i(w1["start"] + 0.010), bnd_i - int(0.045 * sr))
                        win_hi = min(s2i(w2["end"] - 0.010), bnd_i + int(0.035 * sr))
                        # Only accept an onset if it is a GENUINE rise from a low
                        # baseline -- i.e. hf_ratio was sustained low (<0.02) for a
                        # real stretch (>=8ms) immediately before crossing up. Without
                        # this, a word ending in its OWN frication (e.g. "used", voiced
                        # /z/, spelled with a final stop letter so it still passes the
                        # ends_in_stop(w1) gate above) already has high HF throughout
                        # the window, and the scan just grabs the window's left edge
                        # instead of a real transition (confirmed via "used -> to",
                        # which regressed -10.7ms -> -55.7ms without this check).
                        low_run_needed = int(0.008 * sr)
                        low_run = 0
                        onset_i = None
                        for k in range(win_lo, win_hi):
                            if hf_ratio[k] < 0.02:
                                low_run += 1
                            else:
                                if low_run >= low_run_needed:
                                    onset_i = k
                                    break
                                low_run = 0
                        plateau_i = None
                        if onset_i is not None:
                            for k in range(onset_i, win_hi):
                                if hf_ratio[k] >= 0.5:
                                    plateau_i = k
                                    break
                        if onset_i is not None and plateau_i is not None:
                            old_bnd = bnd
                            bnd = ((onset_i + plateau_i) // 2) / sr
                            # If the original (pre-correction) estimate sat meaningfully
                            # LATER than the new one, it was likely already a good match
                            # for w2's own start (not w1's end) -- gold sometimes carves a
                            # real gap out of the middle of one continuous frication event,
                            # attributing early frication to w1 and late frication to w2
                            # (confirmed via "offered -> to": old estimate 12.2001 was
                            # within 1ms of gold's to.start=12.2022, while being 18.9ms
                            # wrong for offered.end -- forcing both to share one point
                            # dragged to.start along with the corrected offered.end).
                            if old_bnd > bnd + 0.002:
                                w2_start_override = old_bnd

                    # Voiced dental fricative /dh/ onset (the/that/this/there/they/
                    # them/then/those/these) has its own dedicated, proven detector
                    # (case 13 below: spectral_flatness>=0.30 + voicing>=0.4), but a
                    # filler word like "um" ending in its own low-flatness murmur can
                    # satisfy THIS case's valley_rms<trail_thresh check first, so case
                    # 13 never runs at all (confirmed via "um -> then": stuck at a
                    # pre-transition dip inside "um"'s own murmur, error -82..-83ms).
                    # Re-run case 13's exact logic here, gated on the current estimate's
                    # flatness still being low (confirms we're stuck before the voiced-
                    # frication rise, not already past it) to avoid the broad collateral
                    # damage that came from moving case 13 earlier unconditionally.
                    elif clean_txt(w1["text"]) in ("um", "uh", "ah", "er") \
                            and clean_txt(w2["text"]) in ("the", "that", "this", "there", "they", "them", "then", "those", "these") \
                            and spectral_flatness[s2i(bnd)] < 0.15:
                        # Narrowed to w1 being a filler specifically, matching the
                        # diagnosed mechanism exactly (a filler's own internal murmur
                        # has low flatness and fools case 11's valley/argmin check) --
                        # without this, ordinary words like "oh" ending in a plain vowel
                        # also have low baseline flatness and triggered on cases that
                        # were already correct (e.g. "oh -> this" regressed 2.0ms->52.6ms).
                        scan_si = s2i(max(w1["start"] + 0.010, p_start - 0.020))
                        # Capped tightly (80ms total span) rather than reaching to
                        # w2["end"] like the original case-13 usage safely could --
                        # this branch fires far more often (whenever case 11 matches),
                        # so an uncapped scan can wander deep into w2's own body and
                        # grab an unrelated later high-flatness/voicing point instead
                        # of the genuine nearby onset (confirmed via "conversation ->
                        # those", which regressed -9.6ms -> +165.7ms without this cap).
                        scan_ei = min(s2i(audio_dur), s2i(w2["end"] + 0.030), scan_si + int(0.080 * sr))
                        found_i = None
                        if scan_ei > scan_si:
                            for k in range(scan_si, scan_ei):
                                if spectral_flatness[k] >= 0.30 and voicing[k] >= 0.4:
                                    found_i = k
                                    break
                        if found_i is not None:
                            bnd = found_i / sr

                    # Only when the plain valley was the final decision (not the HF-ramp or
                    # filler->/dh/ corrections above): pull halfway to the pipe start. Approved by
                    # ear 2026-09-23 incl. the largest shift (102ms, "saying -> that").
                    # Corrected, this leaf: dev 33.5 -> 20.9ms, held-out 36.9 -> 28.7ms.
                    # PULSAR_LEGACY_VALLEY=1 restores the plain valley.
                    if bnd == valley_t and os.environ.get("PULSAR_LEGACY_VALLEY") != "1":
                        bnd = (valley_t + p_start) / 2.0

                # 12. Short unstressed vowel/article ("a", "an", "the", "it", "at", "and", "all")
                elif starts_with_vowel(w2["text"]) and (clean_txt(w2["text"]) in ("a", "an", "the", "it", "at", "and", "all") or (w2["end"] - w2["start"]) <= 0.045):
                    # For monosyllabic w1 (e.g. "you", "be"), CTC can stretch forward by up to 65ms;
                    # for severely squished articles ("a", "an" <= 35ms) after short monosyllabic w1, allow lookback up to 140ms to catch the vowel attack
                    is_squished_article = (clean_txt(w2["text"]) in ("a", "an") and (w2["end"] - w2["start"]) <= 0.035 and len(clean_txt(w1["text"])) <= 3)
                    lookback = 0.140 if is_squished_article else (0.065 if len(clean_txt(w1["text"])) <= 3 else 0.035)
                    scan_si = s2i(max(w1["start"] + 0.040, p_start - lookback))
                    scan_ei = s2i(min(audio_dur, p_start + 0.025))
                    if scan_ei > scan_si:
                        if is_squished_article and scan_ei > scan_si + int(0.010 * sr):
                            diffs = np.diff(rms[scan_si:scan_ei])
                            max_rise_idx = scan_si + int(np.argmax(diffs))
                            bnd = max_rise_idx / sr
                        else:
                            dip_i = scan_si + int(np.argmin(rms[scan_si:scan_ei]))
                            dip_t = dip_i / sr
                            if dip_t < p_start - 0.015:
                                bnd = dip_t + 0.015
                            else:
                                bnd = dip_t
                    else:
                        bnd = p_start

                # 13. Voiced dental fricative /dh/ onset (the/that/this/there/they/them/
                # then/those/these -- excluded from starts_with_voiceless_th above since
                # their "th" is voiced /dh/, not voiceless /th/), when w1 doesn't end in a
                # rhotic (that case is already handled). Voiced frication has BOTH
                # periodicity (voicing stays high, unlike a voiceless consonant) AND noise
                # (spectral flatness rises), simultaneously -- unlike a plain vowel-to-vowel
                # transition where flatness stays low. Falls through to the raw CTC pipe
                # midpoint otherwise, which has no acoustic basis for this transition type.
                # NOTE: deliberately checked AFTER the generic quiet-valley case above --
                # moving it earlier (to also catch cases like "um -> then" where a filler's
                # own internal murmur satisfies the valley check first) was tried and
                # reverted: it intercepts far more pairs than intended and regresses badly
                # (84 changed cases, 61 regressions vs 23 fixes) because the valley/argmin
                # fallback is already well-tuned for the bulk of these pairs.
                elif clean_txt(w2["text"]) in ("the", "that", "this", "there", "they", "them", "then", "those", "these"):
                    scan_si = s2i(max(w1["start"] + 0.010, p_start - 0.020))
                    scan_ei = s2i(min(audio_dur, w2["start"] + 0.030))
                    found_i = None
                    if scan_ei > scan_si:
                        for k in range(scan_si, scan_ei):
                            if spectral_flatness[k] >= 0.30 and voicing[k] >= 0.4:
                                found_i = k
                                break
                    bnd = (found_i / sr) if found_i is not None else p_mid

                # 14. Default connected voiced speech: CTC pipe midpoint
                else:
                    bnd = p_mid
                    # p_start/p_end (and thus p_mid) come from w1/w2's own raw
                    # estimates, which can already be displaced well past a genuine
                    # stop closure when w1 ends in a stop and w2 starts with
                    # something not covered by any case above (e.g. a liquid --
                    # confirmed via "looked -> like": true /kt/ closure sits
                    # ~60-80ms before p_start, entirely outside every case's normal
                    # search window, so nothing above matches and this blind
                    # pipe-midpoint fallback was used instead, landing 72ms late).
                    # Search further back for a genuine, sufficiently deep, sustained
                    # low-RMS region before trusting the naive midpoint.
                    if ends_in_stop(w1["text"]):
                        ext_hi = s2i(p_start)
                        ext_lo = max(s2i(w1["start"] + 0.020), ext_hi - int(0.100 * sr))
                        if ext_hi > ext_lo:
                            ext_min_i = ext_lo + int(np.argmin(rms[ext_lo:ext_hi]))
                            if rms[ext_min_i] < trail_thresh:
                                sustain_half = int(0.005 * sr)
                                chk_lo = max(ext_lo, ext_min_i - sustain_half)
                                chk_hi = min(ext_hi, ext_min_i + sustain_half)
                                if chk_hi > chk_lo and np.mean(rms[chk_lo:chk_hi]) < trail_thresh:
                                    bnd = ext_min_i / sr
                    # Only when the plain pipe midpoint was the final decision: move toward the
                    # pipe start, at most 20ms. By ear 2026-09-23 a 20ms move was "perfect" and a
                    # 30ms move bled w1's /r/ into w2 ("for -> w"), hence the cap. Corrected, this
                    # leaf: dev 36.1 -> 25.2ms (2% -> 18% within 5ms), held-out 25.1 -> 14.6ms
                    # (6% -> 31%). PULSAR_LEGACY_CASE14_PMID=1 restores the plain midpoint.
                    # Skipped when either token is a SPELLED LETTER: the dispatch reads spelling,
                    # but "w" is spoken "double-you" (starts /d/) and "h", "f", "l", "m" start with
                    # a vowel, so this leaf's sonorant-transition reasoning doesn't hold. The only
                    # pair that failed by ear in both listening rounds was "for -> w" (-30ms and
                    # -20ms both bled). Truncations ("y-") are not letters; "a"/"i" are words.
                    _is_letter = lambda t: re.fullmatch(r"[b-hj-z]", str(t).strip().lower()) is not None
                    if bnd == p_mid and os.environ.get("PULSAR_LEGACY_CASE14_PMID") != "1"                             and not (_is_letter(w1["text"]) or _is_letter(w2["text"])):
                        bnd = max(p_start, p_mid - 0.020)
                        # R1 (ear): p_mid -23.6ms when within 10ms of F1's cut. Hit rate 026
                        # 46->50%, 049 26->29%, old14 52->59%; verified unchanged (58%).
                        if ear_rule("R1"):
                            bnd = gated(bnd, p_mid - 0.0236, 0.010)


                # Prelabel corroboration: only trusted when NEITHER of the
                # two signals every other case above relies on (a genuine
                # RMS dip below trail_thresh, or an HF-ratio spike
                # indicating frication) is present ANYWHERE in the window
                # bounding this pair -- i.e. only when our own heuristics
                # truly have nothing to go on, not just when they disagree
                # with the prelabel. Two broader triggers were tried and
                # reverted: case-14-only missed most real dead-ends (they
                # get caught by OTHER cases' own best-effort argmin logic
                # first, which isn't literally p_mid but is equally
                # uninformed); a blanket >40ms-disagreement trigger
                # regressed several already-well-tuned specific-case fixes,
                # including breaking 3 validated regression-suite cases.
                if i in prelabel_by_idx and (i + 1) in prelabel_by_idx:
                    win_lo = s2i(min(w1["start"] + 0.010, p_start))
                    win_hi = s2i(max(w2["end"] - 0.010, p_end))
                    if win_hi > win_lo:
                        has_rms_dip = bool(np.any(rms[win_lo:win_hi] < trail_thresh))
                        has_hf_spike = bool(np.any(hf_ratio[win_lo:win_hi] >= 0.3))
                        if not has_rms_dip and not has_hf_spike:
                            pw1_end = prelabel_by_idx[i][1]
                            pw2_start = prelabel_by_idx[i + 1][0]
                            if pw2_start > pw1_end - 0.005:
                                pre_bnd = (pw1_end + pw2_start) / 2.0
                                if w1["start"] + 0.010 < pre_bnd < w2["end"] - 0.010:
                                    bnd = pre_bnd

                bnd = max(w1["start"] + 0.001, min(w2["end"] - 0.001, bnd))
                w1["end"] = round(bnd - 0.001, 4)
                if w2_start_override is not None:
                    w2["start"] = round(max(w2_start_override, bnd + 0.001), 4)
                else:
                    w2["start"] = round(bnd + 0.001, 4)

        # ── Pass 2: 2ms gap enforcement ───────────────────────────────────────
        for i in range(len(refined) - 1):
            if refined[i + 1]["start"] - refined[i]["end"] < 0.002:
                refined[i]["end"] = round(refined[i + 1]["start"] - 0.002, 4)

        for i in range(len(refined)):
            if refined[i]["start"] < 0.0:
                refined[i]["start"] = 0.0
            if refined[i]["end"] <= refined[i]["start"]:
                refined[i]["end"] = round(refined[i]["start"] + 0.010, 4)
            if i > 0 and refined[i]["start"] <= refined[i - 1]["end"]:
                refined[i]["start"] = round(refined[i - 1]["end"] + 0.002, 4)
                if refined[i]["end"] <= refined[i]["start"]:
                    refined[i]["end"] = round(refined[i]["start"] + 0.010, 4)

        return refined


    def align(self, audio_path, text_or_words, sample_rate=16000, hybrid=True, prelabel_segments=None):
        """
        Aligns words to audio using Wav2Vec2 CTC C++ forced alignment + Silero VAD + acoustic refinement.
        Accepts either a string of words or a list of word strings / dicts.

        prelabel_segments: optional list of externally-provided draft
        word-level segments (see snap_boundaries_hybrid's docstring) --
        fully optional, used only as a corroborating signal in our own
        blind fallback cases, never required for normal operation.
        """
        if isinstance(text_or_words, list):
            raw_words = []
            for item in text_or_words:
                if isinstance(item, str):
                    raw_words.append(item.strip())
                elif isinstance(item, dict):
                    raw_words.append(item.get("text", item.get("word", "")).strip())
            raw_words = [w for w in raw_words if w]
        elif isinstance(text_or_words, str):
            raw_words = [w.strip() for w in text_or_words.strip().split() if w.strip()]
        else:
            return []

        raw_words = split_abbreviations(raw_words)

        if not raw_words:
            return []


        # Load audio using soundfile
        data, sr = sf.read(audio_path)
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        audio_dur = len(data) / sr

        # Resample to 16kHz for model
        wav_tensor = torch.from_numpy(data).float().unsqueeze(0)
        if sr != self.bundle.sample_rate:
            wav_16k = torchaudio.functional.resample(wav_tensor, sr, self.bundle.sample_rate)
        else:
            wav_16k = wav_tensor

        # A Silero VAD pass used to run here on every clip and its result (vad_spans) was
        # passed to snap_boundaries_hybrid, which never reads it (AST-verified: 0 loads).
        # Removed 2026-09-23; predictions verified byte-identical on all 1716 gold boundaries.

        # Clean words for Wav2Vec2 CTC alignment (expand common numbers, strip hyphens, keep valid dict chars).
        # (split_abbreviations already ran above; it is idempotent, verified on 3,280 words.)
        NUM_MAP = {
            "0": "ZERO", "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR",
            "5": "FIVE", "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE",
            "10": "TEN", "11": "ELEVEN", "12": "TWELVE", "13": "THIRTEEN", "14": "FOURTEEN",
            "15": "FIFTEEN", "16": "SIXTEEN", "17": "SEVENTEEN", "18": "EIGHTEEN", "19": "NINETEEN",
            "20": "TWENTY", "30": "THIRTY", "40": "FORTY", "50": "FIFTY", "60": "SIXTY",
            "70": "SEVENTY", "80": "EIGHTY", "90": "NINETY", "100": "HUNDRED"
        }
        # A spelled-out letter (Pulsar tokenization rule 5.3: individually pronounced
        # letters each get their own token, e.g. "t" "v" for TV) is PRONOUNCED as its
        # full letter-name syllable ("tee", "vee"), not as the bare single grapheme. If
        # the CTC forced-alignment target is left as the literal 1-character string, the
        # aligner allocates only enough time for a single stop/phoneme burst and misses
        # most of the syllable's actual duration (confirmed: raw CTC gave "t"/"v" ~20ms
        # each against a real ~300ms each). Map to the spoken name, like NUM_MAP does for
        # digits. Deliberately excludes "a" and "i": unlike the other 24 letters, those
        # are overwhelmingly real short words (article "a", pronoun "i") when standing
        # alone, not spelled letters, and have a genuinely different, shorter pronunciation
        # than their letter-names ("ay", "eye") -- mapping them would corrupt the far more
        # common case to fix the rarer one.
        LETTER_NAME_MAP = {
            "b": "BEE", "c": "SEE", "d": "DEE", "e": "EE", "f": "EFF", "g": "GEE",
            "h": "AYCH", "j": "JAY", "k": "KAY", "l": "EL", "m": "EM", "n": "EN",
            "o": "OH", "p": "PEE", "q": "CUE", "r": "AR", "s": "ESS", "t": "TEE",
            "u": "YOU", "v": "VEE", "w": "DOUBLEYOU", "x": "EX", "y": "WHY", "z": "ZEE",
        }
        # "a"/"i" are deliberately excluded from LETTER_NAME_MAP above since they are
        # overwhelmingly real short words (article/pronoun) on their own -- but when one
        # sits immediately next to an unambiguous spelled letter (e.g. "l" "a" "noire",
        # spelling "L.A."), it's part of the same letter sequence and needs the same
        # letter-name treatment, not its article/pronoun pronunciation. One-hop neighbor
        # context is enough to disambiguate this without touching the far more common
        # standalone "a"/"i" case.
        AMBIGUOUS_LETTER_MAP = {"a": "AY", "i": "EYE"}
        raw_words_lower = [w.strip().lower() for w in raw_words]

        def _is_confident_letter(idx):
            return 0 <= idx < len(raw_words_lower) and raw_words_lower[idx] in LETTER_NAME_MAP

        clean_words = []
        for idx, w in enumerate(raw_words):
            w_str = raw_words_lower[idx]
            if w_str in NUM_MAP:
                cw = NUM_MAP[w_str]
            elif w_str in LETTER_NAME_MAP:
                cw = LETTER_NAME_MAP[w_str]
            elif w_str in AMBIGUOUS_LETTER_MAP and (_is_confident_letter(idx - 1) or _is_confident_letter(idx + 1)):
                cw = AMBIGUOUS_LETTER_MAP[w_str]
            else:
                cw = re.sub(r"[^A-Za-z']", "", w.upper().replace("-", ""))
            clean_words.append(cw if cw else "A")
        formatted_text = "|".join(clean_words)
        target_tokens = [self.dictionary[c] for c in formatted_text]

        with torch.inference_mode():
            emission, _ = self.model(wav_16k.to(self.device))
            emission = emission[0].cpu().unsqueeze(0)

        targets = torch.tensor([target_tokens], dtype=torch.int32)
        aligned_tokens, scores = F.forced_align(
            emission,
            targets,
            torch.tensor([emission.size(1)]),
            torch.tensor([len(target_tokens)]),
            blank=0,
        )
        spans = F.merge_tokens(aligned_tokens[0], scores[0])

        ratio = audio_dur / emission.size(1)
        pipe_id = self.dictionary["|"]
        words = []
        pipes = []
        curr_w = []

        for s in spans:
            if s.token == pipe_id:
                if curr_w:
                    words.append({
                        "start": curr_w[0].start * ratio,
                        "end": curr_w[-1].end * ratio,
                        "score": float(np.mean([sp.score for sp in curr_w])),
                    })
                    curr_w = []
                pipes.append({
                    "start": s.start * ratio,
                    "end": s.end * ratio,
                })
            else:
                curr_w.append(s)

        if curr_w:
            words.append({
                "start": curr_w[0].start * ratio,
                "end": curr_w[-1].end * ratio,
                "score": float(np.mean([sp.score for sp in curr_w])),
            })

        # Map back to original raw words
        mapped_words = []
        if len(words) < len(raw_words):
            print(f"[ForcedAligner] WARNING: CTC produced {len(words)} segments for {len(raw_words)} input words. Redistributing trailing {len(raw_words) - len(words)} tokens.")
        
        for idx, rw in enumerate(raw_words):
            if idx < len(words):
                mapped_words.append({
                    "text": rw,
                    "start": round(words[idx]["start"], 4),
                    "end": round(words[idx]["end"], 4),
                    "score": round(words[idx]["score"], 4),
                })
            else:
                # CTC dropped this word — redistribute from the last valid segment's end
                if mapped_words:
                    last_end = mapped_words[-1]["end"]
                    remaining = len(raw_words) - idx
                    # Allocate equal slices of 30ms each after the last word, capped at audio_dur
                    slot = 0.030
                    slot_start = min(last_end + 0.002, audio_dur - remaining * slot)
                    w_start = slot_start + (idx - len(words)) * slot
                    w_end = w_start + slot - 0.002
                    mapped_words.append({
                        "text": rw,
                        "start": round(max(last_end + 0.002, w_start), 4),
                        "end": round(min(audio_dur - 0.002, w_end), 4),
                        "score": 0.01,  # Low confidence — synthetic placement
                    })
                else:
                    # Edge case: no words at all from CTC
                    mapped_words.append({
                        "text": rw,
                        "start": round(idx * 0.030, 4),
                        "end": round(idx * 0.030 + 0.028, 4),
                        "score": 0.01,
                    })

        if hybrid:
            mapped_words = self.snap_boundaries_hybrid(mapped_words, pipes, audio_path, None, preloaded_audio=(data, sr), prelabel_segments=prelabel_segments)

        return mapped_words

# Manual smoke test: `python forced_aligner.py <audio_file> "word list"`.
# (A previous version of this block self-tested against 6 hardcoded target timestamps
# from an unrelated, no-longer-present clip -- removed as overfitting-prone dead code;
# real validation lives in bench/run_align_benchmark.py against bench/gt_per_clip.json.)
if __name__ == "__main__":
    if len(sys.argv) > 2:
        aligner = ForcedAligner()
        audio_file = sys.argv[1]
        text = sys.argv[2]
        res = aligner.align(audio_file, text)
        for r in res:
            print(f"{r['start']:.3f} - {r['end']:.3f}: {r['text']}")
    else:
        print("Usage: python forced_aligner.py <audio_file> \"word list\"")
