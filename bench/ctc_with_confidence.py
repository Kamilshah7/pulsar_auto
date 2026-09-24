"""
Re-run the wav2vec2 CTC acoustic pass, this time exposing per-word acoustic CONFIDENCE
(mean max-softmax-probability over the frames belonging to that word), not just the
decoded text.

Root cause this addresses: neither Whisper nor our existing CTC extraction ever expose
a confidence signal to the LLM reconciliation step. An ASR model NEVER emits "I don't
know" -- it always outputs its single best guess, confident-sounding or not. So when the
true content is genuinely unclear speech (which Pulsar wants marked "(())"/"((word))"),
every source just guesses a plausible real word, and the reconciler has no way to tell
that guess apart from a solid one. Low CTC confidence at a position is the one signal we
can actually compute (we already run the model; we were just discarding the probabilities
after argmax). This doesn't fix truncation-fragment recovery (that needs a decode-
sensitivity fix, a separate piece of work) or the um/uh/ah acoustic discrimination
question, but it directly targets the unclear-speech-marker gap.
"""
import json
import os

import torch
import torchaudio
import soundfile as sf


def main():
    ordered = json.load(open("output/ordered_clips.json", encoding="utf-8"))

    print("Loading WAV2VEC2_ASR_BASE_960H...")
    bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
    model = bundle.get_model()
    labels = bundle.get_labels()
    print("Loaded.")

    results = []
    for c in ordered:
        c_idx = c["index"]
        fname = c["filename"]
        wav_path = os.path.join("audio", fname)
        if not os.path.exists(wav_path):
            continue

        data, sr = sf.read(wav_path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        tensor_wav = torch.tensor(data, dtype=torch.float32).unsqueeze(0)
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            tensor_wav = resampler(tensor_wav)

        with torch.no_grad():
            emissions, _ = model(tensor_wav)
            log_probs = torch.log_softmax(emissions, dim=-1)
            probs = log_probs.exp()[0]  # (n_frames, n_labels)

        max_probs, indices = torch.max(probs, dim=-1)
        raw_chars = [labels[i] for i in indices]
        frame_confs = max_probs.tolist()

        non_blank = []
        prev = None
        for idx, (c_lbl, conf) in enumerate(zip(raw_chars, frame_confs)):
            t_sec = idx * 0.02
            if c_lbl != prev:
                if c_lbl != '-':
                    non_blank.append({"char": c_lbl, "time": t_sec, "conf": conf})
                prev = c_lbl
            elif c_lbl != '-':
                # extend confidence tracking for repeated (held) non-blank frames:
                # keep the running list of confs for this char-run on the last entry
                non_blank[-1].setdefault("confs", [non_blank[-1]["conf"]]).append(conf)

        acoustic_words = []
        cur_chars = []
        cur_confs = []
        w_st = None
        for item in non_blank:
            ch = item["char"]
            tm = item["time"]
            c_list = item.get("confs", [item["conf"]])
            if ch == '|':
                if cur_chars:
                    acoustic_words.append({
                        "word": "".join(cur_chars).lower(),
                        "start": round(w_st, 2),
                        "end": round(tm, 2),
                        "confidence": round(float(sum(cur_confs) / len(cur_confs)), 4),
                    })
                    cur_chars, cur_confs = [], []
                    w_st = None
            else:
                if w_st is None:
                    w_st = tm
                cur_chars.append(ch)
                cur_confs.extend(c_list)
        if cur_chars:
            acoustic_words.append({
                "word": "".join(cur_chars).lower(),
                "start": round(w_st, 2),
                "end": round(non_blank[-1]["time"], 2),
                "confidence": round(float(sum(cur_confs) / len(cur_confs)), 4),
            })

        low_conf = [w for w in acoustic_words if w["confidence"] < 0.5]
        print(f"clip {c_idx:>2}: {len(acoustic_words)} words, "
              f"{len(low_conf)} below 0.5 confidence: "
              f"{[(w['word'], w['confidence']) for w in low_conf][:8]}")

        results.append({
            "clip_index": c_idx,
            "filename": fname,
            "acoustic_words": acoustic_words,
        })

    with open("output/wav2vec2_acoustic_with_confidence.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nWrote output/wav2vec2_acoustic_with_confidence.json")


if __name__ == "__main__":
    main()
