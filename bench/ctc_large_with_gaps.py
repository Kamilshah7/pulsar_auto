"""
CTC extraction using WAV2VEC2_ASR_LARGE_LV60K_960H instead of the base model, exposing
BOTH per-word confidence (as in ctc_with_confidence.py) AND a scan of silent gaps for
"contested" near-miss letter evidence -- frames where blank won the argmax but a real
letter had non-negligible probability alongside it.

Root cause this targets: truncated word-initial fragments (e.g. "r-", "shou-") are the
single largest remaining category of missed tokens. Verified directly (see conversation)
that with the BASE model, most of these gaps show blank at ~100% confidence -- there is
no near-miss signal to recover, because the base model's representation doesn't cleanly
separate a brief co-articulated fragment from silence/the next word. The LARGE model
(trained on 60k hours vs 960h) was verified on the same three known gap positions to show
meaningfully stronger raw signal: e.g. a clean 0.973 "A" detection where BASE had nothing
(fused into a garbled neighbouring word), and a 0.993 "S" onset where BASE had zero words
at all. So the fix here is model capacity/sensitivity, not a decode-parameter tweak on
the same model -- confirmed empirically before building this.

This does NOT replace the live pipeline's base-model forced-alignment path (that stays on
base, which is what the boundary-refinement heuristics were calibrated against -- swapping
models there was tested earlier and made boundary precision worse). This is a separate,
one-off signal-extraction pass feeding the TEXT reconciliation step only.
"""
import json
import os

import torch
import torchaudio
import soundfile as sf

GAP_CONTEST_THRESHOLD = 0.15  # a non-blank runner-up above this in a "blank-won" gap counts as contested evidence


def main():
    ordered = json.load(open("output/ordered_clips.json", encoding="utf-8"))

    print("Loading WAV2VEC2_ASR_LARGE_LV60K_960H...")
    bundle = torchaudio.pipelines.WAV2VEC2_ASR_LARGE_LV60K_960H
    model = bundle.get_model()
    labels = bundle.get_labels()
    blank_idx = labels.index("-")
    pipe_idx = labels.index("|")
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
            tensor_wav = torchaudio.transforms.Resample(sr, 16000)(tensor_wav)

        with torch.no_grad():
            emissions, _ = model(tensor_wav)
            probs = torch.log_softmax(emissions, dim=-1).exp()[0]  # (n_frames, n_labels)

        audio_dur = len(data) / sr
        n_frames = probs.shape[0]
        ratio = audio_dur / n_frames

        max_probs, indices = torch.max(probs, dim=-1)
        # second-best (best NON-argmax-winner) letter per frame, for gap contesting
        probs_no_winner = probs.clone()
        probs_no_winner.scatter_(1, indices.unsqueeze(1), -1.0)
        runner_probs, runner_idx = torch.max(probs_no_winner, dim=-1)

        raw_chars = [labels[i] for i in indices.tolist()]
        frame_confs = max_probs.tolist()

        # ---- Build words (same approach as ctc_with_confidence.py) ----
        non_blank = []
        prev = None
        for idx, (c_lbl, conf) in enumerate(zip(raw_chars, frame_confs)):
            t_sec = idx * ratio
            if c_lbl != prev:
                if c_lbl != '-':
                    non_blank.append({"char": c_lbl, "time": t_sec, "conf": conf})
                prev = c_lbl
            elif c_lbl != '-':
                non_blank[-1].setdefault("confs", [non_blank[-1]["conf"]]).append(conf)

        acoustic_words = []
        cur_chars, cur_confs = [], []
        w_st = None
        for item in non_blank:
            ch = item["char"]
            tm = item["time"]
            c_list = item.get("confs", [item["conf"]])
            if ch == '|':
                if cur_chars:
                    acoustic_words.append({
                        "word": "".join(cur_chars).lower(),
                        "start": round(w_st, 2), "end": round(tm, 2),
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
                "start": round(w_st, 2), "end": round(non_blank[-1]["time"], 2),
                "confidence": round(float(sum(cur_confs) / len(cur_confs)), 4),
            })

        # ---- Scan for contested gaps: runs of blank-argmax frames with a real runner-up ----
        fragments = []
        i = 0
        is_blank = (indices == blank_idx)
        while i < n_frames:
            if not is_blank[i].item():
                i += 1
                continue
            j = i
            best_letters = []
            while j < n_frames and is_blank[j].item():
                r_idx = runner_idx[j].item()
                r_p = runner_probs[j].item()
                if r_idx != pipe_idx and r_p >= GAP_CONTEST_THRESHOLD:
                    best_letters.append((labels[r_idx], r_p, j))
                j += 1
            gap_len = j - i
            if gap_len >= 3 and best_letters:  # ignore 1-2 frame noise gaps
                # collapse consecutive same-letter runs, keep the peak-confidence letter per run
                collapsed = []
                for ch, p, fi in best_letters:
                    if collapsed and collapsed[-1][0] == ch:
                        if p > collapsed[-1][1]:
                            collapsed[-1] = (ch, p, fi)
                    else:
                        collapsed.append((ch, p, fi))
                if collapsed:
                    frag_str = "".join(c for c, p, fi in collapsed if p >= GAP_CONTEST_THRESHOLD)
                    peak_p = max(p for c, p, fi in collapsed)
                    if frag_str:
                        fragments.append({
                            "letters": frag_str.lower(),
                            "start": round(i * ratio, 2),
                            "end": round(j * ratio, 2),
                            "peak_confidence": round(peak_p, 4),
                        })
            i = j

        print(f"clip {c_idx:>2}: {len(acoustic_words)} words, {len(fragments)} contested gaps: "
              f"{[(f['letters'], f['peak_confidence']) for f in fragments]}")

        results.append({
            "clip_index": c_idx,
            "filename": fname,
            "acoustic_words": acoustic_words,
            "contested_gaps": fragments,
        })

    with open("output/wav2vec2_large_with_gaps.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nWrote output/wav2vec2_large_with_gaps.json")


if __name__ == "__main__":
    main()
