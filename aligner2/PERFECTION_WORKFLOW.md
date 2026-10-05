# Boundary perfection workflow (from 2026-10-05)

**Read this whole file after every context compaction and at the start of every session that touches the aligner.**
It is the agreed way of working; it overrides older habits recorded elsewhere (HANDOFF.md, NOTES.md, memory) where they
conflict.

## Goal

The system's word boundaries must equal the user's golden labels on every boundary of every captured bundle:
golden labels = system output. Not "better on average" -- every boundary, every edge case.

## CURRENT TASK (resume here after a compaction)

Perfect bundle **b15_pack_025** (the first golden capture) before the next one -- the user (2026-10-05): "see the raw data,
for every single case in every single junction and fix them all, only then we move to the next clip. dont stop until
perfection is reached". A cut is fixed when it lands in the window where it sounds right (<= 5 ms of golden; exact =
<= 1 ms also tracked) -- "sometimes there's a window instead of an exact cut point where it sounds right anyway".
- Ledger: `python -m aligner2.case_ledger summary | open [--cls X] | note CLIP J SIDE "..." | refresh --tag "..."`
  (bench/cache/aligner2/case_ledger.json: every missed boundary, its status, notes on what the raw data showed).
- Inspect: `python -m aligner2.cap_case --clip N --j J` (raw 2 ms data), `python -m aligner2.landmark_lab "CLS"`.
- Score: `python -m aligner2.cap_bench [--add X]`; old sets: `python -m aligner2.verify --add X`.
- Order: largest errors first (coarse misplacements), then junction classes by open count. Every rule change: refresh
  the ledger, check every regression one by one, note it, commit.

## Terms (the user, 2026-10-05 -- keep them straight)

- **CURRENT labels** = the labels the CURRENT SYSTEM generates (our aligner's output, injected into the editor by the
  pipeline). They are NOT the platform's prelabels (whatever the task shows before our injection) -- prelabels play no
  part in this workflow.
- **GOLDEN labels** = the CURRENT labels after the user has finished perfecting every boundary by ear.
- The corrections to learn from = GOLDEN - CURRENT; the boundaries the user left alone are CURRENT == GOLDEN, and gold.

## Phase 1 -- data collection (the user)

The user completes 15-35 bundles (enough to capture almost all edge cases). Per bundle:

1. Run the bundle through the app (app.py) as usual. When the injection script is generated, pipeline.py archives the
   bundle immediately (audio + every pipeline file, incl. `injected_tokens.json`) to `bench/bundle_archive/<bundle>/`;
   it archives again when the next bundle starts.
2. Inject the system's labels into the Pulsar editor. THEN click the **Pulsar Label Capture** extension -> **Save
   CURRENT labels**, *before touching anything*. This is the starting point: the current system's labels as the editor
   shows them (never the prelabels -- clicking it before the injection would capture those; the server warns when a
   CURRENT capture does not carry our injected token ids or differs from injected_tokens.json).
3. Correct every boundary by ear until the whole bundle is golden.
4. (No change notes -- dropped by the user.)
5. Click the extension -> **Save GOLDEN labels**. The server answers with how many boundaries differ from the
   starting point -- a quick sanity check that the right state was saved.

Captures land in `bench/label_captures/<bundle>/` (`current.json`, `golden.json`, plus timestamped copies of every
save, nothing is overwritten). They are matched to the clips by the WAV names in the token ids and by `clipIndex`.
If the CURRENT save was forgotten, `bench/bundle_archive/<bundle>/pipeline/injected_tokens.json` is the fallback
starting point.

### Change notes -- DROPPED (the user, 2026-10-05: "too tiresome, you'll get the context from the data")

No notes will be written: derive every case from the audio, the signals and the CURRENT -> GOLDEN differences.
(The capture server still creates an empty notes file per bundle; ignore it. The format below is kept only in case
the user ever adds a note.)

### Change notes format (unused)

One plain-text file per bundle, created automatically (with the format as a header) on the bundle's first capture:
`bench/edit_notes/<batch>_<bundle>.txt`, e.g. `b24_bundle_042.txt` or `b13_pack_006.txt` -- the capture popup shows
its path. Open it in Notepad. (A file with that name made by hand works too.) One line per change:

    <clip #> | <word before> | <word after> | <what I did> | <why>

- `clip #` as the editor numbers it (first clip = 1). `word before` / `word after` are the two words at the boundary;
  for a clip's first word start use `(start)` as word before, for its last word end use `(end)` as word after.
- `what I did`: e.g. `cut 6 ms earlier`, `end of "the" later ~10 ms`, `split "gonna" into two`.
- `why`: the acoustic / pronunciation reason as heard, in the user's own words: `"the" kept the r of rabbit`,
  `t release belongs to "that"`, `breath, not part of the word`, `frication of s runs into "she"`, `flapped t`, ...
- Free-text lines (starting with `#`) for general observations are welcome.

The same transition (e.g. `the|rabbit`) can need different handling depending on frication, pronunciation, speaker,
noise -- the notes are how those distinctions reach the rules.

## Gold semantics (the user, 2026-10-05)

On captured bundles **every boundary of the golden capture is gold**: an unchanged boundary means the system already
had it right (the user reviewed everything), a changed one is a correction. This is NOT circular -- the current system
genuinely produces golden labels for a large part of the audio. Do not restrict evaluation to the changed boundaries.
(The older gold sets 009 / 026 / 049 / old14 keep their own semantics: see memory "old gold is self-referential".)

## Phase 2 -- rule engineering (Claude)

Loop until system output == golden on every captured boundary:

1. **Measure**: run the current system on all captured bundles; list every boundary that differs from golden
   (tolerance: the editor stores whole ms, so |diff| <= 1 ms counts as equal). Group by junction class (phone classes
   at the boundary, pause vs touching words, word identity) and by the user's notes.
2. **Inspect raw data case by case**: 2 ms signals (loudness, periodicity, zcr, spectral bands, bursts, glottal,
   phone posteriors), the waveform, the user's note for that boundary, and how the rule stage placed it
   (`refine.py` trace: which rule fired). Understand the physical reason before writing anything.
3. **Implement** the fix as an explicit rule / rule modification (no model training -- see memory "no model training").
4. **Run everything**: all captured bundles + the old gold sets + the ear judgments (`python -m aligner2.verify`
   style, plus the captured-gold report).
5. **Regressions are NOT a reason to abandon a change.** Go through every regression one by one, inspect its raw data
   and determine why it happened: a special case, an interaction with another rule, or an existing rule that needs
   modification. Fix those, rerun, repeat until the change is clean or every remaining regression is understood and
   scheduled. Only drop a change when the investigation shows the idea itself is wrong.
6. Record each change (what, why, cases fixed, regressions found and how they were resolved) in
   `bench/cache/aligner2/fullread/NOTES.md` and the version line in `aligner2/HANDOFF.md`; commit.
7. Ship (engine redeploy is automatic; verify engine == local on all boundaries) when the user wants it. Listening
   rounds are optional, never a blocker when the gold data show a clear gain (memory "listening validation protocol").

Keep a running scoreboard: boundaries equal to golden (<= 1 ms) / total, per bundle and overall, and the list of
open cases. Report progress against it.

Overfitting check: rules must be phonetically explainable (a reason a phonetician would accept), never keyed to a clip
or a time. Keep reporting the old held-out sets (049, old14) so a rule that only memorises the captures shows up.

## Open cases (seen before the captures; check them in the golden data)

- Overlapping words in the injected output: b15_pack_025 clip 4, "get" 79.123-79.310 overlaps "what" 79.294-79.451
  by 16 ms (pipeline log "1 overlaps"). Our output must never overlap -- find which step produces it.

## Tools

- `bench/bundle_archive/<bundle>/` -- audio + pipeline files per bundle (pipeline.py archive_bundle).
- `pulsar_label_capture/` -- Chrome extension (load unpacked); popup buttons Save CURRENT / Save GOLDEN; posts to
  app.py `POST /api/capture-labels` (app.py must be running).
- `bench/label_captures/<bundle>/` -- captures; `bench/edit_notes/<batch>_<bundle>.txt` -- the user's change notes (local; not committed: the repo is public).
- `aligner2/captures.py` -- loads captured bundles as benchmark clips (golden + starting labels + notes).
- Standing constraints: Modal A10G only, pay only for processing; credentials stay in local_secrets.json (gitignored);
  never commit client secrets; the repo is public on GitHub -- think before committing anything new that is sensitive.
