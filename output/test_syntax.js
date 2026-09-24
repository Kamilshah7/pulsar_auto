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