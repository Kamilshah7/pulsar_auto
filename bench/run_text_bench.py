"""
Text-accuracy benchmark for the transcription/reconciliation step, on the 14 gold clips.

Gold TEXT is far more trustworthy than gold BOUNDARIES: a wrong word is obvious in the
editor, so a human accepting a word is strong verification, whereas accepting a boundary
only means nobody chose to move it. Text errors also corrupt the boundaries around them,
because ForcedAligner force-fits exactly the words it is given.

Compares, with the SAME LLM:
  whisper_only      Groq whisper-large-v3 words, no reconciliation
  pipeline_prompt   pipeline.py's inline prompt (what the live GUI hands the user today)
  reconciler_prompt transcript_reconciler.py's prompt (never wired in; its quoted 8.28% WER is not reproducible)

It drives pipeline.py's real methods with AUDIO_DIR / OUTPUT_DIR redirected to the gold
audio and a scratch directory, so the live output/ state is never modified.

Usage: python bench/run_text_bench.py [--reps 3] [--model openai/gpt-oss-120b]
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_gold_bench import find_wav  # noqa: E402

WORK = os.path.join(ROOT, "bench", "text_bench_work")


def norm(w):
    return re.sub(r"[^a-z0-9'\-()]", "", str(w).lower())


def wer(ref, hyp):
    r = [norm(x) for x in ref if norm(x)]
    h = [norm(x) for x in hyp if norm(x)]
    sm = difflib.SequenceMatcher(None, r, h, autojunk=False)
    errs = sum(max(i2 - i1, j2 - j1) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal")
    matched = sum(i2 - i1 for t, i1, i2, j1, j2 in sm.get_opcodes() if t == "equal")
    return errs, matched, len(r)


def parse_llm_json(raw):
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    txt = (m.group(1) if m else raw).strip()
    if not txt.startswith("{"):
        txt = txt[txt.find("{"): txt.rfind("}") + 1]
    d = json.loads(txt)
    out = {}
    for k, v in d.items():
        out[str(k)] = [(x if isinstance(x, str) else x.get("text", x.get("word", ""))).strip() for x in v]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--model", default="openai/gpt-oss-120b")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)

    gt = json.load(open(os.path.join(ROOT, "bench", "gt_per_clip.json"), encoding="utf-8"))
    gold_dir = os.path.dirname(find_wav(gt["0"]["filename"]))

    # Redirect pipeline.py's module globals BEFORE constructing anything from it.
    import pipeline as P
    P.AUDIO_DIR = gold_dir
    P.OUTPUT_DIR = WORK
    pipe = P.PulsarPipeline()

    clips = []
    for ci in sorted(gt, key=int):
        fn = gt[ci]["filename"]
        with wave.open(find_wav(fn), "rb") as wf:
            dur = wf.getnframes() / wf.getframerate()
        clips.append({"index": int(ci), "id": f"clip_{ci}", "filename": fn,
                      "duration_sec": dur, "start_sec": 0.0, "end_sec": dur, "token_count": 0})

    cache = os.path.join(WORK, "groq_transcriptions.json")
    groq = json.load(open(cache, encoding="utf-8")) if os.path.exists(cache) else pipe._transcribe_all_clips(clips)
    w2v = pipe._run_wav2vec2_acoustic_pass(clips)
    micro = pipe._run_microslice_repair_pass(clips, groq)
    pipe_prompt, pipe_input = pipe._generate_llm_payloads(clips, groq, w2v, micro)

    import transcript_reconciler as TR
    large = {d["clip_index"]: d for d in json.load(open(os.path.join(ROOT, "output", "wav2vec2_large_with_gaps.json"), encoding="utf-8"))}
    gold_by_name = {v["filename"]: int(k) for k, v in gt.items()}
    large = {gold_by_name[d["filename"]]: d for d in large.values() if d["filename"] in gold_by_name}
    payload = []
    for g in groq:
        ci = g["clip_index"]
        ctc = TR._ctc_text_with_confidence_and_gaps(large[ci]["acoustic_words"], large[ci].get("contested_gaps", []))
        payload.append((ci, " ".join(w["word"] for w in g["words"]), ctc))
    rec_prompt = TR.build_full_prompt(payload)

    from groq import Groq
    client = Groq(api_key=P.GROQ_API_KEY)

    def ask(prompt):
        resp = client.chat.completions.create(
            model=args.model, messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_completion_tokens=16000, reasoning_effort="low")
        return resp.choices[0].message.content

    results = {"whisper_only": [{str(g["clip_index"]): [w["word"] for w in g["words"]] for g in groq}]}
    # Historical reconciler runs (v1..v5) on these same clips, one LLM sample each. NOTE:
    # none of them reproduces the "8.28% WER / 96.62% recall" figure quoted in
    # pipeline.py and transcript_reconciler.py under either normalization, and v5 -- the
    # design transcript_reconciler.py implements today -- scores worst of the five.
    for i, suffix in enumerate(["", "_v2", "_v3", "_v4", "_v5"], 1):
        hist = os.path.join(ROOT, "output", f"reconciled_transcript{suffix}.json")
        if os.path.exists(hist):
            results[f"reconciler_hist_v{i}"] = [json.load(open(hist, encoding="utf-8"))]
    for name, prompt in [("pipeline_prompt", pipe_prompt + "\n\n" + "=" * 60 + "\n\n" + pipe_input),
                         ("reconciler_prompt", rec_prompt)]:
        results[name] = []
        for rep in range(args.reps):
            path = os.path.join(WORK, f"{name}_rep{rep}.json")
            if os.path.exists(path):
                results[name].append(json.load(open(path, encoding="utf-8")))
                continue
            for attempt in range(3):
                try:
                    parsed = parse_llm_json(ask(prompt))
                    break
                except Exception as ex:
                    print(f"  [{name} rep{rep}] attempt {attempt + 1} failed: {ex}", flush=True)
                    time.sleep(5)
            else:
                continue
            json.dump(parsed, open(path, "w", encoding="utf-8"), indent=1)
            results[name].append(parsed)

    print(f"\n=== TEXT BENCH ({args.model}, {sum(len(v['tokens']) for v in gt.values())} gold tokens) ===")
    for name, reps in results.items():
        wers, recs = [], []
        for out in reps:
            E = M = N = 0
            for ci, v in gt.items():
                e, m, n = wer([t["text"] for t in v["tokens"]], out.get(ci, []))
                E += e; M += m; N += n
            wers.append(100 * E / N); recs.append(100 * M / N)
        if wers:
            spread = f"  (reps: {', '.join(f'{w:.2f}' for w in wers)})" if len(wers) > 1 else ""
            print(f"  {name:<18} WER {sum(wers)/len(wers):6.2f}%   recall {sum(recs)/len(recs):6.2f}%{spread}")


if __name__ == "__main__":
    main()
