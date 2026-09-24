# aligner2 — handoff (from the cloud session, 2026-09-24)

Branch: `claude/pulsar-auto-conversation-oi3e40` (pushed; not merged; no PR). Everything below is committed there.

## The goal and the user's rules
- Build the best word aligner: new clips aligned automatically with the most precise and accurate boundaries.
- **Generalizable rules, not trained models.** Each rule is a fixed phonetic definition. The data is only used to
  choose between a few principled definitions or to reject one; nothing is fitted.
- **"Your data, when clear, is the source of truth."** Where the signals clearly contradict a gold label, the signals
  win. That is implemented as an audit layer over the gold (`aligner2/gold_audit.py`); the gold files are never edited.
- Read the data in full detail and go down to the root cause (2 ms reads), not surface statistics.
- Gold kinds: **H** = a reviewer moved/placed the boundary. **Accepted** = an older aligner's output a reviewer left
  alone. When the two conventions conflict, follow H, since that is the reviewer's deliberate choice (e.g. weak initial
  fricatives, fricative word ends).
- Dev = sets **009 + 026**. Held-out = **049**: score it only at checkpoints and never pick a definition on it.
  (So far it was used once to reject a variant, J13c, and its worst cases were spot-read after the build. That exposed
  two bugs, fixed in E1 and J14. So it is no longer perfectly clean.)

## Current scores (MAE ms; `python -m aligner2.local_bench --test`)
| | v16 (coarse) | + rule stage |
|---|---|---|
| dev 009+026, all | 21.8 | **17.5** |
| dev, H | 28.9 | **22.7** |
| held-out 049, all | 24.9 | **19.9** |
| held-out 049, H | 28.7 | **22.9** |

## Pipeline
1. **Signals** (GPU, Modal engine `modal_aligner2.py`, app `aligner2-signals`, volume `aligner2-cache`): loudness,
   periodicity, zcr, centroid, band ratios, transients, glottal, MFCCs, and HuBERT CTC letters (4 frame-phase shifts =
   "letter4"), xlsr espeak phones, charsiu 10 ms phones. They are cached locally as
   `bench/cache/aligner2/<key>_98e63a51.npz`, mapped per clip by `bench/tools/clip_cache_map.json` (tracked in git).
2. **Coarse aligner v16** = `segment.align_two_pass` with `run_bench.GRID[0]`. Its predictions and per-token ARPAbet
   are in `bench/prov_runs/aligner2_v16.json`.
3. **Rule stage** `aligner2/refine.py` (`refine.refine(z, texts, arpa, coarse)`): moves each boundary onto the
   acoustic landmark reviewers use for that junction class. The module docstring lists every rule and its evidence.
   Enabled rules are the `refine.RULES` set. It is wired into the engine (`modal_aligner2.align` pops
   `refine=True` from a grid entry; `run_bench.GRID[3]` is v16 + rules) but **has not yet run on Modal**.

## Running locally (CPU, no GPU needed)
- `python -m aligner2.local_bench [--test] [--sides] [--pairs] [--audit] [--rules a,b]`: v16 vs refined.
  `--audit` also scores against the audited gold.
- `python -m aligner2.residuals`: error by rule × kind. `--list PREFIX N [--kind cont] [--fp]` lists the worst cases;
  `--show SET-CLIP K MS [--step 4]` prints a 2 ms table around join k|k+1 with markers G (gold), S (v16),
  N (refined), L (word k's last-letter peak), F (word k+1's first-letter peak).
- `python -m aligner2.landmark_eval "A>B" [--b-phone DH] [--cascade c1,c2]`: candidate landmark definitions vs
  gold for one junction class (all / H / per set).
- `python -m aligner2.rule_ab --drop X | --add X [--sets 049]`: per-class A/B of one rule change.
- `python -m aligner2.gold_audit`: lists the audit corrections.
- `python -m aligner2.rule_debug "pair"`: per-boundary trace for one junction class.
- `python bench/tools/joins.py 026_04 5 9` or `... win T0 T1 STEP`: the wide table used for the full reads.
- Letter peaks are cached in `bench/cache/aligner2/lexical_peaks_letter4.json` (dev + 049). `refine.refine` recomputes
  them if absent (numpy, a few s/clip; `device="cuda"` in the engine).
- `segment.py` imports `aligner2.signals` (torch). To run segment on CPU without torch, stub it:
  `sys.modules['aligner2.signals'] = types.SimpleNamespace(HOP=0.002)`. Reproducing v16 exactly also needs the xlsr
  espeak vocab (`phones.vocab()`, Hugging Face; blocked in the cloud, probably fine locally) and sklearn (only for the
  unused gmm pause model).

## Workflow that produced every rule
residuals → worst cases → 2 ms `--show` reads → a principled definition → `landmark_eval` compares 2-5 definitions →
implement behind a `RULES` flag → `rule_ab` on dev (per class, check H) → `local_bench --sides` → 049 checkpoint →
document in the refine.py docstring and NOTES.md → commit.

## The rule set (details in the `aligner2/refine.py` docstring)
Joins: J1 (stop>V: release, then voicing onset; no release: /nd/ /nt/ elision → nasal rule, flaps → change midpoint),
J4 (V/nas>fric: frication onset), J5 (fric>V crossfade), J6 (stop>fric crossover), J7 (V>nas), J8 (nas>V release),
J9 (V>V/gl/liq: letter-peak midpoint; liq>V loudness rise), J10 (stop>gl/nas, liq>stop), J12, **J13** (any>stop and
any>DH except after a nasal: the quietest frame ±20 ms of the letter midpoint), **J14** (hard glottal onset of a
vowel-initial word after a vowel).
False pauses: **J0** (coarse gap < 100 ms never within 10 dB of the floor → join), **F2** (gap that is frication
throughout before a fricative-initial word → join).
Pause edges: P1 (a separate event after the word: breath / hiss / fricative runs on / stop release), P2, **P3**
(steepest rise within 30 ms). Clip edges: E1 (fixed: running speech only if the level never nears the floor; gap band
measured from the floor), E2.

## Findings (full write-up: `bench/cache/aligner2/fullread/NOTES.md`, last two sections)
- NOTES.md also has the earlier boundary-by-boundary full read: all of 009 and 026-0..026-6, plus 026-7 through join 42.
  The conventions it named are cited by code as R1-R8, e.g. R3 = exclude non-lexical events, R7 = a fricative lasts
  until it dies.
- The old accepted golds drop weak word-initial fricatives and cut final /s z/ early; the H golds never do.
- V>V / V>glide / V>liquid stay at ~20 ms with every estimator available (letters, boundary priors, MFCC trajectories,
  charsiu). That is the resolution of the evidence, not a rule defect.
- Gross errors (|err| > 80 ms, 19% of dev error; filler neighbourhoods are 14-15% of the H error) are
  **coarse / lexical-stage failures**: a transcript that doesn't match the audio (026-04 "we" heard as "we'll"),
  repeated fillers ("uh uh" both placed in the first), spelled letters (the CTC peak marks only the consonant),
  partial words ("s-", "th-"), unintelligible "(())". No rule on the coarse output can fix these.

## Tried and rejected (don't retry without new evidence)
Generic 50%-change rule for all remaining class pairs (-0.28 s); J13 "middle of the near-minimum stretch" (dev +0.2 s,
held-out -0.4 s); nasal+DH dental-nasal release (overshoots 20-56 ms); V>W at the loudness minimum (= letter
midpoint); floor-level-silence missed-pause test (8/10 not pauses); fixed word-peak-relative / end-of-fall /
x%-of-fall pause-end definitions (all worse on accepted golds); J14 after nasals / liquids / fricatives; charsiu as an
arbiter (the rules are closer 298 : 88 where they disagree by > 60 ms); soft / wildcard filler modes (grid 1-2: worse);
J1 dip path on its own.

## Next steps
1. **Modal (needs the user):** `pip install modal`; set `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` for the workspace
   that owns `aligner2-signals` + `aligner2-cache` (it must be able to deploy: `aligner2/remote.py` redeploys when
   the code changes). Then run `python -m aligner2.run_bench` and confirm GRID[3] (v16 + rules) matches local_bench.
   The engine calls `refine.refine(z, texts, fc_strs, p, device="cuda")`, so it recomputes letter peaks with torch
   forward-backward; check they match the numpy cache.
2. **Coarse-stage work (the biggest remaining lever):**
   - Filler-aware lexical alignment (fillers as sustained-vowel islands; repeated fillers split at gaps).
   - Transcript-mismatch detection (the CTC emits letters the transcript lacks).
   - Spelled letters (extend the lexical region by the letter name's vowel).
   - Partial words.
   - Missed pauses next to a quiet word (v16's pause test is relative to the quieter word: yeah|so).
3. The remaining full reads (026-7 from join 43, 026-8..026-11) were never done. That dev data has only been seen
   through the residual tools.
4. Grow the gold audit only with classes that are clear at 2 ms on every dev case they flag.
