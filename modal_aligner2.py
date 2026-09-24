"""
aligner2 GPU engine on Modal (deployed app "aligner2-signals"). Runs the whole aligner:
    signals   HuBERT-large + pyannote on the GPU, DSP signals in the same container
              (aligner2/signals.py), cached per clip on the "aligner2-cache" volume
    align     CTC forward-backward on the GPU (aligner2/lexical.py) + segmentation (aligner2/segment.py)
              for a whole grid of parameter settings in one call

The local client (aligner2/remote.py) redeploys this app automatically when aligner2/*.py or this file
changes. No memory snapshot (it restored stale code after redeploys): a cold container loads the models
itself (~30-60 s); containers stay warm for SCALEDOWN_S after the last call (python -m aligner2.remote warm|cool).
"""
import io
import os

import modal
import numpy as np

APP_NAME = "aligner2-signals"
app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.11")
         .apt_install("ffmpeg", "espeak-ng")
         .pip_install("torch", "torchaudio", "transformers==5.17.0", "pyannote.audio==4.0.7", "soundfile", "numpy",
                      "scipy", "scikit-learn", "num2words", "phonemizer", "huggingface_hub", "g2p_en", "nltk")
         .run_commands('python -c "import nltk; [nltk.download(p) for p in (\'averaged_perceptron_tagger\', \'averaged_perceptron_tagger_eng\', \'cmudict\')]; from g2p_en import G2p; print(G2p()(\'hello world\'))"')
         .env({"HF_HOME": "/cache/hf", "HF_HUB_DISABLE_XET": "1"})   # xet keeps a log open -> blocks VOL.reload
         .add_local_python_source("aligner2", copy=True))   # baked in: a code change = new image = new snapshot
VOL = modal.Volume.from_name("aligner2-cache", create_if_missing=True)
SR = 16000
LAYERS = (6, 12, 18, 24)
SHIFTS = (80, 160, 240)          # 5 / 10 / 15 ms: HuBERT frame-phase ensemble
PYA_BIN = "/cache/pyannote-seg3/pytorch_model.bin"
SIG_DIR = "/cache/signals"
SCALEDOWN_S = 900


def _sig_path(key):
    from aligner2.signals import version
    return f"{SIG_DIR}/{key}_{version()}.npz"


@app.cls(image=image, gpu="A10G", volumes={"/cache": VOL}, timeout=1800, scaledown_window=SCALEDOWN_S,
         max_containers=4)   # no memory snapshot: snapshots kept restoring OLD code after redeploys
class Engine:
    @modal.enter()
    def load(self):
        import torch
        from pyannote.audio import Inference, Model
        from transformers import AutoFeatureExtractor, HubertForCTC, Wav2Vec2ForCTC
        name = "facebook/hubert-large-ls960-ft"
        self.fe = AutoFeatureExtractor.from_pretrained(name)
        self.model = HubertForCTC.from_pretrained(name).eval()
        self.model = self.model.cuda()
        pname = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"          # phoneme CTC (espeak IPA), 20 ms frames
        self.pfe = AutoFeatureExtractor.from_pretrained(pname)
        self.pmodel = Wav2Vec2ForCTC.from_pretrained(pname).eval().cuda()
        # charsiu frame classifier: wav2vec2-base + linear head, 10 ms frames (last conv stride 1)
        self.fcmodel = Wav2Vec2ForCTC.from_pretrained("charsiu/en_w2v2_fc_10ms").eval().cuda()
        self.pya = Inference(Model.from_pretrained(PYA_BIN), step=1.0, duration=5.0, device=torch.device("cuda"))
        self.torch = torch

    def _models(self, x):
        torch = self.torch
        logits, plogits, fclogits, states = [], [], [], {L: [] for L in LAYERS}
        chunk, ctx = 30 * SR, 2 * SR
        for a in range(0, len(x), chunk):
            s0, s1 = max(0, a - ctx), min(len(x), a + chunk + ctx)
            inp = self.fe(x[s0:s1], sampling_rate=SR, return_tensors="pt").input_values.cuda()
            with torch.inference_mode():
                o = self.model(inp, output_hidden_states=True)
            f0, f1 = (a - s0) // 320, (min(a + chunk, len(x)) - s0) // 320
            logits.append(o.logits[0, f0:f1].float().cpu().numpy())
            pinp = self.pfe(x[s0:s1], sampling_rate=SR, return_tensors="pt").input_values.cuda()
            with torch.inference_mode():
                plogits.append(self.pmodel(pinp).logits[0, f0:f1].float().cpu().numpy())
                g0, g1 = (a - s0) // 160, (min(a + chunk, len(x)) - s0) // 160          # 10 ms frames
                fclogits.append(self.fcmodel(pinp).logits[0, g0:g1].float().cpu().numpy())
            for L in LAYERS:
                states[L].append(o.hidden_states[L][0, f0:f1].float().cpu().numpy())
        out = {"logits": np.concatenate(logits).astype(np.float32)}
        pl = np.concatenate(plogits).astype(np.float32)
        n = min(len(pl), len(out["logits"])); out["logits"] = out["logits"][:n]; out["phone_logits"] = pl[:n]
        out["fc_logits"] = np.concatenate(fclogits).astype(np.float32)
        for sh in SHIFTS:                                   # same HuBERT on the audio advanced by sh samples
            xs = x[sh:]; lg = []
            for a in range(0, len(xs), chunk):
                s0, s1 = max(0, a - ctx), min(len(xs), a + chunk + ctx)
                inp = self.fe(xs[s0:s1], sampling_rate=SR, return_tensors="pt").input_values.cuda()
                with torch.inference_mode():
                    o = self.model(inp)
                f0, f1 = (a - s0) // 320, (min(a + chunk, len(xs)) - s0) // 320
                lg.append(o.logits[0, f0:f1].float().cpu().numpy())
            out[f"logits_s{sh}"] = np.concatenate(lg).astype(np.float32)
        for L in LAYERS:
            hs = np.concatenate(states[L]); hn = hs / (np.linalg.norm(hs, axis=1, keepdims=True) + 1e-9)
            out[f"ssl_change_{L}"] = np.r_[0, 1 - (hn[2:] * hn[:-2]).sum(1), 0].astype(np.float32)
        seg = self.pya({"waveform": torch.from_numpy(x.astype(np.float32).copy())[None], "sample_rate": SR})
        out["pya"] = seg.data.astype(np.float32)
        out["pya_starts"] = np.array([seg.sliding_window[i].start for i in range(seg.data.shape[0])], np.float32)
        return out

    def _reload(self):
        try:
            VOL.reload()
        except RuntimeError as e:          # open files on the volume: keep the current view
            print("volume reload skipped:", e)

    def _load(self, key):
        p = _sig_path(key)
        if not os.path.exists(p):
            self._reload()
        z = np.load(p)
        return {k: z[k] for k in z.files}

    @modal.method()
    def ping(self) -> str:
        return "ok"

    @modal.method()
    def code_version(self) -> str:
        """hash of the aligner code this container actually runs (the client checks it matches local)"""
        import hashlib
        from aligner2 import fc_align, lexical, phones, segment, signals
        h = hashlib.sha1()
        for m in (signals, lexical, segment, phones, fc_align):   # the files actually imported
            h.update(open(m.__file__, "rb").read())
        return h.hexdigest() + " @ " + os.path.dirname(segment.__file__)

    @modal.method()
    def missing(self, keys: list) -> list:
        self._reload()
        return [k for k in keys if not os.path.exists(_sig_path(k))]

    @modal.method()
    def signals(self, key: str, audio: bytes, return_data: bool = True) -> dict:
        from aligner2.signals import features
        p = _sig_path(key)
        if os.path.exists(p):
            return self._load(key) if return_data else {"key": key}
        x = np.frombuffer(audio, dtype=np.float32).astype(np.float64)
        z = features(x, self._models(x.astype(np.float32)))
        os.makedirs(SIG_DIR, exist_ok=True)
        np.savez_compressed(p, **z)
        VOL.commit()
        return z if return_data else {"key": key}

    @modal.method()
    def align(self, key: str, texts: list, grid: list) -> dict:
        from aligner2 import fc_align, phones, segment
        units, strs = phones.token_units(texts)
        fc_ids, fc_strs = fc_align.token_phones(texts)
        z = self._load(key)
        preps = {"full": segment.Prepared(z, texts, device="cuda", phone_units=units, phone_strs=strs, fc_ids=fc_ids)}
        for name, cut in (("wild", False), ("wild+cut", True)):            # soft tokens keep their slot as wildcards
            soft = [segment.is_soft(t, cut) for t in texts]
            if any(soft):
                preps[name] = segment.Prepared(z, ["(())" if s_ else t for t, s_ in zip(texts, soft)], device="cuda",
                                               phone_units=[[-1] if s_ else u for u, s_ in zip(units, soft)],
                                               phone_strs=["*" if s_ else x for x, s_ in zip(strs, soft)],
                                               fc_ids=[[-1] if s_ else f for f, s_ in zip(fc_ids, soft)])
        return {"key": key, "preds": [segment.align_two_pass(preps, texts, **g) for g in grid],
                "phones": strs, "arpabet": fc_strs}
