"""
Test accessing 'state' and 'renderAll' in the page context.
"""
from botasaurus.browser import browser, Driver

TASK_URL = (
    "https://pulsar-upload-portal.vercel.app/"
    "?bundle=word_alignment_pass3pack_2026-08-29_SO-70802-b04_pack_041_20260911T090520Z"
    "&dataRowId=cmtwqdpe60h2b0767l1wksy18"
    "&sig=hl0xgAigySeBkvVEGmkK0a-FjkPfJxxeCoLJ9xAz-2s"
)

@browser(
    block_images=False,
    wait_for_complete_page_load=False,
)
def test_context(driver: Driver, data):
    print("Navigating...")
    driver.get(TASK_URL)
    driver.sleep(5)
    
    res = driver.run_js("""
        let stateType = 'not found';
        try { stateType = typeof state; } catch(e) { stateType = e.message; }
        
        let renderAllType = 'not found';
        try { renderAllType = typeof renderAll; } catch(e) { renderAllType = e.message; }
        
        let tokenCount = 0;
        try { tokenCount = state.tokens.length; } catch(e) {}
        
        return {
            stateType: stateType,
            renderAllType: renderAllType,
            tokenCount: tokenCount,
            clipsCount: (state && state.clips) ? state.clips.length : 0
        };
    """)
    print("Result:", res)
    return res

if __name__ == "__main__":
    test_context()
