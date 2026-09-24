"""
Microslice repair using CrisperWhisper 2.0 (via the persistent Modal deployment) instead
of plain Whisper. Reuses the same bloat-detection/clustering logic as microslice_v2.py
(which correctly finds the suspicious spans) but swaps the unreliable re-decode step:
plain Whisper hallucinates on short/repetitive isolated slices (confirmed empirically --
it turned "who came first who came second who came last" into garbage). CrisperWhisper
has built-in hallucination-loop detection and collapse recovery specifically for this
kind of short/tricky audio, and is verbatim-native (won't smooth away the very
disfluencies we're trying to recover), so it should be a fundamentally more reliable
tool for this specific job.

Run against the ALREADY-RECONCILED v2 transcript (Whisper+CTC, 8.28% WER) rather than
raw Whisper words, since that's our current best base and what we want to patch the
remaining ~3.4% missing-token gap on. Falls back to Whisper's own word timings (needed
for the bloat/cluster detection) since the reconciled transcript has no timestamps.
"""
import io
import json
import os
import sys

import numpy as np
import soundfile as sf
import modal

sys.path.insert(0, ".")

ABS_FLOOR_S = 0.45
FUNC_FLOOR_S = 0.55
ADAPTIVE_MULT = 2.2
NEIGHBOR_MULT = 1.3
CONTEXT_PAD_S = 0.35   # CrisperWhisper's own hallucination mitigation tolerates more context
MAX_PAD_FRACTION_OF_GAP = 0.4
FUNCS = {"a", "an", "the", "and", "or", "to", "of", "in", "it", "so", "than", "one", "not"}


def is_bloated(word_text, dur, median_dur, mult=ADAPTIVE_MULT):
    cl = word_text.lower().strip(".,?!\"'")
    thresh = max(ABS_FLOOR_S, mult * median_dur)
    if cl in FUNCS:
        thresh = min(thresh, FUNC_FLOOR_S)
    return dur >= thresh


def cluster_flags(words, flags, median_dur):
    n = len(words)
    include = list(flags)
    for i in range(n):
        if flags[i]:
            if i > 0 and not include[i - 1]:
                d = words[i - 1]["end"] - words[i - 1]["start"]
                if is_bloated(words[i - 1]["word"], d, median_dur, NEIGHBOR_MULT):
                    include[i - 1] = True
            if i + 1 < n and not include[i + 1]:
                d = words[i + 1]["end"] - words[i + 1]["start"]
                if is_bloated(words[i + 1]["word"], d, median_dur, NEIGHBOR_MULT):
                    include[i + 1] = True
    clusters = []
    i = 0
    while i < n:
        if not include[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and include[j + 1]:
            j += 1
        clusters.append((i, j))
        i = j + 1
    return clusters


def slice_bounds(words, audio_dur, ci, cj):
    pad_left = CONTEXT_PAD_S
    if ci > 0:
        gap = max(0.0, words[ci]["start"] - words[ci - 1]["end"])
        pad_left = min(CONTEXT_PAD_S, gap * MAX_PAD_FRACTION_OF_GAP if gap > 0 else CONTEXT_PAD_S * 0.2)
    pad_right = CONTEXT_PAD_S
    if cj + 1 < len(words):
        gap = max(0.0, words[cj + 1]["start"] - words[cj]["end"])
        pad_right = min(CONTEXT_PAD_S, gap * MAX_PAD_FRACTION_OF_GAP if gap > 0 else CONTEXT_PAD_S * 0.2)
    pad_st = max(0.0, words[ci]["start"] - pad_left)
    pad_en = min(audio_dur, words[cj]["end"] + pad_right)
    return pad_st, pad_en


def main():
    groq_results = json.load(open("output/groq_transcriptions.json", encoding="utf-8"))
    Service = modal.Cls.from_name("pulsar-crisperwhisper", "CrisperWhisperService")
    svc = Service()

    results = []
    for c_res in groq_results:
        c_idx = c_res["clip_index"]
        fname = c_res["filename"]
        wav_path = os.path.join("audio", fname)
        words = list(c_res.get("words", []))
        if not words or not os.path.exists(wav_path):
            results.append({"clip_index": c_idx, "words": words})
            continue

        data, sr = sf.read(wav_path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        audio_dur = len(data) / sr

        durs = [w["end"] - w["start"] for w in words]
        median_dur = float(np.median(durs))
        flags = [is_bloated(w["word"], d, median_dur) for w, d in zip(words, durs)]
        clusters = cluster_flags(words, flags, median_dur)

        print(f"clip {c_idx:>2}: {sum(flags)} flagged words -> {len(clusters)} cluster(s) "
              f"(median_word_dur={median_dur*1000:.0f}ms)")

        def _norm(t):
            return t.lower().strip(".,?!\"'-").strip()

        repaired_words = []
        covered_until = 0
        for (ci, cj) in clusters:
            repaired_words.extend(words[covered_until:ci])
            pad_st, pad_en = slice_bounds(words, audio_dur, ci, cj)
            slice_samples = data[int(pad_st * sr):int(pad_en * sr)]
            buf = io.BytesIO()
            sf.write(buf, slice_samples, sr, format="WAV")
            wav_bytes = buf.getvalue()

            try:
                res = svc.transcribe_verbatim.remote(wav_bytes)
                sub_words = res["words"]
                sub = [{"word": w["word"], "start": round(pad_st + float(w["start"]), 3),
                        "end": round(pad_st + float(w["end"]), 3)} for w in sub_words]
            except Exception as e:
                print(f"  [warn] reslice failed: {e}")
                sub = None

            if sub and len(sub) >= 1:
                if ci > 0 and _norm(sub[0]["word"]) == _norm(words[ci - 1]["word"]):
                    sub = sub[1:]
                if sub and cj + 1 < len(words) and _norm(sub[-1]["word"]) == _norm(words[cj + 1]["word"]):
                    sub = sub[:-1]
                repaired_words.extend(sub)
                orig_n = cj - ci + 1
                print(f"  cluster [{ci},{cj}] '{' '.join(w['word'] for w in words[ci:cj+1])}' "
                      f"({orig_n} words, {(words[cj]['end']-words[ci]['start'])*1000:.0f}ms) "
                      f"-> {len(sub)} words: {' '.join(w['word'] for w in sub)}")
            else:
                repaired_words.extend(words[ci:cj + 1])
            covered_until = cj + 1
        repaired_words.extend(words[covered_until:])

        results.append({"clip_index": c_idx, "words": repaired_words})

    with open("output/microslice_crisperwhisper.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nWrote output/microslice_crisperwhisper.json")


if __name__ == "__main__":
    main()
