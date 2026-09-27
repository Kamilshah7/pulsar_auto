"""
EXPERIMENT (2026-09-27; the user: "a step after alignment that makes each word sound exactly right -- micro adjustments
only"). The "listener": the engine's two pretrained recognizers (HuBERT-large letters, xlsr-53 espeak phonemes; no
training) run on a cut-out word segment ALONE, the way the review tool plays it, so aligner2/listen_eval.py can ask
"does this segment sound like exactly this word?" = the CTC probability of the word's letters / phones.
Separate app (aligner2-listen): production is untouched. A10G, containers stop 20 s after the last call.

    in: [(float32 16 kHz segment bytes, {"L": [letter label seqs], "P": [phone label seqs]})]
    out: [{"L": [log P(seq | segment)], "P": [...]}]      (CTC forward, aligner2/lexical.py: the engine's scoring)
"""
import modal

APP_NAME = "aligner2-listen"
app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.11")
         .apt_install("espeak-ng")
         .pip_install("torch", "transformers==5.17.0", "numpy", "phonemizer", "huggingface_hub", "num2words")
         .env({"HF_HOME": "/cache/hf", "HF_HUB_DISABLE_XET": "1"})
         .add_local_python_source("aligner2", copy=True))
VOL = modal.Volume.from_name("aligner2-cache", create_if_missing=True)
SR = 16000


@app.cls(image=image, gpu="A10G", volumes={"/cache": VOL}, timeout=1800, scaledown_window=20, max_containers=4)
class Listener:
    @modal.enter()
    def load(self):
        from transformers import AutoFeatureExtractor, HubertForCTC, Wav2Vec2ForCTC
        name = "facebook/hubert-large-ls960-ft"                     # the engine's letter model
        self.fe = AutoFeatureExtractor.from_pretrained(name)
        self.lm = HubertForCTC.from_pretrained(name).eval().cuda()
        pname = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"            # the engine's phoneme model
        self.pfe = AutoFeatureExtractor.from_pretrained(pname)
        self.pm = Wav2Vec2ForCTC.from_pretrained(pname).eval().cuda()

    @modal.method()
    def units(self, token_lists):
        """per clip token list -> per token phone id lists (aligner2/phones.py, espeak: the engine's own units)"""
        from aligner2.phones import token_units
        return [token_units(t)[0] for t in token_lists]

    @modal.method()
    def run(self, jobs):
        import numpy as np
        import torch
        from aligner2.lexical import forward_backward
        out = []
        for b, hyps in jobs:
            x = np.frombuffer(b, dtype=np.float32)
            res = {}
            for tag, fe, m, wild_from in (("L", self.fe, self.lm, 5), ("P", self.pfe, self.pm, 4)):
                inp = fe(x, sampling_rate=SR, return_tensors="pt").input_values.cuda()
                with torch.inference_mode():
                    lp = torch.log_softmax(m(inp).logits[0].float(), dim=-1).cpu().numpy().astype(np.float64)
                res[tag] = [float(forward_backward(lp, seq, wild_from=wild_from)[1]) if seq else float("nan")
                            for seq in hyps[tag]]
            out.append(res)
        return out
