"""
Speech enhancement / restoration on Modal (app "aligner2-enhance", EXPERIMENTAL: aligner2/preprocess_eval.py uses it to
test whether making degraded speech more like clean speech helps the aligner; production does not call it).
Pretrained models only (no training). Each method has its own image (their dependencies conflict). Every function:
16 kHz mono float32 bytes in -> 16 kHz mono float32 bytes out, the same length.

    deepfilter   DeepFilterNet3 noise suppression (48 kHz internally, delay-compensated)
    dns64        facebookresearch denoiser, DNS64 (16 kHz waveform U-Net)
    metricgan    SpeechBrain MetricGAN+ (VoiceBank) spectral-mask enhancement
    sepformer    SpeechBrain SepFormer DNS4 16 kHz enhancement
    wpe          nara_wpe weighted prediction error dereverberation (classical, CPU)
    voicefixer   VoiceFixer general restoration (noise, reverb, bandwidth, clipping; 44.1 kHz vocoder)
    (Resemble Enhance was dropped: its image compiles DeepSpeed from source and the build kept failing.)
    demucs       htdemucs "vocals" stem (music / background separation)
"""
import modal

app = modal.App("aligner2-enhance")
VOL = modal.Volume.from_name("aligner2-cache", create_if_missing=True)
SR = 16000
common = dict(volumes={"/cache": VOL}, timeout=1800, scaledown_window=20, max_containers=4)
ENV = {"HF_HOME": "/cache/hf", "TORCH_HOME": "/cache/torch", "HF_HUB_DISABLE_XET": "1"}


def _io(fn):
    """bytes -> np float32 -> fn -> float32 bytes of the same length"""
    import numpy as np
    def wrap(audio: bytes) -> bytes:
        x = np.frombuffer(audio, dtype=np.float32).copy()
        y = np.asarray(fn(x), dtype=np.float32).reshape(-1)
        y = y[:len(x)] if len(y) >= len(x) else np.pad(y, (0, len(x) - len(y)))
        return y.astype(np.float32).tobytes()
    return wrap


def _resample(x, sr_in, sr_out):
    import torch, torchaudio
    t = torch.as_tensor(x, dtype=torch.float32)
    return torchaudio.functional.resample(t, sr_in, sr_out).numpy() if sr_in != sr_out else t.numpy()


img_df = (modal.Image.debian_slim(python_version="3.11").apt_install("git")
          .pip_install("torch==2.3.1", "torchaudio==2.3.1", "deepfilternet==0.5.6", "numpy<2").env(ENV))


@app.function(image=img_df, gpu="A10G", **common)
def deepfilter(audio: bytes) -> bytes:
    import torch
    from df.enhance import enhance, init_df
    model, st, _ = init_df()
    def f(x):
        x48 = torch.as_tensor(_resample(x, SR, st.sr()))[None]
        y = enhance(model, st, x48)                          # pad=True: the model's delay is compensated
        return _resample(y[0].cpu().numpy(), st.sr(), SR)
    return _io(f)(audio)


img_dns = (modal.Image.debian_slim(python_version="3.10")
           .pip_install("torch==2.1.2", "torchaudio==2.1.2", "denoiser==0.1.5", "numpy<2").env(ENV))


@app.function(image=img_dns, gpu="A10G", **common)
def dns64(audio: bytes) -> bytes:
    import torch
    from denoiser import pretrained
    model = pretrained.dns64().cuda().eval()
    def f(x):
        with torch.no_grad():
            return model(torch.as_tensor(x)[None, None].cuda())[0, 0].cpu().numpy()
    return _io(f)(audio)


img_sb = (modal.Image.debian_slim(python_version="3.11")
          .pip_install("torch==2.3.1", "torchaudio==2.3.1", "speechbrain==1.0.1", "numpy<2", "huggingface_hub<0.26").env(ENV))


@app.function(image=img_sb, gpu="A10G", **common)
def metricgan(audio: bytes) -> bytes:
    import torch
    from speechbrain.inference.enhancement import SpectralMaskEnhancement
    m = SpectralMaskEnhancement.from_hparams("speechbrain/metricgan-plus-voicebank", savedir="/cache/sb/metricgan",
                                             run_opts={"device": "cuda"})
    def f(x):
        with torch.no_grad():
            return m.enhance_batch(torch.as_tensor(x)[None].cuda(), lengths=torch.tensor([1.0]).cuda())[0].cpu().numpy()
    return _io(f)(audio)


@app.function(image=img_sb, gpu="A10G", **common)
def sepformer(audio: bytes) -> bytes:
    import numpy as np
    import torch
    from speechbrain.inference.separation import SepformerSeparation
    m = SepformerSeparation.from_hparams("speechbrain/sepformer-dns4-16k-enhancement", savedir="/cache/sb/sepformer",
                                         run_opts={"device": "cuda"})
    def f(x):
        out, n = [], 16000 * 10                             # 10 s chunks (attention memory), 0.5 s overlap-add
        hop, ov = n - 8000, 8000
        y = np.zeros(len(x)); w = np.zeros(len(x))
        for s in range(0, len(x), hop):
            seg = x[s:s + n]
            with torch.no_grad():
                e = m.separate_batch(torch.as_tensor(seg, dtype=torch.float32)[None].cuda())[0, :, 0].cpu().numpy()[:len(seg)]
            win = np.ones(len(seg))
            if s > 0:
                win[:min(ov, len(seg))] = np.linspace(0, 1, min(ov, len(seg)))
            y[s:s + len(seg)] += e * win; w[s:s + len(seg)] += win
            if s + n >= len(x):
                break
        return y / np.maximum(w, 1e-9)
    return _io(f)(audio)


img_wpe = modal.Image.debian_slim(python_version="3.11").pip_install("nara_wpe", "numpy<2", "scipy")


@app.function(image=img_wpe, cpu=4, **common)
def wpe(audio: bytes) -> bytes:
    from nara_wpe.utils import istft, stft
    from nara_wpe.wpe import wpe as _wpe
    def f(x):
        Y = stft(x[None], size=512, shift=128).transpose(2, 0, 1)
        Z = _wpe(Y, taps=10, delay=3, iterations=3, statistics_mode="full")
        return istft(Z.transpose(1, 2, 0), size=512, shift=128)[0]
    return _io(f)(audio)


img_vf = (modal.Image.debian_slim(python_version="3.10").apt_install("libsndfile1")
          .pip_install("torch==2.1.2", "torchaudio==2.1.2", "voicefixer==0.1.3", "numpy<1.24", "soundfile").env(ENV))


@app.function(image=img_vf, gpu="A10G", **common)
def voicefixer(audio: bytes) -> bytes:
    import numpy as np
    import soundfile as sf
    from voicefixer import VoiceFixer
    vf = VoiceFixer()
    def f(x):
        sf.write("/tmp/in.wav", _resample(x, SR, 44100), 44100)
        vf.restore(input="/tmp/in.wav", output="/tmp/out.wav", cuda=True, mode=0)
        y, sr = sf.read("/tmp/out.wav", dtype="float32")
        y = _resample(y if y.ndim == 1 else y.mean(1), sr, SR)
        return np.concatenate([np.zeros(108, np.float32), y])   # its output leads by ~6.75 ms (measured: -7 / -7 / -6 ms)
    return _io(f)(audio)


img_dm = (modal.Image.debian_slim(python_version="3.11")
          .pip_install("torch==2.3.1", "torchaudio==2.3.1", "demucs==4.0.1", "numpy<2").env(ENV))


@app.function(image=img_dm, gpu="A10G", **common)
def demucs(audio: bytes) -> bytes:
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    m = get_model("htdemucs").cuda().eval()
    def f(x):
        x44 = torch.as_tensor(_resample(x, SR, m.samplerate))
        wav = torch.stack([x44, x44])[None].cuda()               # stereo in
        with torch.no_grad():
            src = apply_model(m, wav, split=True, overlap=0.25)[0]
        v = src[m.sources.index("vocals")].mean(0).cpu().numpy()
        return _resample(v, m.samplerate, SR)
    return _io(f)(audio)


METHODS = {"deepfilter": deepfilter, "dns64": dns64, "metricgan": metricgan, "sepformer": sepformer, "wpe": wpe,
           "voicefixer": voicefixer, "demucs": demucs}
