"""
Improved microslice repair pass.

Diagnosed failure of the original (`pipeline.py::_run_microslice_repair_pass`): it
correctly flags individual "bloated" words (Whisper words whose duration implies they
absorbed multiple spoken words/disfluencies) using a fixed threshold, but then re-slices
with only 50ms of padding around JUST that single word. Two problems:
  1. The smeared disfluency content frequently spills into an ADJACENT word too (e.g. a
     genuinely dropped "read r-" sits inside the normal-looking word right before the
     flagged one), which never gets included in the re-sliced audio at all.
  2. A fixed absolute duration threshold (1.4s / 0.65s for function words) misses clips
     with a faster speech rate, where a smeared word might only reach ~1.0s -- still far
     longer than that clip's own typical word, just not past the fixed cutoff.

Fixes here (both general, not clip-specific):
  - Adaptive threshold: bloated = duration >= max(ABS_FLOOR, ADAPTIVE_MULT * clip's own
    median word duration), so it scales to each clip's actual speech rate.
  - Cluster flagged words with their immediate neighbours and re-slice the WHOLE cluster
    with generous context padding, instead of one isolated word with 50ms of padding.
"""
import io
import json
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, ".")
from pipeline import GROQ_API_KEY  # noqa: E402
from groq import Groq  # noqa: E402

ABS_FLOOR_S = 0.45
FUNC_FLOOR_S = 0.55
ADAPTIVE_MULT = 2.2
NEIGHBOR_MULT = 1.3       # a neighbor only joins the cluster if it's at least this suspicious too
CONTEXT_PAD_S = 0.25
MAX_PAD_FRACTION_OF_GAP = 0.4  # never let padding cross more than this fraction into a neighbor's own gap
FUNCS = {"a", "an", "the", "and", "or", "to", "of", "in", "it", "so", "than", "one", "not"}


def is_bloated(word_text, dur, median_dur, mult=ADAPTIVE_MULT):
    cl = word_text.lower().strip(".,?!\"'")
    thresh = max(ABS_FLOOR_S, mult * median_dur)
    if cl in FUNCS:
        thresh = min(thresh, FUNC_FLOOR_S)
    return dur >= thresh


def cluster_flags(words, flags, median_dur):
    """Merge flagged words with immediate neighbours into contiguous clusters, but only
    pull in a neighbor if it is ALSO at least borderline-suspicious (NEIGHBOR_MULT) --
    an ordinary short/normal word next to a flagged one should NOT get swept in and
    re-transcribed, since that risks corrupting content that was already correct."""
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


def reslice_cluster(client, data, sr, audio_dur, words, ci, cj):
    # Cap padding so it can't cross more than MAX_PAD_FRACTION_OF_GAP of the way into a
    # neighboring (non-cluster) word's own span -- prevents the reslice from re-decoding
    # (and duplicating) audio that belongs to an already-correct adjacent word.
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
    slice_samples = data[int(pad_st * sr):int(pad_en * sr)]
    buf = io.BytesIO()
    sf.write(buf, slice_samples, sr, format="WAV")
    buf.seek(0)
    try:
        resp = client.audio.transcriptions.create(
            file=("slice.wav", buf.read()),
            model="whisper-large-v3",
            response_format="verbose_json",
            timestamp_granularities=["word"],
            prompt="um, uh, the, and, like, you know, verbatim stutters, repeated words",
            temperature=0.0,
        )
        sub_words = resp.words or []
        return [{"word": sw["word"], "start": round(pad_st + float(sw["start"]), 3),
                  "end": round(pad_st + float(sw["end"]), 3)} for sw in sub_words]
    except Exception as e:
        print(f"  [warn] reslice failed: {e}")
        return None


def main():
    groq_results = json.load(open("output/groq_transcriptions.json", encoding="utf-8"))
    client = Groq(api_key=GROQ_API_KEY)

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

        n_flagged = sum(flags)
        print(f"clip {c_idx:>2}: {n_flagged} flagged words -> {len(clusters)} cluster(s) "
              f"(median_word_dur={median_dur*1000:.0f}ms)")

        def _norm(t):
            return t.lower().strip(".,?!\"'").strip()

        repaired_words = []
        covered_until = 0
        for (ci, cj) in clusters:
            repaired_words.extend(words[covered_until:ci])
            sub = reslice_cluster(client, data, sr, audio_dur, words, ci, cj)
            if sub and len(sub) >= 1:
                # Defense in depth against residual context bleed: if the reslice's
                # first/last token exactly repeats the word immediately outside the
                # cluster (which padding may have partially captured), drop it rather
                # than double-count that word.
                if ci > 0 and sub and _norm(sub[0]["word"]) == _norm(words[ci - 1]["word"]):
                    sub = sub[1:]
                if cj + 1 < len(words) and sub and _norm(sub[-1]["word"]) == _norm(words[cj + 1]["word"]):
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

    with open("output/microslice_v2.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nWrote output/microslice_v2.json")


if __name__ == "__main__":
    main()
