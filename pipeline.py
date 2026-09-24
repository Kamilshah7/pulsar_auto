"""
Core pipeline manager for Pulsar End-to-End Automation.
Handles:
  1. Deep extract with Botasaurus
  2. Audio transcription with Groq Whisper-large-v3
  3. Pre-label comparison and LLM prompt generation
  4. LLM output parsing, timestamp offset calculation, and injector generation
"""
import os
import sys
import json
import wave
import re
import threading
from groq import Groq

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Loaded from the environment or local_secrets.json -- never hardcode (see secrets_loader.py).
from secrets_loader import get_secret
GROQ_API_KEY = get_secret("GROQ_API_KEY", required=False)

ARCHIVE_DIR = os.path.join(BASE_DIR, "bench", "bundle_archive")
ARCHIVED_OUTPUTS = [
    "ordered_clips.json", "current_bundle.txt", "injected_tokens.json", "llm_corrected_tokens.json",
    "groq_transcriptions.json", "wav2vec2_acoustic_transcriptions.json",
    "microslice_repaired_transcriptions.json", "pulsar_llm_prompt.txt", "pulsar_llm_input.txt",
    "clip_list.json", "clip_tokens.json", "bundle_manifest.json", "inject_console.js",
]


# Written by the LLM/inject steps, which are NOT cleared on a new bundle -- until the user runs
# them for the new bundle these still hold the PREVIOUS bundle's tokens.
BUNDLE_LATE_OUTPUTS = ("llm_corrected_tokens.json", "injected_tokens.json", "inject_console.js")


def archive_bundle(bundle_name, log=print):
    """Copy the current bundle's WAVs + sidecars (audio/) and pipeline intermediates (output/)
    to bench/bundle_archive/<bundle>/{audio,pipeline}/. Same layout bench/snapshot_gold.py reads.

    Always refreshes (the archive must reflect the bundle as it LEAVES; skipping an existing
    folder once preserved a stale copy). The LLM/inject outputs are only archived if they were
    written after this bundle started (newer than ordered_clips.json) and, for the injection,
    if its token ids reference this bundle's WAVs -- otherwise they belong to the previous
    bundle and are left out rather than mislabelled.
    Never raises: a failed archive must not stop the next bundle from running."""
    import shutil
    try:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", bundle_name)[:120]
        dest = os.path.join(ARCHIVE_DIR, safe)
        os.makedirs(os.path.join(dest, "audio"), exist_ok=True)
        os.makedirs(os.path.join(dest, "pipeline"), exist_ok=True)
        wavs = set()
        n_audio = 0
        for f in os.listdir(AUDIO_DIR):
            if f.endswith((".wav", ".json")):
                shutil.copy2(os.path.join(AUDIO_DIR, f), os.path.join(dest, "audio", f)); n_audio += 1
                if f.endswith(".wav"):
                    wavs.add(f)
        started = os.path.join(OUTPUT_DIR, "ordered_clips.json")
        t_start = os.path.getmtime(started) if os.path.exists(started) else 0
        n_out, skipped = 0, []
        for f in ARCHIVED_OUTPUTS:
            src = os.path.join(OUTPUT_DIR, f)
            dst = os.path.join(dest, "pipeline", f)
            if not os.path.exists(src):
                continue
            if f in BUNDLE_LATE_OUTPUTS:
                stale = os.path.getmtime(src) < t_start
                if f == "injected_tokens.json" and not stale:
                    ids = {m.group(1) for t in json.load(open(src, encoding="utf-8"))
                           for m in [re.match(r"t_(.+\.wav)_\d+$", str(t.get("id")))] if m}
                    stale = bool(ids) and not (ids & wavs)
                if stale:
                    skipped.append(f)
                    if os.path.exists(dst):
                        os.remove(dst)
                    continue
            shutil.copy2(src, dst); n_out += 1
        log(f"Archived bundle {bundle_name}: {n_audio} audio files, {n_out} pipeline files -> {dest}"
            + (f" (left out {', '.join(skipped)}: from the previous bundle -- LLM/inject never ran for this one)" if skipped else ""))
        return dest
    except Exception as e:
        log(f"WARNING: could not archive bundle {bundle_name}: {e}")
        return None


def _auto_login(driver, log=print, timeout_s=20):
    """Fill the portal's password gate from local_secrets.json and pre-set the annotator email.

    DOM (read from the live page 2026-09-23): form#pulsar-auth-form > input#pulsar-auth-input
    (type=password) + button#pulsar-auth-btn; #pulsar-auth-err shows on a wrong password; on
    success the page stores a signed token in sessionStorage['pulsar_auth_tok2'].
    The email is NOT a form field: the page asks via window.prompt() only when you click Submit
    and keeps the answer in localStorage['pulsar_annotator_id'] -- pre-setting it skips the prompt.
    Returns True when signed in; False means fall back to the manual "I have authenticated" flow."""
    password = get_secret("PULSAR_PORTAL_PASSWORD", required=False)
    email = get_secret("PULSAR_PORTAL_EMAIL", required=False)
    if email:
        try:
            driver.run_js(f"localStorage.setItem('pulsar_annotator_id', {json.dumps(email)}); return true;")
        except Exception as e:
            log(f"Could not pre-set annotator email: {e}")
    if not password:
        log("PULSAR_PORTAL_PASSWORD not configured; sign in manually.")
        return False
    try:
        if driver.run_js("return !!sessionStorage.getItem('pulsar_auth_tok2');"):
            return True  # already signed in this session
        present = driver.run_js(f"""
            const inp = document.getElementById('pulsar-auth-input');
            const form = document.getElementById('pulsar-auth-form');
            if (!inp || !form) return false;
            // native setter + input event so any framework listener sees the value
            Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(inp, {json.dumps(password)});
            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
            if (form.requestSubmit) form.requestSubmit(); else document.getElementById('pulsar-auth-btn').click();
            return true;""")
        if not present:
            log("Password gate not found on the page; sign in manually.")
            return False
        for _ in range(timeout_s * 2):
            driver.sleep(0.5)
            state = driver.run_js("""
                const err = document.getElementById('pulsar-auth-err');
                return {ok: !!sessionStorage.getItem('pulsar_auth_tok2'),
                        err: err && !err.classList.contains('portal-hidden') ? (err.textContent || '').trim() : ''};""")
            if state and state.get("ok"):
                return True
            if state and state.get("err"):
                log(f"Portal rejected the password ({state['err']}); sign in manually.")
                return False
        log("Sign-in did not complete in time; sign in manually.")
    except Exception as e:
        log(f"Auto sign-in failed ({e}); sign in manually.")
    return False


def _wait_for_bundle(driver, log=print, timeout_s=180, stable_polls=3):
    """Wait until the editor's clip list is fully populated: at least one .clip-item, every row's
    .clip-item-time filled in with its duration (_match_and_order_clips parses "0:00 · 28.19s"),
    and the row count unchanged for `stable_polls` consecutive 1s polls so a half-built list is
    never captured. Returns False on timeout -> caller falls back to the manual confirmation."""
    last, same = -1, 0
    for sec in range(timeout_s):
        try:
            s = driver.run_js("""
                const rows = [...document.querySelectorAll('.clip-item')];
                const timed = rows.filter(r => ((r.querySelector('.clip-item-time') || {}).textContent || '').includes('·'));
                const keys = Object.keys(localStorage).filter(k => k.startsWith('pulsar_align_clip_')).length;
                return {rows: rows.length, timed: timed.length, keys: keys};""")
        except Exception:
            s = None
        if s and s["rows"] > 0 and s["timed"] == s["rows"] and s["keys"] > 0:
            same = same + 1 if s["rows"] == last else 1
            last = s["rows"]
            if same >= stable_polls:
                log(f"Bundle loaded: {s['rows']} clips ({sec + 1}s after sign-in).")
                return True
        else:
            same, last = 0, (s["rows"] if s else -1)
        driver.sleep(1)
    log(f"Bundle did not finish loading within {timeout_s}s; confirm manually once the editor shows the clips.")
    return False


class PulsarPipeline:
    def __init__(self):
        self.state = {
            "status": "idle",       # idle, extracting, waiting_auth, transcribing, ready_for_llm, generating_injector, complete, error
            "message": "Ready to start.",
            "task_url": "",
            "clips": [],
            "current_step": 1,
            "total_steps": 4,
            "logs": [],
            "error": None,
            "llm_prompt": "",
            "llm_input": "",
            "combined_llm_payload": "",
            "inject_script": "",
            "tokens_count": 0,
            # NOTE: this used to also contain "median_boundary_ms": 3.2, "mae_boundary_ms":
            # 20.6, "sub_50ms_pct": 87.2 -- static numbers presented in the GUI as if they
            # were real, freshly-measured accuracy for whatever clips were just processed.
            # They were never recomputed from actual output; every run reported the exact
            # same fake numbers regardless of the audio. Removed rather than fixed with a
            # "better" hardcoded number: boundary accuracy is fundamentally unmeasurable
            # without ground-truth timestamps, which production clips don't have. Honest
            # behavior is to not display a boundary-accuracy stat at all in production; see
            # bench/run_align_benchmark.py for real, gold-label-based measurement.
            "acoustic_stats": {
                "total_tokens": 0,
                "token_recovery_pct": 0.0,
                "ctc_framerate": "50 fps CTC",
                "contiguous_snaps": 0,
                "overlap_violations": 0
            }
        }
        self.auth_event = threading.Event()
        self.lock = threading.Lock()
        self._aligner = None
        self._load_existing_state()

    def _compute_recovery_pct(self, n_final_tokens):
        """Fraction of the pre-label token count (from ordered_clips.json, gathered
        per-clip directly from the server's own pre-label JSON in _match_and_order_clips)
        that the final aligned token count reaches. Genuinely computable in production
        (no ground truth needed) and clip-count-agnostic, unlike the hardcoded "/458"
        this replaced, which assumed a fixed expected total left over from a past project
        and silently produced a nonsense percentage for any other clip count."""
        expected = sum(c.get("token_count", 0) for c in self.state.get("clips", []))
        if expected <= 0:
            return 0.0
        return round(min(100.0, n_final_tokens / expected * 100), 1)

    def _get_aligner(self):
        """Lazily initialize and cache ForcedAligner to avoid 60-90s model reload overhead."""
        if self._aligner is None:
            from forced_aligner import ForcedAligner
            self._aligner = ForcedAligner()
        return self._aligner

    def _load_existing_state(self):
        """Restore previous state if files exist."""
        p_path = os.path.join(OUTPUT_DIR, "pulsar_llm_prompt.txt")
        i_path = os.path.join(OUTPUT_DIR, "pulsar_llm_input.txt")
        c_path = os.path.join(OUTPUT_DIR, "ordered_clips.json")
        inj_path = os.path.join(OUTPUT_DIR, "inject_console.js")
        tok_path = os.path.join(OUTPUT_DIR, "injected_tokens.json")

        if os.path.exists(c_path):
            try:
                self.state["clips"] = json.load(open(c_path, encoding="utf-8"))
            except Exception:
                pass

        if os.path.exists(p_path) and os.path.exists(i_path):
            try:
                p_text = open(p_path, encoding="utf-8").read()
                i_text = open(i_path, encoding="utf-8").read()
                self.state["llm_prompt"] = p_text
                self.state["llm_input"] = i_text
                self.state["combined_llm_payload"] = f"{p_text}\n\n{'='*60}\n\n{i_text}"
                self.state["status"] = "ready_for_llm"
                self.state["current_step"] = 3
                self.state["logs"].append(f"Loaded existing session with {len(self.state['clips'])} clips. Ready to copy prompt or paste LLM response.")
            except Exception:
                pass

        # The LLM/inject outputs are not cleared when a new bundle starts, so they may belong to
        # the PREVIOUS bundle. Restoring them flipped the GUI to "complete, ready to inject" with
        # the wrong bundle's script -- injecting that would replace this bundle's editor tokens.
        # Only restore an injection whose token ids reference this bundle's clips.
        injection_current = False
        if os.path.exists(tok_path):
            try:
                ids = {m.group(1) for t in json.load(open(tok_path, encoding="utf-8"))
                       for m in [re.match(r"t_(.+\.wav)_\d+$", str(t.get("id")))] if m}
                current = {c.get("filename") for c in self.state.get("clips", [])}
                injection_current = bool(ids & current) if (ids and current) else not current
                if not injection_current:
                    self.state["logs"].append("Ignoring injected tokens left over from a previous bundle.")
            except Exception:
                injection_current = False

        if os.path.exists(tok_path) and injection_current:
            try:
                toks = json.load(open(tok_path, encoding="utf-8"))
                self.state["tokens_count"] = len(toks)
                snap_count = 0
                for i in range(len(toks) - 1):
                    if toks[i].get("clipIndex") == toks[i+1].get("clipIndex"):
                        gap = toks[i+1]["start"] - toks[i]["end"]
                        if 0.0 < gap <= 0.035:
                            snap_count += 1
                self.state["acoustic_stats"] = {
                    "total_tokens": len(toks),
                    "token_recovery_pct": self._compute_recovery_pct(len(toks)),
                    "ctc_framerate": "50 fps CTC",
                    "contiguous_snaps": snap_count,
                    "overlap_violations": 0
                }
                self.state["status"] = "complete"
                self.state["current_step"] = 4
                self.state["logs"].append(f"Loaded existing aligned session with {len(toks)} perfected tokens. Ready to inject.")
            except Exception:
                pass

        if os.path.exists(inj_path) and injection_current:
            try:
                self.state["inject_script"] = open(inj_path, encoding="utf-8").read()
            except Exception:
                pass

    def log(self, text):
        with self.lock:
            self.state["logs"].append(text)
            self.state["message"] = text
            print(f"[Pipeline] {text}")

    def get_state(self):
        with self.lock:
            return dict(self.state)

    def signal_auth_complete(self):
        """Called when user clicks 'I have authenticated' in the GUI."""
        self.log("Authentication confirmed by user. Resuming extraction...")
        self.auth_event.set()

    def start_pipeline_async(self, task_url):
        t = threading.Thread(target=self._run_extraction_and_transcription, args=(task_url,), daemon=True)
        t.start()

    def _run_extraction_and_transcription(self, task_url):
        try:
            with self.lock:
                self.state["status"] = "extracting"
                self.state["current_step"] = 1
                self.state["task_url"] = task_url
                self.state["error"] = None
                self.state["logs"] = []
                # Don't carry the previous run's injection into this one (the GUI kept showing
                # the last bundle's inject script and token count during the next bundle).
                self.state["inject_script"] = ""
                self.state["tokens_count"] = 0
                self.auth_event.clear()

            self.log(f"Starting extraction for task: {task_url[:60]}...")

            # 1. Run Botasaurus deep extraction
            self._do_botasaurus_extract(task_url)

            # 2. Match WAV files & clips
            with self.lock:
                self.state["status"] = "transcribing"
                self.state["current_step"] = 2
            self.log("Matching audio clips and calculating sample-level offsets...")
            clips = self._match_and_order_clips()

            # 3. Multi-Stream Transcription (Groq Whisper + Wav2Vec2 CTC + Micro-Slice)
            self.log(f"Transcribing {len(clips)} audio clips with Groq Whisper-large-v3...")
            groq_results = self._transcribe_all_clips(clips)

            self.log("Running Wav2Vec2 50fps CTC Acoustic Pass...")
            w2v_results = self._run_wav2vec2_acoustic_pass(clips)

            self.log("Running Targeted Micro-Slice ASR on bloated/disfluent audio windows...")
            microslice_results = self._run_microslice_repair_pass(clips, groq_results)

            # 4. Prepare pre-label-independent LLM payloads
            with self.lock:
                self.state["status"] = "ready_for_llm"
                self.state["current_step"] = 3
            self.log("Generating pre-label-independent LLM prompt and input payload...")
            prompt, payload = self._generate_llm_payloads(clips, groq_results, w2v_results, microslice_results)

            combined = f"{prompt}\n\n{'='*60}\n\n{payload}"
            with self.lock:
                self.state["llm_prompt"] = prompt
                self.state["llm_input"] = payload
                self.state["combined_llm_payload"] = combined
                self.state["message"] = f"All {len(clips)} clips transcribed! Copy the prompt below into your LLM."

            self.log("Ready for LLM! Copy payload and paste LLM response when ready.")

        except Exception as e:
            import traceback
            err_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.log(f"ERROR: {str(e)}")
            with self.lock:
                self.state["status"] = "error"
                self.state["error"] = err_msg

    def _do_botasaurus_extract(self, task_url):
        from botasaurus.browser import browser, Driver

        pipeline = self

        @browser(
            block_images=False,
            wait_for_complete_page_load=False,
        )
        def run_browser(driver: Driver, data):
            pipeline.log("Opening Chrome to Pulsar task URL...")
            driver.get(task_url)
            driver.sleep(3)

            with pipeline.lock:
                pipeline.state["status"] = "waiting_auth"

            # Manual sign-in used to double as the "bundle has loaded" wait: the user only clicked
            # "I have authenticated" once the editor was visible. Auto sign-in finishes in ~1.5s
            # while the bundle is still loading (0 clips listed 3s later), so wait explicitly.
            if _auto_login(driver, pipeline.log) and _wait_for_bundle(driver, pipeline.log):
                pipeline.log("Signed in automatically and bundle loaded.")
            else:
                pipeline.log("Waiting for user to authenticate in Chrome (credentials: see local_secrets.json)...")
                # Wait for user to signal in GUI or terminal
                pipeline.auth_event.wait(timeout=600)  # 10 min timeout
            driver.sleep(2)

            with pipeline.lock:
                pipeline.state["status"] = "extracting"
            pipeline.log("Extracting localStorage and clip data from page...")

            # Extract localStorage
            all_storage = driver.run_js("""
                const result = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    result[key] = localStorage.getItem(key);
                }
                return result;
            """)
            with open(os.path.join(OUTPUT_DIR, "full_localstorage.json"), "w", encoding="utf-8") as f:
                json.dump(all_storage, f, indent=2)

            clip_keys = [k for k in all_storage if k.startswith("pulsar_align_clip_")]
            clips_data = {}
            for key in clip_keys:
                try:
                    clips_data[key] = json.loads(all_storage[key])
                except Exception:
                    clips_data[key] = all_storage[key]

            with open(os.path.join(OUTPUT_DIR, "clip_tokens.json"), "w", encoding="utf-8") as f:
                json.dump(clips_data, f, indent=2)

            # Extract clip list from DOM
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
                    };
                });
            """)
            with open(os.path.join(OUTPUT_DIR, "clip_list.json"), "w", encoding="utf-8") as f:
                json.dump(clip_list, f, indent=2)

            pipeline.log(f"Found {len(clip_list)} clips in editor. Downloading audio bundle...")

            # Download audio bundle ZIP directly via HTTP streaming to prevent CDP websocket hangs
            from urllib.parse import urlparse, parse_qs
            import urllib.request

            parsed = urlparse(task_url)
            qs = parse_qs(parsed.query)
            bundle_name = qs.get("bundle", [None])[0]
            sig = qs.get("sig", [None])[0]

            if not bundle_name or not sig:
                try:
                    loc_search = driver.run_js("return window.location.search")
                    if loc_search:
                        page_qs = parse_qs(loc_search.lstrip("?"))
                        bundle_name = bundle_name or page_qs.get("bundle", [None])[0]
                        sig = sig or page_qs.get("sig", [None])[0]
                except Exception:
                    pass

            if not bundle_name or not sig:
                raise RuntimeError(f"Could not resolve 'bundle' or 'sig' from URL: {task_url}")

            bundle_tracker_path = os.path.join(OUTPUT_DIR, "current_bundle.txt")
            is_new_bundle = True
            if os.path.exists(bundle_tracker_path):
                with open(bundle_tracker_path, "r", encoding="utf-8") as f:
                    if f.read().strip() == bundle_name:
                        is_new_bundle = False
            
            if is_new_bundle:
                # Archive the outgoing bundle BEFORE anything is cleared: its WAVs and the exact
                # tokens we injected are what gold labels get scored against, and both are
                # destroyed below (this is how the first gold set lost its transcripts).
                prev_bundle = None
                if os.path.exists(bundle_tracker_path):
                    with open(bundle_tracker_path, "r", encoding="utf-8") as f:
                        prev_bundle = f.read().strip() or None
                archived = archive_bundle(prev_bundle, pipeline.log) if prev_bundle else None
                if archived:
                    # Safely archived: remove the outgoing bundle's LLM/inject outputs so they
                    # can't be mistaken for the new bundle's (they are not cleared otherwise).
                    for f in BUNDLE_LATE_OUTPUTS:
                        try:
                            os.remove(os.path.join(OUTPUT_DIR, f))
                        except Exception:
                            pass
                pipeline.log(f"New bundle detected ({bundle_name}). Clearing previous output caches...")
                caches_to_clear = [
                    "wav2vec2_acoustic_transcriptions.json",
                    "microslice_repaired_transcriptions.json", 
                    "groq_transcriptions.json",
                    "ordered_clips.json",
                    "bundle_manifest.json"
                ]
                for f in caches_to_clear:
                    try:
                        os.remove(os.path.join(OUTPUT_DIR, f))
                    except Exception:
                        pass
                with open(bundle_tracker_path, "w", encoding="utf-8") as f:
                    f.write(bundle_name)

            origin = f"{parsed.scheme}://{parsed.netloc}"
            dl_url = f"{origin}/api/dl/pulsar-chunk/{bundle_name}?sig={sig}"
            zip_path = os.path.join(AUDIO_DIR, "bundle.zip")

            pipeline.log(f"Streaming audio bundle ({bundle_name[:30]}...)...")
            req = urllib.request.Request(dl_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Download failed with HTTP {resp.status}")
                with open(zip_path, "wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)

            size_mb = os.path.getsize(zip_path) / (1024 * 1024)
            pipeline.log(f"Audio bundle downloaded successfully ({size_mb:.2f} MB). Unpacking ZIP...")

            # Clean existing WAVs & JSONs
            for f in os.listdir(AUDIO_DIR):
                if f.endswith(('.wav', '.json')) and f != "bundle.zip":
                    try:
                        os.remove(os.path.join(AUDIO_DIR, f))
                    except Exception:
                        pass

            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(AUDIO_DIR)
                manifest_wavs = [f for f in zf.namelist() if f.endswith('.wav')]
                with open(os.path.join(OUTPUT_DIR, "bundle_manifest.json"), "w", encoding="utf-8") as mf:
                    json.dump(manifest_wavs, mf, indent=2)

            pipeline.log(f"Audio bundle unpacked ({len(manifest_wavs)} clips saved in manifest)!")
            return True

        run_browser()

    def _match_and_order_clips(self):
        clip_list = json.load(open(os.path.join(OUTPUT_DIR, "clip_list.json"), encoding="utf-8"))
        
        # Determine canonical WAV order directly from the downloaded server bundle.zip
        zip_path = os.path.join(AUDIO_DIR, "bundle.zip")
        manifest_file = os.path.join(OUTPUT_DIR, "bundle_manifest.json")
        bundle_wavs = []
        if os.path.exists(manifest_file):
            bundle_wavs = json.load(open(manifest_file, encoding="utf-8"))
        elif os.path.exists(zip_path):
            import zipfile
            with zipfile.ZipFile(zip_path, "r") as zf:
                bundle_wavs = [f for f in zf.namelist() if f.endswith(".wav")]
        else:
            bundle_wavs = sorted([f for f in os.listdir(AUDIO_DIR) if f.endswith(".wav")])

        # Measure exact durations of audio files
        wav_durs = {}
        for f in bundle_wavs:
            wpath = os.path.join(AUDIO_DIR, f)
            if os.path.exists(wpath):
                with wave.open(wpath, "rb") as wf:
                    wav_durs[f] = wf.getnframes() / wf.getframerate()

        ordered_clips = []
        cur_time_sec = 0.0
        used_wavs = set()

        for idx, c in enumerate(clip_list):
            parts = c["time"].split("·")
            dur_target = float(parts[1].strip().replace("s", ""))

            # Primary Ground Truth: Exact 1-to-1 index from the server bundle archive
            matched_wav = None
            if idx < len(bundle_wavs):
                candidate = bundle_wavs[idx]
                c_dur = wav_durs.get(candidate, 0)
                if abs(c_dur - dur_target) < 0.2:
                    matched_wav = candidate

            # Fallback (only if zip order differed): match strictly unused wav by duration
            if not matched_wav:
                for wname, wdur in wav_durs.items():
                    if wname not in used_wavs and abs(wdur - dur_target) < 0.1:
                        matched_wav = wname
                        break

            if not matched_wav and idx < len(bundle_wavs):
                matched_wav = bundle_wavs[idx]

            used_wavs.add(matched_wav)

            # Get pre-label count directly from the server JSON in the audio bundle
            jpath = os.path.join(AUDIO_DIR, matched_wav.replace(".wav", ".json"))
            pre_word_count = 0
            if os.path.exists(jpath):
                try:
                    jd = json.load(open(jpath, encoding="utf-8"))
                    pre_word_count = len(jd.get("segments", []))
                except Exception:
                    pass

            wpath = os.path.join(AUDIO_DIR, matched_wav)
            with wave.open(wpath, "rb") as wf:
                nframes = wf.getnframes()
                sr = wf.getframerate()

            dur_sec = nframes / sr

            # Parse DOM start time directly from clip_list
            dom_start = None
            try:
                t_str = c["time"].split("·")[0].strip()
                t_parts = t_str.split(":")
                if len(t_parts) == 2:
                    dom_start = float(t_parts[0]) * 60 + float(t_parts[1])
                elif len(t_parts) == 3:
                    dom_start = float(t_parts[0]) * 3600 + float(t_parts[1]) * 60 + float(t_parts[2])
            except Exception:
                pass

            start_sec = dom_start if dom_start is not None else cur_time_sec
            end_sec = start_sec + dur_sec
            cur_time_sec = end_sec

            ordered_clips.append({
                "index": idx,
                "id": f"clip_{idx}",
                "filename": matched_wav,
                "duration_sec": dur_sec,
                "start_sec": round(start_sec, 4),
                "end_sec": round(end_sec, 4),
                "token_count": pre_word_count
            })

        with open(os.path.join(OUTPUT_DIR, "ordered_clips.json"), "w", encoding="utf-8") as f:
            json.dump(ordered_clips, f, indent=2)

        with self.lock:
            self.state["clips"] = ordered_clips
        return ordered_clips

    def _transcribe_all_clips(self, clips):
        client = Groq(api_key=GROQ_API_KEY)
        results = []

        for clip in clips:
            idx = clip["index"]
            fname = clip["filename"]
            path = os.path.join(AUDIO_DIR, fname)
            self.log(f"[{idx+1}/{len(clips)}] Transcribing {fname} ({clip['duration_sec']:.2f}s)...")

            with open(path, "rb") as audio_file:
                resp = client.audio.transcriptions.create(
                    file=(fname, audio_file.read()),
                    model="whisper-large-v3",
                    response_format="verbose_json",
                    timestamp_granularities=["word"]
                )

            clip_result = {
                "clip_index": idx,
                "clip_id": clip["id"],
                "filename": fname,
                "global_offset_sec": clip["start_sec"],
                "duration_sec": clip["duration_sec"],
                "full_text": resp.text.strip(),
                "words": resp.words or []
            }
            results.append(clip_result)

        with open(os.path.join(OUTPUT_DIR, "groq_transcriptions.json"), "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results

    def _run_wav2vec2_acoustic_pass(self, clips):
        w2v_path = os.path.join(OUTPUT_DIR, "wav2vec2_acoustic_transcriptions.json")
        if os.path.exists(w2v_path):
            try:
                cached = json.load(open(w2v_path, encoding="utf-8"))
                if len(cached) >= len(clips):
                    return cached
            except Exception:
                pass

        import torch, torchaudio, soundfile as sf
        bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
        model = bundle.get_model()
        labels = bundle.get_labels()

        results = []
        for c in clips:
            c_idx = c["index"]
            fname = c["filename"]
            wav_path = os.path.join(AUDIO_DIR, fname)
            if not os.path.exists(wav_path):
                continue
            data, sr = sf.read(wav_path)
            if data.ndim > 1:
                data = data.mean(axis=1)
            tensor_wav = torch.tensor(data, dtype=torch.float32).unsqueeze(0)
            if sr != 16000:
                resampler = torchaudio.transforms.Resample(sr, 16000)
                tensor_wav = resampler(tensor_wav)
            with torch.no_grad():
                emissions, _ = model(tensor_wav)
                emissions = torch.log_softmax(emissions, dim=-1)

            indices = torch.argmax(emissions[0], dim=-1)
            raw_chars = [labels[i] for i in indices]

            non_blank = []
            prev = None
            for idx, c_lbl in enumerate(raw_chars):
                t_sec = idx * 0.02
                if c_lbl != prev:
                    if c_lbl != '-':
                        non_blank.append({"char": c_lbl, "time": t_sec})
                    prev = c_lbl

            acoustic_words = []
            cur_w = []
            w_st = None
            for item in non_blank:
                ch = item["char"]
                tm = item["time"]
                if ch == '|':
                    if cur_w:
                        acoustic_words.append({
                            "word": "".join(cur_w).lower(),
                            "start": round(w_st, 2),
                            "end": round(tm, 2)
                        })
                        cur_w = []
                        w_st = None
                else:
                    if w_st is None:
                        w_st = tm
                    cur_w.append(ch)
            if cur_w:
                acoustic_words.append({
                    "word": "".join(cur_w).lower(),
                    "start": round(w_st, 2),
                    "end": round(non_blank[-1]["time"], 2)
                })

            raw_text = " ".join(w["word"].upper() for w in acoustic_words)
            results.append({
                "clip_index": c_idx,
                "clip_id": c.get("id", f"clip_{c_idx}"),
                "filename": fname,
                "duration_sec": c.get("duration_sec", len(data)/sr),
                "raw_acoustic_text": raw_text,
                "acoustic_words": acoustic_words
            })

        with open(w2v_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        return results

    def _run_microslice_repair_pass(self, clips, groq_results):
        rep_path = os.path.join(OUTPUT_DIR, "microslice_repaired_transcriptions.json")
        if os.path.exists(rep_path):
            try:
                cached = json.load(open(rep_path, encoding="utf-8"))
                if len(cached) >= len(clips):
                    return cached
            except Exception:
                pass

        import soundfile as sf, io
        client = Groq(api_key=GROQ_API_KEY)
        results = []
        funcs = ['a', 'an', 'the', 'and', 'or', 'to', 'of', 'in', 'it', 'so', 'than', 'one', 'not']

        for c_res in groq_results:
            c_idx = c_res["clip_index"]
            fname = c_res["filename"]
            wav_path = os.path.join(AUDIO_DIR, fname)
            words = list(c_res.get("words", []))
            
            if not os.path.exists(wav_path):
                results.append({"clip_index": c_idx, "words": words})
                continue
                
            data, sr = sf.read(wav_path)
            if data.ndim > 1:
                data = data.mean(axis=1)

            repaired_words = []
            for w in words:
                st = float(w["start"])
                en = float(w["end"])
                dur = en - st
                cl = w["word"].lower().strip('.,?!"\'')
                is_bloated = (cl in funcs and dur >= 0.65) or (dur >= 1.40)
                
                if is_bloated:
                    pad_st = max(0.0, st - 0.05)
                    pad_en = min(len(data)/sr, en + 0.05)
                    slice_samples = data[int(pad_st * sr):int(pad_en * sr)]
                    buf = io.BytesIO()
                    sf.write(buf, slice_samples, sr, format="WAV")
                    buf.seek(0)
                    try:
                        resp = client.audio.transcriptions.create(
                            file=("slice.wav", buf.read()),
                            model="whisper-large-v3",
                            response_format="verbose_json",
                            timestamp_granularities=["word"],
                            prompt="um, uh, the, and, like, you know, verbatim stutters",
                            temperature=0.0
                        )
                        sub_words = resp.words or []
                        if len(sub_words) > 1:
                            for sw in sub_words:
                                repaired_words.append({
                                    "word": sw["word"],
                                    "start": round(pad_st + float(sw["start"]), 3),
                                    "end": round(pad_st + float(sw["end"]), 3)
                                })
                        else:
                            repaired_words.append(w)
                    except Exception:
                        repaired_words.append(w)
                else:
                    repaired_words.append(w)
            results.append({"clip_index": c_idx, "words": repaired_words})

        with open(rep_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        return results

    def _load_prelabel_words(self, audio_filename):
        """Best-effort load of a clip's prior reference transcript, if one
        exists, from its audio/<name>.json sidecar's "lexical" segments
        (see forced_aligner.py's match_prelabel_segments for the same data
        used downstream at the boundary-refinement stage). Returns a plain
        list of words in order, or [] if no sidecar exists or it has no
        lexical segments -- callers must treat this as fully optional."""
        sidecar_path = os.path.join(AUDIO_DIR, os.path.splitext(audio_filename)[0] + ".json")
        if not os.path.exists(sidecar_path):
            return []
        try:
            sidecar = json.load(open(sidecar_path, encoding="utf-8"))
        except Exception:
            return []
        return [
            s["refTranscript"].strip()
            for s in sidecar.get("segments", [])
            if s.get("type") == "lexical" and s.get("refTranscript", "").strip()
        ]

    def _load_prelabel_segments(self, audio_filename):
        """Like _load_prelabel_words, but returns the raw lexical segment
        dicts (refTranscript + startTime/endTime), which is what
        ForcedAligner.align()'s prelabel_segments param expects -- used at
        the actual boundary-refinement step, not just the LLM prompt."""
        sidecar_path = os.path.join(AUDIO_DIR, os.path.splitext(audio_filename)[0] + ".json")
        if not os.path.exists(sidecar_path):
            return None
        try:
            sidecar = json.load(open(sidecar_path, encoding="utf-8"))
        except Exception:
            return None
        segs = [s for s in sidecar.get("segments", []) if s.get("type") == "lexical"]
        return segs or None

    def _generate_llm_payloads(self, clips, groq_results, w2v_results=None, microslice_results=None):
        if w2v_results is None:
            w2v_results = self._run_wav2vec2_acoustic_pass(clips)
        if microslice_results is None:
            microslice_results = self._run_microslice_repair_pass(clips, groq_results)

        w2v_map = {w["clip_index"]: w for w in w2v_results}
        rep_map = {r["clip_index"]: r for r in microslice_results}
        n_clips = len(clips)
        clip_indices = [c["index"] for c in clips]
        start_idx = clip_indices[0] if clip_indices else 0
        end_idx = clip_indices[-1] if clip_indices else 0

        # NOTE: this prompt previously contained an "ACOUSTIC CTC QUIRK TRANSLATION
        # DICTIONARY" that was a literal memorized lookup table of specific garbled CTC
        # strings mapped to specific answers from an unrelated prior project (e.g.
        # "SAS PRINT" -> "spri- uh sprint", "A SMEPEACOCK" -> "uh s- peacock", "They say
        # stay" -> hallucinated "safe") -- none of which occur in, or generalize to, this
        # project's actual clips. It also contained a factually wrong rule ("newsreaders"
        # -> "news", "readers" as a "compound word split") that isn't in the real Pulsar
        # guidelines, which only split HYPHENATED words, not arbitrary compounds. Removed
        # both; the rules below are restated as general principles with no memorized
        # examples baked in. transcript_reconciler.py holds an alternative prompt. Its quoted
        # "8.28% WER / 96.62% recall" does NOT reproduce (2026-09-23): none of its five saved
        # runs match it, and Groq's gpt-oss-120b now scores its own historical prompt 4.4
        # points worse than on 09-20. Single-run LLM comparisons in this repo (including the
        # CrisperWhisper 3-source verdict) are unreliable -- re-measure with
        # bench/run_text_bench.py (3+ reps, same model) before switching prompts.
        system_prompt = f"""# PULSAR AUDIO ANNOTATION & VERBATIM TOKENIZATION AGENT

You are an expert speech transcription and acoustic reconciliation system for the Pulsar audio alignment project.
Your task is to review {n_clips} audio clips (Clips {start_idx} to {end_idx}) and output the perfected, verbatim word-level tokens for each clip, strictly adhering to the official Pulsar guidelines.

## THE CORE RECONCILIATION PRINCIPLE:
1. Whisper-large-v3: Highly accurate for standard vocabulary, proper nouns, and lexical semantics, BUT it suffers from an aggressive "smoothing" bias (autoregressive LM prior). It systematically strips stutters, false starts, truncated words, phrase repetitions, conversational contractions, and backchannels.
2. Wav2Vec2 Acoustic CTC Stream: Direct acoustic sensor. It has NO language model and NO smoothing. It records essentially every acoustic event -- stutters, restarts, repeated words -- that Whisper drops. Its weakness is spelling: with no notion of real words or grammar, it frequently renders a real word as a garbled or nonsense-looking letter sequence, especially for proper nouns and short function words.
3. RECONCILIATION RULE: trust the CTC stream for WHETHER a disfluency, cut-off restart, repeated word, or filler token exists at all (don't drop something CTC shows just because Whisper dropped it); trust Whisper for the correct SPELLING of a word when both streams clearly refer to the same word. When CTC shows a garbled sequence with no Whisper correspondence, use it to recover an attested word/name via context and phonetic resemblance rather than inventing one from nothing.
4. Prior Reference Transcript (prelabel), WHEN PRESENT: this pipeline is deliberately built to work from Whisper + CTC alone and does NOT require a prelabel to function -- most clips will have none, and that is fine. When a prior reference transcript IS shown for a clip below, treat it as a THIRD independent corroborating signal, not an authority: it comes from an earlier, separately-produced pass over the same audio and may itself be stale, incomplete, or wrong. Use it to help break ties specifically where Whisper and CTC disagree or where CTC's evidence is garbled/ambiguous (disfluency presence, filler identity, a truncated-fragment's likely completion) -- but if the prior transcript conflicts with what BOTH Whisper and CTC agree on, or conflicts with actual acoustic evidence, do not defer to it just because it's there.

## GENERAL PATTERNS (apply the principle, not a memorized example):
1. Truncated stems & false starts: any aborted word fragment is transcribed with a trailing hyphen at the point of cutoff (e.g. a word that starts then is abandoned mid-syllable). CTC often renders a truncated fragment as a short, sometimes-garbled burst right before the (often repeated) completed word -- use that positioning as the cue, not a specific letter pattern.
2. Repeated phrases & stutter restarts (zero-drop policy): Whisper collapses repeated words/phrases into a single fluent reading. Never follow that deletion -- transcribe every audible repetition as its own token, using CTC's presence of the repeat as corroborating evidence.
3. Conversational contractions & reduced spoken forms: Whisper regularly expands casual speech into formal written English (e.g. expanding a contraction, or "cleaning up" a reduced form). Transcribe the spoken form the speaker actually used, per the tokenization rules' allowed-informal-contractions list, not Whisper's normalized rewrite -- but only when there is actual acoustic support (e.g. in the CTC stream) for the reduced form; if every source agrees on the fuller form, don't override it just to force an informal spelling.
4. Individual letters & spelled initialisms: letters spoken individually (an initialism, not an acronym pronounced as a word) are separate single-letter tokens, never the whole abbreviation as one word.
5. Backchannels & fillers: Whisper often strips quiet, murmured backchannels entirely; if CTC shows evidence of one, don't drop it. Nasal closure ("m") is "um"; open vowel is "uh" -- use whichever the acoustic evidence actually supports, don't default to one or the other.
6. Inaudible / indistinct speech: mark with "(())" (nothing recoverable) or "((word))" (a reasonable guess), per the tokenization rules -- never invent confident-sounding text for a stretch neither source can actually support.
7. End-of-clip hallucination risk: Whisper (an autoregressive LM) can occasionally emit a plausible-sounding trailing word near a clip's start or end that has zero acoustic support in the CTC stream. Treat such an unsupported edge word with suspicion.

## CRITICAL TOKENIZATION & FORMATTING RULES:
1. Spoken Form & Lowercase:
   - Transcribe strictly what is spoken, in lowercase (e.g. "billy eichner", "zuckerberg").
2. Strip All Standard Punctuation:
   - Strip all periods, commas, exclamation marks, question marks, colons, quotes.
   - EXCEPTIONS:
     - Apostrophes in valid contractions: "that's", "i'd", "don't", "he's", "she's", "it's", "that'll", "would've", "'cause".
     - Trailing hyphens on cutoffs / truncated words.
3. Hyphenated Words MUST Be Split (compound words that are NOT hyphenated stay as one token -- do not split a plain compound noun just because it looks like two words):
   - Treat as separate lexical items. Split hyphens into separate tokens:
     - "eighty-seven" -> "eighty", "seven"
     - "trick-or-treaters" -> "trick", "or", "treaters"
     - "part-time" -> "part", "time"
     - "coca-cola" -> "coca", "cola"
4. Numbers:
   - Transcribe as spoken words: "three", "one", "two", "hundred", "fifth" (NEVER digits like "3", "1").

## OUTPUT FORMAT:
Return ONLY a valid JSON object mapping clip index ("{start_idx}" to "{end_idx}") to a list of word strings:
```json
{{
  "{start_idx}": ["word1", "word2", ...],
  ...
  "{end_idx}": ["word1", "word2", ...]
}}
```"""

        lines = ["=== CLIPS TO PROCESS ===\n"]
        for clip in groq_results:
            ci = clip["clip_index"]
            fname = clip["filename"]
            lines.append(f"--- CLIP {ci} ({fname}) ---")
            lines.append(f"1. Whisper Full Text:\n   \"{clip['full_text']}\"")
            
            w2v = w2v_map.get(ci, {})
            a_text = w2v.get("raw_acoustic_text", "")
            lines.append(f"2. Acoustic CTC Stream (Wav2Vec2):\n   \"{a_text}\"")
            
            w_words = clip.get("words", [])
            bloated = [w for w in w_words if (w['end'] - w['start']) >= 1.0 or (w['word'].lower().strip('.,?!"\'') in ['a', 'an', 'the', 'and', 'or', 'to', 'of', 'in', 'it', 'so', 'than', 'one'] and (w['end'] - w['start']) >= 0.65)]
            
            if bloated and "acoustic_words" in w2v:
                lines.append("3. Key Disfluent / Bloated Spans to Reconcile:")
                for bw in bloated:
                    st, en = bw['start'], bw['end']
                    cw2v = [aw['word'] for aw in w2v['acoustic_words'] if aw['start'] >= st - 0.2 and aw['end'] <= en + 0.2]
                    lines.append(f"   - Whisper '{bw['word']}' [{st:.2f}s - {en:.2f}s] -> Acoustic CTC heard: {cw2v}")
                    
            rep_entry = rep_map.get(ci, {})
            rep_w = rep_entry.get("words", [])
            if len(rep_w) != len(w_words):
                lines.append(f"4. Targeted Micro-Slice detected {len(rep_w)} words (vs Whisper's {len(w_words)} words).")

            prelabel_words = self._load_prelabel_words(fname)
            if prelabel_words:
                lines.append(f"5. Prior Reference Transcript (independent prior pass -- corroborating context only, not authoritative):\n   \"{' '.join(prelabel_words)}\"")

            lines.append("=" * 60 + "\n")

        input_payload = "\n".join(lines)

        with open(os.path.join(OUTPUT_DIR, "pulsar_llm_prompt.txt"), "w", encoding="utf-8") as pf:
            pf.write(system_prompt.strip())
        with open(os.path.join(OUTPUT_DIR, "pulsar_llm_input.txt"), "w", encoding="utf-8") as inf:
            inf.write(input_payload.strip())

        return system_prompt.strip(), input_payload.strip()

    def generate_acoustic_baseline(self):
        """Run ForcedAligner on Whisper + Micro-slice words with 2ms contiguous snapping (Pre-Label-Independent Baseline)."""
        with self.lock:
            self.state["status"] = "generating_injector"
            self.state["current_step"] = 4
        
        self.log("=================================================================")
        self.log("[Acoustic Engine] RUNNING FORCED ALIGNMENT ON BASELINE (ZERO PRE-LABELS)")
        self.log("=================================================================")

        clips_file = os.path.join(OUTPUT_DIR, "ordered_clips.json")
        if not os.path.exists(clips_file):
            raise FileNotFoundError("ordered_clips.json not found.")
        clips = json.load(open(clips_file, encoding="utf-8"))

        groq_file = os.path.join(OUTPUT_DIR, "groq_transcriptions.json")
        groq_data = json.load(open(groq_file, encoding="utf-8")) if os.path.exists(groq_file) else []
        groq_map = {g["clip_index"]: g.get("words", []) for g in groq_data}

        rep_file = os.path.join(OUTPUT_DIR, "microslice_repaired_transcriptions.json")
        rep_data = json.load(open(rep_file, encoding="utf-8")) if os.path.exists(rep_file) else []
        rep_map = {r["clip_index"]: r.get("words", []) for r in rep_data}

        aligner = self._get_aligner()
        final_tokens = []

        for c in clips:
            c_idx = c["index"]
            fname = c["filename"]
            offset = c["start_sec"]
            wpath = os.path.join(AUDIO_DIR, fname)
            if not os.path.exists(wpath):
                continue

            words_to_use = rep_map.get(c_idx, groq_map.get(c_idx, []))
            raw_words = [w["word"].strip(".,?!\"'") for w in words_to_use if w.get("word")]
            from forced_aligner import split_abbreviations
            raw_words = split_abbreviations(raw_words)
            if not raw_words:
                continue

            aligned_raw = aligner.align(wpath, raw_words, hybrid=True)

            aligned = []
            for idx, ar in enumerate(aligned_raw):
                lbl = raw_words[idx] if idx < len(raw_words) else ar["text"]
                aligned.append({
                    "text": lbl,
                    "start": ar["start"],
                    "end": ar["end"],
                    "score": ar["score"]
                })

            for t_idx, t in enumerate(aligned, 1):
                st = float(t["start"])
                en = float(t["end"])
                final_tokens.append({
                    "id": f"t_{fname}_{t_idx}",
                    "speaker": "S1",
                    "start": round(offset + st, 4),
                    "end": round(offset + en, 4),
                    "text": t["text"],
                    "type": "lexical",
                    "clipId": f"clip_{c_idx}",
                    "clipIndex": c_idx,
                    "wrapOpen": [],
                    "wrapClose": []
                })

            self.log(f"[Acoustic Engine] Clip {c_idx+1}/{len(clips)}: {len(aligned)} tokens aligned.")

        # Save tokens and build injection script
        with open(os.path.join(OUTPUT_DIR, "injected_tokens.json"), "w", encoding="utf-8") as f:
            json.dump(final_tokens, f, indent=2)

        return self._build_injection_script(final_tokens)

    def _validate_llm_tokens(self, parsed_data):
        """Refuse an LLM response that would silently drop clips.

        Observed on 2026-09-23: given the live prompt, Groq's gpt-oss-120b returned its own
        output template -- {"0": [], "1": [], ...} -- in 2 of 3 runs. The old code skipped
        empty clips with `continue`, reported SUCCESS, and the generated injector does
        `editorState.tokens = incoming` (full replacement), so injecting it would have WIPED
        every affected clip's tokens from the editor and localStorage.

        Hard error (nothing aligned, written, or injected) when a clip Whisper heard speech in
        is missing or empty. Returns soft warnings for suspiciously short clips (usually a
        truncated response) and for clip keys that aren't in this bundle."""
        if not isinstance(parsed_data, dict):
            return []  # list format carries explicit timestamps and is validated per token
        clips = json.load(open(os.path.join(OUTPUT_DIR, "ordered_clips.json"), encoding="utf-8"))
        heard = {}
        for name in ("microslice_repaired_transcriptions.json", "groq_transcriptions.json"):
            p = os.path.join(OUTPUT_DIR, name)
            if os.path.exists(p):
                for c in json.load(open(p, encoding="utf-8")):
                    heard.setdefault(c["clip_index"], len(c.get("words", [])))
        problems, warnings = [], []
        for c in clips:
            ci = c["index"]
            n_heard = heard.get(ci, c.get("token_count", 0))
            got = parsed_data.get(str(ci))
            if n_heard and not got:
                problems.append(f"clip {ci}: {'missing' if got is None else 'empty'} "
                                f"(Whisper heard {n_heard} words)")
            elif n_heard and len(got) < 0.5 * n_heard:
                warnings.append(f"clip {ci}: only {len(got)} words vs {n_heard} from Whisper -- "
                                f"response may be truncated")
        extra = sorted(set(parsed_data) - {str(c["index"]) for c in clips}, key=str)
        if extra:
            warnings.append(f"response has clip keys not in this bundle: {extra}")
        if problems:
            msg = ("LLM response rejected -- nothing was aligned, written, or injected.\n  "
                   + "\n  ".join(problems)
                   + "\nThe model most likely returned the output template or was cut off. "
                     "Re-run the prompt (or send fewer clips at once) and paste the full response.")
            with self.lock:
                self.state["status"] = "ready_for_llm"
                self.state["current_step"] = 3
                self.state["error"] = msg
            self.log(f"ERROR: {msg}")
            raise ValueError(msg)
        return warnings

    def process_llm_output_and_generate_injection(self, raw_llm_output):
        """Parse LLM JSON output, run ForcedAligner with hybrid RMS snapping & 2ms rules, and generate inject_console.js."""
        with self.lock:
            self.state["status"] = "generating_injector"
            self.state["current_step"] = 4

        self.log("Parsing LLM response JSON...")

        cleaned_json = raw_llm_output.strip()
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_json)
        if m:
            cleaned_json = m.group(1).strip()

        try:
            parsed_data = json.loads(cleaned_json)
        except Exception as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}")

        from forced_aligner import split_abbreviations
        if isinstance(parsed_data, dict):
            for c_idx_str, toks in list(parsed_data.items()):
                raw_words = []
                for item in toks:
                    if isinstance(item, str):
                        raw_words.append(item.strip())
                    elif isinstance(item, dict):
                        raw_words.append(item.get("text", item.get("word", "")).strip())
                parsed_data[c_idx_str] = split_abbreviations([w for w in raw_words if w])

        # Must run before anything is written or aligned: see _validate_llm_tokens.
        for w in self._validate_llm_tokens(parsed_data):
            self.log(f"WARNING: {w}")

        with open(os.path.join(OUTPUT_DIR, "llm_corrected_tokens.json"), "w", encoding="utf-8") as f:
            json.dump(parsed_data, f, indent=2)

        clips_file = os.path.join(OUTPUT_DIR, "ordered_clips.json")
        clips = json.load(open(clips_file, encoding="utf-8"))
        clip_map = {c["index"]: c for c in clips}

        aligner = self._get_aligner()

        final_tokens = []
        self.log("=================================================================")
        self.log("[Acoustic Engine] RUNNING FORCED ALIGNMENT ON LLM OUTPUT (prelabel-corroborated where available, prelabel-independent otherwise)")
        self.log("=================================================================")

        if isinstance(parsed_data, dict):
            for c_idx_str, toks in parsed_data.items():
                try:
                    c_idx = int(c_idx_str)
                except ValueError:
                    continue
                if c_idx not in clip_map:
                    continue
                c_info = clip_map[c_idx]
                offset = c_info["start_sec"]
                fname = c_info["filename"]
                wpath = os.path.join(AUDIO_DIR, fname)

                if not os.path.exists(wpath):
                    self.log(f"[Acoustic Engine] Audio file {wpath} not found.")
                    continue

                raw_words = toks
                if not raw_words:
                    continue

                prelabel_segments = self._load_prelabel_segments(fname)
                aligned_raw = aligner.align(wpath, raw_words, hybrid=True, prelabel_segments=prelabel_segments)

                aligned = []
                for idx, ar in enumerate(aligned_raw):
                    lbl = raw_words[idx] if idx < len(raw_words) else ar["text"]
                    aligned.append({
                        "text": lbl,
                        "start": ar["start"],
                        "end": ar["end"],
                        "score": ar["score"]
                    })

                for t_idx, t in enumerate(aligned, 1):
                    st = float(t["start"])
                    en = float(t["end"])
                    final_tokens.append({
                        "id": f"t_{fname}_{t_idx}",
                        "speaker": "S1",
                        "start": round(offset + st, 4),
                        "end": round(offset + en, 4),
                        "text": t["text"],
                        "type": "lexical",
                        "clipId": f"clip_{c_idx}",
                        "clipIndex": c_idx,
                        "wrapOpen": [],
                        "wrapClose": []
                    })

                self.log(f"[Acoustic Engine] Clip {c_idx+1}/{len(clips)}: {len(aligned)} tokens aligned.")

        elif isinstance(parsed_data, list):
            sanitized = []
            for idx, item in enumerate(parsed_data):
                if isinstance(item, dict) and "start" in item and "end" in item:
                    sanitized.append({
                        "id": str(item.get("id", f"t_custom_{idx}")),
                        "speaker": str(item.get("speaker", "S1")),
                        "start": round(float(item["start"]), 4),
                        "end": round(float(item["end"]), 4),
                        "text": str(item.get("text", item.get("word", ""))),
                        "type": str(item.get("type", "lexical")),
                        "clipId": str(item.get("clipId", "clip_0")),
                        "clipIndex": int(item.get("clipIndex", 0)),
                        "wrapOpen": list(item.get("wrapOpen", [])),
                        "wrapClose": list(item.get("wrapClose", []))
                    })
                else:
                    self.log(f"[Pipeline] WARNING: Skipping malformed token at index {idx}: {item}")
            final_tokens = sanitized

        with open(os.path.join(OUTPUT_DIR, "injected_tokens.json"), "w", encoding="utf-8") as f:
            json.dump(final_tokens, f, indent=2)

        return self._build_injection_script(final_tokens)

    def _build_injection_script(self, final_tokens):
        packed_tokens = []
        for t in final_tokens:
            packed_tokens.append([
                t["id"],
                t["text"],
                round(t["start"], 3),
                round(t["end"], 3),
                t.get("clipId", "clip_0"),
                t.get("clipIndex", 0),
                t.get("wrapOpen", []),
                t.get("wrapClose", [])
            ])

        tokens_json = json.dumps(packed_tokens, separators=(',', ':'))
        js_code = f"""// === PULSAR RECONCILED INJECTION SCRIPT ===
// Multi-scope detection & localStorage persistence enabled
(function() {{
    const rawPacked = {tokens_json};
    const incoming = rawPacked.map(p => ({{
        id: p[0],
        text: p[1],
        start: p[2],
        end: p[3],
        speaker: "S1",
        type: "lexical",
        clipId: p[4],
        clipIndex: p[5],
        wrapOpen: p[6] || [],
        wrapClose: p[7] || []
    }}));

    console.log('[Pulsar Injector] Unpacked ' + incoming.length + ' tokens.');

    let editorState = null;
    let editorWindow = window;
    if (typeof state !== 'undefined' && state && Array.isArray(state.tokens)) {{
        editorState = state;
    }} else if (typeof window !== 'undefined' && window.state && Array.isArray(window.state.tokens)) {{
        editorState = window.state;
    }} else {{
        const iframes = document.querySelectorAll('iframe');
        for (const ifr of iframes) {{
            try {{
                if (ifr.contentWindow && ifr.contentWindow.state && Array.isArray(ifr.contentWindow.state.tokens)) {{
                    editorState = ifr.contentWindow.state;
                    editorWindow = ifr.contentWindow;
                    break;
                }}
            }} catch(e) {{}}
        }}
    }}

    // Update localStorage
    try {{
        let targetKey = null;
        for (let i = 0; i < localStorage.length; i++) {{
            const k = localStorage.key(i);
            if (k && k.startsWith('pulsar_align_clip_')) {{
                targetKey = k;
                break;
            }}
        }}
        if (targetKey) {{
            const existingRaw = localStorage.getItem(targetKey);
            if (existingRaw) {{
                const parsed = JSON.parse(existingRaw);
                if (Array.isArray(parsed)) {{
                    localStorage.setItem(targetKey, JSON.stringify(incoming));
                }} else {{
                    parsed.tokens = incoming;
                    localStorage.setItem(targetKey, JSON.stringify(parsed));
                }}
            }}
        }}
    }} catch(e) {{}}

    if (editorState) {{
        editorState.tokens = incoming;
        if (!editorState.tokenStats) editorState.tokenStats = {{}};
        for (const t of editorState.tokens) {{
            if (!editorState.tokenStats[t.id]) {{
                editorState.tokenStats[t.id] = {{ played: false, selectedCount: 0 }};
            }}
        }}
        try {{
            if (editorState.markDirty) editorState.markDirty();
            if (editorState.notifyListeners) editorState.notifyListeners();
            if (editorState.render) editorState.render();
            if (typeof editorState.setTokens === 'function') editorState.setTokens(editorState.tokens);
        }} catch(e) {{}}
        try {{
            editorWindow.dispatchEvent(new Event('resize'));
            editorWindow.dispatchEvent(new CustomEvent('tokens-updated', {{ detail: {{ count: incoming.length }} }}));
        }} catch(e) {{}}
        console.log('[Pulsar Injector] SUCCESS! Injected ' + incoming.length + ' tokens.');
    }} else {{
        console.error('[Pulsar Injector] window.state.tokens not found! Please ensure you are on the Pulsar editor page.');
    }}
}})();
"""
        inject_file = os.path.join(OUTPUT_DIR, "inject_console.js")
        with open(inject_file, "w", encoding="utf-8") as f:
            f.write(js_code)

        snap_count = 0
        overlap_violations = 0
        for i in range(len(final_tokens) - 1):
            if final_tokens[i].get("clipIndex") == final_tokens[i+1].get("clipIndex"):
                gap = final_tokens[i+1]["start"] - final_tokens[i]["end"]
                if 0.0 < gap <= 0.035:
                    snap_count += 1
                elif final_tokens[i]["end"] > final_tokens[i+1]["start"]:
                    overlap_violations += 1

        acoustic_summary = {
            "total_tokens": len(final_tokens),
            "token_recovery_pct": self._compute_recovery_pct(len(final_tokens)),
            "ctc_framerate": "50 fps CTC",
            "contiguous_snaps": snap_count,
            "overlap_violations": overlap_violations
        }

        with self.lock:
            self.state["status"] = "complete"
            self.state["inject_script"] = js_code
            self.state["tokens_count"] = len(final_tokens)
            self.state["acoustic_stats"] = acoustic_summary
            self.state["message"] = f"Generated injection script with {len(final_tokens)} tokens!"

        self.log(f"[Acoustic Engine] SUCCESS: Generated {len(final_tokens)} perfected tokens ({acoustic_summary['token_recovery_pct']}% recovery, {overlap_violations} overlaps).")
        return js_code

pipeline = PulsarPipeline()
