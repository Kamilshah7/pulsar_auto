"""
Deep Labelbox Inspector using Botasaurus.
Investigates why the 'Yes' option/button is unclickable or disabled on:
https://app.labelbox.com/projects/cmpg3omk40diw07tn3fnrbghx/data-rows/cmtwqdpe60h2b0767l1wksy18
"""
import os
import json
import time
from botasaurus.browser import browser, Driver

LABELBOX_URL = "https://app.labelbox.com/projects/cmpg3omk40diw07tn3fnrbghx/data-rows/cmtwqdpe60h2b0767l1wksy18"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

@browser(
    profile="labelbox",
    block_images=False,
    wait_for_complete_page_load=False,
    close_on_crash=True,
)
def run_inspection(driver: Driver, data):
    print("\n" + "="*70)
    print("  LABELBOX INTERACTIVE DEEP INSPECTION TOOL")
    print("="*70)
    print(f"\n[1] Opening Labelbox URL in Chrome:\n    {LABELBOX_URL}\n")
    
    driver.get(LABELBOX_URL)
    
    print("-" * 70)
    print("  ACTION REQUIRED IN THE BROWSER:")
    print("  1. Log in to Labelbox (Google, Email, or Alignerr SSO).")
    print("  2. Ensure the data row page and classification questions are visible.")
    print("  3. Come back to THIS console and press ENTER to run the deep inspection.")
    print("-" * 70 + "\n")
    
    # Wait for the user to confirm they are logged in and looking at the page
    driver.prompt("Press ENTER once you are logged in and the page/question is loaded...")
    
    # If login redirected to overview or home, automatically redirect to the data row
    try:
        curr = driver.current_url
        if "data-rows" not in curr:
            print(f"\n[*] Current page is {curr}. Navigating directly to data row: {LABELBOX_URL}...")
            driver.get(LABELBOX_URL)
            print("    Waiting 5 seconds for editor to render...")
            time.sleep(5)
    except Exception as e:
        pass

    print("\n[2] Capturing page state...")
    time.sleep(2)
    
    # Save full screenshot
    screenshot_path = os.path.join(OUTPUT_DIR, "labelbox_page.png")
    try:
        driver.save_screenshot(screenshot_path)
        print(f"    [+] Saved screenshot to: {screenshot_path}")
    except Exception as e:
        print(f"    [-] Screenshot error: {e}")

    # Save complete HTML dump
    html_path = os.path.join(OUTPUT_DIR, "labelbox_page.html")
    try:
        html_content = driver.run_js("return document.documentElement.outerHTML")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content or "")
        print(f"    [+] Saved raw HTML dump to: {html_path} ({len(html_content or '')} bytes)")
    except Exception as e:
        print(f"    [-] HTML dump error: {e}")

    print("\n[3] Running Comprehensive DOM, Iframe, CSS & Event Probing...")

    inspection_js = """
    return (() => {
        try {
            const report = {
                currentUrl: window.location.href,
                pageTitle: document.title,
                timestamp: new Date().toISOString(),
                workflowMode: [],
                allQuestions: [],
                yesCandidates: [],
                disabledElementsNearYes: [],
                iframes: [],
                overlaysAndModals: [],
                alertsAndToasts: [],
                clickProbeResults: []
            };

            // --- 1. Detect Read-Only / Review Mode / Workflow Status ---
            const textContent = document.body ? document.body.innerText.toLowerCase() : '';
            const statusKeywords = [
                'read-only', 'view only', 'submitted', 'in review', 'done', 
                'approved', 'rejected', 'locked', 'read only', 'not editable',
                'assigned to', 'completed', 'benchmark'
            ];
            
            statusKeywords.forEach(kw => {
                if (textContent.includes(kw)) {
                    // Find specific tags containing keyword
                    const matches = Array.from(document.querySelectorAll('span, div, p, h1, h2, h3, badge, a')).filter(e => {
                        return e.children.length === 0 && e.textContent && e.textContent.toLowerCase().includes(kw);
                    });
                    matches.slice(0, 4).forEach(m => {
                        report.workflowMode.push({
                            keyword: kw,
                            text: m.textContent.trim(),
                            tag: m.tagName,
                            className: String(m.className || '').substring(0, 60)
                        });
                    });
                }
            });

            // --- 2. Check for Overlays, Modals, Backdrops ---
            const overlays = document.querySelectorAll('[class*="backdrop" i], [class*="overlay" i], [class*="modal" i], [class*="dialog" i], [role="dialog"]');
            overlays.forEach(ov => {
                const rect = ov.getBoundingClientRect();
                const style = window.getComputedStyle(ov);
                if (rect.width > 50 && rect.height > 50 && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                    report.overlaysAndModals.push({
                        tag: ov.tagName,
                        className: String(ov.className || '').substring(0, 80),
                        rect: { top: Math.round(rect.top), left: Math.round(rect.left), width: Math.round(rect.width), height: Math.round(rect.height) },
                        zIndex: style.zIndex,
                        pointerEvents: style.pointerEvents
                    });
                }
            });

            // --- 3. Check for Alerts, Warnings, Tooltips ---
            const alerts = document.querySelectorAll('[role="alert"], [role="tooltip"], .tooltip, [class*="banner" i], [class*="alert" i], [class*="warning" i]');
            alerts.forEach(a => {
                const txt = a.innerText ? a.innerText.trim() : '';
                if (txt && txt.length < 300) {
                    report.alertsAndToasts.push({
                        tag: a.tagName,
                        text: txt,
                        className: String(a.className || '').substring(0, 60)
                    });
                }
            });

            // --- 4. Scan All Iframes ---
            const iframes = document.querySelectorAll('iframe');
            iframes.forEach((ifr, idx) => {
                let accessible = false;
                let ifrTitle = '';
                let ifrYesCount = 0;
                try {
                    if (ifr.contentDocument) {
                        accessible = true;
                        ifrTitle = ifr.contentDocument.title;
                        ifrYesCount = ifr.contentDocument.querySelectorAll('*').length;
                    }
                } catch (e) {
                    accessible = false;
                }
                report.iframes.push({
                    index: idx,
                    src: ifr.src || ifr.getAttribute('src') || '',
                    id: ifr.id,
                    name: ifr.name,
                    accessible,
                    ifrTitle
                });
            });

            // Helper to inspect an element in detail
            function analyzeElement(el, matchReason) {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();

                // Ancestor inspection
                const ancestorChain = [];
                let curr = el.parentElement;
                let disabledAncestor = null;

                while (curr && curr !== document.body && curr !== document.documentElement) {
                    const cStyle = window.getComputedStyle(curr);
                    const isDis = curr.disabled ||
                                  curr.getAttribute('aria-disabled') === 'true' ||
                                  cStyle.pointerEvents === 'none' ||
                                  String(curr.className).toLowerCase().includes('disabled') ||
                                  String(curr.className).toLowerCase().includes('readonly') ||
                                  curr.getAttribute('readonly') !== null;

                    if (isDis && !disabledAncestor) {
                        disabledAncestor = {
                            tag: curr.tagName,
                            id: curr.id,
                            className: String(curr.className || '').substring(0, 80),
                            disabledAttr: curr.disabled,
                            ariaDisabled: curr.getAttribute('aria-disabled'),
                            pointerEvents: cStyle.pointerEvents,
                            opacity: cStyle.opacity
                        };
                    }

                    ancestorChain.push({
                        tag: curr.tagName,
                        className: String(curr.className || '').substring(0, 50),
                        pointerEvents: cStyle.pointerEvents
                    });
                    curr = curr.parentElement;
                }

                // Element From Point (click collision test)
                let interceptedBy = null;
                if (rect.width > 0 && rect.height > 0) {
                    const cx = Math.min(window.innerWidth - 5, Math.max(5, rect.left + rect.width / 2));
                    const cy = Math.min(window.innerHeight - 5, Math.max(5, rect.top + rect.height / 2));
                    const hit = document.elementFromPoint(cx, cy);
                    if (hit && hit !== el && !el.contains(hit)) {
                        interceptedBy = {
                            tag: hit.tagName,
                            id: hit.id,
                            className: String(hit.className || '').substring(0, 80),
                            pointerEvents: window.getComputedStyle(hit).pointerEvents,
                            rect: hit.getBoundingClientRect()
                        };
                    }
                }

                // Question container context
                let questionContext = '';
                const qParent = el.closest('fieldset, form, [role="radiogroup"], [class*="question" i], [class*="classification" i], [class*="card" i], [data-testid*="question" i], [class*="step" i]');
                if (qParent) {
                    questionContext = qParent.innerText ? qParent.innerText.replace(/\\s+/g, ' ').substring(0, 350) : '';
                } else if (el.parentElement && el.parentElement.parentElement) {
                    questionContext = el.parentElement.parentElement.innerText ? el.parentElement.parentElement.innerText.replace(/\\s+/g, ' ').substring(0, 350) : '';
                }

                return {
                    matchReason,
                    tag: el.tagName,
                    id: el.id,
                    className: String(el.className || ''),
                    text: (el.textContent || '').trim(),
                    attributes: {
                        disabled: el.disabled || false,
                        ariaDisabled: el.getAttribute('aria-disabled'),
                        readonly: el.getAttribute('readonly'),
                        tabindex: el.getAttribute('tabindex'),
                        type: el.getAttribute('type'),
                        role: el.getAttribute('role'),
                        checked: el.checked || false,
                        value: el.value || ''
                    },
                    computedStyle: {
                        pointerEvents: style.pointerEvents,
                        cursor: style.cursor,
                        opacity: style.opacity,
                        display: style.display,
                        visibility: style.visibility,
                        userSelect: style.userSelect
                    },
                    rect: {
                        top: Math.round(rect.top),
                        left: Math.round(rect.left),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    },
                    disabledAncestor,
                    interceptedBy,
                    questionContext: questionContext.trim()
                };
            }

            // --- 5. Find All 'Yes' Candidates in DOM ---
            const allElements = Array.from(document.querySelectorAll('*'));
            allElements.forEach(el => {
                const text = (el.textContent || '').trim().toLowerCase();
                const val = typeof el.value === 'string' ? el.value.toLowerCase() : '';
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                const testId = (el.getAttribute('data-testid') || '').toLowerCase();

                let isMatch = false;
                let reason = '';

                if (el.children.length === 0 && (text === 'yes' || text === 'yes.' || text === 'yes:')) {
                    isMatch = true;
                    reason = 'exact_leaf_text';
                } else if (val === 'yes') {
                    isMatch = true;
                    reason = 'input_value_yes';
                } else if (aria.includes('yes')) {
                    isMatch = true;
                    reason = 'aria_label_yes';
                } else if (testId.includes('yes')) {
                    isMatch = true;
                    reason = 'data_testid_yes';
                }

                if (isMatch) {
                    report.yesCandidates.push(analyzeElement(el, reason));
                }
            });

            // --- 6. Find Classification Questions & Radio Groups ---
            const qElements = document.querySelectorAll('fieldset, [role="radiogroup"], [class*="classification" i], [class*="question" i], [data-testid*="classification" i]');
            qElements.forEach((q, idx) => {
                const qText = q.innerText ? q.innerText.replace(/\\s+/g, ' ').substring(0, 200) : '';
                const inputs = Array.from(q.querySelectorAll('input, button')).map(i => ({
                    tag: i.tagName,
                    type: i.type,
                    value: i.value,
                    text: i.innerText || '',
                    disabled: i.disabled || false,
                    ariaDisabled: i.getAttribute('aria-disabled')
                }));
                if (qText && inputs.length > 0) {
                    report.allQuestions.push({
                        index: idx,
                        text: qText,
                        inputs
                    });
                }
            });

            // --- 7. Interactive Simulated Click Probe on first candidate ---
            if (report.yesCandidates.length > 0) {
                const candidate = report.yesCandidates[0];
                // Try selecting the element
                let targetEl = null;
                allElements.forEach(el => {
                    if (el.tagName === candidate.tag && (el.textContent || '').trim() === candidate.text) {
                        targetEl = el;
                    }
                });

                if (targetEl) {
                    const probeResult = {
                        targetTag: targetEl.tagName,
                        targetClass: targetEl.className,
                        clickWorked: false,
                        error: null
                    };
                    try {
                        // Dispatch mouse events
                        targetEl.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
                        targetEl.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
                        targetEl.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                        if (typeof targetEl.click === 'function') targetEl.click();
                        probeResult.clickWorked = true;
                    } catch (err) {
                        probeResult.error = err.toString();
                    }
                    report.clickProbeResults.push(probeResult);
                }
            }

            return report;
        } catch (e) {
            return {
                fatalError: e.toString(),
                stack: e.stack
            };
        }
    })();
    """

    while True:
        report = driver.run_js(inspection_js)
        
        # Save JSON report
        report_file = os.path.join(OUTPUT_DIR, "labelbox_inspection.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[4] Saved full inspection analysis to: {report_file}\n")

        # Save screenshot
        screenshot_path = os.path.join(OUTPUT_DIR, "labelbox_page.png")
        try:
            driver.save_screenshot(screenshot_path)
            print(f"    [+] Updated screenshot: {screenshot_path}")
        except Exception as e:
            pass

        # Save raw HTML dump
        html_path = os.path.join(OUTPUT_DIR, "labelbox_page.html")
        try:
            html_content = driver.run_js("return document.documentElement.outerHTML")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content or "")
        except Exception as e:
            pass

        # Print clean terminal report
        print("=" * 70)
        print("  INSPECTION RESULTS & ROOT CAUSE ANALYSIS")
        print("=" * 70)

        if not report:
            print("[-] Error: Inspection script returned empty result.")
        elif report.get("fatalError"):
            print(f"[-] JavaScript execution error: {report['fatalError']}")
        else:
            print(f"Page Title:  {report.get('pageTitle')}")
            print(f"Current URL: {report.get('currentUrl')}")
            
            # 1. Workflow / Read-only status
            if report.get("workflowMode"):
                print("\n[!] WORKFLOW STATUS INDICATORS DETECTED:")
                for wm in report["workflowMode"]:
                    print(f"    - [{wm['keyword'].upper()}]: \"{wm['text']}\" in <{wm['tag']}>")
            else:
                print("\n[+] No obvious 'Read-Only' or 'Submitted' lock text found.")

            # 2. Alerts or banners
            if report.get("alertsAndToasts"):
                print("\n[!] ALERTS / WARNINGS ON PAGE:")
                for a in report["alertsAndToasts"]:
                    print(f"    - \"{a['text']}\"")

            # 3. 'Yes' Candidates analysis
            candidates = report.get("yesCandidates", [])
            print(f"\n[+] Detected {len(candidates)} element(s) matching 'Yes':")
            for idx, c in enumerate(candidates, 1):
                print(f"\n--- Candidate #{idx}: <{c['tag']}> [{c['matchReason']}] ---")
                print(f"    Text:             \"{c['text']}\"")
                print(f"    Class:            {c['className'][:70]}")
                print(f"    Disabled:         {c['attributes']['disabled']}")
                print(f"    aria-disabled:    {c['attributes']['ariaDisabled']}")
                print(f"    pointer-events:   {c['computedStyle']['pointerEvents']}")
                print(f"    cursor:           {c['computedStyle']['cursor']}")
                print(f"    opacity:          {c['computedStyle']['opacity']}")
                print(f"    Bounding Box:     {c['rect']['width']}x{c['rect']['height']}px at ({c['rect']['left']}, {c['rect']['top']})")

                # Check for blocking reasons
                blockers = []
                if c['attributes']['disabled']:
                    blockers.append("Attribute 'disabled' is true")
                if c['attributes']['ariaDisabled'] == 'true':
                    blockers.append("Attribute 'aria-disabled' is true")
                if c['computedStyle']['pointerEvents'] == 'none':
                    blockers.append("CSS 'pointer-events: none' is blocking all clicks")
                if c['computedStyle']['cursor'] == 'not-allowed':
                    blockers.append("CSS cursor is 'not-allowed'")
                if c['rect']['width'] == 0 or c['rect']['height'] == 0:
                    blockers.append("Element has 0 width or 0 height (hidden/collapsed)")
                if c['disabledAncestor']:
                    da = c['disabledAncestor']
                    blockers.append(f"Parent <{da['tag']} class='{da['className'][:40]}'> is disabled (disabled={da['disabledAttr']}, aria-disabled={da['ariaDisabled']}, pointer-events={da['pointerEvents']})")
                if c['interceptedBy']:
                    ib = c['interceptedBy']
                    blockers.append(f"Click is physically INTERCEPTED by overlay <{ib['tag']} class='{ib['className'][:40]}'> above it (pointer-events={ib['pointerEvents']})")

                if blockers:
                    print("\n    >>> IDENTIFIED BLOCKERS WHY YOU CANNOT SELECT YES:")
                    for b in blockers:
                        print(f"        * {b}")
                else:
                    print("\n    >>> Element styles appear active. Check if an active annotation/timeline selection is required.")

                if c['questionContext']:
                    print(f"\n    Surrounding Question Context:")
                    print(f"        \"{c['questionContext'][:180]}...\"")

            # 4. Iframes
            if report.get("iframes"):
                print(f"\n[+] Iframes detected ({len(report['iframes'])}):")
                for ifr in report['iframes']:
                    print(f"    - src: {ifr['src'][:70]} (accessible: {ifr['accessible']})")

            # 5. All questions list
            if report.get("allQuestions"):
                print(f"\n[+] Other Questions found on page ({len(report['allQuestions'])}):")
                for q in report["allQuestions"][:4]:
                    print(f"    - {q['text'][:100]}")

            if len(candidates) == 0:
                print("\n[!] Notice: 'Yes' was NOT found on the currently visible page.")
                print(f"    Current URL is: {report.get('currentUrl')}")
                if "overview" in report.get("currentUrl", ""):
                    print("    >>> You are currently on the Project Overview tab, not the Data Row editor!")
                    print(f"    >>> Navigate in Chrome to: {LABELBOX_URL}")

        print("\n" + "=" * 70)
        print("  Options: Press ENTER to re-inspect | Type 'exit' and press ENTER to close")
        print("=" * 70)
        user_choice = input(">> ").strip().lower()
        if user_choice == 'exit' or user_choice == 'q':
            break

    return report

if __name__ == "__main__":
    run_inspection()
