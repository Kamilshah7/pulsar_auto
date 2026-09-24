import os
import json
import time
from botasaurus.browser import browser, Driver

TASK_URL = "https://pulsar-upload-portal.vercel.app/?bundle=word_alignment_rework_2026-08-19_SO-70802-b02_bundle_032&dataRowId=cmtxpah7y2z1m0767bjogungk&sig=jfyuECMxVPnYzoxGwwh71atuQmjyHbkul-zzJjAb2Rk"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")

@browser(block_images=False, wait_for_complete_page_load=False)
def extract_ground_truth(driver: Driver, data):
    print("[1] Navigating to Ground Truth URL...")
    driver.get(TASK_URL)
    driver.sleep(3)

    print("[2] >>> Enter the password (see local_secrets.json) and email (kamilkhan1704@gmail.com) in the browser <<<")
    print("    Once the editor is fully loaded and you see the perfect clips, press ENTER here.")
    driver.prompt()
    driver.sleep(2)

    print("[3] Extracting state.tokens (Perfected Ground Truth) via localStorage...")
    
    # 1. Get ALL localStorage keys and full clip data
    all_storage = driver.run_js("""
        const result = {};
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            result[key] = localStorage.getItem(key);
        }
        return result;
    """)

    clip_keys = [k for k in all_storage if k.startswith("pulsar_align_clip_")]
    
    all_tokens = []
    
    for key in clip_keys:
        try:
            val = json.loads(all_storage[key])
            if 'tokens' in val and isinstance(val['tokens'], list):
                all_tokens.extend(val['tokens'])
        except Exception as e:
            print("Error parsing", key, e)
            pass

    # Sort tokens globally by start time
    all_tokens.sort(key=lambda x: x.get("start", 0))

    out_path = os.path.join(OUTPUT_DIR, "baseline_ground_truth.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_tokens, f, indent=2)
    print(f"    Saved {len(all_tokens)} perfected tokens to {out_path}")

    print("[4] Attempting to download audio bundle...")
    download_result = driver.run_js("""
        return (async () => {
            const bundleName = new URLSearchParams(window.location.search).get('bundle');
            const sig = new URLSearchParams(window.location.search).get('sig');
            const url = '/api/dl/pulsar-chunk/' + bundleName + '?sig=' + sig;
            try {
                const resp = await fetch(url);
                if (resp.ok) {
                    const blob = await resp.blob();
                    const reader = new FileReader();
                    const base64 = await new Promise((resolve, reject) => {
                        reader.onload = () => resolve(reader.result);
                        reader.onerror = reject;
                        reader.readAsDataURL(blob);
                    });
                    return { ok: true, base64: base64, size: blob.size };
                } else {
                    return { ok: false, status: resp.status };
                }
            } catch (e) {
                return { ok: false, error: e.message };
            }
        })();
    """)

    if download_result and download_result.get("ok"):
        print(f"    Bundle download success! Size: {download_result['size']} bytes")
        import base64 as b64
        header, encoded = download_result["base64"].split(",", 1)
        raw_bytes = b64.b64decode(encoded)
        zip_path = os.path.join(AUDIO_DIR, "bundle.zip")
        with open(zip_path, "wb") as f:
            f.write(raw_bytes)
        
        # Clean existing audio
        for f in os.listdir(AUDIO_DIR):
            if f.endswith(('.wav', '.json')) and f != "bundle.zip":
                try: os.remove(os.path.join(AUDIO_DIR, f))
                except: pass
        
        import zipfile
        if zipfile.is_zipfile(zip_path):
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(AUDIO_DIR)
                manifest = [f for f in zf.namelist() if f.endswith('.wav')]
                with open(os.path.join(OUTPUT_DIR, "bundle_manifest.json"), "w", encoding="utf-8") as mf:
                    json.dump(manifest, mf, indent=2)
                print(f"    Extracted ZIP and saved manifest with {len(manifest)} WAVs.")
    else:
        print("    Failed to download bundle:", download_result)

    print("[DONE] Baseline extraction complete.")
    return True

if __name__ == "__main__":
    extract_ground_truth()
