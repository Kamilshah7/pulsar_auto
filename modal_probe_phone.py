"""One-off probe: phoneme model vocabulary vs espeak phonemizer output (runs on Modal)."""
import modal
app = modal.App("aligner2-probe")
image = (modal.Image.debian_slim(python_version="3.11").apt_install("espeak-ng")
         .pip_install("transformers==5.17.0", "torch", "phonemizer", "huggingface_hub").env({"HF_HOME": "/cache/hf"}))
VOL = modal.Volume.from_name("aligner2-cache", create_if_missing=True)


@app.function(image=image, volumes={"/cache": VOL}, timeout=900)
def probe(words: list):
    import json
    from huggingface_hub import hf_hub_download
    from phonemizer import phonemize
    from phonemizer.separator import Separator
    name = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"
    vocab = json.load(open(hf_hub_download(name, "vocab.json")))
    for f in ("config.json", "preprocessor_config.json", "model.safetensors"):
        try:
            hf_hub_download(name, f)
        except Exception as e:
            print("skip", f, type(e).__name__)
    VOL.commit()
    ph = phonemize(words, language="en-us", backend="espeak", separator=Separator(phone=" ", word="", syllable=""),
                   strip=True, preserve_punctuation=False, njobs=1)
    out = {w: p.split() for w, p in zip(words, ph)}
    missing = sorted({x for p in out.values() for x in p if x not in vocab})
    return {"vocab_size": len(vocab), "vocab_sample": sorted(vocab)[:80], "phones": out, "not_in_vocab": missing}


@app.local_entrypoint()
def main():
    import json
    words = ["the", "know", "she", "church", "thing", "uh", "um", "didn't", "podcast", "twenty", "25", "shou", "s", "a",
             "wiggum", "endoparasite", "i've", "you're", "character", "russia", "yeah", "hmm", "okay"]
    r = probe.remote(words)
    print(json.dumps(r, ensure_ascii=False, indent=1))
