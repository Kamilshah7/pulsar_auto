"""
Microslice repair v3: corroborated-evidence trigger instead of duration-alone.

v1/v2 flagged a Whisper word as "bloated" purely from its OWN duration being suspicious.
That's a single noisy signal -- plenty of words are just legitimately long (emphasis, a
drawn-out "um"), so the trigger over-fired and re-decoding those non-problem spans (even
with a better model, CrisperWhisper) sometimes corrupted content that was already fine,
net making WER worse both times (v2: 17.1%->34.5% before padding fixes, still no better
than baseline; CrisperWhisper microslice: 25.9%, worse than doing nothing).

v3 instead requires CORROBORATION from our other two independently-computed, independently-
timestamped sources before touching a span at all: our own wav2vec2 CTC acoustic stream
and CrisperWhisper's own full-clip verbatim transcript. Both already have their own
word-level timestamps computed straight from the audio (no re-slicing needed to get them).
A Whisper word is only flagged if ANOTHER source's words overlapping that same time span
outnumber Whisper's word there -- i.e. two independent, differently-biased systems agree
Whisper compressed multiple spoken words into one timestamp. That is a corroborated signal,
not a proxy (duration), and should fire far more rarely and far more correctly.
"""
import io
import json
import os

import numpy as np
import soundfile as sf
import modal

MIN_CORROBORATING_COUNT = 2   # another source must show >=2 word-MIDPOINTS inside 1 Whisper word's span
CONTEXT_PAD_S = 0.35
MAX_PAD_FRACTION_OF_GAP = 0.4


def count_overlapping(span_start, span_end, other_words):
    """Count words from another source whose MIDPOINT falls strictly inside [span_start,
    span_end]. Midpoint-containment (not any-overlap) matters: independently-decoded
    sources place boundaries slightly differently even for the same single word, so an
    any-overlap test with tolerance triggers on ordinary boundary jitter between adjacent
    words -- it doesn't distinguish "this word's edges touch its neighbours" (normal, for
    every word in every source) from "another source genuinely sees multiple distinct
    words packed into this one span" (the actual compression signal we want)."""
    count = 0
    for w in other_words:
        mid = (w["start"] + w["end"]) / 2.0
        if span_start < mid < span_end:
            count += 1
    return count


def flag_words(whisper_words, ctc_words, crisper_words):
    flags = []
    for w in whisper_words:
        ctc_n = count_overlapping(w["start"], w["end"], ctc_words)
        crisper_n = count_overlapping(w["start"], w["end"], crisper_words)
        flags.append(max(ctc_n, crisper_n) >= MIN_CORROBORATING_COUNT)
    return flags


def cluster_flags(flags):
    """Merge only CONSECUTIVE flagged indices into clusters -- no separate lower-threshold
    neighbor-inclusion rule this time, since the trigger itself is already corroborated,
    not a noisy proxy that needs a widening heuristic to catch spillover."""
    n = len(flags)
    clusters = []
    i = 0
    while i < n:
        if not flags[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and flags[j + 1]:
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
    groq_results = {g["clip_index"]: g for g in json.load(open("output/groq_transcriptions.json", encoding="utf-8"))}
    ctc_results = {d["clip_index"]: d for d in json.load(open("output/wav2vec2_acoustic_transcriptions.json", encoding="utf-8"))}
    crisper_results = {int(k) if not isinstance(k, int) else k: v for k, v in
                        {d["clip_index"]: d for d in json.load(open("output/crisperwhisper_verbatim.json", encoding="utf-8"))}.items()}

    Service = modal.Cls.from_name("pulsar-crisperwhisper", "CrisperWhisperService")
    svc = Service()

    results = []
    total_flagged = 0
    for c_idx, g in groq_results.items():
        fname = g["filename"]
        wav_path = os.path.join("audio", fname)
        whisper_words = list(g.get("words", []))
        ctc_words = ctc_results.get(c_idx, {}).get("acoustic_words", [])
        crisper_words = crisper_results.get(c_idx, {}).get("words", [])
        # normalize crisper word dicts (they use 'word'/'start'/'end' already)

        if not whisper_words or not os.path.exists(wav_path):
            results.append({"clip_index": c_idx, "words": whisper_words})
            continue

        data, sr = sf.read(wav_path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        audio_dur = len(data) / sr

        flags = flag_words(whisper_words, ctc_words, crisper_words)
        clusters = cluster_flags(flags)
        total_flagged += sum(flags)

        print(f"clip {c_idx:>2}: {sum(flags)} corroborated-flagged words -> {len(clusters)} cluster(s)")

        def _norm(t):
            return t.lower().strip(".,?!\"'-").strip()

        repaired_words = []
        covered_until = 0
        for (ci, cj) in clusters:
            repaired_words.extend(whisper_words[covered_until:ci])
            pad_st, pad_en = slice_bounds(whisper_words, audio_dur, ci, cj)
            slice_samples = data[int(pad_st * sr):int(pad_en * sr)]
            buf = io.BytesIO()
            sf.write(buf, slice_samples, sr, format="WAV")
            wav_bytes = buf.getvalue()

            try:
                res = svc.transcribe_verbatim.remote(wav_bytes)
                sub_words = res["words"] or []
                sub = [{"word": w["word"], "start": round(pad_st + float(w["start"]), 3),
                        "end": round(pad_st + float(w["end"]), 3)} for w in sub_words]
            except Exception as e:
                print(f"  [warn] reslice failed: {e}")
                sub = None

            if sub and len(sub) >= 1:
                if ci > 0 and _norm(sub[0]["word"]) == _norm(whisper_words[ci - 1]["word"]):
                    sub = sub[1:]
                if sub and cj + 1 < len(whisper_words) and _norm(sub[-1]["word"]) == _norm(whisper_words[cj + 1]["word"]):
                    sub = sub[:-1]
                repaired_words.extend(sub)
                orig_n = cj - ci + 1
                print(f"  cluster [{ci},{cj}] '{' '.join(w['word'] for w in whisper_words[ci:cj+1])}' "
                      f"({orig_n} words) -> {len(sub)} words: {' '.join(w['word'] for w in sub)}")
            else:
                repaired_words.extend(whisper_words[ci:cj + 1])
            covered_until = cj + 1
        repaired_words.extend(whisper_words[covered_until:])

        results.append({"clip_index": c_idx, "words": repaired_words})

    print(f"\nTotal flagged words across all clips: {total_flagged}")
    with open("output/microslice_v3.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Wrote output/microslice_v3.json")


if __name__ == "__main__":
    main()
