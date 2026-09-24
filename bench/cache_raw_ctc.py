"""
Run the wav2vec2 CTC forced-alignment step ONCE per clip (the slow, model-dependent part)
and cache its raw output (pre any heuristic snapping) plus the raw audio samples to disk.

This lets us iterate on boundary-refinement algorithms purely in numpy afterwards, without
re-running the model every time (CTC forced_align is ~5-10s/clip; refinement should be <0.1s/clip).

Output: bench/raw_cache/<clipIndex>.npz containing:
  - data (float32 mono audio samples), sr
  - word_start, word_end, word_score (raw CTC per-word arrays, aligned to gt token order)
  - pipe_start, pipe_end (CTC separator/blank spans between consecutive words)
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
import torch
import torchaudio
import torchaudio.functional as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_gold_bench import find_wav  # gold clips live in ../pulsar_auto_audio_restore, not audio/

from forced_aligner import split_abbreviations  # noqa: E402


def raw_ctc_align(model, dictionary, bundle, device, audio_path, raw_words):
    data, sr = sf.read(audio_path)
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    audio_dur = len(data) / sr

    wav_tensor = torch.from_numpy(data).float().unsqueeze(0)
    if sr != bundle.sample_rate:
        wav_16k = torchaudio.functional.resample(wav_tensor, sr, bundle.sample_rate)
    else:
        wav_16k = wav_tensor

    raw_words = split_abbreviations(raw_words)
    NUM_MAP = {
        "0": "ZERO", "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR",
        "5": "FIVE", "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE",
        "10": "TEN", "11": "ELEVEN", "12": "TWELVE", "13": "THIRTEEN", "14": "FOURTEEN",
        "15": "FIFTEEN", "16": "SIXTEEN", "17": "SEVENTEEN", "18": "EIGHTEEN", "19": "NINETEEN",
        "20": "TWENTY", "30": "THIRTY", "40": "FORTY", "50": "FIFTY", "60": "SIXTY",
        "70": "SEVENTY", "80": "EIGHTY", "90": "NINETY", "100": "HUNDRED"
    }
    import re
    clean_words = []
    for w in raw_words:
        w_str = w.strip().lower()
        if w_str in NUM_MAP:
            cw = NUM_MAP[w_str]
        else:
            cw = re.sub(r"[^A-Za-z']", "", w.upper().replace("-", ""))
        clean_words.append(cw if cw else "A")
    formatted_text = "|".join(clean_words)
    target_tokens = [dictionary[c] for c in formatted_text]

    with torch.inference_mode():
        emission, _ = model(wav_16k.to(device))
        emission = emission[0].cpu().unsqueeze(0)

    targets = torch.tensor([target_tokens], dtype=torch.int32)
    aligned_tokens, scores = F.forced_align(
        emission, targets,
        torch.tensor([emission.size(1)]),
        torch.tensor([len(target_tokens)]),
        blank=0,
    )
    spans = F.merge_tokens(aligned_tokens[0], scores[0])

    ratio = audio_dur / emission.size(1)
    pipe_id = dictionary["|"]
    words, pipes = [], []
    curr_w = []
    for s in spans:
        if s.token == pipe_id:
            if curr_w:
                words.append({"start": curr_w[0].start * ratio, "end": curr_w[-1].end * ratio,
                               "score": float(np.mean([sp.score for sp in curr_w]))})
                curr_w = []
            pipes.append({"start": s.start * ratio, "end": s.end * ratio})
        else:
            curr_w.append(s)
    if curr_w:
        words.append({"start": curr_w[0].start * ratio, "end": curr_w[-1].end * ratio,
                       "score": float(np.mean([sp.score for sp in curr_w]))})

    mapped_words = []
    for idx, rw in enumerate(raw_words):
        if idx < len(words):
            mapped_words.append({"text": rw, "start": words[idx]["start"], "end": words[idx]["end"],
                                   "score": words[idx]["score"]})
        else:
            if mapped_words:
                last_end = mapped_words[-1]["end"]
                remaining = len(raw_words) - idx
                slot = 0.030
                slot_start = min(last_end + 0.002, audio_dur - remaining * slot)
                w_start = slot_start + (idx - len(words)) * slot
                w_end = w_start + slot - 0.002
                mapped_words.append({"text": rw, "start": max(last_end + 0.002, w_start),
                                       "end": min(audio_dur - 0.002, w_end), "score": 0.01})
            else:
                mapped_words.append({"text": rw, "start": idx * 0.030, "end": idx * 0.030 + 0.028, "score": 0.01})

    return data.astype(np.float32), sr, mapped_words, pipes


def main():
    gt = json.load(open(os.path.join(ROOT, "bench", "gt_per_clip.json"), encoding="utf-8"))
    out_dir = os.path.join(ROOT, "bench", "raw_cache")
    os.makedirs(out_dir, exist_ok=True)

    device = torch.device("cpu")
    print("[cache] loading WAV2VEC2_ASR_BASE_960H...")
    bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
    model = bundle.get_model().to(device)
    labels = bundle.get_labels()
    dictionary = {c: i for i, c in enumerate(labels)}
    print("[cache] loaded.")

    for ci, entry in sorted(gt.items(), key=lambda kv: int(kv[0])):
        out_path = os.path.join(out_dir, f"{ci}.npz")
        wav_path = find_wav(entry["filename"])
        words = [t["text"] for t in entry["tokens"]]
        data, sr, mapped_words, pipes = raw_ctc_align(model, dictionary, bundle, device, wav_path, words)
        np.savez(
            out_path,
            data=data, sr=sr,
            word_start=np.array([w["start"] for w in mapped_words]),
            word_end=np.array([w["end"] for w in mapped_words]),
            word_score=np.array([w["score"] for w in mapped_words]),
            word_text=np.array([w["text"] for w in mapped_words], dtype=object),
            pipe_start=np.array([p["start"] for p in pipes]),
            pipe_end=np.array([p["end"] for p in pipes]),
        )
        print(f"clip {ci}: cached {len(mapped_words)} words, {len(pipes)} pipes -> {out_path}")


if __name__ == "__main__":
    main()
