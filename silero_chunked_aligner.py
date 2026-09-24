"""
Silero VAD + Chunked Phonetic Alignment Engine for Pulsar.
Combines:
  1. Silero Neural VAD (for 100% pause protection and silence detection)
  2. Wav2Vec2 CTC Forced Alignment (strictly bounded within active speech chunks for blended words)
  3. Pulsar non-overlapping constraint enforcement (min duration >= 35ms, min gap >= 2ms)
"""

import os
import sys
import json
import re
import soundfile as sf
import torch
import torchaudio
import numpy as np

# Ensure local imports work
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from forced_aligner import ForcedAligner

def clean_pulsar_word(raw_word):
    """Normalize word per Pulsar rules: lowercase, strip punctuation except apostrophes."""
    w = str(raw_word).strip().lower()
    w = re.sub(r"^[^\w'<>\(\)\-]+", "", w)
    w = re.sub(r"[^\w'<>\(\)\-]+$", "", w)
    w = w.replace(",", "").replace(".", "").replace("?", "").replace("!", "")
    w = w.replace("\"", "").replace(":", "").replace(";", "")
    return w


class SileroChunkedAligner:
    _instance = None

    def __new__(cls, *args, **kwargs):
        # Singleton pattern to prevent re-loading PyTorch models
        if cls._instance is None:
            cls._instance = super(SileroChunkedAligner, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        print("[SileroChunkedAligner] Initializing Silero VAD + Wav2Vec2 Models...")
        from silero_vad import load_silero_vad, get_speech_timestamps
        self.vad_model = load_silero_vad()
        self.get_speech_timestamps = get_speech_timestamps
        self.aligner = ForcedAligner()
        self.device = self.aligner.device
        self._initialized = True
        print("[SileroChunkedAligner] Initialization complete.")

    def align_clip(self, audio_path, words_or_text, clip_duration=None):
        """
        Align words to audio using Silero VAD speech chunking + Wav2Vec2 phonetic alignment.
        words_or_text: list of dicts with 'text', 'start', 'end' (or a raw text string)
        Returns: (aligned_tokens, stats)
        """
        stats = {
            "total_tokens": 0,
            "speech_chunks": 0,
            "silence_preserved_ms": 0.0,
            "blended_words_aligned": 0
        }

        if not words_or_text:
            return [], stats

        # If a string was passed, convert to synthetic words list
        if isinstance(words_or_text, str):
            raw_words = words_or_text.strip().split()
            words_or_text = [{"text": w, "start": 0.0, "end": 0.0, "speaker": "S1"} for w in raw_words]

        # Load audio using soundfile directly (bypasses torchcodec)
        data, sr = sf.read(audio_path)
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        dur_sec = clip_duration or (len(data) / sr)

        wav_16k = torch.from_numpy(data).float()
        if sr != 16000:
            wav_16k = torchaudio.functional.resample(wav_16k, sr, 16000)

        # 1. Run Silero VAD to detect true speech chunks
        speech_chunks = self.get_speech_timestamps(
            wav_16k,
            self.vad_model,
            sampling_rate=16000,
            threshold=0.45,
            min_speech_duration_ms=45,
            min_silence_duration_ms=70,
            return_seconds=True
        )

        if not speech_chunks:
            # Fallback to full duration if no distinct speech detected
            speech_chunks = [{'start': 0.0, 'end': dur_sec}]

        stats["speech_chunks"] = len(speech_chunks)
        tot_speech_sec = sum(c['end'] - c['start'] for c in speech_chunks)
        stats["silence_preserved_ms"] = round(max(0.0, dur_sec - tot_speech_sec) * 1000, 1)

        # 2. Assign words to speech chunks
        has_initial_times = any(w.get("end", 0.0) > w.get("start", 0.0) for w in words_or_text)
        chunk_words = [[] for _ in range(len(speech_chunks))]
        unmapped = []

        if has_initial_times:
            # Map by midpoint
            for w in words_or_text:
                mid = (w["start"] + w["end"]) / 2.0
                best_idx = None
                min_dist = float("inf")
                for idx, c in enumerate(speech_chunks):
                    if c["start"] <= mid <= c["end"]:
                        best_idx = idx
                        min_dist = 0.0
                        break
                    dist = min(abs(mid - c["start"]), abs(mid - c["end"]))
                    if dist < min_dist:
                        min_dist = dist
                        best_idx = idx

                if best_idx is not None and min_dist < 0.40:
                    chunk_words[best_idx].append(w)
                else:
                    unmapped.append(w)
        else:
            # Distribute words evenly across chunks by word count
            n_words = len(words_or_text)
            n_chunks = len(speech_chunks)
            words_per_chunk = max(1, n_words // n_chunks)
            cur = 0
            for i in range(n_chunks):
                take = words_per_chunk if i < n_chunks - 1 else (n_words - cur)
                chunk_words[i] = words_or_text[cur:cur + take]
                cur += take

        # 3. Align each chunk
        results = []
        for c_idx, c in enumerate(speech_chunks):
            words_in_c = chunk_words[c_idx]
            if not words_in_c:
                continue

            c_st = c["start"]
            c_en = c["end"]

            # Single word in chunk: chunk boundaries define the word
            if len(words_in_c) == 1:
                w = words_in_c[0]
                cw = clean_pulsar_word(w.get("text", w.get("word", ""))) or "word"
                if c_en - c_st <= 1.0 or not (w.get("end", 0) > w.get("start", 0)):
                    w_st, w_en = c_st, c_en
                else:
                    orig_st = w["start"]
                    orig_en = w["end"]
                    w_st = max(c_st, round(orig_st - 0.02, 4))
                    w_en = min(c_en, round(orig_en + 0.02, 4))
                    if w_en <= w_st:
                        w_st, w_en = c_st, c_en
                results.append({
                    "text": cw,
                    "start": round(w_st, 4),
                    "end": round(w_en, 4),
                    "speaker": w.get("speaker", "S1")
                })
                continue

            # Multiple words in chunk (blended speech): run Wav2Vec2 inside chunk
            st_sample = int(c_st * 16000)
            en_sample = int(c_en * 16000)
            sub_wav = wav_16k[st_sample:en_sample].unsqueeze(0)

            formatted_words = []
            for w in words_in_c:
                raw_txt = w.get("text", w.get("word", ""))
                cw = clean_pulsar_word(raw_txt).upper()
                valid_ch = "".join([ch for ch in cw if ch in self.aligner.dictionary and ch != "|"])
                if not valid_ch:
                    valid_ch = "A"
                formatted_words.append(valid_ch)

            transcript = "|".join(formatted_words) + "|"
            tokens = [self.aligner.dictionary[ch] for ch in transcript]

            aligned_successfully = False
            if tokens and sub_wav.shape[1] >= 320:
                try:
                    emission = self.aligner.get_emission(sub_wav)
                    trellis = self.aligner.get_trellis(emission, tokens)
                    path = self.aligner.backtrack(trellis, emission, tokens)
                    segments = self.aligner.merge_repeats(path, transcript)
                    word_segs = self.aligner.merge_words(segments)

                    ratio = sub_wav.size(1) / emission.size(0) / 16000

                    if len(word_segs) == len(words_in_c):
                        for idx, w in enumerate(words_in_c):
                            aligned = word_segs[idx]
                            raw_txt = w.get("text", w.get("word", ""))
                            cw = clean_pulsar_word(raw_txt) or "word"
                            results.append({
                                "text": cw,
                                "start": round(c_st + aligned.start * ratio, 4),
                                "end": round(c_st + aligned.end * ratio, 4),
                                "speaker": w.get("speaker", "S1"),
                                "wrapOpen": w.get("wrapOpen", []),
                                "wrapClose": w.get("wrapClose", [])
                            })
                        aligned_successfully = True
                        stats["blended_words_aligned"] += len(words_in_c)
                except Exception:
                    aligned_successfully = False

            if not aligned_successfully:
                tot_dur = c_en - c_st
                has_sub_times = all(w.get("end", 0) > w.get("start", 0) for w in words_in_c)
                if has_sub_times:
                    min_init = min(w["start"] for w in words_in_c)
                    max_init = max(w["end"] for w in words_in_c)
                    init_span = max(0.001, max_init - min_init)
                    for w in words_in_c:
                        rel_st = (w["start"] - min_init) / init_span
                        rel_en = (w["end"] - min_init) / init_span
                        raw_txt = w.get("text", w.get("word", ""))
                        cw = clean_pulsar_word(raw_txt) or "word"
                        results.append({
                            "text": cw,
                            "start": round(c_st + rel_st * tot_dur, 4),
                            "end": round(c_st + rel_en * tot_dur, 4),
                            "speaker": w.get("speaker", "S1"),
                            "wrapOpen": w.get("wrapOpen", []),
                            "wrapClose": w.get("wrapClose", [])
                        })
                else:
                    step = tot_dur / len(words_in_c)
                    for i, w in enumerate(words_in_c):
                        raw_txt = w.get("text", w.get("word", ""))
                        cw = clean_pulsar_word(raw_txt) or "word"
                        results.append({
                            "text": cw,
                            "start": round(c_st + i * step, 4),
                            "end": round(c_st + (i + 1) * step, 4),
                            "speaker": w.get("speaker", "S1"),
                            "wrapOpen": w.get("wrapOpen", []),
                            "wrapClose": w.get("wrapClose", [])
                        })

        # Add any unmapped words back
        for w in unmapped:
            raw_txt = w.get("text", w.get("word", ""))
            cw = clean_pulsar_word(raw_txt) or "word"
            results.append({
                "text": cw,
                "start": round(w["start"], 4),
                "end": round(w["end"], 4),
                "speaker": w.get("speaker", "S1"),
                "wrapOpen": w.get("wrapOpen", []),
                "wrapClose": w.get("wrapClose", [])
            })

        # Sort results chronologically
        results = sorted(results, key=lambda x: (x["start"], x["end"]))

        # 4. Snap boundaries to acoustic RMS energy dips (<3ms) and onsets/offsets
        results = self.aligner.snap_boundaries_hybrid(results, audio_path)

        # 5. Enforce Pulsar Non-Overlapping, Minimum Duration, and Bounds Constraints
        results = self._resolve_boundaries(results, dur_sec, min_dur=0.035, min_gap=0.002)

        stats["total_tokens"] = len(results)
        return results, stats

    def _resolve_boundaries(self, tokens, clip_duration, min_dur=0.050, min_gap=0.002):
        """
        Enforces Pulsar constraints on token boundaries:
        - min duration >= min_dur (default 50ms)
        - min gap >= min_gap (default 2ms)
        - zero overlaps between adjacent tokens
        - strictly bounded within [0.0, clip_duration]
        """
        if not tokens:
            return []

        dur_sec = clip_duration
        valid = []
        for t in tokens:
            st = float(t["start"])
            en = float(t["end"])
            if dur_sec and st >= dur_sec - min_dur:
                continue
            if en <= st:
                en = st + min_dur
            valid.append({**t, "start": st, "end": en})

        if not valid:
            return []

        valid = sorted(valid, key=lambda x: (x["start"], x["end"]))

        # Pass 1: Forward resolution of overlaps and minimum durations
        for i in range(len(valid) - 1):
            cur = valid[i]
            nxt = valid[i + 1]

            if cur["end"] - cur["start"] < min_dur:
                cur["end"] = round(cur["start"] + min_dur, 4)

            if cur["end"] + min_gap > nxt["start"]:
                room = nxt["end"] - (cur["end"] + min_gap)
                if room >= min_dur:
                    nxt["start"] = round(cur["end"] + min_gap, 4)
                else:
                    overlap = (cur["end"] + min_gap) - nxt["start"]
                    cur_len = max(min_dur, cur["end"] - cur["start"])
                    nxt_len = max(min_dur, nxt["end"] - nxt["start"])
                    tot_len = cur_len + nxt_len

                    shift_left = overlap * (cur_len / tot_len)
                    cut = cur["end"] - shift_left

                    cur["end"] = round(cut - (min_gap / 2.0), 4)
                    if cur["end"] - cur["start"] < min_dur:
                        cur["start"] = max(0.0, round(cur["end"] - min_dur, 4))

                    nxt["start"] = round(cur["end"] + min_gap, 4)
                    if nxt["end"] - nxt["start"] < min_dur:
                        nxt["end"] = round(nxt["start"] + min_dur, 4)

        if valid[-1]["end"] - valid[-1]["start"] < min_dur:
            valid[-1]["end"] = round(valid[-1]["start"] + min_dur, 4)

        # Pass 2: Clip to audio duration with backward ripple
        if dur_sec:
            max_limit = round(dur_sec - 0.001, 4)
            if valid[-1]["end"] > max_limit:
                valid[-1]["end"] = max_limit
                valid[-1]["start"] = max(0.0, round(max_limit - min_dur, 4))

            for i in range(len(valid) - 2, -1, -1):
                cur = valid[i]
                nxt = valid[i + 1]
                if cur["end"] + min_gap > nxt["start"]:
                    cur["end"] = max(0.0, round(nxt["start"] - min_gap, 4))
                    if cur["end"] - cur["start"] < min_dur:
                        cur["start"] = max(0.0, round(cur["end"] - min_dur, 4))

        # Pass 3: Final sweep guaranteeing zero overlaps and min duration
        final_results = []
        last_end = 0.0
        for t in valid:
            st = max(last_end + min_gap, t["start"])
            en = max(st + min_dur, t["end"])
            if dur_sec and st >= dur_sec - 0.005:
                continue
            if dur_sec and en > dur_sec:
                en = dur_sec - 0.001
                if en - st < min_dur:
                    st = max(last_end + min_gap, en - min_dur)
            res_dict = {
                "text": t["text"],
                "start": round(st, 4),
                "end": round(en, 4),
                "speaker": t.get("speaker", "S1")
            }
            if "wrapOpen" in t:
                res_dict["wrapOpen"] = t["wrapOpen"]
            if "wrapClose" in t:
                res_dict["wrapClose"] = t["wrapClose"]
            final_results.append(res_dict)
            last_end = round(en, 4)

        return final_results

    def align_transcript(self, audio_path, words_or_tokens, clip_duration=None, hybrid=False):
        """
        Align a sequence of transcript words (e.g. from LLM output) as the ground truth transcript
        against audio using Wav2Vec2 CTC Forced Alignment, while preserving pauses and non-lexical tokens.

        LLM timestamps are treated as untrusted/discarded, and the word labels are treated as ground truth.
        """
        stats = {
            "total_tokens": 0,
            "speech_chunks": 0,
            "silence_preserved_ms": 0.0,
            "blended_words_aligned": 0
        }

        if not words_or_tokens:
            return [], stats

        # Standardize input into a list of token dicts
        raw_items = []
        if isinstance(words_or_tokens, str):
            for w in words_or_tokens.strip().split():
                raw_items.append({"text": w, "speaker": "S1"})
        elif isinstance(words_or_tokens, list):
            for item in words_or_tokens:
                if isinstance(item, str):
                    raw_items.append({"text": item, "speaker": "S1"})
                elif isinstance(item, dict):
                    raw_items.append(item)

        if not raw_items:
            return [], stats

        dur_sec = clip_duration
        if not dur_sec:
            info = sf.info(audio_path)
            dur_sec = info.duration

        # 1. Classify pronounceable vs non-lexical tokens
        valid_items = []
        for idx, t in enumerate(raw_items):
            raw_text = t.get("text", t.get("word", ""))
            cw = clean_pulsar_word(raw_text)
            letters = "".join([c for c in cw.upper() if c in self.aligner.dictionary and c != "|"])
            valid_items.append({
                "orig_idx": idx,
                "orig_token": t,
                "clean_text": cw or "word",
                "letters": letters,
                "speaker": t.get("speaker", "S1")
            })

        pronounceable = [item for item in valid_items if item["letters"]]
        transcript_text = " ".join([item["clean_text"] for item in pronounceable])

        # 2. Run Wav2Vec2 CTC alignment across waveform
        aligned_words = self.aligner.align(audio_path, transcript_text, hybrid=hybrid)

        # 3. Map aligned words back to pronounceable items
        if len(aligned_words) == len(pronounceable):
            for item, w in zip(pronounceable, aligned_words):
                item["start"] = w["start"]
                item["end"] = w["end"]
        else:
            ratio = len(aligned_words) / max(1, len(pronounceable))
            for i, item in enumerate(pronounceable):
                w_idx = min(len(aligned_words) - 1, int(i * ratio))
                item["start"] = aligned_words[w_idx]["start"]
                item["end"] = aligned_words[w_idx]["end"]

        # 4. Position non-pronounceable items (like '(())', '<ol>', etc.) in gaps
        for i, item in enumerate(valid_items):
            if not item["letters"]:
                prev_time = 0.0
                for p in range(i - 1, -1, -1):
                    if "end" in valid_items[p]:
                        prev_time = valid_items[p]["end"]
                        break
                next_time = dur_sec or (prev_time + 0.5)
                for n in range(i + 1, len(valid_items)):
                    if "start" in valid_items[n]:
                        next_time = valid_items[n]["start"]
                        break
                gap = max(0.0, next_time - prev_time)
                dur = min(0.3, max(0.04, gap * 0.8))
                st = prev_time + 0.005
                en = st + dur
                item["start"] = round(st, 4)
                item["end"] = round(en, 4)

        raw_results = []
        for item in valid_items:
            orig = item["orig_token"]
            res_dict = {
                "text": item["clean_text"],
                "start": item["start"],
                "end": item["end"],
                "speaker": item["speaker"]
            }
            if "wrapOpen" in orig:
                res_dict["wrapOpen"] = orig["wrapOpen"]
            if "wrapClose" in orig:
                res_dict["wrapClose"] = orig["wrapClose"]
            raw_results.append(res_dict)

        # 5. Enforce Pulsar non-overlapping & min duration constraints
        final_tokens = self._resolve_boundaries(raw_results, dur_sec)

        # 6. Calculate statistics
        total_speech_sec = sum(t["end"] - t["start"] for t in final_tokens)
        silence_preserved_ms = max(0.0, (dur_sec - total_speech_sec)) * 1000.0

        speech_chunks = 1
        blended_count = 0
        cluster_len = 1
        for i in range(len(final_tokens) - 1):
            gap = final_tokens[i+1]["start"] - final_tokens[i]["end"]
            if gap >= 0.150:
                speech_chunks += 1
            if gap < 0.050:
                cluster_len += 1
            else:
                if cluster_len > 1:
                    blended_count += cluster_len
                cluster_len = 1
        if cluster_len > 1:
            blended_count += cluster_len

        stats["total_tokens"] = len(final_tokens)
        stats["speech_chunks"] = speech_chunks
        stats["silence_preserved_ms"] = round(silence_preserved_ms, 1)
        stats["blended_words_aligned"] = blended_count

        return final_tokens, stats

    def reconcile_with_prelabels(self, audio_path, prelabels_or_path, llm_tokens, clip_duration=None, whisper_words=None):
        """
        Reconcile pre-label acoustic segment boundaries with LLM ground-truth transcript tokens.
        - Pre-labels provide the acoustic boundaries (covering whole words and demarcating blended speech).
        - LLM output provides the corrected transcript words (fixing misrecognitions, inserting missing words).
        - Whisper word timestamps act as acoustic anchors to detect and correct pre-label drift/hallucinations (e.g. word placed on vocal hesitation).
        - Prevents runaway end-of-clip insertions on silence.
        - Expands multi-word replacements into available gaps.
        - Pulsar non-overlapping and duration constraints (>= 50ms) are enforced.
        """
        dur_sec = clip_duration
        if not dur_sec and os.path.exists(audio_path):
            info = sf.info(audio_path)
            dur_sec = info.duration

        pre_segs = []
        if isinstance(prelabels_or_path, str):
            if os.path.exists(prelabels_or_path):
                try:
                    jd = json.load(open(prelabels_or_path, encoding="utf-8"))
                    for s in jd.get("segments", []):
                        tstr_s = s.get("startTime", "0:0:0")
                        tstr_e = s.get("endTime", "0:0:0")
                        def parse_time(ts):
                            parts = str(ts).split(":")
                            if len(parts) == 3:
                                return float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
                            return float(ts)
                        pre_segs.append({
                            "refTranscript": s.get("refTranscript", s.get("text", "")),
                            "start": parse_time(tstr_s),
                            "end": parse_time(tstr_e),
                            "speaker": s.get("speaker", "S1")
                        })
                except Exception:
                    pre_segs = []
        elif isinstance(prelabels_or_path, list):
            pre_segs = prelabels_or_path

        # If no prelabels exist, fall back to pure phonetic alignment
        if not pre_segs:
            return self.align_transcript(audio_path, llm_tokens, dur_sec)

        # Auto-discover whisper words if not explicitly passed
        if whisper_words is None:
            try:
                base_dir = os.path.dirname(os.path.abspath(audio_path))
                gt_path = os.path.join(base_dir, "..", "output", "groq_transcriptions.json")
                if not os.path.exists(gt_path):
                    gt_path = os.path.join(base_dir, "output", "groq_transcriptions.json")
                if os.path.exists(gt_path):
                    gt_data = json.load(open(gt_path, encoding="utf-8"))
                    base_name = os.path.basename(audio_path)
                    for item in gt_data:
                        if item.get("filename") == base_name:
                            whisper_words = item.get("words", [])
                            break
            except Exception:
                whisper_words = None

        llm_tokens = [t if isinstance(t, dict) else {"text": str(t), "speaker": "S1", "wrapOpen": [], "wrapClose": []} for t in llm_tokens]
        import difflib
        p_clean = [clean_pulsar_word(s.get("refTranscript", s.get("text", ""))) for s in pre_segs]
        l_clean = [clean_pulsar_word(t.get("text", t.get("word", ""))) for t in llm_tokens]
        w_clean = [{
            "text": clean_pulsar_word(w.get("word", w.get("text", ""))),
            "start": float(w.get("start", 0)),
            "end": float(w.get("end", 0))
        } for w in (whisper_words or [])]

        matcher = difflib.SequenceMatcher(None, p_clean, l_clean)
        reconciled = []

        audio_data = None
        sr = 16000
        if os.path.exists(audio_path):
            try:
                audio_data, sr = sf.read(audio_path)
                if audio_data.ndim > 1:
                    audio_data = audio_data.mean(axis=1)
            except Exception:
                audio_data = None

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for pi, lj in zip(range(i1, i2), range(j1, j2)):
                    st = pre_segs[pi]["start"]
                    en = pre_segs[pi]["end"]

                    # Check against Whisper acoustic anchor
                    if w_clean:
                        w_match = None
                        for w in w_clean:
                            if w["text"] == l_clean[lj] and abs(w["start"] - st) < 0.60:
                                w_match = w
                                break
                        if w_match and audio_data is not None:
                            p_chunk = audio_data[int(st*sr):int(en*sr)]
                            p_rms = np.sqrt(np.mean(p_chunk**2)) if len(p_chunk) > 0 else 0.0
                            w_chunk = audio_data[int(w_match["start"]*sr):int(w_match["end"]*sr)]
                            w_rms = np.sqrt(np.mean(w_chunk**2)) if len(w_chunk) > 0 else 0.0

                            # Only snap if prelabel started significantly early on silence/hesitation before true speech
                            if (w_match["start"] - st) > 0.12 and p_rms < 0.010 and w_rms > (p_rms * 1.5):
                                st = w_match["start"]
                                en = max(st + 0.050, w_match["end"])

                    reconciled.append({
                        "text": l_clean[lj],
                        "start": st,
                        "end": en,
                        "speaker": llm_tokens[lj].get("speaker", pre_segs[pi].get("speaker", "S1")),
                        "wrapOpen": llm_tokens[lj].get("wrapOpen", []),
                        "wrapClose": llm_tokens[lj].get("wrapClose", [])
                    })
            elif tag == 'replace':
                if i2 - i1 == 1 and j2 - j1 == 1:
                    # 1-to-1 word replacement (e.g. -vail -> veil)
                    reconciled.append({
                        "text": l_clean[j1],
                        "start": pre_segs[i1]["start"],
                        "end": pre_segs[i1]["end"],
                        "speaker": llm_tokens[j1].get("speaker", pre_segs[i1].get("speaker", "S1")),
                        "wrapOpen": llm_tokens[j1].get("wrapOpen", []),
                        "wrapClose": llm_tokens[j1].get("wrapClose", [])
                    })
                else:
                    span_start = pre_segs[i1]["start"]
                    span_end = pre_segs[i2 - 1]["end"]
                    next_seg_start = pre_segs[i2]["start"] if i2 < len(pre_segs) else (dur_sec or 999.0)
                    avail_end = min((dur_sec or 999.0), next_seg_start - 0.02)
                    n_target = j2 - j1

                    # Expand into available gap if current span would crush words into <80ms slivers
                    if (span_end - span_start) / max(1, n_target) < 0.080 and avail_end > span_end:
                        span_end = min(avail_end, span_start + n_target * 0.180)

                    sub_aligned = False
                    target_words = [l_clean[lj] for lj in range(j1, j2)]

                    if audio_data is not None and len(target_words) > 0:
                        try:
                            st_pad = max(0.0, span_start - 0.04)
                            en_pad = min(dur_sec or 999.0, span_end + 0.04)
                            st_samp = int(st_pad * sr)
                            en_samp = int(en_pad * sr)
                            chunk = audio_data[st_samp:en_samp]

                            chunk_t = torch.from_numpy(chunk).float().unsqueeze(0)
                            if sr != 16000:
                                chunk_t = torchaudio.functional.resample(chunk_t, sr, 16000)

                            formatted = []
                            for tw in target_words:
                                valid_c = "".join([c for c in tw.upper() if c in self.aligner.dictionary and c != "|"])
                                formatted.append(valid_c if valid_c else "A")

                            transcript = "|".join(formatted) + "|"
                            tokens = [self.aligner.dictionary[c] for c in transcript]

                            if tokens and chunk_t.shape[1] >= 320:
                                emission = self.aligner.get_emission(chunk_t)
                                trellis = self.aligner.get_trellis(emission, tokens)
                                path = self.aligner.backtrack(trellis, emission, tokens)
                                segs = self.aligner.merge_repeats(path, transcript)
                                w_segs = self.aligner.merge_words(segs)

                                if len(w_segs) == len(target_words):
                                    ratio = chunk_t.size(1) / emission.size(0) / 16000
                                    for idx, lj in enumerate(range(j1, j2)):
                                        w_obj = w_segs[idx]
                                        w_st = round(st_pad + w_obj.start * ratio, 4)
                                        w_en = round(st_pad + w_obj.end * ratio, 4)
                                        reconciled.append({
                                            "text": l_clean[lj],
                                            "start": max(span_start, w_st),
                                            "end": min(span_end, w_en),
                                            "speaker": llm_tokens[lj].get("speaker", "S1"),
                                            "wrapOpen": llm_tokens[lj].get("wrapOpen", []),
                                            "wrapClose": llm_tokens[lj].get("wrapClose", [])
                                        })
                                    sub_aligned = True
                        except Exception:
                            sub_aligned = False

                    if not sub_aligned:
                        tot_dur = span_end - span_start
                        step = max(0.055, tot_dur / max(1, n_target))
                        for idx, lj in enumerate(range(j1, j2)):
                            reconciled.append({
                                "text": l_clean[lj],
                                "start": round(span_start + idx * step, 4),
                                "end": round(min((dur_sec or 999.0) - 0.001, span_start + (idx + 1) * step), 4),
                                "speaker": llm_tokens[lj].get("speaker", "S1"),
                                "wrapOpen": llm_tokens[lj].get("wrapOpen", []),
                                "wrapClose": llm_tokens[lj].get("wrapClose", [])
                            })
            elif tag == 'delete':
                # Target transcript explicitly deleted these words from prelabels: respect deletion
                pass
            elif tag == 'insert':
                prev_end = reconciled[-1]["end"] if reconciled else 0.0
                if i1 >= len(pre_segs):
                    # End of clip: check if audio is silence
                    chunk = audio_data[int(prev_end*sr):] if audio_data is not None else []
                    c_rms = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0.0
                    if c_rms < 0.002:
                        continue # Skip phantom hallucinated tokens over trailing silence!
                    step = 0.150
                else:
                    next_start = pre_segs[i1]["start"]
                    avail = max(0.050 * (j2 - j1), next_start - prev_end - 0.002)
                    step = min(0.250, avail / (j2 - j1))

                for idx, lj in enumerate(range(j1, j2)):
                    st = round(prev_end + 0.002 + idx * step, 4)
                    en = round(st + step - 0.002, 4)
                    if en > (dur_sec or 999.0):
                        break
                    reconciled.append({
                        "text": l_clean[lj],
                        "start": st,
                        "end": en,
                        "speaker": llm_tokens[lj].get("speaker", "S1"),
                        "wrapOpen": llm_tokens[lj].get("wrapOpen", []),
                        "wrapClose": llm_tokens[lj].get("wrapClose", [])
                    })

        # Ensure segments are sorted by start time before boundary resolution.
        reconciled.sort(key=lambda x: x["start"])

        final_tokens = self._resolve_boundaries(reconciled, dur_sec, min_dur=0.050, min_gap=0.002)

        # Statistics
        total_speech_sec = sum(t["end"] - t["start"] for t in final_tokens)
        silence_preserved_ms = max(0.0, (dur_sec - total_speech_sec)) * 1000.0

        speech_chunks = 1
        blended_count = 0
        cluster_len = 1
        for i in range(len(final_tokens) - 1):
            gap = final_tokens[i+1]["start"] - final_tokens[i]["end"]
            if gap >= 0.150:
                speech_chunks += 1
            if gap < 0.050:
                cluster_len += 1
            else:
                if cluster_len > 1:
                    blended_count += cluster_len
                cluster_len = 1
        if cluster_len > 1:
            blended_count += cluster_len

        stats = {
            "total_tokens": len(final_tokens),
            "speech_chunks": speech_chunks,
            "silence_preserved_ms": round(silence_preserved_ms, 1),
            "blended_words_aligned": blended_count
        }

        return final_tokens, stats
