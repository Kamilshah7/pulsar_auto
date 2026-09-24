import torch
import torchaudio
import torchaudio.functional as F
import soundfile as sf
import numpy as np
import os, sys, re
from dataclasses import dataclass
from silero_vad import load_silero_vad, get_speech_timestamps
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
        print("[ForcedAligner] Loading Silero VAD model...")
        self.vad_model = load_silero_vad(onnx=False)
        print("[ForcedAligner] Silero VAD and Wav2Vec2 loaded successfully.")
        
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

    def snap_boundaries_hybrid(self, words, pipes_or_audio_path, audio_path=None, vad_spans=None, preloaded_audio=None):
        """
        Gold-calibrated boundary refinement (v9).

        Connected speech (<80ms CTC gap):
          - Find RMS valley in gap.
          - If valley is genuinely quiet (< trail_thresh): use valley as boundary.
          - Else (continuous voiced speech): use CTC pipe midpoint.

        True pause (>=80ms):
          - w1 end: last energy drop in gap.
          - w2 start: backward scan from CTC start (up to 500ms back).
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
        win_rms = max(1, int(sr * 0.002))   # 2ms RMS window
        sq = data.astype(np.float64) ** 2
        cumsum = np.cumsum(np.pad(sq, (0, win_rms), mode="constant"))
        moving_mean = (cumsum[win_rms:] - cumsum[:-win_rms]) / win_rms
        rms = np.sqrt(np.maximum(moving_mean, 0.0))
        # Lightly smoothed RMS for valley/dip detection only (reduces spurious micro-dips from pitch pulses)
        _sm_k = max(1, int(sr * 0.006))
        _sm_kernel = np.ones(_sm_k) / _sm_k
        rms_s = np.convolve(rms, _sm_kernel, mode="same")

        # Vectorized ZCR (5ms window)
        win_zcr = max(1, int(sr * 0.005))
        signs = np.sign(data)
        signs[signs == 0] = 1.0
        zc = (np.abs(np.diff(signs)) > 0).astype(np.float64)
        zc = np.pad(zc, (0, 1), mode="constant")
        cumsum_zc = np.cumsum(np.pad(zc, (0, win_zcr), mode="constant"))
        zcr = (cumsum_zc[win_zcr:] - cumsum_zc[:-win_zcr]) / (2.0 * win_zcr)

        noise_floor    = float(np.percentile(rms, 10))
        peak_energy    = float(np.percentile(rms, 95))
        speech_thresh  = noise_floor + 0.08 * (peak_energy - noise_floor)
        trail_thresh   = noise_floor + 0.04 * (peak_energy - noise_floor)
        whisper_thresh = noise_floor + 0.01 * (peak_energy - noise_floor)


        # ── Helpers ───────────────────────────────────────────────────────────
        def s2i(t: float) -> int:
            return max(0, min(len(rms) - 1, int(t * sr)))

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
            if c.endswith(("se", "ze", "ve", "fe", "sh", "ch", "th")): return True
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
            for k in range(wf_st_i, si, -1):
                if rms[k] < trail_thresh:
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
                        valley_idx = v_si + np.argmin(rms_s[v_si:v_ei])
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
                    dip_i = si + int(np.argmin(rms_s[si:ei]))
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
                    min_gap_rms = float(np.min(rms_s[p_si:p_ei]))
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
                    if ends_in_stop(w1["text"]) and (w2["start"] - w1["end"]) < 0.400:
                        # Forward check across stop closure: if within 130ms of first_drop_i there is a plosive burst spike >= speech_thresh
                        burst_lim = s2i(min(w2["start"] - 0.020, first_drop_i / sr + 0.130))
                        burst_k = None
                        for k in range(first_drop_i, burst_lim):
                            if rms[k] >= speech_thresh:
                                burst_k = k
                        if burst_k is not None:
                            # Plosive burst found! Find where burst drops back below trail_thresh into silence
                            drop_k = None
                            for k in range(burst_k, s2i(w2["start"] - 0.015)):
                                if rms[k] < trail_thresh:
                                    if k + int(0.012 * sr) >= len(rms) or np.mean(rms[k:k+int(0.012*sr)]) < trail_thresh:
                                        drop_k = k
                                        break
                            if drop_k is not None:
                                w1_end_t = drop_k / sr + 0.005
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
                            if zcr[k] >= 0.080 and rms[k] >= 0.0003:
                                last_sib_k = k
                            elif rms[k] < 0.0002:
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
                            dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
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
                        # Scan backwards from w2 core (peak) across continuous murmur
                        w2_core_i = s2i(min(w2["end"], max(w2["start"] + 0.040, (w2["start"] + w2["end"]) / 2.0)))
                        min_back_i = s2i(w1["end"] + 0.002)
                        silence_run = 0
                        sil_lim = int(0.045 * sr)
                        onset_i = w2_core_i
                        for k in range(w2_core_i, min_back_i, -1):
                            if rms[k] < trail_thresh:
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
                        # looking for where RMS drops below trail_thresh into pause silence,
                        # avoiding internal stop closures in clusters (e.g. sp-, st-, sk-)
                        w2_st_i = s2i(min(w2["end"], w2["start"] + 0.030))
                        min_back_i = s2i(w1["end"] + 0.002)
                        silence_run = 0
                        sil_lim = int(0.015 * sr)
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
                    else:
                        # Scan backwards from w2 across speech to find true acoustic onset
                        # without jumping over pre-pause inhales or noise
                        w2_st_i = s2i(min(w2["end"], w2["start"] + 0.035))
                        min_back_i = s2i(w1["end"] + 0.002)
                        silence_run = 0
                        sil_lim = int(0.015 * sr)
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
                        min_pipe_rms = float(np.min(rms_s[p_si:p_ei]))
                        if min_pipe_rms < 0.0025:
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

                valley_i   = si + int(np.argmin(rms_s[si:ei]))
                valley_rms = rms[valley_i]
                valley_t   = valley_i / sr

                c1 = clean_txt(w1["text"])
                c2 = clean_txt(w2["text"])

                # 1. Sibilants (/s/, /sh/, /ch/, /z/, /kh/)
                if starts_with_sibilant(w2["text"]):
                    if ends_in_sibilant(w1["text"]) or ends_in_fricative(w1["text"]):
                        if w2["text"].endswith("-") and (w2["end"] - w1["start"]) >= 0.250:
                            # Full word into stuttered sibilant restart (e.g. "was -> s-"):
                            # w1 must span its natural syllable duration; find the articulator reset dip
                            dip_si = s2i(w1["start"] + 0.150)
                            dip_ei = s2i(min(audio_dur, min(w1["start"] + 0.240, w2["end"] - 0.040)))
                            if dip_ei > dip_si:
                                dip_i = dip_si + int(np.argmin(rms_s[dip_si:dip_ei]))
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
                                dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
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
                            for k in range(z_ei, z_si, -1):
                                if zcr[k] >= 0.055:
                                    drop_z = (k + int(0.005 * sr)) / sr
                                    break
                            bnd = drop_z if drop_z is not None else p_mid
                        elif (w2["start"] - p_end) >= 0.075:
                            bnd = w2["start"]
                        else:
                            bnd = p_start
                    else:
                        scan_si = s2i(p_start)
                        scan_ei = s2i(p_end)
                        if scan_ei > scan_si:
                            dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
                            bnd = dip_i / sr
                        else:
                            bnd = p_mid

                # 5. Dental fricative /th/ onset after rhotic/liquid (e.g. "fear -> that's")
                elif (c2.startswith("that") or c2.startswith("the") or c2.startswith("this")) and c1.endswith("r"):
                    scan_si = s2i(max(0.0, p_end - 0.030))
                    scan_ei = s2i(min(audio_dur, w2["start"] + 0.010))
                    if scan_ei > scan_si:
                        dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
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
                            dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
                            bnd = dip_i / sr
                    elif w1["text"].startswith("((") or w1["text"] == "(())" or not c1:
                        # Whisper / inaudible token into vowel speech ("(()) -> uh"): find vowel attack after valley
                        scan_si = s2i(p_start)
                        scan_ei = s2i(w2["start"])
                        if scan_ei > scan_si:
                            v_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
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
                        dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
                        bnd = dip_i / sr
                    else:
                        p_si = s2i(p_start)
                        p_ei = s2i(p_end)
                        if p_ei > p_si:
                            dip_i = p_si + int(np.argmin(rms_s[p_si:p_ei]))
                            bnd = dip_i / sr
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
                            dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
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
                            dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
                            bnd = dip_i / sr
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
                        else:
                            scan_si = s2i(p_start)
                            scan_ei = s2i(min(audio_dur, p_start + 0.050))
                            if scan_ei > scan_si:
                                dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
                                bnd = dip_i / sr
                            else:
                                bnd = p_start + 0.020
                    elif ends_in_nasal(w1["text"]):
                        if c1.endswith(("me", "ne")):
                            scan_si = s2i(max(0.0, p_end - 0.035))
                            scan_ei = s2i(max(0.0, p_end - 0.005))
                            dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
                            bnd = dip_i / sr
                        elif c1.endswith("ng") and not c1.endswith("ing"):
                            # Velar nasal /ŋ/ root into vowel ("thing -> is"): release into vowel at p_end
                            bnd = p_end
                        else:
                            scan_si = s2i(max(0.0, p_start - 0.045))
                            scan_ei = s2i(min(audio_dur, min(p_start + 0.035, max(p_end, w2["start"]))))
                            if scan_ei > scan_si:
                                dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
                                bnd = dip_i / sr
                            else:
                                bnd = p_mid
                    elif (p_end - p_start) <= 0.030:
                        # Compact pipe: stop closure entirely within window; p_mid is most reliable
                        bnd = p_mid
                    else:
                        scan_si = s2i(max(0.0, p_start - 0.040))
                        scan_ei = s2i(min(audio_dur, min(p_start + 0.035, max(p_end, w2["start"]))))
                        if scan_ei > scan_si:
                            dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
                            bnd = dip_i / sr + (0.015 if ends_in_stop(w1["text"]) else 0.0)
                        else:
                            bnd = p_mid

                # 11. Quiet valley in search window (< trail_thresh): plosive closure
                elif valley_rms < trail_thresh:
                    bnd = valley_t

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
                            dip_i = scan_si + int(np.argmin(rms_s[scan_si:scan_ei]))
                            dip_t = dip_i / sr
                            if dip_t < p_start - 0.015:
                                bnd = dip_t + 0.015
                            else:
                                bnd = dip_t
                    else:
                        bnd = p_start

                # 13. Default connected voiced speech: CTC pipe midpoint
                else:
                    bnd = p_mid

                bnd = max(w1["start"] + 0.001, min(w2["end"] - 0.001, bnd))
                w1["end"]   = round(bnd - 0.001, 4)
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


    def align(self, audio_path, text_or_words, sample_rate=16000, hybrid=True):
        """
        Aligns words to audio using Wav2Vec2 CTC C++ forced alignment + Silero VAD + acoustic refinement.
        Accepts either a string of words or a list of word strings / dicts.
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

        # Silero VAD detection for speech intervals
        vad_intervals = get_speech_timestamps(
            wav_16k[0],
            self.vad_model,
            sampling_rate=16000,
            threshold=0.15,
            min_silence_duration_ms=30,
        )
        vad_spans = [(ts["start"] / 16000.0, ts["end"] / 16000.0) for ts in vad_intervals]

        # Clean words for Wav2Vec2 CTC alignment (expand common numbers, strip hyphens, keep valid dict chars)
        raw_words = split_abbreviations(raw_words)
        NUM_MAP = {
            "0": "ZERO", "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR",
            "5": "FIVE", "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE",
            "10": "TEN", "11": "ELEVEN", "12": "TWELVE", "13": "THIRTEEN", "14": "FOURTEEN",
            "15": "FIFTEEN", "16": "SIXTEEN", "17": "SEVENTEEN", "18": "EIGHTEEN", "19": "NINETEEN",
            "20": "TWENTY", "30": "THIRTY", "40": "FORTY", "50": "FIFTY", "60": "SIXTY",
            "70": "SEVENTY", "80": "EIGHTY", "90": "NINETY", "100": "HUNDRED"
        }
        clean_words = []
        for w in raw_words:
            w_str = w.strip().lower()
            if w_str in NUM_MAP:
                cw = NUM_MAP[w_str]
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
            mapped_words = self.snap_boundaries_hybrid(mapped_words, pipes, audio_path, vad_spans, preloaded_audio=(data, sr))

        return mapped_words

# Test run if main
if __name__ == "__main__":
    import json
    if len(sys.argv) > 2:
        aligner = ForcedAligner()
        audio_file = sys.argv[1]
        text = sys.argv[2]
        res = aligner.align(audio_file, text)
        for r in res:
            print(f"{r['start']:.3f} - {r['end']:.3f}: {r['text']}")
    else:
        aligner = ForcedAligner()
        llm_data = json.load(open(r"output/llm_fusion_output.json", encoding="utf-8"))
        clip0_toks = llm_data["0"]
        wav_path = r"audio\zencastr-en_66589d8247eb9800139a4b85-00000_41.wav"
        if os.path.exists(wav_path):
            results = aligner.align(wav_path, clip0_toks, hybrid=True)
            print(f"\nAligned {len(results)}/{len(clip0_toks)} tokens.")
            gold_targets = [
                ("thing", "I", 3.006, "thing -> I transition ~3.006s"),
                ("for", "for", 9.015, "for start ~9.015s"),
                ("irish", "Irish", 9.325, "Irish start ~9.325s"),
                ("newsreaders", "newsreaders", 9.858, "newsreaders start ~9.858s"),
                ("been", "been", 12.419, "been start ~12.419s"),
                ("day", "day", 13.318, "day start ~13.318s"),
            ]
            print("\n" + "=" * 85)
            print("USER TARGET TEST CASES BENCHMARK")
            print("=" * 85)
            for tag, match_word, tgt_st, desc in gold_targets:
                for idx, w in enumerate(results):
                    w_text = w["text"].lower().strip(".,?!\"'")
                    if w_text == match_word.lower():
                        if match_word.lower() == "been" and not (12.0 <= w["start"] <= 13.0):
                            continue
                        if match_word.lower() == "i" and not (2.9 <= w["start"] <= 3.2):
                            continue
                        if match_word.lower() == "irish" and not (9.1 <= w["start"] <= 9.6):
                            continue
                        delta = (w["start"] - tgt_st) * 1000
                        status = "FLAWLESS" if abs(delta) <= 15 else ("GOOD" if abs(delta) <= 30 else f"Err={abs(delta):.1f}ms")
                        print(f"{w['text']:14s} | {w['start']:8.3f}s     | {w['end']:8.3f}s     | {tgt_st:8.3f}s     | {delta:+7.1f} ms  | {status}")
                        break
            print("=" * 85)
