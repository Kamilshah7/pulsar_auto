"""
Validate pipeline._auto_login without restarting app.py.

Opens a fresh Botasaurus Chrome (same setup as the pipeline), loads the task URL, runs the
exact _auto_login function the pipeline uses, and reports the result. Read-only: no bundle
download, no extraction, nothing written to output/. The running server is not touched.

    python test_auto_login.py "<task url>"            # closes the browser when done
    python test_auto_login.py "<task url>" --keep     # leaves it open until you press Enter
"""
import sys
import time

from botasaurus.browser import browser, Driver

from pipeline import _auto_login, _wait_for_bundle  # exactly what the pipeline runs

if len(sys.argv) < 2 or not sys.argv[1].startswith("http"):
    sys.exit('usage: python test_auto_login.py "<pulsar task url>" [--keep]')
TASK_URL = sys.argv[1]
KEEP = "--keep" in sys.argv


# output=None: Botasaurus otherwise saves the return value to output/run.json
@browser(block_images=False, wait_for_complete_page_load=False, output=None)
def run(driver: Driver, data):
    print("[1] opening task URL in a fresh browser profile...")
    driver.get(TASK_URL)
    driver.sleep(3)

    before = driver.run_js("return {gate: !!document.getElementById('pulsar-auth-input'),"
                           " token: !!sessionStorage.getItem('pulsar_auth_tok2')};")
    print(f"[2] before login: password gate on page = {before['gate']}, already signed in = {before['token']}")

    t0 = time.time()
    ok = _auto_login(driver, lambda m: print(f"    _auto_login: {m}"))
    print(f"[3] _auto_login returned {ok} after {time.time() - t0:.1f}s")

    t1 = time.time()
    loaded = ok and _wait_for_bundle(driver, lambda m: print(f"    _wait_for_bundle: {m}"))
    print(f"[3b] _wait_for_bundle returned {loaded} after {time.time() - t1:.1f}s")
    after = driver.run_js("""
        const ov = document.getElementById('pulsar-auth-overlay');
        return {token: !!sessionStorage.getItem('pulsar_auth_tok2'),
                overlay_hidden: !ov || ov.style.display === 'none' || ov.offsetParent === null,
                annotator_id_set: !!localStorage.getItem('pulsar_annotator_id'),
                clips_in_sidebar: document.querySelectorAll('.clip-item').length};""")
    print(f"[4] after login: session token = {after['token']}, gate hidden = {after['overlay_hidden']}, "
          f"email pre-set = {after['annotator_id_set']}, clips listed = {after['clips_in_sidebar']}")

    passed = ok and loaded and after["token"] and after["overlay_hidden"] and after["clips_in_sidebar"] > 0
    print("\nRESULT:", "PASS - auto sign-in and bundle-load wait work" if passed else "FAIL - see the lines above")
    if not after["annotator_id_set"]:
        print("note: PULSAR_PORTAL_EMAIL not set, so the Submit prompt would still ask for your email")
    if KEEP:
        driver.prompt("Browser left open for inspection. Press Enter here to close it.")
    return {"passed": bool(passed)}


if __name__ == "__main__":
    run()
