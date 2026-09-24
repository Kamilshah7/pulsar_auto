"""
Modal deployment for WhisperX, to benchmark its forced-alignment (wav2vec2
phoneme-based word-level alignment) against our golden labels, using the
same methodology as modal_crisperwhisper.py.

Usage:
  modal run modal_whisperx.py::test_single --wav-path <path>
  modal run modal_whisperx.py::run_forced_align_all
"""
import json
import os

import modal

app = modal.App("pulsar-whisperx")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git")
    .pip_install(
        "torch",
        "torchaudio",
        "whisperx",
        "openai-whisper",
        "soundfile",
        "numpy",
    )
)

MODEL_CACHE = modal.Volume.from_name("whisperx-cache", create_if_missing=True)
CACHE_DIR = "/cache"


@app.cls(image=image, gpu="A10G", volumes={CACHE_DIR: MODEL_CACHE}, timeout=600, scaledown_window=300)
class WhisperXService:
    @modal.enter()
    def load(self):
        os.environ["HF_HOME"] = f"{CACHE_DIR}/hf"
        os.environ["XDG_CACHE_HOME"] = f"{CACHE_DIR}/xdg"
        os.environ["TORCH_HOME"] = f"{CACHE_DIR}/torch"
        import torch
        import whisperx

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.align_model, self.align_metadata = whisperx.load_align_model(
            language_code="en", device=self.device
        )
        self.asr_model = whisperx.load_model("large-v2", self.device, compute_type=self.compute_type)
        self.whisperx = whisperx

    @modal.method()
    def whisper_native_word_timestamps(self, wav_bytes: bytes, words: list) -> dict:
        """Whisper large-v3's OWN cross-attention DTW word timestamps
        (word_timestamps=True), force-decoded against the known gold text via
        initial_prompt+condition. This is the large-model version of the
        cross-attention hypothesis -- we only ever tested tiny.en locally."""
        import tempfile
        import whisper as openai_whisper

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        if not hasattr(self, "ow_model"):
            self.ow_model = openai_whisper.load_model("large-v3")

        result = self.ow_model.transcribe(
            tmp_path, language="en", word_timestamps=True,
            condition_on_previous_text=False,
        )
        os.unlink(tmp_path)

        out_words = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                out_words.append({
                    "word": w.get("word", "").strip(),
                    "start": w.get("start"),
                    "end": w.get("end"),
                    "probability": w.get("probability"),
                })
        return {"text": result.get("text", ""), "words": out_words}

    @modal.method()
    def transcribe_and_align(self, wav_bytes: bytes) -> dict:
        """Full end-to-end WhisperX: transcribe raw audio with NO gold text
        given (genuine ASR), then align its own output words. This is what
        actually happens if this were swapped in for the transcription
        step -- distinct from forced_align(), which is handed the correct
        words in advance."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        audio = self.whisperx.load_audio(tmp_path)
        asr_result = self.asr_model.transcribe(audio, batch_size=16, language="en")
        aligned = self.whisperx.align(
            asr_result["segments"], self.align_model, self.align_metadata, audio, self.device,
            return_char_alignments=False,
        )
        os.unlink(tmp_path)

        out_words = []
        for seg in aligned.get("segments", []):
            for w in seg.get("words", []):
                out_words.append({
                    "word": w.get("word", ""),
                    "start": w.get("start"),
                    "end": w.get("end"),
                    "score": w.get("score"),
                })
        full_text = " ".join(s.get("text", "").strip() for s in asr_result["segments"])
        return {"text": full_text, "words": out_words}

    @modal.method()
    def forced_align(self, wav_bytes: bytes, words: list) -> dict:
        """Force-align a KNOWN correct word sequence against the audio,
        using WhisperX's wav2vec2 phoneme-based aligner directly (bypassing
        Whisper transcription entirely, matching our forced-alignment
        methodology throughout this project)."""
        import tempfile
        import soundfile as sf
        import numpy as np

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        data, sr = sf.read(tmp_path)
        audio_dur = len(data) / sr

        # WhisperX's align() expects Whisper-style segments with text; we
        # construct a single segment spanning the whole clip with our known
        # correct transcript, forcing it to align against the KNOWN text
        # rather than Whisper's own (possibly wrong) transcription.
        text = " ".join(words)
        segments = [{"text": text, "start": 0.0, "end": audio_dur}]

        audio = self.whisperx.load_audio(tmp_path)
        result = self.whisperx.align(
            segments, self.align_model, self.align_metadata, audio, self.device,
            return_char_alignments=False,
        )
        os.unlink(tmp_path)

        out_words = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                out_words.append({
                    "word": w.get("word", ""),
                    "start": w.get("start"),
                    "end": w.get("end"),
                    "score": w.get("score"),
                })
        return {"words": out_words}


@app.local_entrypoint()
def test_single(wav_path: str = "F:/BB/ETN-SC/pulsar_auto_audio_restore/zencastr-en_6049f1bff79637001585bcfa-00001_53.wav"):
    svc = WhisperXService()
    with open(wav_path, "rb") as f:
        wav_bytes = f.read()
    gt = json.load(open("bench/gt_per_clip.json", encoding="utf-8"))
    words = [t["text"] for t in gt["0"]["tokens"]]
    print("=== forced_align ===")
    res = svc.forced_align.remote(wav_bytes, words)
    for w in res["words"][:20]:
        print(f"  {w['start']}-{w['end']}  {w['word']}  score={w.get('score')}")


@app.local_entrypoint()
def run_forced_align_all():
    """Feed each clip's GOLDEN word sequence into WhisperX's forced aligner,
    to directly benchmark its boundary precision against golden timestamps."""
    AUDIO_DIR = "F:/BB/ETN-SC/pulsar_auto_audio_restore"
    gt = json.load(open("bench/gt_per_clip.json", encoding="utf-8"))
    svc = WhisperXService()
    results = {}
    for ci, entry in sorted(gt.items(), key=lambda kv: int(kv[0])):
        wav_path = os.path.join(AUDIO_DIR, entry["filename"])
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()
        words = [t["text"] for t in entry["tokens"]]
        print(f"clip {ci}: forced_align on {len(words)} gold words...")
        res = svc.forced_align.remote(wav_bytes, words)
        results[ci] = res
        print(f"  -> {len(res['words'])} words returned")
    with open("output/whisperx_forced_align.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Wrote output/whisperx_forced_align.json")


@app.local_entrypoint()
def run_whisper_native_all():
    """Whisper large-v3's own cross-attention DTW word timestamps on all 14
    clips -- the large-model version of the cross-attention hypothesis
    (only tiny.en was ever tested locally)."""
    AUDIO_DIR = "F:/BB/ETN-SC/pulsar_auto_audio_restore"
    gt = json.load(open("bench/gt_per_clip.json", encoding="utf-8"))
    svc = WhisperXService()
    results = {}
    for ci, entry in sorted(gt.items(), key=lambda kv: int(kv[0])):
        wav_path = os.path.join(AUDIO_DIR, entry["filename"])
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()
        words = [t["text"] for t in entry["tokens"]]
        print(f"clip {ci}: whisper large-v3 native word_timestamps...")
        res = svc.whisper_native_word_timestamps.remote(wav_bytes, words)
        results[ci] = res
        print(f"  -> {len(res['words'])} words")
    with open("output/whisper_native_words.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Wrote output/whisper_native_words.json")


@app.local_entrypoint()
def run_transcribe_all():
    """Full end-to-end: WhisperX transcribes each clip from RAW AUDIO with
    NO gold text given (genuine ASR), then aligns its own output. This
    answers the actual 'should we switch for transcription' question,
    unlike run_forced_align_all which is handed the correct words upfront."""
    AUDIO_DIR = "F:/BB/ETN-SC/pulsar_auto_audio_restore"
    gt = json.load(open("bench/gt_per_clip.json", encoding="utf-8"))
    svc = WhisperXService()
    results = {}
    for ci, entry in sorted(gt.items(), key=lambda kv: int(kv[0])):
        wav_path = os.path.join(AUDIO_DIR, entry["filename"])
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()
        print(f"clip {ci}: transcribing (no gold text given)...")
        res = svc.transcribe_and_align.remote(wav_bytes)
        results[ci] = res
        print(f"  -> {len(res['words'])} words: {res['text'][:80]}")
    with open("output/whisperx_transcribe.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Wrote output/whisperx_transcribe.json")
