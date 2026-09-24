import os
import sys
import time
import datetime
import threading
import winsound
from botasaurus.browser import browser, Driver

PROJECT_URL = "https://app.labelbox.com/projects/cmpg3omk40diw07tn3fnrbghx/overview"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configuration
CHECK_INTERVAL_SEC = 0.3    # In-page scan rate (every 300ms)
AUTO_RELOAD_INTERVAL_SEC = 12 # Refresh page if queue didn't live-update
SIREN_ACTIVE = threading.Event()
STOP_REQUESTED = threading.Event()

def play_siren():
    """Loud, oscillating dual-tone air-raid siren on Windows."""
    print("\n" + "!" * 70)
    print("  🚨🚨🚨 TASK DETECTED! SIREN ACTIVATED! 🚨🚨🚨")
    print("!" * 70)
    while SIREN_ACTIVE.is_set() and not STOP_REQUESTED.is_set():
        tones = [
            (850, 200),
            (1150, 200),
            (1450, 250),
            (1150, 200),
            (850, 200),
            (650, 200)
        ]
        for freq, dur in tones:
            if not SIREN_ACTIVE.is_set() or STOP_REQUESTED.is_set():
                break
            try:
                winsound.Beep(freq, dur)
            except Exception:
                pass

JS_CHECK_AND_CLICK = """
(() => {
    // 1. Locate the Start button
    const buttons = Array.from(document.querySelectorAll('button, a[role="button"]'));
    let startBtn = null;
    for (const b of buttons) {
        const txt = (b.textContent || '').trim();
        if (/^start/i.test(txt) || txt === 'Start') {
            startBtn = b;
            break;
        }
    }

    if (!startBtn) {
        return { found: false, active: false, reason: "Button not in DOM" };
    }

    // 2. Check if disabled or Mui-disabled
    const isDisabled = startBtn.disabled ||
                       startBtn.hasAttribute('disabled') ||
                       startBtn.classList.contains('Mui-disabled') ||
                       startBtn.getAttribute('aria-disabled') === 'true';

    const style = window.getComputedStyle(startBtn);
    const isClickable = style.pointerEvents !== 'none' && style.cursor !== 'not-allowed';

    if (isDisabled) {
        return {
            found: true,
            active: false,
            text: startBtn.textContent.trim(),
            bg: style.backgroundColor,
            reason: "Disabled"
        };
    }

    // 3. Button is ACTIVE / BLUE! Click it immediately!
    try {
        startBtn.scrollIntoView({ behavior: 'instant', block: 'center' });
        startBtn.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, cancelable: true }));
        startBtn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
        startBtn.dispatchEvent(new MouseEvent('pointerup', { bubbles: true, cancelable: true }));
        startBtn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
        startBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        if (typeof startBtn.click === 'function') startBtn.click();
        
        // Handle split dropdown menu if present
        setTimeout(() => {
            const menuItems = document.querySelectorAll('[role="menuitem"], .MuiMenuItem-root');
            if (menuItems.length > 0) {
                menuItems[0].click();
            }
        }, 120);

        return {
            found: true,
            active: true,
            text: startBtn.textContent.trim(),
            bg: style.backgroundColor,
            clicked: true
        };
    } catch (err) {
        return {
            found: true,
            active: true,
            error: err.toString()
        };
    }
})();
"""

@browser(
    headless=False,
    profile="labelbox",
    block_images=False,
    close_on_crash=True
)
def run_sniper(driver: Driver, data):
    print("=" * 70)
    print("       🎯 LABELBOX 'START' BUTTON SNIPER & LOUD SIREN ALERT")
    print("=" * 70)
    print(f"[*] Target: {PROJECT_URL}")
    print(f"[*] Check Interval: {CHECK_INTERVAL_SEC}s | Auto-Reload: Every {AUTO_RELOAD_INTERVAL_SEC}s")
    print("=" * 70)

    # Initial navigation
    curr_url = driver.current_url or ""
    if PROJECT_URL not in curr_url:
        print(f"\n[1] Navigating to: {PROJECT_URL}")
        driver.google_get(PROJECT_URL, bypass_cloudflare=False)
        time.sleep(3)

    print("\n[+] Sniper active! Monitoring the 'Start' button continuously.")
    print("    If you see a sign-in screen, log in now — the sniper will wait.")
    print("    Press Ctrl+C in this console at any time to stop.\n")

    check_count = 0
    last_reload = time.time()

    try:
        while not STOP_REQUESTED.is_set():
            check_count += 1
            now_str = datetime.datetime.now().strftime("%H:%M:%S")

            # Check button state via JS
            res = None
            try:
                res = driver.run_js(JS_CHECK_AND_CLICK)
            except Exception as e:
                # Browser might be in transition or loading
                time.sleep(CHECK_INTERVAL_SEC)
                continue

            if res and isinstance(res, dict):
                if res.get("active") and res.get("clicked"):
                    # >>> TASK SNAGGED! <<<
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    shot_path = os.path.join(OUTPUT_DIR, f"task_snagged_{timestamp}.png")
                    try:
                        driver.save_screenshot(shot_path)
                    except Exception:
                        pass

                    print("\n" + "#" * 70)
                    print(f"[{now_str}] 🎯🎯🎯 SUCCESS! TASK SNAGGED & CLICKED! 🎯🎯🎯")
                    print(f"    [+] Button text: \"{res.get('text')}\"")
                    print(f"    [+] Saved screenshot to: {shot_path}")
                    print(f"    [+] Current URL: {driver.current_url}")
                    print("#" * 70 + "\n")

                    # Fire Siren in background thread
                    SIREN_ACTIVE.set()
                    siren_thread = threading.Thread(target=play_siren, daemon=True)
                    siren_thread.start()

                    # Wait for user input to stop alarm
                    try:
                        input("\n[🚨 SIREN BLARING] Press ENTER to silence siren and keep working...")
                    except Exception:
                        time.sleep(30)
                    SIREN_ACTIVE.clear()
                    print("[+] Siren silenced. You have the task!")
                    break

                elif res.get("found"):
                    sys.stdout.write(f"\r[{now_str}] Scans: {check_count} | Button: {res.get('reason', 'Waiting')} (Grey/Disabled)   ")
                    sys.stdout.flush()
                else:
                    sys.stdout.write(f"\r[{now_str}] Scans: {check_count} | Button: Loading / Not yet in DOM...              ")
                    sys.stdout.flush()

            # Auto-reload timer check
            if time.time() - last_reload > AUTO_RELOAD_INTERVAL_SEC:
                sys.stdout.write(f"\n[{now_str}] 🔄 Auto-refreshing page to poll new queue items...\n")
                sys.stdout.flush()
                try:
                    driver.run_js("window.location.reload()")
                    time.sleep(3)
                except Exception:
                    pass
                last_reload = time.time()

            time.sleep(CHECK_INTERVAL_SEC)

    except KeyboardInterrupt:
        print("\n\n[!] Monitoring stopped by user (Ctrl+C).")
    finally:
        SIREN_ACTIVE.clear()
        STOP_REQUESTED.set()

if __name__ == "__main__":
    run_sniper()
