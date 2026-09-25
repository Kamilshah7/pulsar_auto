"""
Production denoiser on Modal (app "aligner2-denoise"): facebookresearch denoiser DNS64, a pretrained 16 kHz waveform
U-Net (no training here). aligner2/remote.py calls it for every clip of a bundle; aligner2/denoise_gate.py keeps the
denoised audio only for clips whose background noise it clearly removes (floor drop >= 15 dB, or >= 5 dB under a loud
background), so clean clips are aligned from the original audio, unchanged. Own image (its dependencies are pinned
apart from the engine's). A fresh image's first containers can take minutes to start (seen once, 2026-09-25):
aligner2/production.py gives the denoiser a time budget and otherwise aligns from the original audio.

    in: 16 kHz mono float32 bytes -> out: 16 kHz mono float32 bytes of the same length (zero delay, checked)
"""
import modal

APP_NAME = "aligner2-denoise"
app = modal.App(APP_NAME)
image = (modal.Image.debian_slim(python_version="3.10")
         .pip_install("torch==2.1.2", "torchaudio==2.1.2", "denoiser==0.1.5", "numpy<2")
         .env({"TORCH_HOME": "/cache/torch"}))
VOL = modal.Volume.from_name("aligner2-cache", create_if_missing=True)


@app.cls(image=image, gpu="A10G", volumes={"/cache": VOL}, timeout=900, scaledown_window=20, max_containers=4)
class Denoiser:
    @modal.enter()
    def load(self):
        from denoiser import pretrained
        self.model = pretrained.dns64().cuda().eval()

    @modal.method()
    def run(self, audio: bytes) -> bytes:
        import numpy as np
        import torch
        x = np.frombuffer(audio, dtype=np.float32).copy()
        with torch.no_grad():
            y = self.model(torch.as_tensor(x)[None, None].cuda())[0, 0].cpu().numpy()
        y = y[:len(x)] if len(y) >= len(x) else np.pad(y, (0, len(x) - len(y)))
        return y.astype(np.float32).tobytes()
