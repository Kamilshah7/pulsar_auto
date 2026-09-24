"""
Modal deployment for CrisperWhisper 2.0 (nyrahealth), to evaluate it as a standalone
replacement and/or hybrid component for the current Whisper+CTC+LLM reconciliation and
forced-alignment pipeline.

We test three of its capabilities against our golden labels:
  1. transcribe(mode="verbatim") -- a single-call replacement for our whole
     Whisper+wav2vec2-CTC+LLM reconciliation stage (word-level, disfluency-preserving).
  2. forced_align(audio, text) -- their own forced aligner, given a known-correct word
     sequence, as a direct alternative/cross-check to our wav2vec2 CTC + boundary_refiner.
  3. verbatimize(audio, transcript) -- inject real disfluencies into an existing clean
     transcript (e.g. plain Whisper output), as a recall-boosting alternative to our
     microslice-repair approach.

Usage:
  modal run modal_crisperwhisper.py::test_single --wav-path audio/xxx.wav
  modal run modal_crisperwhisper.py::run_all_clips
"""
import json
import os

import modal

app = modal.App("pulsar-crisperwhisper")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("crisperwhisper[ct2,convert]")
    .pip_install("soundfile", "numpy")
)

MODEL_CACHE = modal.Volume.from_name("crisperwhisper-cache", create_if_missing=True)
CACHE_DIR = "/cache"


@app.cls(image=image, gpu="A10G", volumes={CACHE_DIR: MODEL_CACHE}, timeout=600, scaledown_window=300)
class CrisperWhisperService:
    @modal.enter()
    def load(self):
        os.environ["HF_HOME"] = f"{CACHE_DIR}/hf"
        os.environ["XDG_CACHE_HOME"] = f"{CACHE_DIR}/xdg"
        from crisperwhisper import CrisperWhisperModel
        self.model = CrisperWhisperModel("large")

    @modal.method()
    def transcribe_verbatim(self, wav_bytes: bytes) -> dict:
        import io
        import soundfile as sf
        import numpy as np
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        result = self.model.transcribe(tmp_path, language="en", word_timestamps=True)
        os.unlink(tmp_path)
        return {
            "text": result.text,
            "words": [{"word": w.word, "start": w.start, "end": w.end} for w in result.words],
        }

    @modal.method()
    def forced_align(self, wav_bytes: bytes, words: list) -> dict:
        import tempfile
        text = " ".join(words)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        result = self.model.forced_align(tmp_path, text)
        os.unlink(tmp_path)
        out_words = getattr(result, "words", result)
        return {"words": [{"word": w.word, "start": w.start, "end": w.end} for w in out_words]}

    @modal.method()
    def verbatimize(self, wav_bytes: bytes, clean_transcript: str) -> dict:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        result = self.model.verbatimize(tmp_path, clean_transcript)
        os.unlink(tmp_path)
        words = getattr(result, "words", None)
        out = {"text": getattr(result, "text", str(result))}
        if words:
            out["words"] = [{"word": w.word, "start": w.start, "end": w.end} for w in words]
        return out


@app.local_entrypoint()
def test_single(wav_path: str = "audio/zencastr-en_6049f1bff79637001585bcfa-00001_53.wav"):
    svc = CrisperWhisperService()
    with open(wav_path, "rb") as f:
        wav_bytes = f.read()
    print("=== transcribe_verbatim ===")
    res = svc.transcribe_verbatim.remote(wav_bytes)
    print(res["text"])
    for w in res["words"][:15]:
        print(f"  {w['start']:.3f}-{w['end']:.3f}  {w['word']}")


@app.local_entrypoint()
def run_all_clips():
    ordered = json.load(open("output/ordered_clips.json", encoding="utf-8"))
    svc = CrisperWhisperService()
    results = []
    for c in ordered:
        wav_path = os.path.join("audio", c["filename"])
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()
        print(f"clip {c['index']}: transcribing verbatim...")
        res = svc.transcribe_verbatim.remote(wav_bytes)
        results.append({"clip_index": c["index"], "filename": c["filename"], **res})
        print(f"  -> {len(res['words'])} words")
    with open("output/crisperwhisper_verbatim.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Wrote output/crisperwhisper_verbatim.json")


@app.local_entrypoint()
def run_forced_align_all():
    """Feed each clip's GOLDEN word sequence into CrisperWhisper's own forced_align(),
    to directly benchmark its boundary precision against golden timestamps, matching
    the same methodology as bench/run_align_benchmark.py (correct text in, measure how
    close the predicted boundaries land)."""
    gt = json.load(open("bench/gt_per_clip.json", encoding="utf-8"))
    svc = CrisperWhisperService()
    results = {}
    for ci, entry in sorted(gt.items(), key=lambda kv: int(kv[0])):
        wav_path = os.path.join("audio", entry["filename"])
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()
        words = [t["text"] for t in entry["tokens"]]
        print(f"clip {ci}: forced_align on {len(words)} gold words...")
        res = svc.forced_align.remote(wav_bytes, words)
        results[ci] = res
        print(f"  -> {len(res['words'])} words returned")
    with open("output/crisperwhisper_forced_align.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Wrote output/crisperwhisper_forced_align.json")


@app.local_entrypoint()
def run_verbatimize_all():
    """Feed each clip's plain Whisper transcript into CrisperWhisper's verbatimize(),
    to test it as a recall-boosting alternative to our microslice-repair approach."""
    groq_results = json.load(open("output/groq_transcriptions.json", encoding="utf-8"))
    svc = CrisperWhisperService()
    results = {}
    for g in groq_results:
        ci = str(g["clip_index"])
        wav_path = os.path.join("audio", g["filename"])
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()
        print(f"clip {ci}: verbatimize...")
        res = svc.verbatimize.remote(wav_bytes, g["full_text"])
        results[ci] = res
        print(f"  -> {res['text'][:100]}")
    with open("output/crisperwhisper_verbatimize.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Wrote output/crisperwhisper_verbatimize.json")
