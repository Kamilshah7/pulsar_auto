from secrets_loader import get_secret
"""
Step 1: Explore the Pulsar editor page using Botasaurus.
  - Open the task URL
  - Handle password/email prompts
  - Investigate DOM structure (audio sources, segment data, etc.)
"""
from botasaurus.browser import browser, Driver

TASK_URL = (
    "https://pulsar-upload-portal.vercel.app/"
    "?bundle=word_alignment_pass3pack_2026-08-29_SO-70802-b04_pack_041_20260911T090520Z"
    "&dataRowId=cmtwqdpe60h2b0767l1wksy18"
    "&sig=hl0xgAigySeBkvVEGmkK0a-FjkPfJxxeCoLJ9xAz-2s"
)
PASSWORD = get_secret("PULSAR_PORTAL_PASSWORD", required=False)
EMAIL = "kamilkhan1704@gmail.com"


@browser(
    block_images=False,
    wait_for_complete_page_load=False,
)
def explore_editor(driver: Driver, data):
    """Open the Pulsar editor, authenticate, and dump the DOM structure."""

    print("[1] Navigating to task URL...")
    driver.get(TASK_URL)
    driver.sleep(3)

    # --- Pause so the user can see the page & help with auth if needed ---
    print("[2] Page loaded. Pausing for manual inspection...")
    print("    Check the browser - you may need to enter password/email.")
    driver.prompt("Page loaded. Enter password/email if prompted, then press Enter here.")

    # --- After auth, dump useful information ---
    print("[3] Investigating page structure...")

    # Get page title
    title = driver.run_js("return document.title")
    print(f"    Page title: {title}")

    # Check for audio elements
    audio_info = driver.run_js("""
        const audios = document.querySelectorAll('audio');
        const sources = document.querySelectorAll('audio source, source');
        const result = {
            audioCount: audios.length,
            audioSrcs: Array.from(audios).map(a => ({
                src: a.src || a.currentSrc || '',
                duration: a.duration,
                paused: a.paused,
            })),
            sourceTags: Array.from(sources).map(s => s.src),
        };
        return result;
    """)
    print(f"    Audio elements: {audio_info}")

    # Check for any global state / React data
    global_state = driver.run_js("""
        const keys = Object.keys(window).filter(k => 
            !['chrome','__coverage__','webpackJsonp'].includes(k) &&
            (typeof window[k] === 'object' || typeof window[k] === 'function') &&
            k.startsWith('_') || k.includes('state') || k.includes('clip') || 
            k.includes('audio') || k.includes('bundle') || k.includes('editor') ||
            k.includes('App') || k.includes('store') || k.includes('data')
        );
        return keys.slice(0, 50);
    """)
    print(f"    Interesting global keys: {global_state}")

    # Check for fetch/XHR requests that loaded audio
    network_info = driver.run_js("""
        // Check performance entries for audio/blob URLs
        const entries = performance.getEntriesByType('resource');
        const audioEntries = entries.filter(e => 
            e.name.includes('audio') || e.name.includes('.wav') || 
            e.name.includes('.mp3') || e.name.includes('.ogg') ||
            e.name.includes('.flac') || e.name.includes('.webm') ||
            e.name.includes('blob') || e.name.includes('storage') ||
            e.name.includes('cdn') || e.name.includes('upload') ||
            e.name.includes('bundle') || e.name.includes('zip') ||
            e.name.includes('pack')
        );
        return audioEntries.map(e => ({
            name: e.name.substring(0, 200),
            type: e.initiatorType,
            size: e.transferSize,
        }));
    """)
    print(f"    Network audio entries: {network_info}")

    # Check for clip/segment data in the DOM
    clip_data = driver.run_js("""
        // Look for clip items in the sidebar
        const clipItems = document.querySelectorAll('.clip-item');
        const clips = Array.from(clipItems).map(ci => ({
            text: ci.textContent.trim().substring(0, 100),
            classes: ci.className,
        }));
        
        // Look for token/segment elements
        const tokens = document.querySelectorAll('.token');
        const tokenData = Array.from(tokens).slice(0, 20).map(t => ({
            text: t.textContent.trim(),
            style: t.style.cssText.substring(0, 200),
            classes: t.className,
        }));
        
        return { clipCount: clips.length, clips: clips.slice(0, 5), tokenCount: tokens.length, tokens: tokenData };
    """)
    print(f"    Clip/Token data: {clip_data}")

    # Check for any JSON data stored in localStorage or sessionStorage
    storage_info = driver.run_js("""
        const ls = {};
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            const val = localStorage.getItem(key);
            ls[key] = val.substring(0, 200);
        }
        const ss = {};
        for (let i = 0; i < sessionStorage.length; i++) {
            const key = sessionStorage.key(i);
            const val = sessionStorage.getItem(key);
            ss[key] = val.substring(0, 200);
        }
        return { localStorage: ls, sessionStorage: ss };
    """)
    print(f"    Storage data: {storage_info}")

    # Try to find the internal data model
    react_data = driver.run_js("""
        // Try to find React fiber root
        const appDiv = document.getElementById('root') || document.getElementById('app') || document.querySelector('[data-reactroot]');
        if (!appDiv) return { rootFound: false };
        
        const fiberKey = Object.keys(appDiv).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
        return { 
            rootFound: true, 
            rootTag: appDiv.tagName,
            rootId: appDiv.id,
            hasFiber: !!fiberKey,
            fiberKey: fiberKey || 'none',
        };
    """)
    print(f"    React data: {react_data}")

    # Dump all script src tags
    scripts = driver.run_js("""
        return Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
    """)
    print(f"    Script sources: {scripts}")

    # Check for any inline scripts that might contain config
    inline_scripts = driver.run_js("""
        const scripts = document.querySelectorAll('script:not([src])');
        return Array.from(scripts).map(s => s.textContent.substring(0, 300));
    """)
    print(f"    Inline scripts (first 300 chars each): {inline_scripts}")

    print("\n[4] Pausing for manual inspection of the browser...")
    print("    Explore the editor, then come back here.")
    driver.prompt("Explore the editor manually. Press Enter when done.")

    return {
        "audio_info": audio_info,
        "global_state": global_state,
        "network_info": network_info,
        "clip_data": clip_data,
        "storage_info": storage_info,
        "react_data": react_data,
    }


if __name__ == "__main__":
    result = explore_editor()
    from botasaurus import bt
    bt.write_json(result, "editor_exploration")
    print("\nResults saved to output/editor_exploration.json")
