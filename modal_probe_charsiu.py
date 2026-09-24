"""One-off probe of charsiu/en_w2v2_fc_10ms (frame-classification phone aligner) on Modal."""
import modal
app = modal.App("aligner2-probe-charsiu")
image = (modal.Image.debian_slim(python_version="3.11")
         .pip_install("transformers==5.17.0", "torch", "huggingface_hub", "safetensors", "g2p_en", "nltk")
         .env({"HF_HOME": "/cache/hf", "HF_HUB_DISABLE_XET": "1"}))
VOL = modal.Volume.from_name("aligner2-cache", create_if_missing=True)


@app.function(image=image, volumes={"/cache": VOL}, timeout=900)
def probe():
    import json, os
    from huggingface_hub import hf_hub_download, list_repo_files
    out = {}
    for repo in ("charsiu/en_w2v2_fc_10ms", "charsiu/tokenizer_en_cmu"):
        files = list_repo_files(repo); out[repo] = files
        for f in files:
            if f.endswith(".json") or f.endswith(".txt"):
                p = hf_hub_download(repo, f); txt = open(p, encoding="utf-8").read()
                out[f"{repo}/{f}"] = txt[:3000]
    import torch
    for f in out["charsiu/en_w2v2_fc_10ms"]:
        if f.endswith(".bin") or f.endswith(".safetensors"):
            p = hf_hub_download("charsiu/en_w2v2_fc_10ms", f)
            sd = torch.load(p, map_location="cpu") if f.endswith(".bin") else __import__("safetensors.torch", fromlist=["x"]).load_file(p)
            out["state_dict_keys_tail"] = [f"{k} {tuple(v.shape)}" for k, v in list(sd.items())[-8:]]
            out["state_dict_keys_head"] = [f"{k} {tuple(v.shape)}" for k, v in list(sd.items())[:6]]
    VOL.commit()
    return out


@app.local_entrypoint()
def main():
    import json
    r = probe.remote()
    for k, v in r.items():
        print("=====", k); print(v if isinstance(v, str) else json.dumps(v, indent=1)[:3000])
