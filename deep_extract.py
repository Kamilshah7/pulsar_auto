from secrets_loader import get_secret
"""
Step 2: Deep extraction - get full clip/token data from localStorage,
intercept the audio ZIP download, and extract audio files.
"""
from botasaurus.browser import browser, Driver
import json
import os

import sys

DEFAULT_TASK_URL = (
    "https://pulsar-upload-portal.vercel.app/"
    "?bundle=word_alignment_production_2026-08-29_SO-70802-b04_bundle_048"
    "&dataRowId=cmte54vwkhrkn073238x10iwk"
    "&sig=-vg1jesPClcCgnXgGWXbF2uHS79hut0bMTKFTFagPqc"
)
TASK_URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else DEFAULT_TASK_URL
PASSWORD = get_secret("PULSAR_PORTAL_PASSWORD", required=False)
EMAIL = "kamilkhan1704@gmail.com"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)


@browser(
    block_images=False,
    wait_for_complete_page_load=False,
)
def deep_extract(driver: Driver, data):
    """Extract all clip data and download audio files."""

    print("[1] Navigating to task URL...")
    driver.get(TASK_URL)
    driver.sleep(3)

    # Wait for user to enter password + email
    print("[1b] >>> Enter the password and email in the browser <<<")
    print("     Password: (see local_secrets.json)")
    print("     Email: kamilkhan1704@gmail.com")
    print("     Once you see the editor loaded with clips, press ENTER here.")
    driver.prompt()
    driver.sleep(3)  # Let the page finish loading after auth

    # --- 1. Get ALL localStorage keys and full clip data ---
    print("[2] Extracting localStorage data...")
    all_storage = driver.run_js("""
        const result = {};
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            result[key] = localStorage.getItem(key);
        }
        return result;
    """)

    # Save full storage dump
    with open(os.path.join(OUTPUT_DIR, "full_localstorage.json"), "w", encoding="utf-8") as f:
        json.dump(all_storage, f, indent=2)
    print(f"    Saved {len(all_storage)} localStorage keys")

    # --- 2. Extract clip token data specifically ---
    clip_keys = [k for k in all_storage if k.startswith("pulsar_align_clip_")]
    print(f"    Found {len(clip_keys)} clip data keys")

    clips_data = {}
    for key in clip_keys:
        try:
            clips_data[key] = json.loads(all_storage[key])
        except json.JSONDecodeError:
            clips_data[key] = all_storage[key]

    with open(os.path.join(OUTPUT_DIR, "clip_tokens.json"), "w", encoding="utf-8") as f:
        json.dump(clips_data, f, indent=2)

    # --- 3. Get all clip info from the DOM ---
    print("[3] Extracting clip list from DOM...")
    clip_list = driver.run_js("""
        const clipItems = document.querySelectorAll('.clip-item');
        return Array.from(clipItems).map((ci, idx) => {
            const label = ci.querySelector('.clip-item-label');
            const time = ci.querySelector('.clip-item-time');
            return {
                index: idx,
                label: label ? label.textContent.trim() : '',
                time: time ? time.textContent.trim() : '',
                classes: ci.className,
                isDone: ci.classList.contains('done'),
                isUntouched: ci.classList.contains('untouched'),
                isActive: ci.classList.contains('active'),
            };
        });
    """)
    with open(os.path.join(OUTPUT_DIR, "clip_list.json"), "w", encoding="utf-8") as f:
        json.dump(clip_list, f, indent=2)
    print(f"    Found {len(clip_list)} clips in sidebar")

    # --- 4. Get token data for the ACTIVE clip with full timing ---
    print("[4] Extracting active clip token details...")
    token_details = driver.run_js("""
        const tokens = document.querySelectorAll('.token');
        return Array.from(tokens).map(t => {
            const content = t.querySelector('.token-content');
            const text = t.querySelector('.tk-text');
            return {
                text: (text || content || t).textContent.trim(),
                style: t.style.cssText,
                left: t.style.left,
                width: t.style.width,
                classes: t.className,
                dataset: Object.assign({}, t.dataset),
            };
        });
    """)
    with open(os.path.join(OUTPUT_DIR, "active_clip_tokens.json"), "w", encoding="utf-8") as f:
        json.dump(token_details, f, indent=2)

    # --- 5. Try to get the audio data via the download API ---
    print("[5] Attempting to download audio bundle...")
    auth_token = driver.run_js("return sessionStorage.getItem('pulsar_auth_tok2')")
    print(f"    Auth token: {auth_token[:30]}..." if auth_token else "    No auth token found!")

    # Try to download the bundle ZIP using the browser's fetch
    download_result = driver.run_js("""
        return (async () => {
            const bundleName = new URLSearchParams(window.location.search).get('bundle');
            const sig = new URLSearchParams(window.location.search).get('sig');
            const url = '/api/dl/pulsar-chunk/' + bundleName + '?sig=' + sig;
            
            try {
                const resp = await fetch(url);
                const contentType = resp.headers.get('content-type');
                const contentLength = resp.headers.get('content-length');
                const contentDisp = resp.headers.get('content-disposition');
                
                if (resp.ok) {
                    const blob = await resp.blob();
                    const reader = new FileReader();
                    const base64 = await new Promise(function(resolve, reject) {
                        reader.onload = function() { resolve(reader.result); };
                        reader.onerror = reject;
                        reader.readAsDataURL(blob);
                    });
                    return {
                        ok: true,
                        status: resp.status,
                        contentType: contentType,
                        contentLength: contentLength,
                        contentDisposition: contentDisp,
                        size: blob.size,
                        base64: base64,
                    };
                } else {
                    const text = await resp.text();
                    return { ok: false, status: resp.status, body: text.substring(0, 500) };
                }
            } catch (e) {
                return { ok: false, error: e.message };
            }
        })();
    """)

    if download_result and download_result.get("ok"):
        print(f"    Bundle download success! Size: {download_result['size']} bytes, Type: {download_result['contentType']}")
        
        # Save the base64 data and decode it
        import base64 as b64
        data_url = download_result["base64"]
        # data URL format: data:application/zip;base64,XXXX
        header, encoded = data_url.split(",", 1)
        raw_bytes = b64.b64decode(encoded)
        
        zip_path = os.path.join(AUDIO_DIR, "bundle.zip")
        with open(zip_path, "wb") as f:
            f.write(raw_bytes)
        print(f"    Saved bundle to {zip_path} ({len(raw_bytes)} bytes)")

        # Clean existing audio and json files before unpacking new bundle
        for f in os.listdir(AUDIO_DIR):
            if f.endswith(('.wav', '.json')) and f != "bundle.zip":
                try:
                    os.remove(os.path.join(AUDIO_DIR, f))
                except Exception:
                    pass

        # Try to extract the ZIP
        import zipfile
        if zipfile.is_zipfile(zip_path):
            with zipfile.ZipFile(zip_path, 'r') as zf:
                names = zf.namelist()
                print(f"    ZIP contains {len(names)} files: {names[:10]}")
                zf.extractall(AUDIO_DIR)
                print(f"    Extracted all files to {AUDIO_DIR}")
        else:
            print("    Downloaded file is not a valid ZIP. Checking format...")
            with open(zip_path, "rb") as f:
                magic = f.read(4)
            print(f"    File magic bytes: {magic.hex()}")
    else:
        print(f"    Bundle download failed: {download_result}")

    # --- 6. Get global JS functions/state available ---
    print("[6] Checking available global functions...")
    global_funcs = driver.run_js("""
        const interesting = [];
        for (const key of Object.keys(window)) {
            if (typeof window[key] === 'function' && 
                !key.startsWith('on') && !key.startsWith('webkit') &&
                key.length > 3) {
                interesting.push(key);
            }
        }
        return interesting;
    """)
    print(f"    Global functions: {global_funcs}")
    
    # --- 7. Check if there's an internal state/model we can access ---
    print("[7] Looking for internal clip model...")
    internal_state = driver.run_js("""
        // Try to access clipEditSignal which we saw in the global state
        let clipEdit = null;
        try { clipEdit = typeof clipEditSignal; } catch(e) {}
        
        // Try to find any global clip/token arrays
        let result = { clipEditSignalType: clipEdit };
        
        // Check for common SPA state patterns
        for (const key of ['_clips', '_tokens', '_model', '_state', '_app', '_editor', 
                           'clips', 'tokens', 'model', 'state', 'app', 'editor',
                           'bundleData', 'audioCtx', 'audioContext']) {
            try {
                if (window[key] !== undefined) {
                    result[key] = typeof window[key];
                }
            } catch(e) {}
        }
        return result;
    """)
    print(f"    Internal state: {internal_state}")

    print("\n[DONE] All data extracted. Check the output/ and audio/ directories.")
    return {
        "clip_count": len(clip_list),
        "clip_keys_count": len(clip_keys),
        "download_result_ok": download_result.get("ok") if download_result else False,
        "global_funcs": global_funcs,
        "internal_state": internal_state,
    }


if __name__ == "__main__":
    result = deep_extract()
    from botasaurus import bt
    bt.write_json(result, "deep_extract_summary")
    print("\nSummary saved to output/deep_extract_summary.json")
