# Full read of all 50 clips (render_full, v16 system = soft off)

NOTE (2026-09-24): sections 009-0 .. 009-7 below were SKIMMED at 10 ms/char and partly pattern-matched to earlier
notes ('confirmations'). They are superseded by the deep re-read (zoom.py, 2-4 ms/char, CTC letters, every
boundary checked) that starts at 009-8 and is redone for 009-0 .. 009-7 afterwards. Treat them as hypotheses only.
Deep-read method: toktab.py (exact gold/system times per token) + zoom.py SET_CLIP t0 t1 ms (rows at 2-4 ms,
clip-percentile digits, ctc_top = HuBERT letter argmax per 20 ms frame, '.' blank, '_' word separator).

## 009-0 (first pass, before err row)
- speech_prob (pyannote) is 9 everywhere except true long pauses (>~300 ms, e.g. 8.2-8.8 s): useless below that.
- ctc_wordsep spikes (20 ms) sit between words; ctc_blank long runs = pauses / non-lexical stretches.
- Stop closures inside words ("podcast" /k/, 1.4 s) make loudness dips indistinguishable from word joins.
- '(())' at 8.93 s: wildcard absorbed the start of "only" -> system (())|only 140 ms late (9.47 vs gold 9.33);
  gold puts "only" right after a loudness dip (9.26-9.29) at the rise.
- after "elsewhere" (8.13 s) a low bump 8.16-8.40 (breath/laugh?) then silence; system extended "elsewhere" over it.
- "week ... uh": long low-level decay/noise 3.35-3.85 s between them (levels 1-5); system onset for "uh" matches gold.

## 009-0 (with err row)
- clip starts IN speech ("uh" at 0.00, loudness 7 at t=0): system put first token at 0.27 (err 9). Rule needed:
  if the clip's first frames are already speech-level, first token starts at 0.
- "uh" at 0.00-0.12 is CTC-BLANK (ctc_blank 9, no letters); the letter CTC squeezes U,H right before "we" ->
  uh|we cut 70 ms late. FILLERS ARE BLANK FOR THE LETTER MODEL: speech-level sound + CTC blank = non-lexical.
- AFTER-WORD NON-LEXICAL SOUNDS that gold excludes but system keeps inside the word (all err 9):
  * "week" end 3.28: bump 3.28-3.41, UNVOICED (periodicity 1-2), BRIGHT (centroid 7-8) = breath. CTC blank 9.
  * "elsewhere" end 8.13: bump 8.16-8.40, low periodicity, high centroid/flatness = breath/noise. CTC blank 9.
  * "was" end 11.47: bump 11.52-11.65 VOICED (periodicity 5-6) but LOW centroid (0-1) = hum/"mm". CTC blank 9.
  -> they are 5-15 dB below words, not "quiet" by the 20 dB word-reference test. Word edge should be where the
     word's own sound changes into the non-lexical sound (acoustic change inside the CTC "between" region).
- '(())' wildcard (best-letter emission) ATE the start of "only": (())|only 160 ms late although ctc_wordsep
  peaks exactly at the gold boundary (9.31) and loudness dips 9.26-9.29. Best-letter wildcard is too greedy.
- ctc_wordsep peaks (20 ms) often sit right on gold boundaries even where the system is off (e.g. 9.31).
- "i|thought" 10.0-10.2: fricative-like dip (flatness 9) at 10.03-10.08 but gold "thought" starts 10.21 -
  unclear, possibly label late.
- many continuous errors 10-50 ms at plain joins (you 45, on 44, was 44, a 22, had 21).

## 009-1 (mostly good; pause edges mostly 0-2)
- "monday" end 3.58: voiced (per 5-6) LOW-centroid bump 3.58-3.77 (hum) + CTC blank -> gold excludes, system keeps (err 8).
- before "and" 6.81: 6.56-6.76 low-level BREATH (centroid 8-9, periodicity 2-4, CTC blank), dip 6.76-6.79, word
  rises 6.79+. Gold starts at the rise after the dip; system started 120 ms early inside the breath.
- FALSE PAUSES at short dips (30-60 ms) that gold calls continuous: "thomas|kennedy" (stop closure before /k/,
  gold cut at the burst 10.45), "chief|investment" (/f/ then dip), "wealth|management". System splits them.
- mid-pause breath 19.06-19.17 (between "strategies" and "thank") handled fine (quiet enough).

## 009-2
- more FALSE PAUSES at stop closures between words: "unless|people" (/p/ closure dip 1.76-1.82, gold continuous
  cut at the burst 1.84), "boosters|get" (/g/), "chief|there"-type. Gold = one cut at the END of the closure (burst).
- two fillers in a row ("uh" 6.91-7.33 long, then "uh you know i" after a dip 7.37-7.45): both fillers are CTC-blank,
  system put the 2nd "uh" inside the 1st one's long vowel (err 9). An island split (dip) would place them right.
- "that|it" 13.42 vs gold 13.51: two ctc_wordsep peaks (13.44, 13.55); system took the first; gold near the dip
  13.53-13.57 between them.
- WORD-FINAL WEAK FRICATIVE TAILS: "desserts" gold end 24.37 while loudness is already 0 from 24.31 - centroid
  (7-9) and flatness show the /s/ continues faintly. Loudness (low-freq dominated) misses it; the end is where the
  last sound's own band (HF for fricatives) fades. -> per-band presence (any band above its own noise floor).
- CLIP END "bar": gold ends at 25.62 near the end of the decay (loudness ~2-3); system (steepest fall) at 25.54,
  the START of the decay (err 8). Humans end words at the tail of the decay, starts at the sharp onset.
- 4.55-5.2 / 12.5-13.1 / 19.5-20.4 long pauses: background loudness 2-3, speech_prob 0; pause edges all 0-2 err.

## 009-3
- stop-closure false pauses again: "their|chest" (/tS/ closure 18.83-18.87, gold one cut at 18.87 = end of
  closure), "didn't|think", "report|that" (/t/ + weak /D/ dip, gold 1.96 inside dip).
- BREATH/NOISE BEFORE A WORD, system starts early inside it:
  * "uh" 24.76: 24.44-24.72 mid-level (4-6), aperiodic, flat, centroid 5-7 -> system 24.68 (err 8).
  * "just" 21.33: 21.00-21.18 high-centroid frication (after "is") + 21.18-21.33 mid noise; gold pause until
    21.33, system 21.18 (err 9). CTC blank 9 all along; "just" letters appear ~21.5.
- spelled letters "p e" (PE): system p|e at 8.60 vs gold 8.74 (err 9); ctc_wordsep peak 8.67.
- repeated "i ... i": misplaced (err 6-7).
- long noise stretches inside pauses (9.21-9.56 level 4, flat, bright; 17.54-17.75; 19.51-19.84) are handled
  well when they are between a clear word end and a clear onset.
- clip end "take": gold 26.44 right after the /k/ release; system 26.52 in the trailing noise (err 7).

## 009-4
- WEAK FRICATIVE TAILS cut (confirmed twice more): "because" /z/ 16.48-16.58 + weak tail to 16.67 (gold end),
  system 16.60; "fans" /z/ 7.66-7.76 (loudness 2-4, flatness/centroid 9) -> system made a pause at 7.70, gold
  continuous "fans|and" at 7.77.
- stop-closure false pauses: "some|people" (/p/), "truth|to" (/T/ + /t/ closure; gold cut at the burst 20.46).
- stutter "they they": dip 8.94-8.97 not quiet; gold pause 8.97-9.06, system one cut 8.98 (err 8).
- "and so" at clip start: "and" only 70 ms (0.02-0.09), /s/ frication 0.17-0.37; system put and|so at 0.37
  (vowel onset after /s/) - err 280 ms; ctc_wordsep peak 0.18-0.21 was right before the /s/.
- "your uh opinion" 21.7-22.1: system started "uh"/"opinion" 80-130 ms early inside a dip/decay region.
- long pauses with speech_prob still 9 (5.88-6.26, 19.11-19.74): pyannote misses pauses up to ~600 ms.

## 009-5  *** key pattern: noise next to a word belongs to it ONLY if the word's edge sound is noise-like ***
- POST-WORD EXHALES (aperiodic, flatness 9, centroid 7-9, level 3-5) excluded by gold, included by system:
  "awful" (/l/) end 7.41, breath to 7.65 -> system 7.57 (err 9); "fun" (/n/) end 17.42, breath 17.38-17.62 ->
  system 17.63 (err 9); after "miserable" 18.66-18.83 (inside pause, fine).
- /h/-INITIAL WORD: "horrible" gold starts 5.08 at the start of a LONG aspiration noise (5.00-5.55, flat, bright,
  CTC blank) = the /h/; system started 5.39 inside it (err 9). Same acoustics as breath, opposite verdict.
- => rule from phonetics: an aperiodic noise segment touching a word belongs to that word iff the word's edge
  phone is a fricative / h (s z f v T D S Z h) [weak fricative tails 009-2 "desserts", 009-4 "because","fans"
  also fit]; for stop edges only the short release/aspiration (~<=60-80 ms); vowel/nasal/liquid/glide edges
  never take the noise (it is breath).
- stop-closure false pause again: "it's|time" (/s/ + /t/ closure).
- uncertain token "((there's))" 1.75-2.39 soft/low-centroid speech: system placed it 240 ms late (letters not heard).
- "that's" 10.44: possible /D/ 10.29-10.40 before gold start (gold may exclude a weak /D/).

## 009-6  *** pauses with several silences: pick the silences, not the longest one ***
- "swift's" end 4.66: silence 4.66-4.73, then a VOICED LOW-CENTROID island 4.74-4.90 (hum, CTC blank, not in the
  transcript), then long silence 4.90-5.51. Pause logic took the LONGEST quiet run -> word end 4.97 (err 9, 290 ms).
  Correct: word ends at the FIRST silence after its last-letter evidence; next word starts after the LAST silence
  before its first-letter evidence; non-lexical islands in between belong to the pause (the user's island idea
  applies to all pauses, not only soft tokens).
- the opposite case: "platinum | and | things": "and" is a weak voiced low-centroid island 9.68-9.95 between two
  silences, CTC blank (not recognised) -> system misplaced "and" (err 9). An island that the transcript needs a
  token for must take it -> assign tokens to speech islands monotonically (islands vs tokens).
- post-vowel exhale excluded by gold again: "blah" end 17.06, breath 17.06-17.33 -> system 17.23 (err 9).
- untranscribed speech at clip start (0.00-0.46, other speaker?): first token "you" 0.46; system 0.56.
- likely GOLD ERROR: "spotify ... for": gold pause 14.25-14.30 is actually the /f/ of "for" (flatness 9);
  system cut 14.23 at the /f/ onset looks more correct.
- "or" 8.46 ... "you" 8.79: bright island 8.62-8.79 before "you", unclear.

## 009-7 (confirmations)
- post-STOP long breath: "week" (/k/) gold end 2.94, noise 2.99-3.27 (flat 9, bright) -> system 3.20 (err 9).
  Stop edges take only the short release; long noise after it is breath.
- post-vowel breath: "haiti" end 12.95, breath 12.95-13.21 -> system 13.07 (err 9).
- false pauses at stop closures / weak onsets: "the|kenyan" (/k/), "that|they" (weak /D/), "not|be" (/t/+/b/
  closures, 30-40 ms silence), "to|do" (/d/), "like|the" (/k/+/D/), "a|force" (weak /f/ onset treated as silence).
- sonorant join "people|over": 100 ms late (no landmark).
- "be|able": glottal dip 15.66-15.69 between /i/ and /eI/; gold 15.76 (70 ms later) - possibly gold imprecise.
- mid-pause breath/room noise (7.64-7.94, 18.25-18.56) handled fine when the words' edges are clear.


## 009-8  DEEP READ (20.80 s, 47 tokens)
Token errors >= 20 ms (sys - gold): nuclear|freeze +34, movement.end -33, um.end -23, huge.start +59,
huge|groundswell +26, populist|support -48/-50, support.end -57, was|already +24, that|we +20, we|had +23,
had|to +21, to|stop +79, stop.end -21, no|one +24, how.start +57, go|about +21, about|it -30, and|part +68/+100,
of|this -23, this.end -52, film.start -94, was.end -61 (false pause was|able), imagine.end -64,
particularly|for +40. All other boundaries within 20 ms.

- nuclear|freeze (gold 0.660, sys 0.694): /r/ -> /f/. high_ratio rises 0.638-0.658, zcr rises 0.666, flatness
  1->7 over 0.63-0.67. Gold 0.660 = the frication ONSET (half-way up the high_ratio/flatness rise). CTC: word
  separator 0.674-0.73, letter F only at 0.72-0.74 = the CTC puts its separator INSIDE the /f/, ~40 ms after the
  frication onset, and the letter late in the fricative. System (radius 10 ms around the lexical median) could
  not reach the onset.
- freeze|movement (gold 1.015, sys 1.018, ok): /z/ -> /m/. /z/ frication (flatness 9, high_ratio 9, periodicity
  1-2 = devoiced) 0.958-1.010; frication decays 1.014-1.042; /m/ voicing (periodicity 6-7) from ~1.05.
  Gold 1.015 = where the /z/ frication STARTS to fall (end of the fricative plateau), not the /m/ voicing onset.
  CTC separator frame 1.002-1.018 matched it. Letter CTC also emits the silent final E after Z (0.94-0.96).
- movement.end (gold 1.547, sys 1.514): CTC's last letter T at 1.40-1.42 (!). Strong transient at 1.448
  (burst), aspiration 1.44-1.48 (flatness 6-7, high_ratio 6-7), then a VOICED low tail 1.48-1.544 (periodicity
  7-8, flatness 2-5, centroid 3-4, low_ratio 9, loudness 5-6), then breath 1.54-1.99 (flatness 7-8, centroid 7-8,
  periodicity 2-3, loudness 4 falling to 1). Gold end 1.547 = END OF VOICING (periodicity drop 1.544) - the voiced
  tail after the burst is kept, the aperiodic breath is not. System ended at a loudness step (6->5) in the tail.
- um.start (gold 2.012, ok): loudness 0 at 2.000-2.016 then sharp rise; gold one frame before the rise.
- um.end (gold 3.023, sys 3.000): long hum (centroid 2, flatness 0, low_ratio 9). Loudness 8 until 2.93, slow decay
  7-6 (2.93-3.01), 5 (3.012-3.024), 4 (3.024-3.048), 3, 2, 1 by 3.09. Periodicity stays 5-7 until ~3.08 (voicing
  continues through the decay). Gold 3.023 = mid-decay (level 5->4), NOT the end of voicing -> contrast with
  'movement' (end of voicing). Need dB values to see if both are the same dB-above-floor level.
- huge.start (gold 3.243, sys 3.302): silence (loudness 0) 3.15-3.244, then /h/ aspiration from 3.246
  (flatness 8-9, centroid 7-8, high_ratio 8, zcr 2-4, periodicity 1). Gold = first frame of the rise out of the
  silence floor. System started 60 ms in (loudness level 5). CTC: blank, then 'A' at ~3.32 and a separator
  3.36-3.40 (CTC hears 'a' in the /h/+vowel?), no H. The /h/ is quiet relative to the word -> the 20 dB
  word-reference quiet test calls it silence. Word STARTS after silence should be at the rise out of the floor.
- huge|groundswell (gold 3.903, sys 3.929): /dZ/ -> /g/. Frication of /dZ/ (flatness 7-8, high_ratio 6-7) 3.852-3.89,
  decays 3.892-3.905; voiced transition (periodicity 5-6) 3.90-3.92; /g/ closure (loudness 7->6, voiced) 3.920-3.945;
  release transient 3.932-3.936(?) and letters G at 3.962. CTC separator 3.882-3.92. Gold 3.903 = END OF FRICATION
  (same as freeze|movement). System 3.929 sat on the mfcc_change peak at the closure.
  => pattern so far (3/3): a fricative next to the boundary defines it - cut at the frication edge facing the
     other word (onset for word-initial fricatives, offset for word-final ones).
- dB levels (zoom footer: re clip p99 / re local floor = min of 50 ms-smoothed loudness within +-1 s):
  movement.end gold -31 / +22 (sys -24 / +29); um.end gold -35 / +22 (sys -25 / +32); huge.start gold -54 / +3
  (sys -25 / +32). The system's pause edges sit exactly at the word-ref -20 dB crossing (~-24 re p99); gold ENDS
  are 7-10 dB deeper, gold STARTS at the rise out of the floor (+3). Breath after 'movement' is +18..+21 re floor,
  i.e. almost as loud as the gold end level -> a dB threshold alone cannot separate them; the voiced->aperiodic
  change (periodicity drop + flatness/high_ratio rise at 1.544, transients 1.544-1.568) is what marks the end.
- movement word inspected whole: CTC letters M 1.04, O 1.12, V 1.164, E 1.18-1.20, M 1.26, E 1.32, N 1.34, T 1.38,
  separator 1.42-1.46. Acoustic burst 1.448-1.46 + aspiration to 1.47, then the voiced tail to 1.544. The CTC
  letters run ~50-100 ms AHEAD of the acoustics at the end of this word.
- of|populist (gold gap 4.795-4.826 = the /p/ closure): of.end at the loudness minimum (+8 re floor), populist.start
  4.826 exactly at the /p/ BURST (transient 9 at 4.822-4.832), +6 re floor. System 4.788 / 4.832 (fine).
  Stop-initial word starts at its burst; the closure silence went to the gap here (vs. continuous cuts at the
  burst in other clips - both put the start at the burst).
- populist|support (gold 5.424, sys 5.377, -48): /...st s.../ = one continuous frication 5.29-5.44 (flatness 8-9,
  zcr 7-8, loudness 8-9, NO closure dip, no clear /t/ burst; tiny transient 5.372). CTC: S 5.32, separator
  5.38-5.40, S 5.40, U 5.46, P 5.48. Vowel of 'support' starts 5.44 (low_ratio 0->9, centroid 9->4). Gold 5.424
  sits on an mfcc_change peak INSIDE the frication (5.404-5.428, value 7) = a change of fricative quality; the
  system took the CTC separator (middle). Landmark inside a geminate fricative = spectral-shape change, not level.
- support.end (gold 5.989, sys 5.932, -57) / everyone.start (gold 6.003, sys 6.010): 5.87-5.99 is a low
  (-23..-33 re p99, +15..+26 re floor), weakly periodic (2-4), NON-noisy (flatness 2-3) stretch = the /rt/ tail
  (glottalised /t/?). 'everyone' starts with a glottal attack: transient 9 at 5.996-6.004, glottal crest 9.
  Gold treats it as ~continuous (14 ms gap) ending 'support' right before the attack; the system called it a
  78 ms pause because it is 20 dB under the word (-23 re p99). Minimum between the words is +15 dB over floor
  -> not a silence. Pause requires reaching near the floor; word-relative -20 dB is not a pause test.
- was|already (gold 7.146, sys 7.170, +24): /z/ -> vowel. /z/ frication plateau 7.07-7.125 (flatness 9, high_ratio
  9, devoiced), drop at 7.126-7.136, a last small frication bump 7.136-7.144, then a weakly voiced, half-noisy
  transition (periodicity 3, flatness 5-6) until voicing builds 7.175-7.21. CTC: S 7.05-7.08, separator 7.08-7.14,
  A only at 7.24. Gold = end of the LAST frication (7.146 = end of the bump). System = voicing build-up.
  -> 4th fricative case: gold at the frication edge (end), again.
- already|convinced (gold 7.670, sys 7.686, +16): voicing stops 7.646 (periodicity 5 -> 2), loudness only drops
  8 -> 6 (dB>floor stays >= 27: NOT silent), /k/ BURST transient 9 at 7.684-7.690, aspiration 7.688-7.722
  (flatness 7-9), vowel ~7.74. Gold is 16 ms BEFORE the burst (between voicing end and burst); system at the burst.
  Within label precision; gold seems to be at 'start of the /k/' (~burst - 15 ms).
- convinced|that (gold 8.125/8.127, sys 8.115/8.117, ok): 'convinced' final /s/ is WEAK (+12..+15 dB over floor,
  flatness 9, zcr 8-9) until ~8.12, then a near-floor stretch 8.118-8.146 (+0..+6 dB, still flat) = closure,
  then transient 8 at 8.154-8.158 and 'that' vowel. Gold starts 'that' at the START of the near-floor closure
  (the /D/ realised as a stop: closure + release), not at the release. Level at the cut: +7..+12 dB over floor.
- that|we (gold 8.249, sys 8.269, +20): /t/ (unreleased/glottal) -> /w/. No closure silence; small loudness dip
  8.206-8.214; glottal crest peak 8.278-8.286; transients 8.282-8.29, 8.302. CTC: T 8.222-8.24, separator
  8.24-8.28, W 8.28. Gold = separator START; system = separator middle. No clear acoustic landmark at 8.249.
- we|had (gold 8.362, sys 8.385, +23): /i/ -> /h/. Periodicity falls to 1-2 around 8.37, flatness rises 5->7
  gradually 8.29-8.37, loudness 7 -> 6 only at 8.394. CTC separator 8.35-8.39, H 8.39-8.43. Gold ~ voicing loss
  (start of the /h/ breathiness); system later.
- had|to (gold 8.579, sys 8.601, +21): /d/+/t/ = one closure with a VOICE BAR (low_ratio 9, loudness 7, +40 dB
  over floor: a voiced closure is NOT quiet) 8.55-8.596, /t/ burst transient 9 at 8.596-8.61. Gold 17 ms before
  the burst (~closure middle), system at the burst.
- to|stop (gold 8.637, sys 8.716, +79): /t/ burst 8.596-8.61 (transient 9, glottal 9), then CONTINUOUS voiceless
  frication to 8.80+ (flatness 9, zcr 8-9, periodicity 1-2: 'to' has no voiced vowel). Inside the noise:
  formant_vel 9 at 8.634-8.666 and a low_ratio bump 8.646-8.66 (= devoiced vowel of 'to'), low_ratio -> 0 from
  8.676 (= pure /s/). CTC: T 8.596-8.636, O 8.656-8.676, separator 8.676-8.716, S 8.756+. Gold 8.637 = end of the
  /t/ aspiration / start of formant movement (~40 ms after the burst). System took the CTC separator (8.716).
  The CTC's letters in this devoiced cluster are ~40-80 ms late.
- label-precision note: already|convinced (-16), had|to (-17): stop-initial words in continuous speech start
  ~15-20 ms BEFORE the burst (inside the closure); of|populist (after a gap) exactly at the burst; convinced|that
  at the closure START. Closure assignment is inconsistent in gold -> 15-25 ms scatter here is label noise.
- stop.end (gold 9.226, sys 9.206, -21): /p/ BURST transient 9 at 9.184-9.196 (glottal 8 just before), then
  aspiration 9.196-9.25 (flatness 8, high_ratio 6, zcr 2-3) decaying to the floor by 9.245. Gold keeps the burst +
  ~30 ms of aspiration and ends at +14 dB over floor (mid-decay); system ended at +28 (word-ref -20 dB).
- this.start (gold 9.428, ok): rise out of the floor + transient 9 at 9.428-9.436 (/D/ as a stop again). +8 dB
  over floor at the gold start. Pause 9.25-9.42 is pure floor (room noise, flatness 6-7), no breath.
- this|arms (gold gap 9.860-9.886, sys 9.844/9.894, ok-ish): 'this' /s/ frication (flatness 9, zcr 9, high_ratio 9)
  runs until 9.884; loudness at its weakest (level 5, +24..+27 over floor) 9.844-9.888; arms starts exactly at the
  frication OFFSET 9.886 (zcr/centroid drop, low_ratio -> 9). Gold ends 'this' 9.860 INSIDE the weak /s/ and
  leaves a 26 ms gap = the gold does not always keep the weak fricative tail (vs. 'desserts' in 009-2 where it did).
- CAVEAT on dB>floor: the floor is the min within +-1 s; for 0.0-1.4 s of this clip there is no silence in the window,
  so 'floor' = the quietest speech and dB>floor reads low (3-8 = 9-24 dB) during speech. Use a longer window or the
  clip's global floor for pause tests.
- said.start (gold 0.000, sys 0.006): clip starts inside the /s/ (flatness 9, zcr up to 9, loudness 7-8 at t=0);
  pyannote speech_prob 0 for the first 10 ms (warm-up), then 9. Gold = clip start.
- said|the (gold 0.201, sys 0.191): /d/+/D/ closure = loudness dip 8 -> 7 at 0.196-0.204; gold at the dip CENTRE;
  mfcc_change peaks 0.194-0.198 and 0.208-0.218; /D/ release transient 0.214-0.23. System at the dip start (-10).
- the|nuclear (gold 0.326, sys 0.317): nasal murmur onset: centroid falls to 2 at 0.322, flatness to 1-2 at 0.326,
  periodicity rises to 6 from 0.30. CTC separator 0.30-0.34, N 0.34-0.38. Gold = murmur onset (centroid/flatness
  fall), system 10 ms before.
- race.end (gold 10.587, sys 10.578): /s/ frication loud (8-9) until 10.558, loudness falls 7 -> 5 by 10.586, then the
  frication continues QUIETLY (loudness 4-3, zcr 8-9, +20 over floor) to ~10.654 and turns into a long breath
  10.6-11.0 (flatness 7-9, centroid 9 -> 5 falling slowly, high_ratio 9 -> 4, low_ratio rising, +6..+15 over floor,
  ssl_change bump 10.89-10.93). Gold ends 'race' where the LOUD part of the /s/ falls (-29 re p99, +27 re floor);
  the quiet frication tail + breath are excluded (same as 'this' 9.860). System -9 ms: fine.
  speech_prob stays 9 through this 460 ms pause.
- but.start (gold 11.054, sys 11.046): loudness at floor 10.994-11.042; first weak transient 11.05-11.058 (+11 dB
  over floor) = gold; main onset transient 9 at 11.07-11.078. CTC B 11.05-11.07. Gold = the first event out of
  the floor (the /b/ burst), not the loud onset.
- but|no (gold 11.183, sys 11.189, ok): glottalised /t/ (glottal crest 9 at 11.12-11.144 = creak), loudness dip 6 at
  11.156-11.184, nasal (centroid 2-3, low_ratio 9) from ~11.15, periodicity dip 11.18-11.19 then rises; gold at the
  end of the dip / periodicity trough.
- no|one (gold 11.412, sys 11.434, +24): /oU/ -> /w/, loudness 9 throughout, no dip. formant_vel rises at 11.404
  (active to 11.456 = F2 fall into /w/), high_ratio and centroid dip to 3 from 11.396-11.408. CTC separator
  11.40-11.44, O 11.50, N 11.52. Gold = ONSET OF THE FORMANT MOVEMENT; system = separator middle.
- one|could've (gold 11.605, sys 11.623, +18): periodicity dip 11.572-11.58, then voiced low murmur (periodicity 6-7,
  centroid 2, flatness 2-3) 11.584-11.62, /k/ burst transient 9 at 11.628-11.64, aspiration 11.644-11.70. Gold 25 ms
  before the burst (inside the voiced murmur/closure); system just before the burst.
- could've|imagined (gold 11.828, sys 11.847, +19): no level landmark (loudness 8-9 throughout, voiced); CTC has
  no V/E for 'could've' (C O U L D then separator 11.78-11.82, I 11.84). high_ratio minimum 11.82-11.832,
  mfcc_change peak 11.832-11.84, ssl_change peak ~11.82. Gold ~ mfcc peak - 7 ms, system +12.
- tally of continuous-cut landmarks so far (009-8): frication onset (nuclear|freeze); frication end
  (freeze|movement, huge|groundswell, was|already); spectral change inside a geminate fricative (populist|support);
  nasal-murmur onset (the|nuclear, but|no); formant-movement onset (no|one); voicing loss (we|had); closure centre
  (said|the); closure start (convinced|that); 15-25 ms before a burst (already|convinced, had|to, one|could've);
  aspiration end after a burst (to|stop); no clear landmark (that|we, could've|imagined).
- imagined.end (gold 12.570, sys 12.552) / how.start (gold 12.581, sys 12.638, +57): /n/ murmur until ~12.49; /d/
  release at 12.492-12.508 (transient 9, glottal crest 9, mfcc_change 8); near-floor dip 12.508-12.532 (the quietest
  point within +-1 s); a short VOICED blip 12.528-12.548 (periodicity 3-7) = /d/ release vowel; then the /h/ of
  'how' from ~12.55 (flatness 7-8, high_ratio 8, zcr 3-5, periodicity 1-2, loudness level 5 = -28 re p99,
  +12..+18 over floor). CTC: separator 12.40-12.46 (!! 'imagined' ends 170 ms early in CTC), H only at 12.66,
  O 12.72, W 12.74. Gold keeps the voiced blip in 'imagined' (ends 12.570, ~20 ms into the /h/ noise) and starts
  'how' at 12.581 in the /h/ noise. System: 'imagined' ends at the blip end (12.552, good) but calls the /h/ a
  pause (quiet by word-ref -20 dB) and starts 'how' at the loudness step 5 -> 6 (12.638). /h/-initial word
  eaten by the pause test again (3rd case with huge 3.243, horrible 009-5).
- how|to (gold 12.833, sys 12.823, ok): flapped /t/: loudness dip 9 -> 8 and periodicity dip 1-2 at 12.834-12.844,
  release transient 12.856. Gold = start of the dip. CTC separator 12.80-12.84, T 12.84.
- to|go (gold 12.925, sys 12.905, -20): loudness 8 -> 7 at 12.916 (closure start), 6-5 at 12.95-12.96, voiceless
  part 12.964-12.978 (periodicity 1-2), /g/ BURST transient 9 at 12.98-12.988; formant_vel active from 12.948,
  ssl_change 9 at 12.94-12.958. CTC separator 12.90-12.94, G 12.96. Gold = CLOSURE START (~60 ms before the burst).
- go|about (gold 13.094, sys 13.115, +21): vowel -> vowel with a GLOTTAL ATTACK: glottal crest 9 at 13.088-13.096,
  transient 6 at 13.092-13.096, periodicity dip 1-2 at 13.094-13.10. Gold exactly on it. CTC separator 13.06-13.10,
  A 13.12. System 21 ms late. Vowel-initial words: the glottal attack is the landmark.
- about|it (gold 13.457, sys 13.427, -30): glottalised /t/ of 'about': glottal crest 9 over 13.424-13.464, periodicity
  1-3 from 13.40, release transient 9 at 13.448 (+ flatness rise 13.44-13.452, mfcc_change peak 13.444-13.448),
  then 'it' voicing (periodicity 4-5) from 13.456. CTC: T 13.384-13.40, separator 13.42-13.44, I 13.46. Gold = after
  the release, at the vowel voicing onset (the /t/ closure AND release stay in 'about'); system = CTC separator =
  start of the glottal closure.
- it.end (gold 13.543, sys 13.542, ok): voicing ends 13.544 (periodicity 5-6 -> 3), then an aperiodic decay to the floor
  by 13.63 and a lone transient 8 at 13.652-13.66 (late /t/ release or click). Gold = END OF VOICING (+28 over floor);
  the decay and the late transient are excluded.
- um.start (gold 14.245, sys 14.236, ok): pre-word CLICK/lip noise 14.216-14.24 (transient 9, glottal 9, flatness 8-9,
  centroid 8, mfcc_change 9) then the vowel (centroid 6-5, periodicity 3-4) and loudness 8 by 14.256. Gold starts
  AFTER the click (at the vowel, loudness level 5, +28 over floor); a faint inhale 14.10-14.17 (level 1-2, flatness
  6-7) is also excluded. speech_prob rises 14.156-14.21.
- um.end (gold 14.711, sys 14.704, ok): hum (centroid 2, flatness 1-2, low_ratio 9) steps down at 14.70-14.73 (7 -> 6
  -> 5, glottal crest 7-8 at 14.69-14.72, mfcc_change 7 at 14.724-14.732), then a QUIETER hum continues to ~14.78
  (level 4-5, +15..+20 over floor, periodicity 3-5) and fades by 14.84. Gold ends at the step, excluding the quiet
  trailing hum (same as um.end 3.023). Contrast: 'movement' kept a voiced tail at level 5-6 (vowel-like, centroid
  3-4) and ended at voicing end. Difference = level of the tail (hum tail ~15 dB under the body; movement tail
  ~10 dB under) and/or a clear step + creak at the gold end.
- and.start (gold 15.051, sys 15.044, ok): floor until 15.03, onset with transient 9 at 15.046-15.058, glottal rising,
  flatness 7-8 (noisy attack), mfcc_change 9 at 15.03-15.054; gold at loudness level 4 (mid-rise).
- and|part (gold 15.310/15.312, sys 15.378/15.412, +68/+100) - whole of 'part' read (15.28-15.76):
  /n/ of 'and' (centroid 2, flatness 1-2, periodicity 6-7, loudness 9) until 15.30; VOICING BREAK 15.30-15.308
  (periodicity -> 1, glottal 4); voiced low murmur 15.312-15.39 (periodicity 4-7, loudness 7 = only ~5 dB under the
  nasal, flatness 0-1, centroid 2, low_ratio 9); /p/ BURST 15.388-15.408 (transient 9, glottal 9, mfcc_change 8-9);
  then 180 ms of NOISE 15.41-15.59 (flatness 8-9, centroid 6-9, high_ratio 7-9, zcr 4-6, loudness 5-6, low_ratio
  falling 5 -> 1) = very long aspiration; vowel /A/ 15.596 (loudness 7-9, flatness 4, formant_vel 6-9 just before);
  /t/ glottalised 15.724-15.748; 'of' from 15.752. CTC: P 15.484-15.50 (in the noise), A 15.62, R 15.64-15.68,
  T 15.70. Gold 'part' = voicing break + murmur (closure) + burst + aspiration + vowel + /t/: the word starts at the
  END OF THE PREVIOUS SOUND (closure onset). System gave the murmur to 'and', called the loudness drop to level 5-6
  after the burst a pause (-23 re p99) and started 'part' after the burst.
- part|of (gold 15.753, ok): glottalised /t/ release 15.724-15.748 (transients 3-4, glottal rising), 'of' vowel from
  15.752. Gold = vowel onset after the release (release stays with 'part'), same as about|it.
- of|this (gold 15.890, sys 15.867, -23): /v D/ = loudness dip 8-9 -> 7 with periodicity 3 over 15.872-15.908,
  release 15.90-15.912 (transient 5, glottal 8), vowel from 15.912. Gold = middle of the dip; system = dip start.
- this|film (gold end 16.129, gap, film 16.172; sys 16.078 for both, -52/-94) at 2 ms: strong /s/ (zcr 7, centroid 9,
  loudness 8) until 16.064-16.084; still sibilant (centroid 8, zcr 5-7, loudness 6-5) to ~16.14; weak labiodental
  stretch 16.14-16.166 (centroid 7, zcr 3-4, loudness 5-4, low_ratio bump 9 at 16.146-16.156, periodicity 3);
  TRANSIENT 6 + GLOTTAL CREST 9 at 16.168-16.174; vowel 16.19 (flux 9, loudness 8-9). CTC: separator 16.062-16.098,
  F 16.14-16.16. Gold: 'this' ends where the sibilant weakens (16.129, loudness 6 -> 5), 43 ms gap over the weak
  /f/ friction, 'film' starts AT the transient (16.172). System cut at the end of the strong /s/ and gave the
  whole weak stretch to 'film'. The CTC F lies inside the gold gap -> CTC letter times are not edge anchors.
- (tool) at.py SET_CLIP t0 t1 step: numeric table in real units: dB re p99, dB over local floor (+-1 s), dB over
  the clip's global floor (2nd pct of 50 ms-smoothed loudness), periodicity, flatness dB, log-centroid, high/low
  ratio dB, zcr, transient, glottal, mfcc_change, formant_vel, ssl_change, P(sep), P(blank), CTC top + prob.
- film.end (gold 16.602, sys 16.588, ok): /m/ with creak (glottal crest 9 at 16.508-16.56); loudness steps 7 -> 6 -> 5
  around 16.59-16.60 (mfcc_change peak 16.604-16.612), then a slow /m/ decay to the floor by ~16.70. Gold at the
  step (+32 over floor), trailing nasal decay excluded (like the um ends). The floor here is a LOW-FREQUENCY HUM
  (centroid 0-1, low_ratio 9) and periodicity reads 2-6 IN SILENCE -> periodicity is unreliable below ~+10 dB.
- was.start (gold 16.962, sys 16.964, ok): flatness drops from noise level to tonal (6 -> 0) at 16.948-16.96 = voicing
  onset of /w/; loudness rises from 16.96; mfcc_change peak 16.964-16.972; creaky onset (glottal 9) 16.968-17.02;
  transient 9 at 16.988. Gold at the flatness drop / start of the rise (+21 over floor).
- was|able (gold 17.244, sys 17.180 + 17.240, false pause) at 4 ms (numbers): /z/ strong frication 17.10-17.164
  (high_ratio -1 dB, zcr 0.6, loudness -9..-12 re p99); weakens 17.164-17.172 (high_ratio -8, zcr 0.2); weak tail
  17.176-17.236 (loudness -21..-30 re p99 = +28..+40 over floor, high_ratio -4..-11, centroid 6.7-7.8, periodicity
  0.2-0.4) with a small noise burst (transient 5.9) at 17.212 and transients ~3 at 17.232-17.236; vowel of 'able'
  from 17.240-17.248 (periodicity 0.40 -> 0.58, loudness -20 -> -7, high_ratio -> -21). CTC separator 17.14-17.20.
  Gold: no pause, 'was' keeps the whole weak /z/ tail, 'able' starts at the voicing onset. System: word-ref -20 dB
  crossing (17.180) -> false 60 ms pause. The tail is the SAME sound fading (continuous with the /z/), 30+ dB over the
  floor; a breath after a word is a DIFFERENT sound (spectral change) and is excluded.
- able|to (gold 17.519, sys 17.517, ok): glottal crest 9 at 17.51-17.52 (glottalised closure, loudness dip 8 -> 7 at
  17.498-17.504), /t/ BURST transient 9 at 17.522-17.53, aspiration from 17.516-17.532 (flatness rises). Gold 3 ms
  before the burst.
- to|imagine (gold 17.648, sys 17.627, -21): 'to' = burst 17.522 + voiceless aspiration 17.53-17.61 (flatness 9,
  periodicity 1-2, loudness level 6-7, ~80 ms) + voicing onset 17.608-17.624 (flatness 8 -> 3, formant_vel 7 at
  17.608-17.626, loudness jump 6 -> 9 at 17.624). Gold gives 'to' 22 ms of the vowel and starts 'imagine' at a
  glottal-crest peak (7 at 17.646) + mfcc_change peak (17.642-17.646) = glottal onset of the vowel-initial word.
  CTC: T 17.54, O 17.58-17.60, separator 17.62-17.66, I 17.68. System at the voicing onset.
- imagine.end (gold 18.490, sys 18.426, -64): /n/ steps down at 18.412-18.436 (loudness 7 -> 5, periodicity dip,
  transient 5, glottal bump, mfcc_change + ssl_change peaks at 18.432) = system end; the /n/ then continues quieter
  (level 5 to 18.48, 4 to 18.504, 3 to 18.53) and fades to the floor by 18.58 (ssl_change bump 18.536-18.572 during
  the fade). Gold keeps 60 ms of the quieter nasal, ends at -31 re p99. Contrast 'film' (16.602) where gold ended at
  the step: SAME LEVEL (-29 vs -31 re p99), different time because the decays differ in shape.
- *** LEVEL AT GOLD PAUSE-ENDS (dB re clip p99) in 009-8: movement -31, um -35, support -33, it -31, um -33,
  this(9.86) -29, race -29, this(16.129) -28, film -29, imagine -31, of(4.795) -29 (/p/ closure), stop -42
  (burst+aspiration decaying). i.e. -28..-35 re p99 in 11 of 12 cases. The system's ends sit at -23..-25 (word-ref
  -20 dB). Gold starts after pauses vary with the onset type: -28..-31 for gradual onsets (everyone, how /h/, um,
  and, film, populist), -40..-54 at the very first rise for abrupt ones (was -40, but -44, this -49, particularly -52,
  huge -54).
- particularly.start (gold 18.925, sys 18.926, ok): /p/ burst transient 9 at 18.92-18.932, loudness rises from
  18.924. Before it (18.84-18.92) a faint noise at +0..+3 over the floor (flatness 6-9, centroid rising, zcr 2-5)
  - excluded. Gold at the burst (+13 over floor).
- particularly|for (gold 19.563, sys 19.602, +40): creak at the end of the /i/ (glottal crest 8-9 at 19.538-19.556,
  ssl_change peak 19.54-19.56); at 19.558 loudness 9 -> 8, periodicity dip, centroid 4 -> 3, high_ratio dips; then
  the /f/ builds GRADUALLY: flatness 5 -> 7 (19.57-19.59), high_ratio 5 -> 7 (19.582-19.598), zcr from 19.598,
  strongest 19.638-19.678; vowel /O/ from ~19.69. CTC: Y 19.522-19.56, separator 19.562-19.60, F 19.642-19.66.
  Gold = the FIRST change after the vowel (end of creak, 19.563) = separator START; system = separator middle
  (19.602, where zcr starts). For a gradually building fricative the gold takes its earliest onset.
- for|one (gold 19.823, sys 19.825, ok): /r/ -> /w/, loudness steady; formant_vel 6 at 19.794-19.814 and 4-5 at
  19.83-19.846, glottal crest 7 at 19.822-19.838. CTC separator 19.76-19.80.
- one|person (gold 20.071, sys 20.076, ok): /n/ murmur runs straight into the /p/ burst (loudness 7, no silent
  closure), glottal crest 9 at 20.066-20.076, BURST transient 9 at 20.072-20.082. Gold at the burst.
- person.end (gold 20.614, sys 20.620, ok): /n/ steps 6 -> 5 at ~20.606 (gold, -27 re p99, +32 over floor), quieter nasal
  to ~20.69 with end creak (glottal 7-8 at 20.656-20.684), floor from 20.716. Trailing quiet nasal + creak excluded.
  (speech_prob falls only at 20.672-20.688; formant_vel 9 at 20.744-20.764 IN SILENCE = LPC on noise, meaningless.)
- groundswell|of (gold 4.664, sys 4.670, ok): glottal onset of vowel-initial 'of': log_f0 jump (pitch irregularity)
  at 4.66-4.664, glottal crest 7 at 4.648, transient 4 at 4.652. CTC separator 4.644-4.684, O 4.684.
- everyone.end (gold 6.684, sys 6.674, ok): /n/ voicing ends 6.666-6.69, transient 9 at 6.654-6.666, flatness 1 -> 9
  over 6.654-6.69, centroid 2 -> 7 over 6.67-6.686, formant_vel 9 at 6.67-6.69, then a 260 ms BREATH 6.69-6.95
  (flatness 8-9, centroid 6-8, high_ratio 7-8, zcr 2-4, -32..-40 re p99, +13..+18 over floor, speech_prob 9).
  Gold 6.684 = when the voiced->noise change is complete (centroid 7, flatness 9); breath excluded.
- was.start (gold 6.954, ok): flatness 9 -> 0 at 6.946-6.962 (breath -> tonal voicing), formant_vel 8 at 6.946-6.966,
  glottal crest 9 at ~6.96, loudness rise from 6.956. +13 over floor.
- arms|race (gold 10.230, ok): /z/ -> /r/: centroid drops 8 -> 4 at 10.232-10.238, flatness 8 -> 6, zcr 4 -> 2,
  loudness 7 -> 8, mfcc_change peak 10.23-10.236. Gold = FRICATION OFFSET (5th case of the fricative edge).

### 009-8 summary (all 94 boundaries read)
- Fricative edges (8 cases) decide continuous cuts: freeze|movement, huge|groundswell, was|already, arms|race
  (frication OFFSET for word-final fricatives), nuclear|freeze, particularly|for (frication ONSET for word-initial
  ones; for a gradual build-up the earliest change). The CTC separator/letters sit 20-60 ms inside the fricative.
- Vowel-initial words after a vowel/voiced sound: GLOTTAL ATTACK (glottal crest, transient, periodicity dip, log_f0
  jump) = gold (go|about, groundswell|of, to|imagine); after a /t/ release: vowel voicing onset (about|it, part|of).
- Glide onsets: formant_vel onset (no|one). Nasal onsets: centroid/flatness fall (the|nuclear).
- Stops: bursts are reliable landmarks (transient 9). Stop-initial word after a pause starts at the burst (populist,
  particularly, but, this) or at the first rise; in continuous speech the gold cut lies between the closure onset
  and the burst (closure start: to|go, and|part, convinced|that; 15-25 ms before burst: had|to, already|convinced,
  one|could've; at burst: one|person, able|to). Stop-final words keep their release (about|it, part|of, stop.end
  keeps burst + ~30 ms aspiration).
- FALSE PAUSES from the word-ref -20 dB quiet test: support|everyone (glottalised /rt/ tail +15..+26 over floor),
  was|able (weak /z/ tail +28..+40 over floor), and|part (post-burst aspiration level 5-6), imagined|how (/h/ noise).
  None of them reach the floor. Gold pauses in this clip always reach < ~+15 dB over the floor OR are tiny gaps
  between two fricatives (this|arms 26 ms, this|film 43 ms, support|everyone 14 ms).
- PAUSE-EDGE LEVELS: gold ends at -28..-35 re p99 (11/12), system at -23..-25. Gold starts at the first rise for abrupt
  onsets (-40..-54) and ~-30 for gradual ones. /h/-initial words start at the aspiration onset (huge, how).
- NON-LEXICAL: breaths after words (movement 1.54-1.99, everyone 6.69-6.95, race 10.6-11.0) and pre-word clicks
  (um 14.216) and faint inhales are excluded; trailing quiet hums/nasal decays after a clear step are excluded
  (um x2, film, person) except 'imagine' (60 ms kept; same end LEVEL -31 as the others).
- CTC facts: letters can be 50-170 ms off the acoustic edges (movement T 100 ms early, imagined separator 170 ms early,
  to|stop letters 40-80 ms late, film F inside the gold gap); silent letters are emitted (freeze E); contractions
  lose letters (could've -> COULD). The separator is a good 'somewhere near here' prior, not an edge.
- Signal caveats: dB>floor with a +-1 s window is wrong where no silence is nearby; periodicity is unreliable near
  the floor (hum floor reads periodic); formant_vel is noise in silence; speech_prob stays 9 through 250-460 ms pauses.

## 009-0  DEEP RE-READ (27.54 s, 117 tokens)
- uh (gold 0.002-0.125) | we (sys uh 0.136-0.198, we 0.199; +134/+73): the clip starts IN the filler: breathy schwa
  (flatness 7, centroid 5-6, periodicity 4-5, loudness level 7 = -13 re p99) with creak 0.048-0.096 (glottal 6-7,
  periodicity dip 1-2 at 0.044-0.08). Loudness trough (level 5, +9..+12 over floor) 0.088-0.132 with a GLOTTAL PEAK 8
  at 0.124-0.128 and transient 3 at 0.128 = gold uh|we. Then /w/: log_f0 rising 0.136-0.188, mfcc_change 8 at
  0.164-0.168, transient 5 at 0.172, low_ratio -> 8-9 and centroid -> 2 by 0.18-0.20, voicing 5-8 from 0.20.
  CTC: all blank until W at 0.22 (the filler is CTC-blank). speech_prob 0 only for the first 8 ms.
  System did not start at 0 and squeezed 'uh' into the /w/ onset. Correct structure: filler = from the clip start
  (sound already present) to the loudness trough/glottal break before the first lexical word's letters.
- we|didn't (gold 0.303, sys 0.321, +18): lenited /d/ - loudness 9 throughout, no closure dip, periodicity 7-8.
  Transients 3 at 0.28 and 0.296-0.30, 2-3 at 0.336-0.344; mfcc_change 5 at 0.328-0.344; ssl_change 6 at 0.32-0.344.
  CTC separator 0.296-0.316, D 0.32. Gold = separator start / small transient; system = separator end. No landmark.
- didn't|say (gold 0.478, sys 0.526, +48): /n/ (glottal 8 at 0.42-0.424) until ~0.48; NO /t/ closure or burst (t
  merged); voicing falls 0.484-0.516 while frication rises: flatness 5 -> 9 (0.484-0.508), zcr 1 -> 9 (0.492-0.516),
  centroid and high_ratio up, low_ratio down from 0.492; transients 3 at 0.496-0.504. CTC: N 0.42-0.46, ' 0.46,
  T 0.48-0.52 (INSIDE the /s/), separator 0.52-0.54, S 0.56-0.58. Gold = FRICATION ONSET (just before it); system =
  CTC separator, 50 ms inside the /s/. (Same as nuclear|freeze, to|stop.)
- (tool) toktab/zoom now show whether each gold boundary was HUMAN-MOVED (H) or ACCEPTED from the earlier system (.).
  009-0 tokens 0-15 are all accepted except uh (HH); many later ones (16-34, 38, 42) were moved by a person.
- say|it (gold 0.632/0.634 ACCEPTED, sys 0.702/0.703, +70): /s/ ends 0.598, vowel /eI/ from 0.606, loudness 9 from
  0.626; mfcc_change peak 7 at 0.602-0.61 (/s/->vowel) and 8 at 0.726-0.73; ssl_change 7 at 0.686-0.698; glottal
  crest 7 at 0.714-0.726 (creaky onset of 'it'); log_f0 flat 6 from 0.618 to 0.726 then drops; transient 3 at
  0.618-0.622. CTC: A 0.622-0.64, Y 0.64-0.66, separator 0.68-0.70, I 0.702, T 0.72. Gold gives 'say' only 28 ms of
  vowel and cuts in the MIDDLE of the CTC 'AY' letters. SUSPECTED GOLD ERROR (accepted, never moved): the evidence
  (separator, ssl_change, creak onset) puts say|it at ~0.69-0.71, where the system is.
- it|on (gold 0.743, sys 0.758, +15): glottal /t/ (glottal crest 7 at 0.71-0.74) then loudness dip 8 at 0.73-0.738,
  release transient 5 at 0.742, flux rising 0.722-0.738, 'on' vowel. Gold = release. CTC separator 0.74-0.78.
- on|the (gold 0.852, sys 0.858, ok): /n/ -> lenited /D/, loudness 9, periodicity 7-8 steady; formant_vel 4-5 at
  0.822-0.842, centroid 3 -> 2 at 0.826, mfcc_change 8 at 0.862-0.87. CTC separator 0.84-0.86. No sharp landmark.
- the|podcast (gold 0.931 continuous; sys 'the' ends 0.932, 'podcast' 0.964, +31): vowel of 'the' decays 0.906-0.93
  (transient 9 at 0.914-0.918 inside the decay), /p/ CLOSURE AT THE FLOOR 0.938-0.962 (dB>floor 0, glottal crest 9,
  flatness 5-8 = faint noise), BURST transient 9 at 0.966-0.97, loudness 8-9 (burst+aspiration) 0.966-0.978.
  Gold = CLOSURE START (continuous; 'podcast' owns the 30 ms silent closure). System called the closure a pause and
  started at the burst. Same situation as of|populist (009-8, closure 31 ms at +3..+12 dB) where gold did the
  OPPOSITE (closure as a gap, start at the burst) -> for a 30 ms silent closure the gold is a coin flip; either
  convention costs ~30 ms on half of such cases.
- 'podcast' internal /dk/ closure 1.204-1.244 is AT THE FLOOR (dB>floor 0) - a word-internal 40 ms silence; the
  system correctly did not split there (letters on both sides). /k/ burst transient 9 at 1.236-1.24.
- podcast|so (gold 1.540 ACCEPTED, sys 1.504, -36) numeric: ONE continuous frication 1.452-1.572 (loudness -17..-22 re
  p99, zcr 0.62-0.73, high_ratio ~0 dB), NO dip > 3 dB, NO transient -> the /t/ of 'podcast' is not realised.
  Inside: formant_vel spike 2.6-2.9 at 1.488-1.504 (spectral-shape jump), low_ratio minimum -36/-37 at 1.512-1.536
  then rising from 1.544 (anticipation of the /oU/), ssl_change rising steadily to its peak 0.52 at 1.552, P(sep)
  peak 0.91 at 1.512-1.516, CTC S (for 'so') at 1.54-1.56. Vowel onset 1.576. Midpoint of the frication 1.512.
  Gold 1.540 = 70% into the frication (36 ms before the vowel); system near the midpoint. With populist|support
  (009-8: gold 70% in, 16 ms before the vowel, on an mfcc_change peak) this is the 2nd GEMINATE /s#s/: gold sits
  late, where the spectrum starts to change toward the next vowel. No sharp landmark; inherently ambiguous.
- so|much (gold 1.700 ACCEPTED, sys 1.696, ok): centroid 3 -> 2 and flatness 4 -> 3 around 1.68-1.70 (nasal onset),
  mfcc_change 9 at 1.712-1.72, formant_vel 5 at 1.70-1.72. CTC separator 1.70-1.74.
- much.end (gold 2.031 ACCEPTED, sys 2.026, ok) / but.start (gold 2.050, sys 2.048, ok): /tS/ closure 1.92-1.95 (glottal
  9 at 1.932), release transient 7 at 1.948-1.952, frication 1.952-2.048 (flatness 9, zcr 5-8) fading; the gap
  2.031-2.050 is the faintest frication tail (the local loudness minimum, +0..+6 over floor). 'but' = a 90 ms
  PREVOICED /b/: voice bar from 2.052 (periodicity 1 -> 7 by 2.076, loudness level 6, centroid 1-2, flatness 0-1,
  low_ratio 9), glottal 8 at 2.112, burst transient 9 at 2.12, vowel 2.148. CTC B 2.10-2.12. Gold starts 'but' at
  the VOICING ONSET of the voice bar (not the burst). A voice bar is loud (+15..+24 over floor) -> not a pause.
- but|later (gold 2.274 ACCEPTED, sys 2.293, +19): glottalised /t/ (glottal crest 9 at 2.26-2.264), transient 4 at
  2.268, release transient 7 at 2.284, loudness 7 -> 5 from 2.276, periodicity dip 2.28-2.288, mfcc_change 9 at
  2.28-2.296, /l/ after. CTC separator 2.24-2.30. Gold 10 ms before the release, system 9 ms after.
- later|in (gold 2.604 ACCEPTED, sys 2.662, +58): flap /t/ of 'later' ~2.50-2.52 (loudness dip, mfcc_change 8 at
  2.512, ssl_change 8 at 2.492, glottal 6 at 2.504); /@r/ 2.52-2.60; at ~2.596 loudness 8 -> 9, flatness 2 -> 1,
  high_ratio 2 -> 1 (= vowel change /@r/ -> /I/, gold); at 2.656-2.668 a loudness dip 9 -> 7, centroid 3 -> 2,
  mfcc_change 6 at 2.652, transients at 2.664-2.68 = the /n/ ONSET INSIDE 'in' (system took this). CTC: R 2.58-2.60,
  separator 2.62-2.66, I 2.66-2.70, N 2.70-2.72 (CTC places 'in' 50 ms late). A word-internal nasal onset is a
  stronger landmark than a vowel-vowel word boundary -> landmark choice must respect the phone sequence (the /n/ is
  the LAST phone of 'in', so its onset cannot be the word start).
- in|the (gold 2.721 ACCEPTED, sys 2.745, +24): /n/ -> /D/ (assimilated), loudness 8 steady, no dip; mfcc_change
  minimum at 2.712-2.716 then rising to 9 at 2.76-2.764; formant_vel 2-4 at 2.74-2.768. CTC N 2.70-2.72, separator
  2.72-2.74. Gold = separator start; no acoustic landmark.
- the|week (gold 2.943 ACCEPTED, sys 2.877, -66): /@/ plateau (flatness 0, high_ratio 0) until 2.872; /w/ gesture:
  flatness 0 -> 1 at 2.876, loudness 8 -> 7 at 2.888-2.904 and 2.912-2.932, formant_vel 3 at 2.90-2.92, transient 3-5
  at 2.912-2.916, ssl_change 5 at 2.928-2.936; /w/ -> /i/ release: mfcc_change 9 at 2.956-2.976, loudness 8 from
  2.96. CTC: separator 2.84-2.88, W 2.94-2.96. System = START of the /w/ gesture; gold = 60 ms later, near the
  CTC W letter / end of the constriction. SUSPECTED GOLD ERROR (accepted; glide onset placed late).
- week.end (gold 3.212 ACCEPTED, sys 3.378, +166) numeric, compared with stop.end (009-8, gold 9.226):
  week: vowel /i/ decays -13 (3.14) -> -30 (3.20) -> -36 re p99 at 3.212 (gold); weak voicing (periodicity 0.5-0.65)
  continues at -35..-40 until 3.236 = the /k/ closure (+15..+23 over floor); BURST transient 12 at 3.248-3.254;
  aspiration 3.254-3.33 SUSTAINED at -29..-34 (flatness -1..-3, centroid 8, zcr 0.3-0.4); then a LOUDER low-frequency
  aperiodic exhale 3.33-3.39 (-19..-29, low_ratio ~0 dB, centroid 5-6.7, formant_vel spikes); floor 3.392-3.404;
  more breath noise after 3.42 (transients 3-4). CTC: K 3.164-3.194, separator 3.224-3.25, blank after.
  stop: vowel decays -19 -> -37 by 9.154; quiet closure -37..-40 (9.154-9.184, +17..+21 over floor); BURST
  transient 16 at 9.184-9.196; burst peak -21, then aspiration decays FAST (-31, -36, -42 at gold 9.226, floor by 9.256).
  Same structure up to the burst; gold keeps the release in 'stop' (short, decays to floor within ~60 ms) and drops
  it in 'week' (release followed by 140 ms of sustained aspiration + exhale = heard as a breath). Rule candidate:
  a post-closure release belongs to the word only if the noise after it dies out within ~60-80 ms (a stop's own
  aspiration); if it is sustained/leads into more noise, the word ends at the closure start (vowel decay).
  In 009-7 'week' ended the same way (gold before a long post-/k/ noise).
- pause 3.40-3.79: breath noise (flatness 8-9, centroid 7-8, +12..+18 over floor) with ssl_change peaks (9 at 3.506-3.51,
  7 at 3.526-3.554, 8-9 at 3.59 and 3.606-3.618) = HuBERT marks breath events; CTC blank throughout; floor 3.73-3.774.
- uh.start (gold 3.793 ACCEPTED, sys 3.798, ok): onset with a click/glottal attack: transient 9 at 3.786, glottal
  crest 9 at 3.774-3.802, brief bright flash (centroid 7-8) then the vowel; gold 7 ms after the transient peak at
  -48 re p99 (+11 over floor).
- uh (3.793-4.125): the letter CTC DOES emit 'A' here (3.944-3.96) + separator 4.06-4.08 - fillers are not always blank.
  uh.end (gold 4.125 ACCEPTED, sys 4.120, ok): creaky end (glottal crest 5-8 over 4.04-4.12), voicing falls 4.076-4.088,
  flatness and centroid collapse to 0 at 4.104-4.12 (a glottal closure), TRANSIENT 9 at 4.12 (glottal release /
  click), mfcc_change 9 at 4.136-4.14. Gold = right after the transient.
- gap 4.125-4.260: noise bump 4.17-4.21 (+24 over floor, flatness 5-6, centroid 3-6, zcr 2-3) between two minima
  (+9..+12 at 4.156 and 4.236) = breath event inside the gap.
- i've.start (gold 4.260 ACCEPTED, sys 4.258, ok): the word begins with a breathy/fricative onset 4.232-4.272 (centroid
  8-9, flatness 8-9, high_ratio 8-9, zcr up to 9, voicing 1-2) before the /aI/ vowel (4.276+). Gold starts 28 ms into
  that onset noise (at loudness level 4-5, -30 re p99).
- i've|said (gold 4.388 HUMAN-MOVED, sys 4.420, +32): /v/ 4.36-4.385 (flatness dips to 4, centroid 2), then /s/:
  voicing ends 4.38-4.396, flatness 5 -> 9 (4.376-4.40), centroid 2 -> 9 (4.392-4.408), zcr 1 -> 8 (4.388-4.41),
  low_ratio 9 -> 1 (4.388-4.408), transient 5 at 4.396, mfcc_change 7 at 4.384-4.392, formant_vel 8-9 at 4.384-4.404,
  ssl_change 8 at 4.368-4.384. Gold (moved by a person) = FRICATION ONSET exactly. CTC: V 4.36-4.38, then the SILENT
  'E' of i've at 4.38-4.42 (inside the /s/), separator 4.42-4.44 -> system 32 ms late.
  *** SILENT FINAL LETTERS (freeze, i've, and likely 'like', 'have', 'take', 'site', 'more', 'are', 'there') are emitted
  by the letter CTC AFTER the last sound -> the separator lands inside the next word. The lexical boundary prior
  must not assume letters are sounds (use the phoneme model or discount silent letters).
- said|this (gold 4.644 ACCEPTED, sys 4.654, ok): shared /d D/ closure 4.60-4.672 with a VOICE BAR (loudness 9 -> 7,
  periodicity 6-7, flatness 0, centroid 1, high_ratio 0 = +34..+42 over floor), release burst transient 9 +
  mfcc_change 9 at 4.668-4.676. Gold at the closure MIDDLE (4.636 mid; gold 4.644). CTC D 4.60-4.62, separator
  4.62-4.66. Shared (geminate) closures are split in the middle (also had|to, said|the in 009-8).
- this|on (gold 4.874 ACCEPTED, sys 4.902, +29): /s/ -> vowel: zcr 9 -> 1 and low_ratio 0 -> 9 over 4.848-4.864, voicing
  onset 4.848-4.868, centroid 9 -> 2 at 4.86-4.868, formant_vel 9 at 4.86-4.88, glottal 8 at 4.852. Gold = FRICATION
  OFFSET / vowel onset (+6 ms). CTC separator 4.816-4.856 is EARLY here and O at 4.94 is 70 ms late; system 30 ms late.
- on|you (gold 5.201 ACCEPTED, sys 5.151, -50): a loudness DIP 5.154-5.218 (8 -> 7) = the /n/ murmur of 'on' (+ /j/);
  glottal crest 9 at 5.166, mfcc_change 8 at 5.146-5.15 (dip onset) and 8-9 at 5.17-5.19, transient 4 at 5.194-5.214
  (release). CTC: separator 5.12-5.16, Y 5.20. Gold = END of the dip (nasal release), system = START of the dip.
  *** Consonant-ownership principle: the consonant segment next to the boundary belongs to the word that has that
  phone; cut at the segment's edge that faces the OTHER word: nasal-final word -> murmur offset (on|you);
  nasal-initial -> murmur onset (the|nuclear); fricative-final -> frication offset; fricative-initial ->
  frication onset; shared stop closure -> middle; stop-initial after a vowel -> closure start or burst (gold varies).
  The system's change-point picks the nearest/strongest change within +-10 ms of the lexical median, which is
  often the wrong edge of the same segment.
- you|know (gold 5.281 ACCEPTED, sys 5.264, -16): /u/ -> /n/: centroid 2 -> 1 at 5.274-5.29 (nasal onset),
  ssl_change 9 at 5.27-5.294, mfcc_change 8-9 at 5.262-5.27. CTC separator 5.26-5.28, SILENT K 5.28-5.30, N 5.30.
  Gold = nasal onset.
- know.end (gold 5.424 ACCEPTED, sys 5.420, ok): creak at the end (glottal 6-8 at 5.382-5.41), transient 9 at 5.418,
  loudness falls 5.402-5.434 to the floor, voicing ends ~5.43. Gold at -38 re p99 (+2 over floor).
- gap 5.424-5.455 (floor): weak noise onset at 5.434-5.44 (transient 8, flatness rising 2 -> 7) before the main /t/
  burst transient 9 at 5.458. talked.start (gold 5.455, sys 5.460, ok) = the main burst, not the weak pre-noise.
- talked|about (gold 5.652 HUMAN-MOVED, sys 5.678, +26): /kt/ closure 5.594-5.646 is VOICED (loudness level 6,
  periodicity 7, flatness 0, centroid 1, high_ratio 0), release BURST transient 9 + glottal 8 + mfcc_change 8 at
  5.638-5.646, formant_vel 9 at 5.63; 'about' vowel from 5.65. Gold = right after the release (release stays with
  'talked'). CTC spells T-A-L-K-E-D: silent L 5.54, K 5.58, E 5.60, D 5.62-5.66 (covering closure+burst), separator
  5.66-5.68 -> system 26 ms late (silent letters again).
- about|it (gold 5.801 ACCEPTED, sys 5.812, ok): /t/ release transient 7 at 5.798 (+ 4 at 5.802), loudness dip 7 at
  5.79-5.802, ssl_change 9 at 5.80-5.822. Gold at the release.
- it|on (gold 5.930 ACCEPTED, sys 5.883, -47): flapped/glottal /t/ with NO loudness dip (8-9 throughout, periodicity 7);
  small transient 2 and formant_vel 3 at 5.866-5.87, glottal crest 6 at 5.91-5.918. CTC: I 5.84, T 5.86-5.88,
  separator 5.88-5.90, O 5.92-5.94. Gold ~12 ms after the glottal peak (vowel of 'on'); system at the CTC separator
  start (40 ms early here). Weak landmark only (glottal crest).
- on|the (gold 5.991 HUMAN-MOVED, sys 5.990, exact): /n/ -> /D/ with no visible landmark.
- the|site (gold 6.032 HUMAN-MOVED, sys 6.071, +38): reduced 'the' (40 ms); /s/ onset: flatness 3 -> 9 over 6.01-6.05,
  high_ratio 3 -> 9 over 6.018-6.054, zcr from 6.03, centroid 2 -> 9 over 6.038-6.05, voicing 7 -> 1 over 6.01-6.062,
  mfcc_change 8 at 6.014, formant_vel 9 at 6.018-6.03, transient 4 at 6.01. CTC gives 'the' only a weak 'a' at
  6.04-6.06 (INSIDE the /s/) and a separator 6.08-6.10. Gold (person) = FRICATION ONSET (start of the rise, 6.03);
  system 40 ms late, driven by the CTC.
- site|a (gold 6.281 ACCEPTED, sys 6.306, +26): /t/ (glottal crest 6 at 6.262-6.266) released at 6.286 (transient 3,
  flux 6, mfcc_change 7 at 6.282-6.286); a second mfcc_change peak 8 at 6.302-6.31. CTC: 'site' heard as S..I..D E
  (silent E 6.26-6.28), separator 6.28-6.32, A 6.32-6.34. Gold = the release; system = separator middle.
- a|little (gold 6.323 HUMAN-MOVED, sys 6.340, +18): /@/ -> /l/: flatness 3 -> 1 over 6.31-6.35, glottal crest 8 at
  6.346-6.35, mfcc_change minimum 6.342 then rising, transients 3-5 at 6.362-6.382. CTC: A 6.32-6.34 (inside the
  gold 'little'!), separator 6.34-6.36, L 6.36. The person put 'a' at 6.281-6.322 (41 ms), ~20 ms BEFORE the CTC's
  own 'A' frame. No clear acoustic landmark for /@/ -> /l/.
- little|bit (gold 6.517 ACCEPTED, sys 6.526, ok): /l/ -> voiced /b/ closure 6.48-6.52 (flatness 0, high_ratio 0,
  loudness 7 -> 6, periodicity 5-7), BURST transient 9 at 6.522-6.526 + mfcc_change 9 at 6.51-6.53. Gold 5-9 ms before
  the burst, system at it. CTC: silent E of 'little' 6.48-6.52 then separator 6.52-6.54 - here the silent E covers
  the closure, so no harm.
- bit|and (gold 6.686 HUMAN-MOVED, sys 6.706, +21): after the /t/ (CTC T 6.64-6.68) a dip 6.686-6.72 (loudness 7 -> 5-6,
  centroid 3 -> 1, periodicity dips 5, flatness 5 -> 3) = GLOTTAL STOP before 'and'; transient 6 at 6.722-6.726,
  glottal crest 9 at 6.734, flux 7 at 6.73. Gold (person) = START of the glottal constriction (the [?] belongs to
  the vowel-initial word); system = its middle.
- 'and and and' 6.686-7.260 (repetition, quiet: -23..-28 re p99): CTC hears the 1st (A 6.74, N 6.76, D 6.80, separator
  6.82-6.86) and the 3rd (A 7.16, N 7.20, separator 7.26-7.28, no D); the MIDDLE 'and' (6.911-7.094) is all CTC-blank.
  - and|and (gold 6.911 HUMAN-MOVED, sys 6.898, -13): loudness minimum 6.904-6.92 (the quietest point within +-1 s),
    periodicity dip 6.90-6.93, mfcc_change 7 at 6.896-6.90. Gold at the minimum.
  - and|and (gold 7.095 HUMAN-MOVED, sys 7.108, +14): dip 7.104-7.144 (loudness 6 -> 5, periodicity 3-4 at 7.124-7.132)
    with glottal crest 7 at 7.108, mfcc_change 8 at 7.124-7.132, transient 4 at 7.132-7.136 (= glottal attack of the
    3rd 'and'). Gold at the START of the dip (the glottal constriction belongs to the vowel-initial word, as in
    bit|and); system at the glottal peak.
- and|said (gold 7.261 HUMAN-MOVED, sys 7.276, +15): /s/ onset: flatness 3 -> 9 over 7.256-7.284, zcr from 7.264, centroid
  from 7.264, high_ratio from 7.26, low_ratio 9 -> 0 over 7.28-7.312, voicing drop 7.272-7.292. Gold = frication onset;
  CTC separator 7.26-7.28, S 7.30.
- said|it (gold 7.467 ACCEPTED, sys 7.476, ok): /d/: loudness dip 7.452-7.464, periodicity dip 3 at 7.46, release
  transient 6 at 7.468-7.476. Gold right before the release. (CTC hears 'said' as S E T.)
- it|elsewhere (gold 7.567 ACCEPTED, sys 7.580, ok): /t/ as a loudness dip (8 -> 7) 7.528-7.576, vowel from 7.58.
  CTC separator 7.56-7.60. Gold 13 ms before the vowel onset.
- elsewhere|like (gold 7.960 ACCEPTED, sys 7.944, -16): /r/ -> /l/, loudness flat; mfcc_change 8 at 7.956-7.964. CTC
  silent E 7.90-7.92, separator 7.92-7.98, L 7.98. Gold on the mfcc_change peak.
- like.end (gold 8.136 ACCEPTED, sys 8.344, +208): vowel decays (level 5 at 8.078-8.106, 4, 3, 2, 1), /k/ CLOSURE AT THE
  FLOOR 8.134-8.158 (dB>floor 0, -52 re p99), /k/ BURST transient 9 at 8.154, then ~110 ms of bright noise 8.154-8.262
  (flatness 8-9, centroid 5-8, zcr 3-5, loudness 3-5 = +18..+27 over floor), a short VOICED low-centroid bit
  8.274-8.302 (hum, periodicity 5-7, centroid 1), more noise 8.30-8.40 (flatness 7-8), fade to the floor by ~8.45;
  ssl_change 7 at 8.314-8.322. speech_prob drops to 2 from 8.19 (pyannote calls it non-speech here, unlike after
  'week'). Gold = CLOSURE START (vowel end reaching the floor); burst + noise + hum excluded. 3rd case (week x2, like):
  stop-final word + release followed by sustained noise -> word ends at the closure start. System extended over all
  of it (+208) because the noise is louder than word-ref -20 dB... no: it is quieter, but the pause test needs
  P(between) > 0.5 AND quiet, and the end refinement took the last quiet-run edge.
- pause 8.45-8.77: floor (dB>floor 0-1), centroid 0-1.
- (()).start (gold 8.771 HUMAN-MOVED, sys 8.774, ok): a small bright blip 8.746-8.762 (centroid 1-3, transients 2-5)
  precedes the main onset; main onset transients 6-9 at 8.774-8.778, glottal crest 7-9 at 8.766-8.806, loudness rise
  from 8.774. Gold (person) = main onset, the pre-blip excluded.
- (()) 8.771-9.130 (HUMAN-MOVED both) | only 9.168: CTC is blank over the whole (()) and then emits 'T H E' at 9.242-9.30,
  separator 9.30-9.32, O 9.34, N 9.36-9.40, L 9.40, Y 9.44 -> the CTC hears 'THE ONLY' inside the gold 'only'.
  Acoustics: (()) voiced 8.78-9.10; voicing breaks and loudness falls 9.102-9.142 (min +12 over floor at 9.142-9.146);
  a breathy/fricative noise 9.126-9.166 (flatness 7-8, high_ratio 7-8, zcr 2-4); GLOTTAL ATTACK at 9.166-9.17
  (glottal crest 9, transient 4, flux 9 at 9.178-9.182), voicing and loudness rise -> 'only' vowel. Gold: (()) ends at
  the voicing break (9.130), gap = the noise, 'only' starts at the glottal attack (9.168). This dip is the ONLY
  break between 8.80 and 9.46. System: the (()) wildcard absorbed the CTC 'THE' letters -> (()) to 9.332, 'only'
  +165. => the soft-token / lexical-word cut = the strongest break (trough + voicing break + attack) between the soft
  token and the next word's first letter, NOT letter-driven. (Same logic gave uh|we in this clip.)
- only|chance (gold 9.491 ACCEPTED continuous, sys 9.470 / 9.510 = false 40 ms pause): vowel /i/ loud until 9.466,
  loudness 9 -> 6 over 9.47-9.502 (closure onset, voicing falling), minimum level 3-4 at 9.51-9.53 (+18 over floor,
  not silent), /tS/ burst ~9.514-9.518 (transient 9), frication from ~9.50 (flatness, high_ratio up at 9.494-9.498,
  zcr from 9.506, 8 by 9.53), mfcc_change 9 at 9.502-9.522. CTC separator 9.46-9.52, C 9.52. Gold = CLOSURE START
  (affricate-initial word owns its closure); the system's quiet test made the closure a pause.
- chance|i (gold 9.866 ACCEPTED, sys 9.811, -55): 'chance' = /tS/ to 9.576, /ae/ 9.58-9.71, a breathy/fricative bit
  9.712-9.76 (flatness 7-8, high_ratio 7-8, centroid 4-5, voiced), then a NASAL HUM 9.76-9.85 (periodicity 6-7,
  flatness 0 / -11 dB, high_ratio -54 dB = pure low tone, centroid 0-1, loudness -21..-25 re p99) that the CTC leaves
  BLANK (separator 9.76-9.80). Hum falls 9.852-9.864 (-29, -34), voicing break at 9.864 (periodicity 0.11), click /
  glottal attack of 'I' at 9.870 (transient 14, centroid 6.8), 'I' creaky onset. Gold = the break (9.864-9.866); the
  continuous hum is INSIDE 'chance'. System cut in the middle of the hum (lexical prior at the CTC separator).
  -> a CTC-blank voiced stretch that is CONTINUOUS with the word (no trough before it) belongs to the word; the
  word ends at the first break (trough/voicing break), cf. the 'movement' voiced tail (009-8).
- i|thought (gold i.end 10.040 ACCEPTED, gap, thought.start 10.077 HUMAN-MOVED; sys 10.003/10.005, -37/-72) numeric:
  'I' voiced to ~10.02 (-14 at 10.002), breathy offset with frication creeping in from 10.008 (flatness -2.9,
  high_ratio -15, transient 2.5), decay -21 (10.026), -27 (10.032), -36 (10.038 = gold end), noise continues
  (centroid 7.2-7.6) through a TROUGH -42..-43 re p99 at 10.056-10.068 (+17 over the clip floor), transients 2.8 /
  5.0 / 4.4 at 10.068 / 10.074 / 10.086 and the /T/ gets louder (-37 -> -25, zcr 0.3-0.4), vowel at 10.104.
  CTC: separator 10.026-10.044, T 10.062-10.074, H 10.08-10.098, O 10.122. Gold: 'i' ends at the -36 crossing, a
  37 ms gap over the trough, 'thought' starts at the transient where the /T/ becomes loud. System: continuous cut at
  the EARLIEST frication (10.005) - the 'fricative onset' rule applied too early: the first weak frication overlaps
  the vowel decay; the person heard the /T/ from its loud part.
- thought|baylor (gold 10.258 ACCEPTED, sys 10.312, +55): glottalised /t/ (glottal crest 8-9 at 10.224-10.252, voicing
  dip 10.248-10.26), then a 60 ms VOICE BAR 10.264-10.34 (periodicity 6-7, flatness 0, centroid 1, high_ratio 0,
  loudness level 7) = prevoiced /b/ closure, BURST transient 9 + mfcc_change 9 at 10.316-10.336, vowel ~10.36.
  CTC: T 10.24-10.26, separator 10.26-10.32, B 10.32. Gold = START of the voice bar (the closure belongs to 'baylor');
  system just before the burst.
- baylor|really (gold 10.609 ACCEPTED, sys 10.601, ok): /@r/ -> /r/, loudness flat, flatness 1 over 10.584-10.644, no
  landmark; gold = middle of the CTC separator 10.60-10.62; mfcc_change 9 at 10.644-10.652 (inside 'really').
- really|had (gold 10.881 ACCEPTED, sys 10.901, +20): /i/ -> /h/: transient 5 at 10.86, glottal crest 7-8 at
  10.868-10.888, periodicity 7 -> 5 at 10.876-10.884, centroid bump then drop at 10.884, formant_vel 8 at 10.892;
  a second voicing dip 10.932-10.952 inside 'had'. CTC separator 10.84-10.88, H 10.92 (late). Gold = the
  voicing/glottal change (onset of the /h/ breathiness), as in we|had (009-8).
- had|was (gold 11.201 ACCEPTED, sys 11.243, +42): lenited /d/ (periodicity dip 11.152-11.18, no loudness dip),
  release = mfcc_change 9 at 11.196-11.208 (glottal 7 at 11.188), then /w/ (centroid -> 2, high_ratio and flatness
  falling, formant_vel 5 at 11.256-11.296). CTC: D 11.16-11.18, separator 11.20-11.28, W 11.30. Gold = /d/ RELEASE
  (release stays with 'had'); system = separator middle.
- was.end (gold 11.668 HUMAN-MOVED, sys 11.768, +100): /z/ frication 11.556-11.664 (zcr up to 9, centroid 9, high_ratio 9,
  loudness falling 8 -> 3); frication STOPS at 11.664-11.668 (zcr -> 0, centroid 9 -> 0, flatness 7 -> 1, -37 re p99,
  trough +15 over floor, formant_vel 9 at 11.664-11.676); then a HUM 11.684-~11.79 (voicing back to 6, centroid 0,
  flatness 0, loudness 6-7 = +27 over floor, flux 9 at 11.692, mfcc_change 9 at 11.70-11.712, transient 7 at 11.72),
  fading to 11.85. CTC: S 11.52-11.54 (start of the /z/), separator 11.56-11.62, blank over the hum.
  Gold (person) = END OF THE FRICATION; the hum is excluded. Contrast 'chance' (/n/ -> continuous hum, included):
  a hum continues a NASAL word (same sound) but not a FRICATIVE word (different sound after a trough).
  (The skim note '11.52-11.65 bump' had the times wrong - the hum is 11.684-11.79.)
- !!! METHOD WARNING (found at 12.63): counting characters from the left edge of a 150-220-char zoom row mis-located
  positions by up to 5-8 chars (20-30 ms). The zoom ruler now prints the time after every 100 ms mark and t0 is
  rounded to the 2 ms grid; all error-boundary claims are checked with at.py numbers. Earlier 009-8/009-0 positions
  taken from long-row counting may be off by ~10-30 ms; the qualitative findings were cross-checked with at.py
  where it mattered (movement, stop, week, was|able, podcast|so, chance|i|thought, they|could).
- maybe.start (gold 12.101 ACCEPTED, sys 12.106, ok): rise out of the floor with transient 9 + mfcc_change 9 at
  ~12.11 (onset click of /m/?), gold at the first rise (+3 over floor).
- maybe|they (gold 12.520 ACCEPTED, sys 12.511, ok): no visible landmark; CTC separator 12.50-12.52, T 12.52.
- they|could (gold 12.632 ACCEPTED, sys 12.621, -11) numeric: vowel falls -7 (12.60) -> -24 (12.62) -> -30
  (12.628-12.632 = gold) -> -36 (12.64); /k/ closure 12.636-12.664 is NOISY (flatness -1.6..-2.8, centroid 7.2-7.5,
  zcr 0.14-0.23, -33..-36 re p99) = frication during the closure; BURST transient 9.6 at 12.672. CTC separator
  12.62-12.64, C 12.64. Gold = CLOSURE START at the -30 crossing (again stop-initial word owns its closure).
- could|take (gold 12.792 ACCEPTED, sys 12.769, -23): shared /d t/ closure: loudness falls 12.726-12.766 (7 -> 3), ONE
  burst transient 9 at 12.766-12.77, aspiration 12.76-12.81 (flatness 9, zcr 5-8), vowel 12.81. CTC: D 12.74-12.76,
  separator 12.762-12.80, T 12.80. Gold (accepted) is 25 ms AFTER the burst in the middle of the aspiration;
  system at the burst. A geminate closure would be split mid-closure (~12.745) or at the burst; gold looks off
  here (accepted, never moved) - label noise.
- take|some (gold 12.972 HUMAN-MOVED, sys 12.985, +13): /k/ release transients 4-6 at 12.97-12.978, frication from
  12.958-12.97 (flatness, zcr, centroid rising). Gold (person) = release / frication onset; CTC separator 12.97-12.99.
- some|shots (gold 13.133 ACCEPTED, sys 13.157, +24): /S/ frication rises 13.106-13.134 (flatness, centroid,
  high_ratio), transients 5-6 at 13.118-13.126, mfcc_change 9 at 13.126, formant_vel 9 at 13.122-13.126, zcr from
  13.138. CTC: silent E of 'some' 13.07-13.11, separator 13.11-13.15, S 13.17. Gold = top of the frication rise;
  system 24 ms late (silent E pushes the separator).
- shots|down (gold 13.493 ACCEPTED, sys 13.495, ok): weak final /s/ (zcr 9 to 13.496, -38 re p99 at the end), frication
  stops 13.50-13.512, /d/ burst transient 8 at 13.508. Gold = frication end.
- down|the (gold 13.681 ACCEPTED, sys 13.695, ok): /n/ -> /D/, CTC separator 13.66-13.70; no landmark.
- the|field (gold 13.755 HUMAN-MOVED; sys the.end 13.786 + field.start 13.828 = FALSE PAUSE, -32/+73): /f/ onset at
  13.752-13.76 (mfcc_change 7, transient 5, flatness 5 -> 9 over 13.756-13.78, centroid and high_ratio rising,
  formant_vel 8 at 13.764-13.772, zcr from 13.772). The /f/ is WEAK in broadband loudness (-28..-35 re p99, only
  +6..+12 over the floor) but clearly frication (flatness 9, centroid 7-8, high_ratio ~9). Gold (person) = frication
  onset. The word-ref -20 dB quiet test called the /f/ a pause (same as 'a|force' in 009-7). Silence test must be
  per-band: a stretch whose HF energy is well above the HF floor is frication, not silence.
- field|cause (gold field.end 14.037 ACCEPTED + cause.start 14.038 HUMAN-MOVED = continuous; sys 14.022 / 14.064 =
  false pause) numeric: /d/ decay -8 (14.00) -> -22 (14.02) -> -33 (14.028) -> -40 (14.032) -> closure at the floor
  -42..-49 (14.036-14.056), /k/ BURST transient 17.8 at 14.060, aspiration -31 (14.064-14.11), vowel 14.112. Gold =
  CLOSURE START (-42): the person gave the 25 ms silent closure to 'cause'. System: end at word-ref -20 dB (14.022),
  start after the burst (14.064). P(sep) = 0.9 over 14.012-14.032 (CTC is sure the word ends before the closure).
- cause|((they)) (gold 14.187 HUMAN, sys 14.189): exact.
- ((they))|they (gold 14.581 HUMAN-MOVED, sys 14.455, -127) numeric: the first 'they' is PROLONGED (voiced vowel
  14.30-14.51, CTC letters T-H-E-Y 14.18-14.30, separator 14.36-14.40, then BLANK 14.40-14.56); the second /D/ =
  14.516-14.556 (loudness -21..-25, periodicity 0.8, flatness -9..-11 dB, high_ratio -54 dB = voiced, no frication);
  release 14.56-14.592 (transients 4.4-7.3, mfcc_change 4.9 at 14.58, formant_vel 1.5 at 14.572); vowel from 14.59.
  CTC T 14.56, H 14.58. Gold (person) = in the /D/ release (mfcc peak); the /D/ onset is 14.516. System cut inside the
  prolonged vowel, 60 ms before the /D/ even starts.
  *** Lexical uncertainty is variable: when the letter evidence of word 1 ends long before word 2's first letter
  (here 160 ms of blank), a fixed +-10 ms radius around the prior median is meaningless. The search window for the
  acoustic landmark should span the letter-posterior gap [last letter of w1, first letter of w2] (+ margin).
- they|do (gold they.end 14.790 ACCEPTED, gap, do.start 14.822 ACCEPTED; sys 14.742 for both, -48/-79) numeric: vowel
  -8 at 14.72; a dip to -21..-24 at 14.732-14.748 (= CTC separator, P(sep) 1.0); then a VOICED, TONAL, low stretch
  14.752-14.788 (-20..-22, periodicity 0.7-0.8, flatness -9..-10, high_ratio -43..-48 = voice-bar-like); decay -25 ->
  -31 over 14.788-14.812 (transient 6 at 14.792); voicing stops 14.816 (-34); /d/ BURST transients 9-19 at
  14.820-14.824; 'do' vowel from 14.828. Gold: the voiced stretch stays with 'they' (end at its decay, -25),
  closure = gap, 'do' starts AT THE BURST. System: cut at the CTC separator dip (14.742).
  Voice-bar ownership is inconsistent in gold: 'but' 2.050 and 'baylor' 10.258 start at the voice bar onset; here the
  voice bar stays with the previous word and 'do' starts at the burst (all ACCEPTED).
- do|take (gold do.end 15.033 ACCEPTED, gap 6 ms, take.start 15.039 ACCEPTED; sys 14.980, -53/-58) numeric: 'do' vowel
  -1 until 14.972, decays -7 / -13 (14.976-14.992, still voiced) / -15..-20 (15.0-15.012) / -23..-31 (15.016-15.028),
  closure at the floor -42/-43 (15.032-15.036), /t/ BURST transient 15 at 15.040. CTC separator P(sep) 0.9-1.0 over
  14.98-15.016 = IN THE DECAY. Gold: end at the closure (first frame below ~-35), start at the burst. System at the
  decay onset (the separator).  *** The CTC separator sits in the decaying tail of a vowel before a stop closure;
  the acoustic word end is 30-50 ms later where the decay reaches the closure.
- take|shots (gold 15.257 ACCEPTED, sys 15.301, +45) numeric: the silent E of 'take' is emitted by the CTC over
  15.22-15.256 (!); frication onset at 15.252-15.26 (high_ratio -29 -> -16, formant_vel 2.3-2.6, transient 6.2 at
  15.260 = /k/ release), /S/ frication 15.26-15.32 (centroid 7.3-8.2, zcr 0.3-0.47). CTC separator 15.26-15.32. Gold =
  FRICATION ONSET / release; system = separator middle (45 ms into the /S/). Silent-E count in 009-0 so far:
  i've, like, some, take, site (E), little (E), elsewhere (E), talked (E+D).
- shots|that's (gold 15.779 ACCEPTED, sys 15.787, ok) numeric: /t/ closure 15.714-15.73 (to -54, floor), /s/ frication
  15.726-15.80 (zcr 0.4-0.73, centroid 8.4-8.7, WEAK: -31..-49 re p99), /s/ -> /D/ change 15.798-15.818 (zcr drop,
  centroid drop, low_ratio up, loudness -30 -> -11). Gold and system both ~20 ms BEFORE the frication offset (inside
  the /s/), cf. this|arms (009-8) where gold also ended 'this' inside the weak /s/ tail.
- that's|one (gold 15.976 ACCEPTED, sys 16.001, +25) numeric: /s/ frication to 15.968, offset 15.968-15.976 (zcr 0.34 ->
  0.08, centroid 8.1 -> 5.8, low_ratio -8.7 -> -0.5). Gold = FRICATION OFFSET exactly; system at the CTC separator
  (P(sep) 0.98 at 15.992) / /w/ formant movement (formant_vel 2.9 at 15.992-16.0).
- one|of (gold 16.165 ACCEPTED, sys 16.148, -17): /n/ -> /V/, loudness 9 flat; CTC silent E of 'one' 16.10-16.12,
  separator 16.12-16.14, O 16.14-16.16, F 16.16-16.18. Gold 'of' (46 ms) sits AFTER the CTC's own O. No landmark.
- the|things (gold the.end 16.346 + things.start 16.348 ACCEPTED continuous; sys 16.296 / 16.360): 'the' decays to the
  FLOOR at ~16.296 and a 50 ms SILENCE (-61 re p99) follows before the /T/ onset (~16.348-16.36). Gold (accepted from
  the old system) keeps the silence INSIDE 'the' - inaudible either way, so the reviewer accepted it. Where a
  silence precedes a non-stop consonant, accepted gold may put the whole silence in the previous word.
- things|that (gold 16.618 ACCEPTED, sys 16.582, -36) numeric: /N/ voiced until ~16.57, then a VOICED /z/ 16.57-16.63
  (high_ratio -27 -> -12, flatness -5.8 -> -3.5, centroid 5.3 -> 6.3, zcr up to 0.11, periodicity 0.6), /z/ -> /D/
  at 16.632-16.644 (high_ratio down, loudness up). CTC: S 16.544-16.576, separator 16.58-16.616, T 16.62, H 16.64.
  Gold = near the /z/ OFFSET; system = the /z/ ONSET (wrong edge of the owner's consonant).
- that|they (gold that.end 16.792 ACCEPTED, they.start 16.794 HUMAN-MOVED; sys 16.750 / 16.826) numeric: 'that' vowel
  decays -28 (16.738) -> -45 (16.758) -> floor -58..-62 over 16.766-16.818 (56 ms silent closure), release with
  glottal crest 23 at 16.822 and transients 11-20 at 16.826-16.834 (/D/ as a stop). Gold (person) = the EXACT
  MIDDLE of the silent closure (16.766-16.822 -> 16.794): shared closure /t/ + /D/-stop split in half. System made
  the closure a pause (end -35 re p99, start at the release).
- stop-closure tally (gold): END of word 1 = closure start in most cases (the|podcast, field|cause, they|do, do|take,
  of|populist, to|go, and|part); START of word 2 = closure start (continuous: the|podcast, field|cause, to|go, and|part,
  only|chance, they|could), burst (gap: of|populist, they|do, do|take, know|talked, particularly), or closure middle
  (shared closures: that|they, said|this, had|to, said|the). ~Half-and-half -> irreducible scatter ~= half a closure.
- they|are (gold 17.028 HUMAN-MOVED, sys 17.050, +23): vowel -> vowel; CTC separator ~16.996-17.02, 'a' (weak) ~17.10.
  No strong landmark in the zoom (loudness 6-7 flat, glottal crest 5-6 at 17.00-17.02).
- are.end (gold 17.244 HUMAN-MOVED, sys 17.432, +188) numeric: voiced vowel to ~17.17 (-22 at 17.168); breathy offset
  17.176-17.21 (-35, aperiodic, centroid 7.2-7.5); a louder noise bump 17.216-17.24 (-24..-32, ssl_change 0.52 at
  17.232, formant_vel 1.2); DIP -34..-37 at 17.248-17.256; then a 210 ms EXHALE 17.264-17.47 (-20..-34 re p99 = +26..+40
  over floor, flatness -1.5..-2.5, centroid 7.0-7.6, high_ratio -10..-17, zcr 0.2-0.3, periodicity 0.2-0.3, transient
  4.3 at its onset 17.264, CTC blank), decaying to the floor by 17.52; /k/ burst of 'kind' at 17.544 (transient 18).
  Gold (person) = the dip right before the exhale onset; the exhale is excluded. System ended inside the exhale.
  The exhale is LOUDER than the gold end level -> level thresholds cannot separate it; its onset event (transient,
  low_ratio drop, rising centroid) after a dip, CTC blank, aperiodic + bright = breath.
- kind.start (gold 17.554 ACCEPTED, sys 17.540, -14): /k/ burst transient 18 at 17.544, gold 10 ms after it.
- kind|of (gold 17.670 HUMAN, sys 17.671) exact; of|a (gold 17.737 HUMAN, sys 17.750, +13).
- a|signature (gold 17.780 HUMAN-MOVED, sys 17.822, +42): /s/ onset: flatness rises from 17.778, centroid/high_ratio/zcr
  from 17.782-17.786, low_ratio drops 17.786-17.80, mfcc_change 8 at 17.782-17.786, formant_vel 9 at 17.786-17.794.
  CTC puts 'a' at 17.78-17.80 (INSIDE the /s/ onset) and the separator 17.80-17.84. Gold (person) = frication onset.
- signature|in (gold 18.276 HUMAN, sys 18.276) exact.
- in|their (gold 18.340 HUMAN-MOVED, sys 18.374, +35): /n/ -> /D/, loudness flat; CTC: I 18.306-18.322, N 18.326-18.342,
  separator 18.346-18.382, T 18.386. mfcc_change 7 and glottal crest 7 at 18.342-18.346. Gold = END of the CTC N =
  START of the separator region (= the weak /D/); system = separator middle.
- *** CTC-separator geometry (from ~25 junctions so far): the separator span [s0, s1] usually covers the junction
  CONSONANT whose letter the CTC has not emitted yet (weak /D/, /f/, /s/, /h/, glottal attacks, voice bars, the /z/
  of 'was' after its S letter). Gold sits at the separator EDGE on the side of the word that does NOT own that
  consonant: word-2 consonant -> s0 (in|their, in|the, that|we, particularly|for, a|signature-ish); word-1 consonant
  -> s1 (was|already, freeze|movement). The system uses the separator MIDDLE ((A+B)/2 density) -> systematic
  half-separator error (15-40 ms). Refinement must pick the correct edge by phone ownership, then snap to the
  acoustic landmark of that consonant (frication/murmur/closure/voicing edge).
- their|offense (gold 18.506 HUMAN, sys 18.505) exact: /r/ -> vowel; CTC R 18.48-18.50, separator 18.50-18.544; gold at s0.
- offense|like (gold 18.851 ACCEPTED, sys 18.852) exact: /s/ frication 18.80-18.852 ends -> /l/; gold = frication offset.
- like|they (gold 18.976 ACCEPTED, sys 18.979): /k/ + /D/ closure at the floor ~18.97-19.00 (-55 re p99), release
  transient 9 ~19.0; both gold and system cut at the closure START here.
- they|will (gold 19.095 ACCEPTED, sys 19.087): vowel -> /w/, ok.
- will|throw (gold 19.306 ACCEPTED, sys 19.305) exact: /l/ fades to a loudness minimum at ~19.30-19.31, /T/ frication
  from ~19.32.
- the|ball (gold 19.531 HUMAN-MOVED, sys 19.560, +29): 'the' vowel loud to 19.552; voicing break 19.556-19.572, glottal
  crest 8-9 at 19.572-19.58, /b/ VOICE BAR 19.576-19.60 (flatness 0, high_ratio 0, centroid 1, periodicity 6-7),
  burst ~19.60-19.61, mfcc_change 9 at 19.584-19.596. CTC E 19.53-19.55, separator 19.55-19.566, B 19.566. The system
  cut at the voicing break (= closure start); the person put it 26 ms EARLIER while the vowel is still at full
  loudness (only a loudness step 8 -> 9 at 19.528). Human-moved but not on a landmark: label scatter ~25 ms.
- ball|deep (gold 19.793 ACCEPTED, sys 19.764, -30): /l/ -> /d/ VOICE BAR 19.784-19.852 (flatness 0, centroid 0,
  high_ratio 0), burst transients 6-9 at 19.84-19.856, formant_vel 9 at 19.844-19.848, mfcc_change 9 at 19.872. CTC
  separator 19.72-19.76, D 19.80. Gold = voice bar START (+8 ms) = closure start; system = separator end.
- deep.end (gold 20.065 ACCEPTED, sys 20.056, ok): loudness decays 20.044-20.084 to the floor; gold at -36 re p99.
- pause 20.065-20.201: after 'deep' the loudness reaches the floor (20.09-20.15), then a NOISE burst 20.13-20.20 (flatness
  8-9, centroid 7-9, zcr up to 9 at 20.174-20.182) = delayed /p/ release + aspiration or an inhale; gold excludes it.
- more.start (gold 20.201 ACCEPTED, sys 20.206, ok): flatness 8 -> 3 and centroid drop at 20.202 (noise -> /m/ murmur),
  loudness rises 20.198-20.218, glottal 7. Gold at -42 re p99.
- more|often (gold 20.397 HUMAN-MOVED, sys 20.383, -15): glottal attack of the vowel-initial 'often' (glottal crest 9 at
  20.382, flux 9 ~20.39-20.40); /f/ of 'often' from ~20.43-20.44. CTC: separator 20.32-20.34, O 20.36-20.38, F
  20.38-20.40 (both INSIDE the gold 'more' / at the gold start). Gold 15 ms after the glottal peak; system on it.
- often|than (gold 20.576 ACCEPTED, sys 20.575) exact; than|they're (gold 20.681 ACCEPTED, sys 20.677) ok.
- they're|not (gold 20.800 HUMAN-MOVED, sys 20.836, +36) numeric: loudness flat (-12..-14); spectral change starts 20.788-
  20.82 (high_ratio -37 -> -31, flatness -7.3 -> -5, centroid 5.3 -> 6.0), transients 2-2.4 at 20.788-20.804,
  mfcc_change peak 3.0 at 20.804, formant_vel 0.86 at 20.808, ssl_change 0.58 at 20.812. CTC: E 20.78-20.80,
  separator 20.80-20.82, N 20.82. Gold (person) = onset of the spectral change = separator START; system = separator
  end.
- to|throw (gold 21.073 HUMAN-MOVED, sys 21.050, -23) numeric: 'to' vowel decays -13 (21.03) -> -20 (21.05) -> -30
  (21.066) -> -38..-40 (21.074-21.078 = loudness minimum); /T/ frication rises: high_ratio -25 (21.05) -> -14 (21.07)
  -> -8 (21.074) -> -6; zcr 0.08 -> 0.16 -> 0.31 -> 0.47 over 21.07-21.086; centroid 6.0 -> 7.1 at 21.07-21.074.
  Gold = the CROSSOVER (vowel decayed to its minimum, frication now dominant); system = start of the vowel decay /
  first frication influence. Same as i|thought (gold at the -36 crossing / trough). Hypothesis to test later:
  vowel -> fricative boundary ~ where high_ratio crosses ~-15 dB (HF energy overtakes LF).
- like.end (gold 21.366 HUMAN-MOVED, sys 21.546, +180) numeric: vowel -14 (21.316) -> -26 (21.332) -> -37 (21.34) ->
  closure at the floor -51 (21.348-21.356) -> /k/ BURST transient 8.7 at 21.364 -> 240 ms of HF noise 21.372-21.60
  (-27..-37, flatness -1.6..-2.4, centroid 7.2-7.9, zcr 0.2-0.35, low_ratio -15..-27) -> floor 21.612-21.644 -> 'they'
  21.652-21.668. CTC K 21.324-21.34 (0.33), separator 21.34-21.38, blank after. Gold (person) = AT THE BURST ONSET
  (closure + burst instant kept, the 240 ms noise excluded). 2nd 'like' in this clip: the accepted one (8.136) ended
  at the closure start. Post-release sustained noise excluded in all 5 cases (week x2, like x2 + are's exhale).
- not|to (gold 20.966 ACCEPTED, sys 20.956, -10): shared /t t/ closure ~20.94-20.965 (loudness down to level 2-3), one
  burst transient 9 at ~20.968, aspiration after. Gold AT THE BURST (accepted), system mid-closure. (Shared closures:
  middle in that|they/said|this/had|to, burst here, 25 ms after the burst in could|take - scatter.)
- throw|like (gold 21.255 ACCEPTED, sys 21.236, -19): /oU/ -> /l/, loudness flat; CTC: w 21.18-21.20, a spurious 'g'
  21.22-21.24, L 21.26-21.30. Gold = CTC L start; mfcc_change rising 21.24-21.27. No sharp landmark.
- they.start (gold 21.669 ACCEPTED, sys 21.656, -13): after the 'like' noise, floor at 21.612-21.644, /D/ release
  transients 2-5.7 at 21.644-21.668, loudness -59 -> -38 (gold) -> -13 (21.676). Gold mid-rise; system at the first
  transient.
- they|don't (gold 21.764 HUMAN, sys 21.758) ok.
- don't|have (gold 21.866 HUMAN-MOVED, sys 21.889, +23): /t/ unreleased, /h/ VOICED ([h\], periodicity 7-8 continues),
  loudness flat; formant_vel 6 at 21.86 (gold) and 8 at 21.892-21.896 (system). CTC: T 21.86-21.88, separator
  21.88-21.92, H 21.92. Gold at the CTC T onset / first formant movement; no sharp landmark.
- have|much (gold 22.031 HUMAN-MOVED, sys 22.044, +13): /v/ -> /m/; CTC V 21.98-22.00, silent E 22.00-22.02, separator
  22.02-22.08, M 22.08. Gold ~ separator start.
- much|of (gold 22.252 ACCEPTED, sys 22.250) exact: /tS/ frication 22.184-22.26 ends at 22.252-22.264 = gold (frication
  offset).
- of|an (gold 22.338 HUMAN, sys 22.337) exact; an|intermediate (gold 22.429 ACCEPTED, sys 22.434) ok.
- intermediate|game (gold 22.958 ACCEPTED, sys 22.948, -10): shared /t g/ closure ~22.96-23.03, VOICED (periodicity 5-6,
  loudness level 4-5 = -29..-33 re p99, +25..+29 over floor), /g/ burst transient 9 at ~23.036-23.04. Gold = closure
  START (loudness 6 -> 5).
- game|like (gold 23.157 ACCEPTED, sys 23.146, -11): /m/ -> /l/, ok.
- like|they're (gold like.end 23.285 ACCEPTED, gap 31 ms, they're.start 23.316 HUMAN-MOVED; sys continuous 23.292):
  'like' decays to the floor by ~23.29 (-58 re p99); floor to ~23.32; /D/ release transient ~9 at ~23.33. No /k/
  release (merged into the /D/ closure). CTC: K 23.26-23.28, silent E 23.28-23.30, separator 23.30-23.34, T 23.34.
  The person made the silent closure a GAP and started 'they're' ~15 ms before the release (+12 over floor).
- they're|usually (gold 23.449 HUMAN-MOVED, sys 23.514, +65): /r/ -> /j/, loudness flat; mfcc_change peak 6 at
  23.448-23.456 (= gold), ssl_change 9 at 23.476-23.492. CTC spells THEY'RE: T 23.30, H, E, Y 23.36-23.38, separator,
  ' 23.40, R 23.42-23.44, SILENT E 23.44-23.48, separator 23.48-23.50, U 23.52. Gold (person) = mfcc_change peak; the
  silent E pushed the separator/system 65 ms late. (Contractions: the apostrophe and silent letters each take CTC
  frames.)
- usually|either (gold 23.757 ACCEPTED, sys 23.750, ok); either.end (gold 24.064 ACCEPTED, sys 24.064) exact.
- pause 24.064-24.342: 'either' reaches the floor ~24.07-24.08; a low BREATH 24.08-24.30 (+6..+18 over floor, flatness
  7-9, centroid 5-7, zcr 2-4); floor 24.30-24.33; it's.start (gold 24.342 ACCEPTED, sys 24.338) at the first rise
  (-38 re p99), glottal 8-9 and transients up to 9 at 24.34-24.35.
- it's|usually (gold 24.469 ACCEPTED, sys 24.456, -13): /s/ frication 24.416-24.468, offset 24.46-24.476 (centroid,
  zcr, flatness fall). Gold ~ middle of the offset; system at its start.
- usually|either (gold 24.640 HUMAN, sys 24.634) ok.
- either|screens (gold 24.758 ACCEPTED, sys 24.825, +66) numeric: /s/ onset 24.752-24.76 (loudness -18 -> -29, high_ratio
  -29 -> -16, voicing 0.45 -> 0.17, formant_vel 2.5-2.8, zcr from 24.76) = gold. CTC: the R of 'either' at 24.76-24.80
  (INSIDE the /s/), separator 24.80-24.84 -> the CTC lags 50 ms at this vowel -> /s/ junction; system 70 ms into the /s/.
- screens|or (gold 25.269 ACCEPTED, sys 25.250, -19): weak voiced /z/ ~25.23-25.27 (high_ratio bump to level 6 at
  25.252-25.268), 'or' vowel after. Gold ~ end of the /z/ HF bump; system mid-/z/ (CTC separator 25.24-25.28).
- or|they're (gold 25.363 ACCEPTED, sys 25.326, -37): /r/ -> /D/: loudness step 8 -> 7 at ~25.312 (constriction onset),
  glottal crest rising to 9 at 25.356, loudness back to 8 at 25.356; mfcc_change peak 25.308-25.316, ssl_change peaks
  25.312-25.316 and 25.36-25.384. CTC separator 25.32-25.34, T 25.34. Gold = END of the /D/ constriction (release,
  after the glottal peak); system near its onset. /D/ label scatter: onset (convinced|that, like|they, in|their),
  middle (said|the, of|this, that|they), release (((they))|they, here) -> +-25 ms irreducible for /D/.
- they're|taking (gold 25.510 HUMAN, sys 25.508) exact: closure start (loudness falls to level 1-2 at 25.51-25.53), /t/
  burst transient 9 at ~25.54.
- taking|some (gold 25.761 ACCEPTED, sys 25.780, +19): /N/ -> /s/: flatness and high_ratio rise from 25.746-25.75, zcr
  from 25.758 (7-8 by 25.78), low_ratio drops 25.762-25.782. Gold = frication onset; system where the frication is
  fully developed (CTC separator 25.758-25.82 middle).
- some|kinda (gold 25.989 HUMAN-MOVED, sys 25.976, -13): /m/ -> /k/: loudness falls 25.954-25.99 to the closure (-35 re
  p99 at gold), burst ~26.02. Gold = closure start.
- kinda.end (gold 26.310 HUMAN-MOVED, sys 26.302) / intermediate.start (gold 26.343 HUMAN-MOVED, sys 26.362, +19): 'kinda'
  vowel falls 26.298-26.33 (gold end at -37 re p99), brief floor 26.326-26.34 (~15 ms), then a GRADUAL creaky onset
  (glottal crest rising to 9 ~26.36) 26.342-26.38. Gold start = the very first rise out of the floor (+0 dB);
  system 20 ms later at level 3.
- intermediate|to (gold 26.808 HUMAN-MOVED, sys 26.832, +24): shared /t t/: closure minimum ~26.796-26.812 (loudness level
  2-3), release -> aspiration from 26.804 (flatness 7-9, centroid up, zcr from 26.80) to ~26.83, vowel after. Gold
  (person) = AT THE RELEASE / aspiration onset; system at the vowel onset (end of aspiration).
- to|deep (gold 26.901 ACCEPTED, sys 26.895) ok.
- deep|shot (gold 27.076 ACCEPTED, sys 27.122, +46): /i/ ends with creak (glottal crest 9 at 27.056-27.068), short /p/
  closure 27.068-27.08, /p/ BURST transient 9 at 27.08-27.084, then a weak TONAL segment 27.084-27.11 (loudness level
  3, flatness 1-2, centroid 1, voicing fading 3 -> 0), /S/ frication from 27.112 (flatness 3 -> 9, centroid and
  high_ratio up, zcr from 27.124, low_ratio falling). Gold (accepted) = just BEFORE the burst (the burst + weak segment
  go to 'shot'); system = frication onset (+10). Accepted-from-old-system convention; a person might not hear the
  difference.
- shot.end (gold 27.542 HUMAN, sys 27.532): clip end.

### 009-0 summary (all 117 tokens / 232 boundaries read)
- Biggest errors and their causes:
  * non-lexical sound after a word kept by the system: week (+166: /k/ burst + sustained aspiration + exhale), like
    8.136 (+208) and 21.366 (+180) (burst + 110-240 ms noise), are (+188: exhale after a dip), was (+100: hum after
    the /z/ frication). Gold ends at the closure start / burst onset / the dip before the exhale / the frication end.
  * soft tokens: uh at clip start (+134/+73), (()) swallowing CTC 'THE' letters (+201/+165).
  * prolonged vowel with a long CTC blank before the next word (((they))|they -127).
  * false pauses: the|field (weak /f/ called silence), field|cause and the|podcast and that|they (silent closure made a
    pause), only|chance (closure).
  * CTC separator placement: late into fricatives (didn't|say +48, say|it?, the|site +38, a|signature +42, take|shots
    +45, either|screens +66, i've|said +32, some|shots +24) - often due to SILENT LETTERS (e in i've, some, take, like,
    site, little, elsewhere, they're, one, have; e+d in talked) and contractions (' takes frames); early in vowel
    decays before stops (do|take -53/-58, they|do -48/-79).
  * wrong edge of the owner's consonant: on|you (-50), things|that (-36), chance hum (-55), in|their (+35),
    they're|not (+36), they're|usually (+65).
- Suspected gold errors (accepted, never moved): say|it 0.634 (28 ms into the vowel, mid-CTC 'AY'), the|week 2.943
  (60 ms late into the /w/), could|take 12.792 (25 ms after the burst), the|things (silence inside 'the').
- Label scatter that no rule can remove: stop closures (closure start vs burst vs middle), /D/ (onset/middle/release),
  vowel-vowel and liquid joins without landmarks (+-15-25 ms).

## 009-1  DEEP RE-READ (21.18 s, 63 tokens)
- clip start: faint noise 0.00-0.07 (+9..+15 over floor, flatness 7-9), floor 0.068-0.126. uh.start (gold 0.121
  HUMAN-MOVED, sys 0.136, +15): glottal attack 0.128-0.14 (transients 9, glottal 7-9), loudness rise from 0.128. Gold
  ~10 ms BEFORE the onset (at the floor).
- uh|so (gold 0.453 HUMAN-MOVED, sys 0.431, -21) numeric: 'uh' vowel -4 re p99 to 0.416 (bright: high_ratio -18);
  darker tonal stretch 0.42-0.45 (centroid 6.2 -> 5.4, high_ratio -> -36, still -6..-9 re p99); loudness falls from
  0.452 (-8) to -20 (0.492); a VERY WEAK VOICED /s/ 0.472-0.50 (high_ratio up to -18, zcr 0.13, periodicity 0.6-0.7);
  glottal attack of the vowel 0.508-0.516 (periodicity dip 0.31, glottal 17.6-18.8, mfcc_change 4.1), vowel from 0.52.
  CTC: separator 0.376-0.40 (!), S 0.48-0.50. Gold (person) = START OF THE LOUDNESS FALL toward the weak /s/; system =
  onset of the darker stretch. A lenited /s/ has almost no frication - no HF landmark.
- so|please (gold 0.626 HUMAN-MOVED, sys 0.614, -12): loudness declines 0.61 -> 0.71 (voiced, weak /p/ closure), burst
  transients up to 9 ~0.72-0.735. CTC separator 0.60-0.64, P 0.66. Gold early in the decline (closure start region).
- please.end (gold 0.999 ACCEPTED, sys 0.992, ok): /z/ frication starts ~0.986 and continues WEAKLY (zcr 6-9, flatness
  7-9, centroid 7-9, +15..+20 over floor) to ~1.06; /t/ closure dip 1.062-1.078 (+3..+6); /t/ burst 1.078 + aspiration
  to ~1.15. Gold ends 'please' only ~10 ms into the /z/ (at -29 re p99) and leaves the weak /z/ tail in the gap. Same
  as race/this in 009-8: word-final /s z/ before a PAUSE end where the frication loudness falls, not where the
  frication stops.
- to.start (gold 1.079 ACCEPTED, sys 1.080) = the burst after the closure dip.
- to|our (gold 1.186 HUMAN, sys 1.182) ok; our|audience (gold 1.341 ACCEPTED, sys 1.358, +17): /@r/ -> /O/, ssl_change
  peak 8 at 1.342-1.346 = gold; CTC separator 1.32-1.36 (system at its end).
- audience|please (gold 1.678 ACCEPTED, sys 1.676, ok): no audible final /s/ in 'audience' (CTC C 1.62-1.64 + silent E
  1.64-1.66 without frication); loudness dip (closure) ~1.66-1.675; /p/ BURST + bright aspiration 1.675-1.70 (zcr up to
  9, centroid 9, flux 9). Gold = at the burst onset.
- please|join (gold 1.843 HUMAN-MOVED, sys 1.855, +11): one frication cluster 1.83-1.91 (zcr up to 8 at 1.848-1.856,
  centroid 9 then 6-8, loudness level 7-8), mfcc_change peak 1.888-1.892, small dip 1.912-1.916, vowel from 1.92.
  CTC: S 1.80-1.82, silent E 1.82-1.84, separator 1.84-1.88, J 1.88. The person put 'join' at the START of the whole
  frication cluster (the /z/ of 'please' merged into the /dZ/).
- join|us (gold 2.127 HUMAN, sys 2.135) ok.
- us|uh (gold us.end 2.447 ACCEPTED, uh.start 2.448 HUMAN-MOVED; sys 2.366 / 2.396; -81/-52): 'us' has NO /s/ frication
  (zcr 0, centroid 0-1 over 2.20-2.44) although the CTC emits S at 2.28-2.32; after the vowel a quieter VOICED
  low-centroid murmur 2.36-2.45 (-22..-27 re p99, periodicity 5-8, it is the quietest stretch within +-1 s - no real
  silence nearby); then a GLOTTAL ATTACK 2.456-2.476 (glottal crest 9, transient 9 at 2.464, periodicity dips) and
  the breathy 'uh' vowel (centroid 5-6, flatness 6-7) to 2.68. Gold: the murmur stays in 'us'; 'uh' starts AT the
  attack. System: 'us' ends at the level drop (word-ref -20 dB), a 30 ms gap, 'uh' inside the murmur.
  -> continuous voiced stretch after a word belongs to it up to the next break (3rd case: chance hum, movement tail).
  -> the filler begins at its own onset event (glottal attack) - same as uh 3.793 (009-0).
- uh|again (gold 2.684 HUMAN, sys 2.690) ok.
- again|on (gold 2.923 ACCEPTED, sys 2.944, +21): /n/ -> /A/, no landmark; CTC separator 2.86-2.90, O 2.92 (gold = O start).
- on|monday (gold 3.041 ACCEPTED, sys 3.036) ok.
- monday.end (gold 3.606 HUMAN-MOVED, sys 3.690, +84) / senior.start (gold 3.793 HUMAN-MOVED, sys 3.736, -57) numeric:
  'monday' vowel loud to 3.588, falls -21 / -24 / -28 (3.594-3.606 = gold end); a 50 ms pure HUM 3.612-3.66 (-16..-25
  re p99, periodicity 0.6-0.8, flatness -10..-11, high_ratio -46..-59); transition 3.66-3.69 (formant_vel 2.2-2.5); the
  /s/ of 'senior' 3.70-3.79 is VERY WEAK (-36..-43 re p99 = +0..+5 over the local floor, zcr 0.3-0.6, centroid 7.3-8.4,
  high_ratio ~0 dB, partly voiced); vowel 3.792-3.81 (mfcc_change 3.7). CTC: separator 3.44-3.52 (!), S 3.744-3.756.
  Gold (person): 'monday' ends at the dip BEFORE the hum (hum excluded), 'senior' starts AT THE VOWEL (the floor-level
  /s/ excluded). System kept the hum and started in the middle of the /s/.
  => a word-initial fricative at the floor level (+0..+5 dB) is NOT part of the word for the listener; at +6..+12
  (the|field) it is. Weak fricatives: this|film and i|thought also started at the louder part.
- senior|uh (gold 4.257 HUMAN-MOVED, sys 4.188, -69): 'senior' R letters to 4.10, separator 4.12-4.18; then a CREAKY /
  breathy stretch 4.18-4.25 (periodicity 2-3, flatness up to 5-6, glottal crest 8 at 4.184-4.196 and 4.24-4.256);
  centroid dip + formant_vel 4-5 at 4.236-4.256, TRANSIENT 8 at 4.268 (= glottal attack of 'uh'); 'uh' vowel 4.27-4.34
  (CTC A 4.30-4.32 - lexical this time). Gold (person) keeps the creaky tail in 'senior' and starts 'uh' at the
  attack (~10 ms before the transient); system cut at the creak onset.
- uh|barron's (gold 4.394 HUMAN-MOVED, sys 4.370, -24): /b/ closure 4.344-4.41 (loudness level 5-6, voicing 2-3,
  mfcc_change 9 at 4.36-4.368, glottal 9 at 4.376-4.392), burst -> loud vowel at 4.416. Gold ~15 ms before the burst
  (most of the closure given to 'uh'); system mid-closure.
- barron's|senior (gold 4.672 ACCEPTED, sys 4.680) ok (/z/ -> /s/).
- senior|managing (gold 4.888 HUMAN-MOVED, sys 4.902, +15): /@r/ -> /m/; CTC R 4.846-4.886, separator 4.886-4.906,
  M 4.906; centroid -> 0 from ~4.89 (nasal onset). Gold = separator START = nasal onset.
- managing|editor (gold 5.240 ACCEPTED, sys 5.262, +22): /N/ -> vowel with a glottal constriction: voicing dip
  5.238-5.246, vowel from 5.25. CTC: G 5.22-5.24, separator 5.24-5.28, E 5.30. Gold = start of the glottal dip
  (= separator start); system in the vowel onset.
- editor.end (gold 5.642 ACCEPTED, sys 5.632) / lauren.start (gold 5.694 ACCEPTED, sys 5.692): pause of 52 ms, both ok.
- lauren|rublin (gold 6.014 ACCEPTED, sys 6.012) exact; rublin.end (gold 6.579 ACCEPTED, sys 6.572) ok (-30 re p99).
- and.start (gold 6.837 ACCEPTED, sys 6.716, -121): pause 6.58-6.81 = a strong BREATH 6.60-6.78 (flatness 8-9, centroid
  7-8, high_ratio 8-9, zcr 4-7, low_ratio 0-2, +12..+24 over floor, CTC blank) then the floor 6.782-6.81; 'and' onset
  with transients 9 at 6.826-6.83 and 6.854-6.858, loudness up by 6.842; CTC A 6.87. Gold = onset after the floor
  (first transient). System started 'and' INSIDE the breath (its louder part is above the word-ref quiet threshold).
- and|deputy (gold 6.955 ACCEPTED, sys 6.962) ok.
- deputy|editor (gold deputy.end 7.419 / editor.start 7.431 ACCEPTED, sys 7.412): glottal dip 7.404-7.436 (loudness 7 -> 4,
  glottal crest 8 around 7.41-7.43) before the vowel-initial 'editor'; gold's 12 ms gap sits at the dip minimum;
  system at the dip start.
- editor.end (gold 7.925 ACCEPTED, sys 7.918) / ben.start (gold 7.966, sys 7.960): short floor pause, /b/ burst ~7.965. ok.
- ben|levisohn (gold 8.164 ACCEPTED, sys 8.158) ok.
- levisohn|will (gold 8.724 ACCEPTED, sys 8.705, -20): /n/ -> /w/: loudness 7 -> 6 at ~8.74, /w/ dip 8.768-8.772,
  mfcc_change 9 at 8.776-8.788, transient 9 at ~8.792 (release into /I/). CTC separator 8.66-8.70, W 8.76. Gold between
  the separator and the /w/ dip; no sharp landmark at 8.724.
- will|talk (gold 8.998 HUMAN, sys 8.994) ok: loudness falls into the /t/ closure ~8.96-9.0, burst ~9.004.
- talk.end (gold 9.379 HUMAN-MOVED, sys 9.366, -13) numeric: /k/ closure at the floor ~9.34, burst 9.348-9.352
  (transient 5.3), then a strange TONAL HF sound 9.352-9.42 (voiced 0.44-0.75, centroid 7.3 constant, zcr 0.19
  constant, low_ratio -17..-32, flatness -7..-9.6) decaying -23 -> -42 (a whistle/squeak or voiced release); floor
  9.428-9.456. Gold at -37 re p99 in the decay (the '-30..-37 end level' again); system at -23.
- with.start (gold 9.466 HUMAN-MOVED, sys 9.482, +16): /w/ rises from the floor at 9.456-9.46 (very tonal: high_ratio
  -42..-62); gold at -38 (start of the rise), system at -27.
- with.end (gold 9.775 ACCEPTED, sys 9.768, ok): CTC W-I-T-H to 9.74, separator 9.74-9.82; the word decays 9.76-9.82;
  a strong sibilant-like frication 9.816-9.86 (centroid 9, zcr up to 9, flatness 9) AFTER the separator = excluded
  by gold (breath through the teeth / unlettered). Gold at -33 re p99.
- thomas.start (gold 9.933 HUMAN-MOVED, sys 9.946, +13): /t/ burst transients 9 at 9.928-9.952; gold at the burst onset
  (floor level).
- thomas|kennedy (gold 10.309 ACCEPTED continuous; sys 10.276 / 10.338 = false pause): CTC S of 'thomas' at 10.20-10.236,
  separator 10.24-10.276, K 10.30-10.316. The vowel decays 10.25-10.31 (level 7 -> 5 -> 4), short closure 10.31-10.33,
  /k/ burst (transient 9 at 10.356-10.368) + strong aspiration 10.33-10.40 (zcr 5-7, centroid 8-9), /E/ from 10.41.
  Gold = CLOSURE START (loudness 5 -> 4). System: end at the separator end, start inside the aspiration.
  (The skim note 'gold cut at the burst 10.45' was wrong.)
- kennedy|chief (gold 10.705 HUMAN-MOVED, sys 10.731, +26): /i/ -> /tS/: loudness 8 -> 4 over 10.696-10.716 (closure),
  release after. CTC separator 10.62-10.68, C 10.70. Gold (person) = CLOSURE START; system ~ the release.
- chief|investment (gold 10.981 HUMAN-MOVED; sys chief.end 10.946 + investment.start 10.978 = small false gap, -34/-3):
  weak final /f/ of 'chief' = a dip 10.95-10.975 (loudness level 3, not frication-bright), then the GLOTTAL ATTACK of
  the vowel-initial 'investment' (transient 9 + glottal crest 9 + mfcc_change 9 at 10.968-10.984). Gold (person) =
  at the attack; the weak /f/ stays in 'chief'. System cut 'chief' at word-ref -20 dB (-30 re p99 at 10.946).
- investment|strategist (gold 11.402 ACCEPTED, sys 11.418, +16): /t/ closure at the floor 11.376-11.396, /t/ release
  transient 8 at ~11.388, /s/ frication from 11.404 (zcr 3 -> 9). Gold = FRICATION ONSET; CTC separator 11.36-11.40,
  S 11.40.
- strategist.end (gold 11.976 ACCEPTED, sys 11.986, +10): final /st/ frication 11.944-12.00 at loudness level 4-5;
  gold at -31 re p99 in the MIDDLE of the frication; the weak tail + /t/ closure (min 12.004-12.012) sit in the
  43 ms gap. of.start (gold 12.019 ACCEPTED, sys 12.024) after transients 2-6 at 12.008-12.02.
- of.end (gold 12.132 ACCEPTED, sys 12.130): the /v/ decays 12.12-12.2; gold at -28 re p99.
- global.start (gold 12.253 ACCEPTED, sys 12.210, -43): a bright CLICK at 12.224-12.236 (transient 9, high_ratio 9,
  centroid 5-7) out of the floor, back to the floor 12.24-12.26, then the /g/ burst (transient 8 at 12.26-12.264) and the
  vowel (loudness up by 12.272). Gold excludes the click and starts at the /g/ burst; the system started at the click.
  A click separated from the word by ~25 ms of floor is not part of the word (cf. um 14.216 in 009-8).
- global|wealth (gold 12.517 ACCEPTED, sys 12.509) ok.
- wealth|management (gold 12.772 ACCEPTED continuous; sys 12.750 / 12.792 = false 42 ms gap): weak /T/ 12.74-12.77
  (flatness 7, zcr 2) fading to a loudness MINIMUM 12.77-12.782 (-44 re p99, +6 over floor), /m/ rises from 12.786.
  Gold = continuous cut AT THE MINIMUM; system made the minimum a pause (edges +-20 ms around gold).
- management|at (gold 13.272 ACCEPTED, sys 13.268) ok.
- SPELLED LETTERS 'j p' (J.P. Morgan):
  - at|j (gold 13.418 ACCEPTED, sys 13.424) ok: shared /t dZ/ closure 13.404-13.432, /dZ/ release transient 9 at
    13.432-13.436, frication 13.42-13.48. Gold = closure (just before the release).
  - j|p (gold 13.614 ACCEPTED, sys 13.560, -54): the letter name 'J' = /dZ/ + /eI/; the CTC emits J only at the /dZ/
    (13.44-13.456) and leaves the /eI/ BLANK; separator 13.58-13.596; P letter 13.64-13.656. The /eI/ is loud to 13.576
    and decays -33..-36 re p99 at 13.60-13.616 (= gold), /p/ closure 13.62-13.64, BURST transient 9 at 13.644,
    aspiration 13.636-13.712, /i/ from 13.716. System = (A+B)/2 of the letter spikes = INSIDE the /eI/ (55 ms early).
    For letter names the vowel part carries no letter -> the lexical midpoint is wrong; the word end is where the
    vowel decays (the -30..-36 crossing), then the stop closure.
  - p|morgan (gold 13.797 HUMAN-MOVED, sys 13.755, -42): /i/ -> /m/ with loudness flat and centroid already 1;
    formant_vel 3-5 at 13.796-13.804 and 13.816-13.824; CTC separator 13.76-13.816, M 13.84. Gold (person) at the
    formant movement onset; system at the separator start.
- morgan.end (gold 14.319 ACCEPTED, sys 14.312) ok (-35 re p99); pause = BREATH 14.34-14.56 (flatness 9, centroid 7-8,
  high_ratio 8, zcr 3-7, +12..+27 over floor, CTC blank) + floor 14.56-14.58; about.start (gold 14.583 ACCEPTED, sys
  14.582) at the glottal attack (transient 9 at 14.584-14.596).
- about|the (gold 14.794 ACCEPTED, sys 14.798) ok.
- the|outlook (gold 14.907 ACCEPTED, sys 14.928, +21): GLOTTAL ATTACK of 'outlook' (glottal crest 8 at 14.90, transient 7
  at 14.908) = gold; system at the CTC separator (14.90-14.94) middle.
- outlook.end (gold 15.297 ACCEPTED, sys 15.276, -21): /k/ word decays 15.22-15.32; gold at -36 re p99, system at -27.
- for.start (gold 15.416 ACCEPTED, sys 15.370, -46): the /f/ of 'for' is AT THE FLOOR (loudness level 0, dB>floor 0-1)
  but clearly fricative (flatness 8-9, high_ratio 7-9, zcr 1-4) over 15.33-15.41; vowel onset 15.412-15.432. Gold starts
  at the VOWEL (floor-level /f/ excluded, as monday|senior); system started inside the /f/.
- for|the (gold 15.594 ACCEPTED, sys 15.556, -38): two dips: 15.556-15.572 (loudness 7, periodicity dip = /r/ offglide,
  CTC separator 15.52-15.56 ends here -> system) and 15.596-15.608 (loudness 6, flatness up, transient 5 at 15.604,
  glottal 7 = the /D/ constriction+release). Gold = ONSET OF THE /D/ DIP; mfcc_change 7 at 15.588-15.592.
- the|economy (gold 15.697 ACCEPTED, sys 15.714, +17): vowel-vowel, loudness flat; CTC separator 15.68-15.72, E 15.72;
  gold ~separator middle; formant_vel 9 at 15.736-15.76 (inside 'economy').
- economy|and (gold 16.252 ACCEPTED, sys 16.240) ok: loudness step 9 -> 8 -> 7 at 16.238-16.26 (glottal onset of 'and').
- and|financial (gold 16.426 ACCEPTED, sys 16.431) ok: /f/ frication onset ~16.418-16.43 (flatness 8-9, high_ratio 7-8)
  while the /d/ decays.
- financial|markets (gold 16.868 ACCEPTED, sys 16.873) ok.
- markets.end (gold 17.273 ACCEPTED, sys 17.276, ok): strong final /s/ 17.244-17.33 (zcr 8-9, centroid 9) - gold cuts
  it at -33 re p99 (mid-/s/) and leaves its weaker tail (loudness level 2-3) in the pause (4th case of a final
  sibilant before a pause cut at the ~-30 dB crossing). Pause = a sibilant-like BREATH 17.33-17.55 (+6..+18 over floor)
  + floor 17.56-17.61.
- and.start (gold 17.615 ACCEPTED, sys 17.618) ok: glottal attack transients 9 at 17.608-17.624.
- and|investment (gold 17.779 ACCEPTED, sys 17.798, +19): /d/ -> /I/, no strong landmark; CTC separator 17.72-17.76,
  I 17.78 (= gold).
- investment|strategies (gold 18.211 ACCEPTED, sys 18.232, +21): /s/ frication onset 18.21-18.222 (zcr, centroid) = gold;
  system at the CTC separator end.
- strategies.end (gold 18.834 ACCEPTED, sys 18.808, -26): the final /z/ is VOICED without frication (zcr 1-4, centroid
  2-4); the word decays slowly; gold at -33 re p99 (level 5 -> 4), system at -26. After it: low breathy noise
  18.85-19.06, floor ~18.96-19.13.
- thank.start (gold 19.162 ACCEPTED, sys 19.140, -22) numeric: weak /T/ 19.138-19.162 (transients 2-6, high_ratio -24 ->
  -12, loudness -55 -> -45 = +2..+12 over the local floor, -3..+3 over the global floor); vowel from 19.166 (-27 -> -3).
  Gold = VOWEL ONSET (floor-level /T/ excluded: 4th case with monday|senior, for.start, this|film). System at the /T/.
- thank|you (gold 19.309 ACCEPTED, sys 19.312) ok.
- you|for, for|listening (gold 19.426 / 19.549 ACCEPTED, sys 19.434 / 19.546) ok.
- listening|all (gold 19.949 ACCEPTED, sys 20.006, +57): /N/ -> CREAKY onset of the vowel-initial 'all': periodicity
  drops to 2-4 over 19.93-20.06, glottal crest up to 9 ~19.99, formant_vel 7 at 19.97, transients 5 at ~19.978 and
  8 at ~20.054. CTC: G 19.93-19.97, separator 19.97-20.03, A 20.09. Gold = START of the glottalisation (as bit|and,
  managing|editor, and|and); system at the separator middle.
- all|have (gold 20.300 ACCEPTED, sys 20.298) ok.
- have|a (gold 20.480 HUMAN-MOVED, sys 20.500, +20): weak voiced /v/ dip 20.448-20.48, then the GLOTTAL ATTACK of 'a'
  (glottal crest 7 at 20.48-20.484, transient 4 at 20.488, mfcc_change 7 at 20.492). Gold (person) = attack start.
- a|great (gold 20.546 HUMAN-MOVED, sys 20.587, +40): 'a' vowel to ~20.56; /g/ closure ~20.565-20.595 (loudness 8 -> 4),
  burst transient 9 at ~20.596-20.60. CTC: A 20.52-20.536, separator 20.54-20.60, G 20.60. Gold (person) = separator
  start, ~20 ms before the closure onset; system mid-closure.
- great|weekend (gold 20.770 ACCEPTED, sys 20.772) exact; weekend.end (gold 21.176, sys 21.168) = clip end region.

### 009-1 summary (63 tokens / 126 boundaries)
- Mostly good; the big errors: and.start -121 (system started inside a breath), us|uh -81/-52 (murmur after 'us' is
  part of 'us'; 'uh' starts at its glottal attack), monday|senior +84/-57 (hum after 'monday' excluded; floor-level
  /s/ excluded), senior|uh -69 (creaky tail stays with 'senior'), j|p -54 (letter-name vowel is CTC-blank),
  listening|all +57 (glottalised onset), global.start -43 (click), for.start -46 & thank.start -22 (floor-level
  initial fricatives excluded), for|the -38 (picked the /r/ dip instead of the /D/ dip).
- Recurring gold conventions confirmed with HUMAN-MOVED labels: vowel-initial words start at the onset of their
  glottal attack/constriction; stop-initial words at the closure start (kennedy|chief, and the accepted
  thomas|kennedy); continuous post-word voiced stretches belong to the word; separate hums/breaths/clicks do not;
  final sibilants before pauses end at ~-30..-36 re p99.

## 009-2  DEEP RE-READ (25.5 s, 93 tokens)
- SPELLED 'U F C' (all HUMAN-MOVED): CTC hears 'YU ... SEeS' (no F letter; C heard as S-E). Acoustics: /ju/ 0.18-0.26,
  /E/ of 'F' 0.26-0.30 (voiced, creaky glottal 8-9), ONE frication 0.325-0.405 (= /f/ of F + /s/ of C: flatness 9,
  centroid 9, zcr 9), /i/ of 'C' 0.408-0.45, 'is' /Iz/ ~0.45-0.49 (weak /z/ zcr 3-4 at 0.464-0.48).
  - u|f (gold 0.261, sys 0.300, +39): system gave the /E/ of 'F' to 'U' (cut at the frication onset); gold at ~0.26
    (vowel-vowel, no landmark: glottal creak region).
  - f|c (gold 0.329, sys 0.335): gold at the FRICATION ONSET (the whole /f s/ frication goes to 'C').
  - c|is (gold 0.453, sys 0.403, -50): system cut at the frication offset (giving 'C' only its /s/); gold after the
    /i/ (loudness 9 -> 8 step at 0.456). Letter names again: their vowel is CTC-blank, so letter-anchored priors
    misplace them.
- is|gon' (gold 0.508 HUMAN, sys 0.512), gon'|be (gold 0.636 HUMAN, sys 0.648) ok. CTC hears 'gon'' as 'COULD'.
- be|left (gold 0.713 ACCEPTED, sys 0.730, +17) ok-ish.
- left|behind (gold 0.883 ACCEPTED, sys 0.930, +47): /f/ ~0.83-0.86, /t/ closure ~0.87-0.885, /t/ release transient 6
  at 0.888, noise to ~0.93, /b/ burst transient 9 at 0.932. Gold = right before the /t/ RELEASE (release + noise + /b/
  closure given to 'behind'); system at the /b/ burst.
- behind|unless (gold 1.319 HUMAN, sys 1.329) ok.
- unless|people (gold 1.624 ACCEPTED continuous; sys unless.end 1.574 + people.start 1.634 = false gap, -49/+9): /s/
  strong 1.53-1.565 (zcr 8, centroid 9), decays to the floor by ~1.59, /p/ closure AT THE FLOOR 1.59-1.635, BURST
  transient 9 at 1.636. Gold = continuous cut LATE in the closure (12 ms before the burst: the closure goes to
  'unless' this time). System ended at the /s/ decay (-36) and started at the burst. (Skim note times were wrong.)
- people.end (gold 2.119 ACCEPTED, sys 2.122) ok; like.start (gold 2.153 HUMAN, sys 2.158) ok.
- like|the (gold 2.354 HUMAN-MOVED, sys 2.388, +34): /k/ release = transient 5 + flux 9 at 2.348-2.352 (gold right at
  it); CTC places 'THE' at 2.42-2.50 (late). System 35 ms after the release.
- the|boosters (gold 2.513 ACCEPTED, sys 2.520) ok.
- boosters|get (gold 2.884 ACCEPTED continuous; sys boosters.end 2.860 + get.start 2.908): 'boosters' /s/ 2.65-2.74,
  /@r/ 2.74-2.80, weak /z/ 2.80-2.856 (CTC S 2.82-2.856), /g/ closure 2.856-2.876 (loudness level 4), BURST transient 9
  at 2.876, vowel from 2.884. CTC separator 2.86-2.896, G 2.90 (late). Gold = at the BURST (closure given to
  'boosters'); system: end at the closure start, start 25 ms after the burst.
- get|behind (gold 3.034 ACCEPTED, sys 3.056, +23): /t/ + /b/ closure 3.016-3.05 (loudness 5-4), bursts transient 9 at
  3.048-3.052 and 3.064. Gold = closure start; system at the first burst.
- behind|this (gold 3.471 ACCEPTED, sys 3.478) ok.
- this.end (gold 3.874 ACCEPTED, sys 3.874) exact: a 200 ms /s/ (3.67-3.87, zcr 9) fading; both at -38 re p99; a faint
  bright tail 3.88-3.91 in the pause.
- and.start (gold 3.954 ACCEPTED, sys 3.952) ok (glottal attack transient 9 at ~3.956).
- and|uh (gold 4.223 HUMAN, sys 4.220) ok: mfcc_change 9 at 4.216-4.228, formant_vel 7 at 4.204, pitch jump ~4.21.
- uh.end (gold 4.505 ACCEPTED, sys 4.502) ok (-37 re p99). Pause 4.51-5.155: long BREATH 4.52-5.10 (+12..+21 over floor,
  flatness 8-9, centroid 7-9); pyannote speech_prob DOES drop to 0 over 4.56-5.02 here. A click at 5.076-5.084
  (transient 6.6), floor 5.09-5.15.
- so.start (gold 5.155 ACCEPTED, sys 5.162) ok: /s/ onset with transient 20 at 5.156, zcr 0.66-0.74 from 5.164.
- so|there's (gold 5.304 ACCEPTED, sys 5.302) ok.
- there's|another (gold 5.460 HUMAN-MOVED, sys 5.482, +22): weak /z/ 5.408-5.456 (flatness 7-9, centroid 6-7, zcr 3-4),
  offset 5.456-5.468. Gold = FRICATION OFFSET; system at the CTC separator start (5.48; S 5.44-5.476).
- another|option (gold 5.731 HUMAN-MOVED, sys 5.747, +16): /@r/ -> /A/, loudness flat, no landmark; CTC separator
  5.68-5.72, O 5.76.
- option.end (gold 6.143 ACCEPTED, sys 6.132) ok (-34 re p99).
- and.start (gold 6.491 ACCEPTED, sys 6.496) ok (glottal attack transient 9 at 6.488-6.496).
- 'and uh uh you know i' 6.49-7.66 (all HUMAN-MOVED) numeric:
  * and|uh (gold 6.777, sys 6.744, -33): /ae/ 6.50-6.70, /n/ NASAL 6.712-6.76 (centroid 0, flatness 1), nasal release
    6.76-6.776 (centroid back up, formant_vel 5, mfcc_change 8 at 6.752). Gold = END of the nasal (nasal-final word
    -> murmur offset); system = middle of the nasal.
  * uh(1) = a 420 ms flat vowel 6.78-7.19 (loudness -9..-12, periodicity 0.5, centroid 6.5); glottal event 7.17-7.18
    (glottal crest 22-24, transients 5.7); decays -16 -> -24 at 7.186-7.194 (= gold uh.end); quiet creaky tail
    7.198-7.25 (-30..-44); near-floor 7.254-7.286 (-44..-50).
  * uh(2) starts 7.277 (gold), just before a BURST at 7.290 (transient 19, glottal 21, mfcc_change 4.3; loudness
    -43 -> -13); then ONE continuous voiced stretch 7.29-7.46 (-7..-13, periodicity 0.6, no landmarks) that gold splits
    uh(2) 48 ms / you 61 ms / know 65 ms. CTC hears 'A I N ' T' (!) over it.
  * System: put uh(2) and 'you' INSIDE the long uh(1) (7.07-7.37): -122/-205/-170/-170. It ignored the island
    structure: island 1 = and + uh(1) (6.49-7.19), quiet 7.20-7.28, island 2 = uh(2) you know i (7.29-7.66).
    => tokens should be assigned to islands (speech stretches between quiet gaps) monotonically using the lexical
    evidence where it exists; within an island without landmarks, split proportionally.
  * know|i (gold 7.454 HUMAN, sys 7.460) ok.
- i.end (gold 7.660 HUMAN-MOVED, sys 7.626, -34): /aI/ decays 7.61-7.67; gold at -34 re p99 (the end-level rule), system
  at -28. Pause 7.66-8.14 = breath (flatness 9, centroid 7-9); speech_prob 2 over 7.78-8.00.
- i.start (gold 8.141 ACCEPTED, sys 8.170, +29): breath fades to a FLOOR dip 8.142-8.162, then the 'I' onset 8.166-8.20
  with a glottal attack (transients up to 9 ~8.19, glottal crest 9 at 8.198-8.202). Gold (accepted) sits at the START
  of the floor dip (-54 re p99) - 25 ms of inaudible silence included; system at the onset. Label noise in silence.
- i|like (gold 8.247 HUMAN, sys 8.248) exact.
- like|those (gold 8.406 ACCEPTED continuous; sys 8.394 / 8.432 = false gap, -11/+25): /k/ closure 8.37-8.40 (loudness
  level 5-6), /k/ RELEASE frication 8.406-8.426 (transient 9 at 8.418, flatness 9, centroid 7-8, zcr 4), then /D/ +
  vowel from 8.43 (glottal crest 9). Gold = release ONSET (the release frication goes to 'those', as left|behind);
  system made closure-to-release a gap.
- those|guys (gold 8.568 HUMAN, sys 8.574) ok; guys|i (gold 8.827 ACCEPTED, sys 8.817): /z/ frication 8.784-8.832
  (zcr 5-9, flatness 9), offset 8.832-8.84 ~= gold.
- i|like (gold 8.877 HUMAN, sys 8.858, -18): 'I' is 48 ms; gold = CTC L onset; no sharp landmark.
- like|the (gold 8.989 ACCEPTED, sys 9.003) ok.
- the|guys (gold 9.069 ACCEPTED, sys 9.099, +29): 'the' vowel, short /g/ closure ~9.06-9.068 (loudness 7 -> 6, creaky:
  glottal 8-9), BURST transients 8 at ~9.072-9.08, loudness up after. CTC separator 9.06-9.10, G 9.10. Gold ~5 ms
  before the burst; system at the separator end.
- guys|that (gold 9.273 ACCEPTED, sys 9.266) ok.
- that|run (gold 9.343 HUMAN-MOVED, sys 9.371, +28): 'that' /t/ release + aspiration 9.30-9.34 (flatness 8, centroid
  6-7), then /r/ (flatness falls 7 -> 1 over 9.34-9.40, centroid 3). Gold (person) = END OF THE ASPIRATION (release
  kept by 'that'); system at the CTC separator start (9.36).
- run|this (gold 9.544 ACCEPTED, sys 9.528, -16) ok.
- this|one (gold 9.695 ACCEPTED, sys 9.712, +17): /s/ (zcr 9) 9.632-9.684, offset 9.684-9.696 = gold (FRICATION OFFSET);
  system at the /w/ formant movement / CTC separator (9.68-9.72).
- one.end (gold 10.000 ACCEPTED, sys 10.026, +26): after /wVn/ a LONG QUIET HUM ~9.90-10.08 (centroid 0, flatness 1-2,
  loudness flat at -30..-35 re p99) then decay to ~10.16. At 10.000 a TRANSIENT 9 + flux 9 and the sound turns
  breathier (flatness 1 -> 3-5, high_ratio up). Gold = at that change; the level rule cannot decide inside a flat
  hum. System 26 ms later.
- um.start (gold 10.156 ACCEPTED, sys 10.158) ok.
- um.end (gold 10.543 ACCEPTED, sys 10.538) ok: /m/ hum drops at 10.534-10.546 (gold at -41 re p99).
- so.start (gold 10.567 ACCEPTED, sys 10.586, +19): /s/ onset = transient 9 + centroid jump at 10.566-10.57 = gold.
- so|a (gold 10.676 ACCEPTED, sys 10.706, +30): vowel-vowel, loudness flat, no landmark; gold = end of the CTC A
  letter (10.66-10.68); system at the separator (10.68-10.74) middle.
- a|little (gold 10.721 ACCEPTED, sys 10.740, +19), little|different (gold 10.920, sys 10.908) - no sharp landmarks.
- different|feel (gold 11.128 HUMAN-MOVED, sys 11.158, +30): unreleased /t/, /f/ frication rises from 11.126-11.14 (zcr
  from 11.126, flatness/centroid/high_ratio from ~11.138). Gold (person) = FRICATION ONSET; CTC T 11.10-11.12,
  separator 11.12-11.16 (system at its end).
- feel|a (gold 11.429 HUMAN, sys 11.440), a|little (gold 11.482, sys 11.488), little|different (gold 11.711, sys 11.711) ok.
- different|approach (gold 11.941 HUMAN-MOVED, sys 11.964, +23): the /t/ of 'different' is a GLOTTAL STOP (glottal crest
  8 at 11.926-11.93, no burst); CTC N 11.922-11.938, T 11.942-11.958, separator 11.962-11.978, A 11.982. Gold (person) =
  at the CTC T onset = the glottal stop -> assigned to the vowel-initial 'approach' (its glottal attack).
- approach.end (gold 12.523 HUMAN-MOVED, sys 12.474, -49): final /tS/ frication fades 12.43-12.53 (loudness 7 -> 0);
  the PERSON included the whole fading frication down to -50 re p99 (+10 over floor); system at -28 (word-ref -20 dB).
  !! Contrast with the ACCEPTED final-sibilant ends at -30..-36 re p99 (please, race, markets, strategist): the -30
  rule may be the OLD SYSTEM's convention that reviewers tolerated; human-moved ends of fading fricatives go deeper
  (approach -50, the|site/a|signature onsets at the very first rise). Both are 'acceptable' to the ear.
- pause 12.53-13.17: breath (+12..+18 over floor), speech_prob 0 over 12.55-13.15.
- and.start (gold 13.192 ACCEPTED, sys 13.212, +20) numeric: floor to 13.168; onset transient 11.4 at 13.172 (loudness
  -60 -> -38); a quieter voiced pre-segment 13.172-13.20 (-30..-39); main glottal attack 13.204-13.22 (transients 5.6-
  6.8, loudness -> -7). Gold in the pre-segment (21 ms after the first onset); system at the main attack.
- 'and that it was a was at' 13.19-14.21 (HUMAN-MOVED): the CTC MISRECOGNISES it as 'THEY HAD ... i S ... a S' - the
  letter prior is garbage here; the system followed it: that|it -101, it|was -41, was|a -29, a|was -26.
  Acoustic landmarks match the person's cuts: that|it 13.526 inside the glottal /t/ dip (periodicity dip 13.488-13.54,
  loudness 9 -> 6 at 13.512-13.54); it|was 13.614 right after a glottal event (glottal crest 8 at 13.60-13.612);
  was|a 13.813 = /z/ FRICATION OFFSET (voiceless /z/ 13.728-13.804, flatness 9, zcr 6-9); a|was 13.856 (/w/ onset);
  was|at 13.992 = 2nd /z/ offset (frication 13.912-13.984, zcr falls 9 -> 3 at 13.98-13.996).
  => when the CTC's letters do not match the transcript, a phone-class landmark search on the transcript's own
  phones (z, w, t...) still finds the right cuts.
- at.end (gold 14.208 ACCEPTED, sys 14.190, -18): gold at -31 re p99 (+7 over floor), system at -27.
- a (14.267-14.495, ACCEPTED; sys 14.268-14.470): a 230 ms 'a' between two short pauses; a.end gold at -34 re p99,
  system at -30 (-25 ms). private.start (gold 14.525, sys 14.528): /p/ burst transient 9 at 14.52-14.528.
- private|home (gold 14.826 HUMAN, sys 14.839, +13) ok.
- home|in (gold 15.028, sys 15.015), in|manhattan (gold 15.114, sys 15.096, -18), manhattan|beach (15.451 / 15.452) ok.
- beach.end (gold 15.717 ACCEPTED, sys 15.714): /tS/ frication 15.63-15.77 fading; gold (accepted) at -33 re p99 in the
  middle of the fading frication (contrast approach.end HUMAN at -50). man.start (gold 15.847, sys 15.850) ok.
- man|they (gold 16.140 ACCEPTED, sys 16.116, -24): /n/ + /D/ (assimilated) = one nasal segment 16.106-16.15 (centroid
  0, flatness 0-1), release at 16.154 (glottal crest 9, transient 9). Gold ~2/3 into the shared nasal; system at the
  CTC separator (16.10-16.14).
- they|had (gold 16.241 HUMAN, sys 16.256, +16): gold = CTC H onset; no strong landmark.
- had|a (gold had.end 16.315 + a.start 16.323 HUMAN; sys 16.346, +31/+23): weak voiced /d/ closure = periodicity dip
  16.294-16.322, release transient 7 at ~16.31. Gold = right after the /d/ RELEASE; system at the CTC separator end.
- a|sushi (gold 16.428 HUMAN-MOVED, sys 16.453, +25): /s/ onset 16.418-16.438 (flatness, centroid, zcr from 16.434,
  formant_vel 8 at 16.434-16.446). Gold = FRICATION ONSET; system at the separator end.
- sushi|bar (gold 16.850 ACCEPTED, sys 16.834, -16): /b/ closure from ~16.855 (loudness 7 -> 6), burst transient 9 at
  ~16.878. Gold ~ closure start.
- bar|to (gold bar.end 17.148 + gap + to.start 17.187, ACCEPTED; sys continuous 17.114, -34/-73): 'bar' decays 17.11-17.18
  (level 7 -> 3), /t/ closure ~17.16-17.19, BURST transient 9 at 17.194-17.198. Gold: end at -35 re p99, start just
  before the burst. System cut at the CTC separator (17.10-17.16) at -17 re p99 and made it continuous.
- to|die (gold 17.315 ACCEPTED, sys 17.293, -22): /d/ closure from 17.314 (loudness 6 -> 5), burst ~17.35. Gold =
  closure start.
- die|for (gold 17.544 HUMAN-MOVED; sys die.end 17.562 + for.start 17.606 = false gap, +19/+62): /f/ frication 17.55-17.65
  (flatness 6 -> 9 from 17.55, centroid from 17.574, zcr from 17.582) at loudness level 4 (-32 re p99, ~+4 over the
  local floor). Gold (person) = the FIRST flatness rise. The system called the weak /f/ a pause.
  NOTE: this weak /f/ is INCLUDED because it follows the previous word continuously; the floor-level initial
  fricatives that were excluded (senior, for 15.416, thank) came right AFTER A PAUSE.
- for|they (gold 17.787 ACCEPTED, sys 17.762, -25): /r/ -> /D/, no strong landmark.
- they|had (gold 17.896 ACCEPTED, sys 17.884) ok.
- had|sushi (gold 17.950 ACCEPTED, sys 17.974, +24): /s/ onset 17.944-17.96 (flatness, centroid, zcr, transient 5 at
  17.952) = gold; system at the fully developed frication.
- sushi|chef (gold 18.344 ACCEPTED, sys 18.377, +32): small loudness dip at 18.344 (end of /i/), a first frication burst
  18.36-18.38 (zcr 5-6, centroid 5-7), main /S/ from ~18.39. Gold 16 ms before the first frication; system at its peak.
- chef|there (gold chef.end 18.694 + there.start 18.696 ACCEPTED continuous; sys 18.680 / 18.726): /f/ frication 18.588-
  18.688, then a SILENT stretch at the floor 18.688-18.74 (-36 re p99), 'there' rises from 18.744. Gold: continuous at
  the frication end - the silence belongs to 'there' (/D/ closure). System: end at the frication end (-14, ok),
  start mid-silence (+30).
- there|it (19.023 / sys 19.008), it|was (19.099 / 19.088; gold at -31..-34 in the /t/ dip), was|really (19.253 / 19.248)
  ok (all ACCEPTED).
- really|good (gold 19.507 ACCEPTED, sys 19.486, -21): /g/ VOICE BAR 19.502-19.522 (flatness 0, centroid 0), burst
  transient 9 at 19.53. Gold = closure start (+5 ms); system at the CTC separator.
- good.end (gold 19.772 ACCEPTED, sys 19.784, +12): /d/ closure 19.75-19.77 (flatness 0), release frication 19.774-19.79
  with transient 9 at 19.786. Gold (accepted) ends BEFORE the release; system at the release. (stop.end in 009-8
  kept burst + aspiration: stop-release inclusion is inconsistent in gold.)
- uh.start (gold 20.342 HUMAN, sys 20.344): sound rises from ~20.29 with clicks (transients 4-6) and the voiced onset
  (glottal crest 9 at 20.354-20.39); gold starts ~50 ms after the first noise (pre-voicing clicks excluded).
- uh|huge (gold 20.601 HUMAN, sys 20.590, -11): /h/ onset = flatness / centroid / zcr rise from ~20.60 = gold.
- huge|tower (gold 20.917 ACCEPTED continuous; sys 20.906 / 20.934): /dZ/ frication ~20.85-20.91 merging with the /t/;
  closure dip 20.916-20.93 (loudness level 3); gold = closure start (-39 re p99). Small system gap.
- tower|like (gold 21.264 HUMAN, sys 21.258), like|a (gold 21.474 HUMAN, sys 21.473): exact; the /k/ release (transient
  9 at 21.444-21.452 + frication to ~21.47) stays with 'like' (human).
- a|charcuterie (gold 21.549 ACCEPTED, sys 21.570, +21): /S/ onset 21.544-21.56 (flatness, centroid), zcr from 21.556;
  gold = frication onset.
- charcuterie|board (gold 22.109 ACCEPTED, sys 22.096): /b/ voice bar from ~22.10 (flatness 0), burst transient 9 at
  22.156; gold ~ closure start.
- board|tower (gold 22.353 ACCEPTED, sys 22.340 / 22.372): shared /d t/ closure 22.328-22.37 (voiced then silent), /t/
  burst transient 9 at 22.372-22.376. Gold = closure MIDDLE; system: gap from closure onset to burst.
- tower.end (gold 22.875 ACCEPTED, sys 22.868) ok (-36 re p99). Pause 22.88-23.38 = breath + floor 23.18-23.32 with
  clicks (transients 9 at ~23.246-23.25, 7-9 at ~23.31, ~23.36). great.start (gold 23.385, sys 23.388) ok.
- great|desserts (gold 23.589 ACCEPTED, sys 23.587) ok.
- desserts.end (gold 24.277 HUMAN-MOVED, sys 24.198, -79) numeric: final /s/ 24.02-24.30 (zcr 0.3-0.6, centroid 8-8.5)
  decaying -21 (24.16) -> -30 (24.226) -> -40 (24.262) -> -49 (24.274 = gold) -> -58 (24.30). The PERSON ended at
  -49..-51 re p99 (+12 over floor), i.e. the end of audible frication. System -25 (word-ref -20 dB).
  *** Final fricative before a pause: HUMAN-MOVED ends at -49..-51 re p99 (approach, desserts); ACCEPTED ends at
  -30..-36 (please, race, markets, strategist, beach, this). Two conventions ~40 ms apart on a slow decay; a
  compromise at ~-40 re p99 costs ~+-15 ms on both.
- open.start (gold 24.830 ACCEPTED, sys 24.834): glottal attack transient 9 at 24.83.
- open|bar (gold 25.104 ACCEPTED, sys 25.088, -16): /n/ + /b/ voice bar 25.038-25.10 (centroid 0, flatness 0-1), /b/
  BURST transient 9 at 25.102-25.106 = gold.
- bar.end = CLIP END (gold 25.492 HUMAN-MOVED, sys 25.404, -88): 'bar' decays 25.40-25.53 (9 -> 3); gold at -37 re p99
  (the end-level rule); the system ended 88 ms early at -11 re p99 (letter-anchored clip-edge logic: CTC separator
  25.40-25.48). Clip ends need the same decay rule as pause ends. (Skim note times were wrong.)

### 009-2 summary (93 tokens / 186 boundaries)
- Big errors: 'and uh uh you know i' island mis-assignment (-122/-205/-170), and|that|it|was|a|was with CTC
  misrecognition (-101/-41/-29/-26), bar clip end (-88), desserts final /s/ (-79, human includes the full fade),
  bar|to (-34/-73: false continuity at the separator), die|for (+62: weak /f/ called a pause), c|is (-50: letter
  names), approach.end (-49), unless|people (-49), left|behind (+47).
- New/confirmed conventions: fricative onset/offset rules hold for human-moved cuts (a|sushi, different|feel,
  there's|another, was|a, was|at); nasal-final -> murmur offset (and|uh); islands separate fillers; after a PAUSE a
  floor-level initial fricative is excluded, but INSIDE continuous speech a weak /f/ is part of the next word.

## 009-3  DEEP RE-READ (26.5 s, 85 tokens)
- and.start (gold 0.000, sys 0.006): clip starts in speech.
- and|yet (gold 0.090 ACCEPTED, sys 0.129, +39): very reduced 'and' (~0.03-0.09), tonal /j/-like stretch from 0.068
  (flatness 0, centroid 1); gold = CTC separator start (0.096); system later. Weak landmark.
- yet|they (gold 0.298 ACCEPTED continuous; sys 0.270 / 0.326): shared /t D/ closure 0.28-0.33 (loudness level 2-3),
  /D/ release transient 9 at 0.336. Gold = closure MIDDLE; system made it a gap (decay onset -> release).
- they|still (gold 0.480 HUMAN-MOVED, sys 0.524, +44): /s/ onset 0.468-0.488 (centroid, zcr, high_ratio rising) = gold.
- still|didn't (gold 0.911 ACCEPTED, sys 0.924) ok.
- didn't.end (gold 1.287 ACCEPTED, sys 1.270, -17): gold at -45 re p99 (deeper than the usual -30..-36), system -24.
  Pause 1.29-1.525: low noise + floor; report.start (gold 1.525, sys 1.528) ok.
- report|that (gold 1.964 ACCEPTED continuous; sys 1.932 / 2.022 = gap, -31/+57): /t/ closure ~1.932-1.96 (level 1-2,
  +6..+9 over floor), release + /D/ frication 1.956-2.0 (transient 9 at 1.972-1.976, flatness 7-8), vowel ~2.0.
  Gold = END of the closure (the release + /D/ frication go to 'that'); system: closure made a gap and 'that'
  started after the frication.
- that|to (gold 2.238 ACCEPTED continuous; sys 2.198 / 2.306 = gap, -39/+67): 'that' decays ~2.20-2.24, SILENT shared
  /t t/ closure ~2.24-2.30 at the floor, /t/ burst ~2.30. Gold early in the closure (-56 re p99); system: decay onset
  to burst as a gap.
- to|the (2.429 / 2.418), the.end (2.535 / 2.530), parents.start (2.624 / 2.622, /p/ burst) ok (ACCEPTED).
- parents|they (gold 3.037 HUMAN-MOVED continuous; sys parents.end 3.002 + they.start 3.042 = false gap, -34/+5): final
  /s/ 2.972-3.04 (zcr 6-9, centroid 6-9) at loudness level 5 (-33 re p99), /D/ from 3.04 (centroid 9 -> 2). Gold =
  FRICATION OFFSET; the system called the weak end of the /s/ a pause (word-ref -20 dB).
- they|didn't (gold 3.144 ACCEPTED, sys 3.156) ok.
- didn't|think (gold 3.390 ACCEPTED continuous, sys 3.378 / 3.400): /T/ onset with transients 8 at 3.396 and 7 at
  ~3.404 (flatness 5-8, zcr 3-5) = gold. ok.
- think|they (gold 3.553 ACCEPTED, sys 3.571, +17): /k/ closure from 3.556 (loudness dip), release transient 6 at
  3.572-3.58. Gold = closure start; system = release.
- they|had (3.703 / 3.721, +17), had|a (gold 3.870 HUMAN, sys 3.886, +17: glottal crest 8-9 at 3.844-3.868 = /d/ +
  glottal onset of 'a'; gold at its end), a.end (4.113 / 4.114) ok.
- responsibility (4.468-5.404) exact both edges; responsibility|to exact.
- to|say (gold 5.551 ACCEPTED, sys 5.554): 'to' = /t/ burst transient 9 at 5.436-5.444 + aspiration + short vowel;
  /s/ onset at 5.548 (centroid, zcr) = gold.
- say|oh (gold 5.819 HUMAN, sys 5.835, +16): vowel-vowel with a glottal constriction (periodicity dip + glottal crest
  8-9 over 5.812-5.848); gold at its START.
- oh|by (gold 5.965 ACCEPTED, sys 5.981, +16), by|the (gold 6.122 HUMAN, sys 6.117) ok.
- the|way (gold 6.186 HUMAN-MOVED, sys 6.215, +28): /w/ constriction ~6.16-6.19 (centroid 0-1, flatness dip, transient 6
  at 6.16, loudness dip 7 at 6.184); gold near its END; CTC separator 6.20-6.24, W 6.24 (system at the separator).
- way.end (gold 6.401 ACCEPTED, sys 6.390) ok.
- your.start (6.775 / 6.774) ok. your.end (gold 6.943 ACCEPTED, sys 6.910, -33): /r/ decays 6.88-6.95; gold at -49 re p99
  (deep), system -22.
- kid.start (gold 6.979 HUMAN, sys 6.980): /k/ burst transient 9 at 6.976-6.984. kid.end (7.223 / 7.220) ok.
- passed.start (7.277 / 7.278, /p/ burst) ok; passed|out (7.590 / 7.598) ok.
- out.end (gold 7.789 ACCEPTED, sys 7.760, -29): /t/ word decays 7.72-7.80; gold at -49 re p99, system -26.
  today.start (gold 7.812 HUMAN, sys 7.820): /t/ burst transient 9 at ~7.82-7.832, gold just before it (+9 over floor).
- NOTE: accepted pause-ends in 009-3 sit at -45..-49 re p99 (didn't 1.287, your, out) vs -30..-36 in 009-8/009-1:
  the end LEVEL convention varies by clip/reviewer -> a single dB threshold has +-15 ms scatter.
- today|at (gold 8.272 HUMAN, sys 8.292, +20): glottal attack of 'at' (glottal crest 9 at 8.252-8.264, transient 9 at
  8.256); gold ~10 ms after it (here the person cut at the END of the glottal event, not its start).
- at.end (8.409 / 8.420) ok; p.start (8.491 / 8.490) = /p/ burst.
- SPELLED 'p e' (gold p|e 8.686 ACCEPTED, sys 8.544, -142): /p/ burst 8.49, then ONE continuous /i:/ 8.51-9.15 (640 ms,
  loudness 8-9 flat, no acoustic landmark at all) covering both letter names /pi:/ + /i:/. CTC: P 8.52-8.56,
  separator 8.70-8.74, E 8.78-8.86. Gold = at the CTC separator START; the system cut right after the P letter
  (aspiration -> vowel change). With no acoustics, the CTC separator is the only evidence and must be followed.
- e.end (9.148 / 9.150) ok.
- that's.start exact (9.776).
- that's|because (gold 10.094 ACCEPTED continuous; sys 10.060 / 10.122 = gap): /s/ 9.99-10.08 (zcr 5-9), /b/ closure
  10.084-10.112 (level 2), BURST transient 9 at 10.116-10.12. Gold = closure START (-51 re p99); system: end in the /s/
  (-23), start at the burst.
- because.end (gold 10.756 ACCEPTED, sys 10.742, -14): /z/ frication 10.70-10.76 fading; gold -32 re p99, system -23.
- uh.start (gold 10.808 HUMAN, sys 10.824, +16): floor 10.77-10.80, rise from 10.804; gold at the rise start (+9 over floor).
- uh|we (11.015 HUMAN / 11.028), we|allowed (11.228 HUMAN / 11.240), allowed|them (11.581 / 11.594), them|to (11.748 /
  11.756), to|do (11.840 / 11.856; /d/ burst transient 9 at ~11.842-11.85 = gold), do|something (12.025 / 12.020; /s/
  onset ~12.01-12.02): all within 16 ms.
- something|that (12.419 / 12.414), that|you (12.529 / 12.538; /t/ release transients 9 at ~12.51-12.518, gold after
  it), you|didn't (12.651 / 12.670, +19), didn't|know (12.890 / 12.884), know|anything (13.050 HUMAN / 13.051),
  anything|about (13.395 / 13.397): all within 19 ms.
- about.end (gold 13.834 ACCEPTED, sys 13.822): gold at -38 re p99, BEFORE the /t/ release (transients 5-8 at 13.836-13.84).
- which.start (gold 13.878 ACCEPTED, sys 13.922, +44): 13.84-13.88 = the release/aspiration of 'about' (flatness 5-6, level
  4-5); /w/ voicing from 13.88 (flatness 6 -> 2 by 13.892 -> 0 by 13.92, periodicity 4-5). Gold = /w/ VOICING ONSET;
  system at the fully tonal /w/ (+44).
- which|was (gold 14.168 ACCEPTED, sys 14.185, +17): /tS/ frication 14.10-14.16, offset ~14.164 = gold.
- was.end (gold 14.556 ACCEPTED, sys 14.548): /z/ frication fades from 14.55; gold at -34 re p99 (tail excluded).
- basically.start (14.943 / 14.936; /b/ burst) and basically.end (15.411 / 15.398, gold -26 re p99) ok; breath after.
- wear.start (gold 15.629 ACCEPTED, sys 15.668, +39) numeric: floor to 15.588; a short pre-onset CLICK 15.592-15.616
  (transient 15.5 at 15.604, glottal 18, loudness to -33); dip to -53 at 15.624; the /w/ rises GRADUALLY 15.628-15.68
  (-43 -> -29 -> -25 -> -17 -> -8, tonal). Gold = the START of the /w/ rise (click excluded); system at -17 (late in
  the gradual rise). Onsets = first rise of the word's own sound, not the steepest/loudest point.
- wear|a (15.955 HUMAN / 15.956) exact; a.end (16.222 HUMAN / 16.206; gold -29 re p99); a.start (16.311 / 16.312) exact;
  a.end (16.632 HUMAN / 16.624; gold -43); the.start (16.815 HUMAN / 16.790, -25: first rise ~16.788, /D/ release
  transient 9 at 16.804-16.808, gold just after the release); the|you (16.897 / 16.904); you|know (16.980 / 16.994).
- know|a (gold 17.164 HUMAN, sys 17.191, +26): vowel-vowel, loudness flat; CTC separator 17.14-17.18, A 17.20; gold near the
  separator start, system at its end; mfcc_change 7-8 only later (17.222-17.246).
- a.end (gold 17.296 HUMAN-MOVED, sys 17.330, +34): a VOICING BREAK at 17.286-17.294 (periodicity -> 1), then a quieter
  voiced continuation 17.294-17.34 and decay. The person ended 'a' AT THE BREAK (-23 re p99) - the post-break trailing
  voice is excluded (like the um tails). System in the decay (-29).
- pause: breath 17.37-17.71, floor 17.71-17.74; corset.start (17.751 / 17.748) = /k/ burst transient 9 at ~17.755.
- corset|around (18.189 / 18.204, +15), around|their (18.514 / 18.528) ok.
- their|chest (gold 18.741 ACCEPTED continuous; sys 18.690 / 18.768 = false gap, -50/+27): /r/ decays 18.70-18.74, /tS/
  closure 18.744-18.766 (level 2, +7 over floor), frication from 18.764, burst transient 9 at ~18.79. Gold = closure
  START; system: end at word-ref -20 dB (-22), start at the frication onset.
- chest.end (gold 19.275 HUMAN-MOVED, sys 19.222, -53) numeric: /s/ at -21..-25 to 19.24, decays -30 / -39 / -48 / -54
  (19.276 = gold) to the floor (-61 at 19.282); then the /t/ release (transient 5.3 at 19.294) + 70 ms of noise
  (-40..-52) - excluded. Person = end of the /s/ decay at the floor dip; system at -25. (Final-fricative human ends
  now: approach -50, desserts -51, chest -54.)
- 'i it i- this' 19.6-20.4 (HUMAN-MOVED; the CTC is almost ALL BLANK here - only a weak 'i' at 19.66):
  * i.start (gold 19.607, sys 19.642, +35): loudness rises from 19.614 (first rise), transients 6-9 at 19.642-19.662.
    Gold = first rise (+8 over floor); system at the transient.
  * i|it (gold 19.820, sys 19.758, -61): two dips: 19.77-19.79 (loudness 5-4, periodicity 2-3) and the GLOTTAL ATTACK of
    'it' (glottal crest 9 at 19.826-19.838, transient 9 at 19.83). Gold = start of the glottal attack (vowel-initial
    word owns it); system at the first dip.
  * it.end (20.031 / 20.022; gold -51), i-.start (20.151 / 20.162), i-.end (20.266 / 20.254; gold -53), this.start
    (20.346 ACCEPTED / 20.348) ok.
  => with a blank CTC, the transcript (5 tokens) + acoustic islands/dips + glottal attacks still determine the cuts.
- this|is (20.652 / 20.646) ok. is.end (gold 20.844 ACCEPTED, sys 20.822, -22): the /z/ of 'is' is a 140 ms frication
  20.78-20.92 (zcr 9); gold (accepted) at -33 re p99 in its middle, weak tail excluded.
- just.start (gold 21.197 ACCEPTED, sys 21.024, -173): pause = breath 20.92-21.18 with a short VOICED CREAKY bump
  21.02-21.08 (loudness level 5-6, glottal crest 6-9 at ~21.03-21.05, centroid 3, CTC blank) in the middle; the /dZ/
  burst transient 9 at 21.192-21.196, CTC J at 21.22. Gold = the /dZ/ burst; system started at the voiced bump
  (louder than its quiet threshold). A short non-lexical voiced island ~120 ms before the word's own onset is not
  part of it. (Skim note times were wrong.)
- just|insane (gold 21.472 HUMAN-MOVED, sys 21.488, +17) numeric: /s/ 21.376-21.408, /t/ closure dip -33 at 21.416, /t/
  release transient 3.7 at 21.424 + frication 21.424-21.464, vowel onset abruptly at 21.472 (-23 -> -7 dB, centroid
  8.2 -> 5.6). Gold = release-frication OFFSET = vowel onset.
- insane|as (21.882 HUMAN / 21.895), as|a (22.042 / 22.049), a.end (22.107 / 22.104), parent.start (22.134 HUMAN /
  22.140; /p/ burst transient 9 at 22.136-22.148), parent.end (22.491 / 22.478; gold -44) ok.
- REPEAT 'i i' (gold i.end 22.749 + i.start 22.764 ACCEPTED; sys cut 22.688, -61/-76): the only break is a dip at
  22.752-22.768 (loudness 8 -> 4, periodicity 1-2) with the GLOTTAL ATTACK of the 2nd 'I' (glottal crest 9 at 22.764).
  CTC: I 22.52-22.536, I 22.68-22.696 (inside the gold's 1st 'I'), separator 22.74-22.776. Gold = the dip; system
  followed the 2nd CTC 'I' letter. For repeated identical words the acoustic break decides.
- i|don't (22.849 / 22.838) ok.
- don't|understand (23.065 / 23.088, +23): /t/ release transient 7 at ~23.054, glottal onset of 'understand'; system at the
  CTC separator end. understand|it (23.671 HUMAN / 23.672) exact.
- it|at (gold 23.789 ACCEPTED continuous, sys 23.766 / 23.820): /t/ closure + release ~23.77-23.83 then 'at'; small errors.
- at|all (gold 23.944 HUMAN-MOVED, sys 24.008, +65) numeric: FLAPPED /t/ = slight dip -11..-13 at 23.90-23.922 (voiced,
  high_ratio -57), release transient 14.6 at 23.922, vowel of 'all' from 23.928; mfcc_change 3.0 at 23.94-23.946 = gold.
  CTC T 23.904-23.934, separator 23.94-23.98 (P(sep) 0.97 at 23.952). System 64 ms late (end of the separator).
- all.end (gold 24.308 ACCEPTED, sys 24.286, -22): gold -36 re p99, system -23.
- uh.start (gold 24.624 ACCEPTED, sys 24.540, -84): pause = BREATH 24.33-24.60 (flatness 6-7, centroid 6-7, +12..+17 over
  floor, ~-25 re p99 at its loud end), then the GLOTTAL ATTACK of 'uh' (glottal crest 8-9 at 24.62-24.67). Gold = attack
  onset; system started inside the breath (3rd time: and 6.716 in 009-1, just 21.024, here).
- uh|laura's (gold 24.717 HUMAN, sys 24.744, +27): /l/ onset = flatness 3 -> 1 at ~24.716-24.72 (gold); CTC L 24.76-24.80.
- laura's|online (25.120 / 25.110) ok.
- online|too (25.529 / 25.517): /t/ closure then burst transient 9 at ~25.54; gold ~ closure start.
- too|laura (gold 25.673 HUMAN, sys 25.703, +30): mfcc_change 9 at 25.678-25.686 (the /u/ -> /l/ change) = gold -6; system
  at the CTC separator.
- laura|what's (gold 25.959 ACCEPTED, sys 25.928, -31): /w/ constriction = loudness dip 25.954-25.962; gold in it, system
  at the separator start.
- what's|your (26.125 / 26.127) exact; your|take (26.250 HUMAN / 26.244) ok.
- take.end = CLIP END (gold 26.425 ACCEPTED, sys 26.504, +79): vowel decays 26.40-26.45, /k/ closure 26.45-26.49, burst
  transient 9 at ~26.51 + noise to the clip end. Gold at the vowel decay (-32 re p99), closure + release excluded
  ('week' pattern); system at the burst.

### 009-3 summary (85 tokens / 170 boundaries)
- Biggest: just.start -173 (started at a creaky voiced bump inside a breath), p|e -142 (identical vowels, follow the CTC
  separator), uh.start -84 (inside a breath), take clip end +79, i|i -61/-76 (repeat: acoustic dip + glottal attack),
  i|it -61 (blank CTC; glottal attack), at|all +65 (flap release), their|chest / report|that / that|to / that's|because
  / yet|they (closures made into gaps), chest.end -53 (human includes the fading /s/ to -54).
- Pause-end levels: accepted ends at -33..-49 here; human-moved fricative ends at -54.

## 009-4  DEEP RE-READ (22.6 s, 71 tokens)
- and|so (gold 0.116 ACCEPTED, sys 0.239, +122) numeric: 'and' onset 0.036 (transient 15), vowel 0.06-0.11; 0.116-0.20 a
  LOUD VOICED but noisier segment (-5..-7 re p99, periodicity 0.5-0.7, flatness -3.5..-2.1, centroid 6-7) = the /nd/
  (CTC N 0.10-0.14, D 0.14-0.164); separator 0.18-0.216; the real /s/ from 0.204-0.212 (voiceless, zcr 0.4-0.6,
  centroid 8.1-8.4). Gold puts 'so' at 0.116 = including the /nd/ in 'so'. SUSPECTED GOLD ERROR (accepted): the /s/
  onset (~0.205) is the boundary; system 0.239 is 30 ms late of that.
- so.end (0.676 / 0.696, +20) ok; 2nd so.start (0.824 HUMAN / 0.828) = /s/ onset.
- so|i (gold 1.014 HUMAN, sys 0.970, -43): a dip 0.98-1.008 (loudness 7 -> 4) between 'so' and 'I' (glottal constriction);
  gold at the END of the dip (rise of 'I'), system at its start. (Human vowel-initial convention is not stable: start
  of the constriction in bit|and/and|and/managing|editor, end here and in today|at.)
- i|was (gold 1.062 HUMAN, sys 1.022, -39): 47 ms 'I', 50 ms 'was'; no landmark; system shifted by the so|i cut.
- was|just (1.113 HUMAN / 1.119) ok.
- just|really (1.293 / 1.308), really|quick (1.535 ACCEPTED continuous / sys gap 1.510-1.552 over the /k/ closure),
  quick.end (1.817 HUMAN / 1.814), uh (1.919-2.078 HUMAN / 1.922-2.082), there.start (2.141 / 2.144): all within 24 ms.
- there|h- (gold 2.469 HUMAN, sys 2.430, -39): /r/ -> /h/ of a cut-off word: voicing dip at 2.458-2.47, flatness and
  high_ratio rising 2.446-2.494, formant_vel 4-7 over 2.454-2.51. Gold = the voicing dip (breathiness onset); system at
  the CTC separator.
- h-|is (2.566 / 2.582 HUMAN+ACCEPTED; sys 2.556 / 2.580), is.end (2.862 ACCEPTED / 2.852; gold -31 re p99 inside the
  /z/ frication), kind.start (2.897 / 2.900; /k/ burst), kind|of (3.144 exact), of|a (3.268 exact).
- a.end (3.404 / 3.392) ok.
- concern.start (gold 3.480 ACCEPTED, sys 3.514, +34): floor 3.44-3.475, /k/ BURST transient 9 at 3.478-3.482, weak
  aspiration 3.48-3.54 (loudness 3-4), vowel from ~3.55. Gold = the burst; system inside the aspiration (its onset
  refinement looks for the steepest loudness rise, which is the vowel).
- concern|though (gold 4.104 HUMAN-MOVED, sys 4.040, -63): long /n/ ~3.96-4.09; at ~4.09 the spectrum turns very tonal/
  low (centroid -> 1, high_ratio -> 0, flatness -> 0) = the /D/ onset. Gold = that change (nasal-final -> murmur
  offset); system inside the /n/ at the CTC separator (T-H letters 4.06-4.14 straddle the change).
- though.end (4.369 / 4.364), amongst.start (4.400 / 4.404) ok.
- amongst|some (gold 4.904 ACCEPTED, sys 4.845, -60): GEMINATE /st s/ = one frication 4.75-4.93 (zcr 8-9, centroid 9);
  formant_vel 9 at 4.884-4.896 inside it; vowel of 'some' from ~4.93. CTC: S 4.74-4.78, T 4.78-4.80, separator
  4.80-4.86, S 4.90-4.92. Gold = 25 ms before the vowel, at the CTC's 2nd S (3rd geminate case: gold late in the
  frication near the next vowel); system at the separator end.
- some|people (gold 5.139 ACCEPTED continuous; sys 5.110 / 5.184 = gap): /p/ closure 5.14-5.17 (level 3), burst transient
  9 at ~5.172. Gold = closure START; system end in the /m/ decay (-28), start after the burst (+45).
- people|that (5.569 HUMAN / 5.564) ok.
- that.end (5.769 / 5.752, -17) ok; pause = breath; aren't.start (6.122 / 6.140, +18): glottal attack transients up to 9
  at 6.132-6.148; gold ~10 ms before them.
- aren't|big (gold 6.464 ACCEPTED, sys 6.489, +25): closure 6.47-6.49 (loudness falls from 6.432), /b/ burst transient 9
  at ~6.496-6.504. Gold near the closure start; system near the burst.
- big|murkowski (gold 6.637 ACCEPTED, sys 6.660, +23): /g/ release transient 7 at ~6.636 = gold; system at the CTC
  separator end.
- murkowski|fans (7.299 / 7.295) ok.
- fans|and (gold fans.end 7.774 + and.start 7.775 HUMAN continuous; sys fans.end 7.704 + and.start 7.774, -70/-1): the /z/
  frication 7.61-7.73 (flatness 9, centroid 8-9, zcr 4-8) fades to the floor by ~7.77. The PERSON ends 'fans' where
  the /z/ reaches the floor (-37 re p99, +3 over floor); system ended inside the /z/ (-34 at 7.704 - loudness already
  low, the word-ref -20 dB test calls the weak /z/ quiet). 4th human-moved final-fricative end at the floor
  (approach, desserts, chest, fans).
- and|i (7.969 / 7.976), i|know (8.086 exact).
- know|them (8.342 HUMAN / 8.323, -19), them|and (8.584 / 8.583), and|they (8.698 / 8.679, -20) ok-ish.
- they|they STUTTER (gold they.end 8.890 ACCEPTED + gap + they.start 8.988 HUMAN; sys continuous 8.904; +13/-84): the 1st
  'they' vowel trails and fades 8.88-8.98 (-24..-32 re p99); a VOICING BREAK at 8.982-8.994 (periodicity 0-1); the 2nd
  'they' /D/ = voiced tonal murmur 8.998-9.03 (flatness 0, centroid 0), release transient 7 at ~9.048. Gold: 1st
  'they' ends at -32 (trailing fade in the gap), 2nd 'they' starts AT THE VOICING BREAK. System cut once at 8.904.
- they|don't (9.100 HUMAN / 9.095), don't|like (9.228 / 9.232), like|murkowski (9.370 / 9.374) ok.
- murkowski.end (10.043 / 10.042) exact; that.start (10.505 / 10.502); that.end (10.838 / 10.818, -20); the.start (10.993 /
  11.000) ok (pauses with floor / weak breath).
- the|republicans (gold 11.270 ACCEPTED, sys 11.205, -66): a long 'the' (10.99-11.27) sonorant -> /r/, all tonal and loud,
  no level landmark; formant_vel 4-5 at ~11.21-11.225 (system) and ~11.275 (gold). CTC: T 11.15, H 11.20, E 11.25-11.27,
  separator 11.35-11.395, R 11.45. Gold = END OF THE CTC 'E'; system snapped to an earlier formant change.
- republicans|are (11.908 / 11.897; /z/ offset ~11.90), are|gonna (12.000 / 11.987), gonna|divide (12.185 HUMAN /
  12.174; /d/ closure at the loudness minimum, burst ~12.21), divide|themselves (12.564 / 12.567): all within 14 ms.
- themselves|and (13.440 / 13.422, -18: /z/ offset 13.426-13.438 = gold), and|that (13.612 / 13.590, -22), that.end
  (13.842 / 13.830; gold -38), the.start (14.257 / 14.238; /D/ release transient 9 at ~14.264, gold just before it),
  the|democrat (14.354 / 14.349): all within 22 ms.
- democrat|will (14.917 / 14.914), will|win (15.142 / 15.147), win.end (15.807 / 15.796; a long /n/ 15.35-15.78, gold -31),
  because.start (16.111 / 16.100; /b/ burst): all within 11 ms. Pause = breath 15.82-16.08.
- because.end (gold 16.537 HUMAN-MOVED, sys 16.470, -67): /z/ frication 16.44-16.57 fading; the PERSON ended at -48 re p99
  (+12 over floor, late in the fading /z/), system at -26 (word-ref -20 dB). 5th human-moved final-fricative case.
- alaska.start (16.665 / 16.668) ok; alaska|has (17.195 HUMAN / 17.194) exact.
- has|some (gold 17.485 ACCEPTED, sys 17.444, -41) numeric: 'has' vowel 17.28-17.40 (CTC S of 'has' at 17.40-17.41 during
  the vowel decay); ONE voiceless frication 17.43-17.55+ (zcr 0.55-0.71, centroid 8.4-8.7) with low_ratio drifting
  -14 -> -27 over 17.44-17.50; separator 17.44-17.47; CTC S of 'some' 17.52-17.54. Gold 55 ms into the frication;
  system at its onset.
  *** GEMINATE /s#s/-type estimator check (4 cases): gold vs the START of the 2nd word's first CTC letter: amongst|some
  4.904 vs 4.90, podcast|so 1.540 vs 1.54, populist|support 5.424 vs 5.40, has|some 5.485 vs 5.52 -> errors 0-35 ms,
  better than midpoint or fixed-fraction rules.
- some|democrat (17.691 / 17.696) ok.
- democrat.end (gold 18.186 ACCEPTED, sys 18.164, -22): gold -33 re p99, system -29.
- sympathies.start (gold 18.204 ACCEPTED, sys 18.244, +40): a gradually building /s/ after an 18 ms gap: flatness rises from
  ~18.19, zcr and centroid only from ~18.25-18.29 (loudness level 3-4 = -35 re p99). Gold = the EARLIEST frication rise
  (+13 over floor); system mid-rise.
- sympathies.end (18.975 ACCEPTED / 18.972): final /z/ fading 18.83-19.03; accepted end at -32 re p99. Long breath pause
  19.0-19.56 (+6..+13 over floor).
- is.start (19.565 / 19.572) ok; is|there (gold 19.707 ACCEPTED, sys 19.684, -23): /z/ frication ~19.69-19.74; gold ~20 ms
  into it, system at its onset.
- there|any (19.821 HUMAN / 19.842, +21), any.end (20.002 / 19.982) + truth.start (20.034 / 20.036) ok.
- truth|to (gold 20.368 ACCEPTED continuous; sys truth.end 20.326 + to.start 20.376): /T/ frication ~20.28-20.34, /t/
  closure 20.34-20.37 (level 3-4), burst transient 7 at ~20.38. Gold = closure END (just before the burst; the /T/ tail
  + closure go to 'truth'); system ended inside the /T/ (-32 re p99) and started at the burst.
- to|that (20.478 / 20.474), that|what (20.678 / 20.659, -20) ok.
- what|what (20.872/20.878 / sys 20.860/20.898), what|is (21.054 exact), is|your (21.179 / 21.156, -24), your|what (21.343/
  21.354 / 21.348), what|is (21.516 exact), is|your (21.654 / 21.633, -22; the /z/ frication ~21.63-21.72 lies mostly
  AFTER the gold cut - gold gives the /z/ to 'your' here?). All ACCEPTED, within 24 ms.
- 'your uh opinion' (your.end 21.849 ACCEPTED, uh 21.889-21.972 HUMAN, opinion.start 22.029 ACCEPTED; system 21.794 /
  21.794-21.848 / 21.892: -55/-94/-124/-137): 'your' loud 21.66-21.80, decays to level 2 by ~21.88; a short schwa
  ISLAND 21.888-21.96 (level 6-7); low stretch 21.96-22.03 (~floor, the /p/ closure); 'opinion' from ~22.03. The CTC
  heard the schwa island as the O of 'opinion' (O at 21.94-21.98, P at 22.04) and the system followed it, pushing 'uh'
  into the decay of 'your'. Gold = islands: 'your' ends in its decay (-35), 'uh' = the schwa island, 'opinion' starts
  after the gap. A transcript filler must own a whole island; with one schwa island available, the lexical word
  starts after it.
- opinion|of (22.323 HUMAN / 22.326) ok.
- of|that (gold 22.424 ACCEPTED, sys 22.454, +30): /v D/ constriction = dip 22.428-22.44 (level 3-4), release transient 7 at
  ~22.444. Gold = dip START; system after the release. that.end (22.614 / 22.612) ok.

### 009-4 summary (71 tokens / 142 boundaries)
- Biggest: your|uh|opinion (-55..-137, filler/island assignment vs CTC), and|so +122 (suspected gold error),
  they|they -84 (stutter: voicing break), fans.end -70 / because.end -67 (human includes the fading /z/), the|republicans
  -66, concern|though -63 (nasal offset), amongst|some -60 / has|some -41 (geminates), some|people +45, which.start
  +44-type gradual onsets (sympathies +40, concern.start +34).

## 009-5  DEEP RE-READ (21.2 s, 75 tokens)
- uh|it's (gold 0.181 HUMAN, sys 0.237, +56): clip starts in a breathy low 'uh' (level 4-6, CTC blank); loudness rises
  gradually 0.15-0.26 into 'it's' (CTC I 0.28). No sharp landmark; the person cut early in the rise; system just before
  the CTC letters.
- it's|time (gold 0.460 ACCEPTED continuous; sys 0.440 / 0.472): /s/ 0.34-0.43, closure at the floor 0.44-0.456, /t/ burst
  transient 9 at ~0.456. Gold = the burst (closure given to 'it's'); system made the closure a gap.
- time|to (0.712 / 0.732, +20) ok.
- to|f- (gold 0.795 HUMAN, sys 0.846, +51): /f/ frication: flatness rises from ~0.79, zcr from ~0.808, centroid from ~0.824,
  full by 0.84. Gold (person) = the EARLIEST frication rise; system at the fully developed frication.
- f-|(()) (gold 0.980 HUMAN, sys 1.008, +28): /f/ frication fades to the floor ~0.976-0.984; (()) onset transient 9 at
  ~0.99. Gold = frication end; system after the onset transient.
- (())|here (gold 1.577 HUMAN, sys 1.530, -46): CTC hears 'o u t _ o _ H E R E' across the (()) + 'here' (t 1.54, o 1.58-1.60,
  H 1.66); voicing drops at ~1.52 (/t/), release transients 6-7 at ~1.532-1.552. The person started 'here' at ~1.577 (at
  the CTC 'o' after the /t/); system at the /t/. Uncertain speech - weak evidence either way.
- here.end (gold 1.816 ACCEPTED, sys 1.946, +130) / ((there's)).start (gold 1.854 HUMAN, sys 1.974, +120): 'here' vowel decays
  ~1.85-1.93, a CLICK at ~1.90 (transient 9), a creaky voiced bump 1.93-1.98 (glottal crest 9, tonal), floor 2.0-2.016,
  then more uncertain speech. The person started the uncertain ((there's)) at 1.854 (before the click and bump); 'here'
  ends at 1.816 (-24 re p99). System kept the decay + click + bump in 'here'. ((...)) = uncertain transcription.
- ((there's))|a (gold 2.293 / 2.318 HUMAN; sys 2.278 / 2.328): floor 2.28-2.32 between them. ok.
- a|a #1 (gold 2.444 HUMAN, sys 2.500, +56): CTC all blank (filler not recognised). Loudness dips -14 -> -25/-26 re p99 at
  2.444-2.448, transient 9.0 at 2.448, zcr .11->.46, per .42->.25 (breathy/aspirated attack of the 2nd 'a'). Gold at the
  loudness minimum just before the attack transient. System had no landmark (trn 4.9 at 2.500, loud -7) - it split the
  filler run lexically. => repeated fillers: loudness-dip + attack transient is the boundary; there are NO letters to use.
- a|a #2 (gold 2.616/2.618 HUMAN, sys 2.584/2.624): 2nd 'a' decays -24 (2.576) -> -31 (2.584) -> -37 (2.608-2.616) with
  per .35-.48 (still partly voiced tail), then 2.616-2.624 per .07-.10, zcr .36-.40, cent 7.7-7.9, glottal 16 = breathy
  /h/-like onset of the 3rd 'a', trn 5.8 at 2.624. Gold end = loudness minimum at the onset of the aperiodic attack; the
  decaying partly-voiced tail belongs to 'a' #2. System inserted a pause 2.584-2.624 (word-ref -20 dB test: -31 re p99 is
  +14 dB over floor). => again: decaying voiced tail -> keep to the next attack.
- a|there's (gold 2.765 acc, sys 2.760): loudness min 2.752-2.764 then /DH/ rise; CTC 'T' only at ~2.82. ok.
- there's|no (gold 3.048 acc, sys 3.060, +12): /Z/ zcr .44 (3.006) -> .15 (3.024) -> .04 (3.048); loudness dip -13 at
  3.030-3.036; per .31 -> .54 (3.042); fvel spike 2.37 at 3.042; CTC separator 3.024-3.054. Fricative->nasal change at
  ~3.036-3.042. Gold 6 ms after, sys 18 ms after (at separator end / blank rise). Minor.
- no|saving (gold 3.258 acc, sys 3.300, +42): /S/ onset: cent 5.9 -> 7.06 at 3.270, hi -17.5 -> -7.9 (3.270) -> -4.8,
  trn 4.8 at 3.270, fvel 1.70 at 3.270, per .57 -> .46 -> .25 (3.282). CTC separator 3.258 (.10) -> .94 (3.294), blank
  from 3.300. Fricative onset ~3.264-3.270; gold 3.258 (6-12 ms early, accepted). System at the separator END = 30+ ms
  inside the /S/. => word-initial fricative: boundary at the fricative onset (spectral jump), not the separator geometry.
- saving.end (gold 3.870 acc, sys 3.860) / this.start (gold 3.873 HUMAN, sys 4.012, +139): /NG/ of 'saving' = cent 4.6-5.0,
  lo ~0, hi -22..-35, per 0-.25 (creaky), loud -13..-27 through 3.864. At 3.870: cent 5.0->6.5, hi -22->-11, trn 4.6,
  fvel 3.50 (spike) = onset of 180 ms of aperiodic noise 3.870-4.050 (cent 7.0-8.4, hi -2..-10, zcr .2-.5, per .1-.2,
  loud -26..-31 re p99 = +13..+18 over floor, level flat, no gap) that runs straight into the loud vowel at 4.056.
  CTC 'T' only at 4.020-4.038, 'H' 4.044-4.074. Human put the whole noise into 'this' (a prolonged 'thhh-'), start at
  the nasal->noise spectral change. System at 4.008 (pause model: -26..-31 < word p90-20). Contrast with breaths which the
  person excludes: this noise is sibilant-like (cent 7-8, zcr up to .5) and CONTIGUOUS with the word (no level gap
  before the vowel). => word-initial fricative prolonged: boundary = the spectral onset of the noise.
- this.end 4.369 acc / that.start 4.421 acc: sys -7 / -1. ok.
- that|guy's (gold 4.618/4.622 acc; sys 4.570 end, pause, 4.606 start): 'that' vowel decays -11 -> -29 (4.540-4.588) with
  per .35-.45, cent 4.6-5.2, lo ~0 (voiced closure / voice bar), 4.594 per drops, 4.600 trn 14.8 glo 20.8 = /T/ RELEASE,
  4.606-4.612 aspiration (cent 8.2, hi -3.5, -19/-20), 4.618-4.636 quiet -31..-38 = /G/ closure, 4.642 trn 17.7 = /G/
  burst. Gold boundary = end of the /T/ aspiration = start of /G/ closure. System ended 'that' before its own closure +
  release (4.570, voice-bar tail -19 taken as pause start) and started 'guy's' at the /T/ release (4.606). => a word-final
  stop's closure AND release+aspiration belong to that word; the following stop's closure silence belongs to the next word.
- guy's|horrible (gold 4.980 acc / 4.982 HUMAN, sys 4.968 / 5.272 (+290)): /Z/ zcr .75 (4.900) -> .35 (4.960), hi
  -0.2 -> -8, lo -17 -> -3; 4.96-4.99 weak (-22..-26), CTC separator 4.92-4.98. From 5.000: lo -13, cent 8.2-8.5, hi
  -1..-5, zcr .45-.60, per .1-.3, level -28..-33 re p99 (+14..+18 over floor) until 5.13, rising -24..-30 5.14-5.26, -15..-18
  5.28-5.49; CTC 'H' only at 5.425-5.47, vowel 'O' ~5.60. i.e. ~500 ms of homogeneous aspiration noise (an exaggerated
  'hhhhorrible') contiguous with /Z/ (never back to floor). Human started the word at the /Z/ -> /h/ change (CTC separator
  end, lo-ratio flip at ~4.99-5.00). System started where level crossed the word-ref threshold (5.27). => same class as
  this.start: a weak, spectrally homogeneous fricative/aspiration run contiguous with the word = part of the word.
- horrible.end (gold 5.928 acc, sys 5.944): /L/ voiced tail -19..-30 wiggles, CTC separator from 5.920. No landmark; ok.
- that.start (gold 6.290 acc, sys 6.272, -18): floor -40 to 6.272, tiny bump -34/-32 at 6.278-6.284 (fvel 2.6), dip -35 at
  6.290 (trn 4.3), /DH/ rise -25 at 6.296. Gold at the dip before the rise; sys at the bump. Minor.
- that|woman (gold 6.409/6.411 acc, sys 6.434, +25): 'that' vowel to 6.386, decay -26 at 6.392, 6.398 trn 5.2 cent 7.9
  hi -4.5 = /T/ release, aspiration to ~6.410, quiet -32/-33 6.410-6.428, trn 5.9 at 6.428, /W/ onset -16 at 6.434 (per
  .31, lo -0.2). Gold = end of /T/ release noise (gap goes to 'woman'); system = /W/ onset (gap to 'that'). Same
  convention as that|guy's: boundary right after the final stop's release noise.
- woman|is (gold 6.720 HUMAN, sys 6.726): N->IH: trn 6.0, cent 6.2->7.4, lo -0.6->-4.4 at 6.720; CTC separator
  6.702-6.738. Gold at the transient; sys +6. ok.
- is.end 6.920 acc / awful.start 7.025 acc: sys -4 / +1. ok.
- awful.end (gold 7.369 acc, sys 7.516, +147): /L/ voiced to 7.350 (per .41, cent 4.8-5.3, lo -0.1). 7.360 cent 7.7 zcr
  .33; 7.370 dip to -30 (13 dB drop); 7.380-7.640 aperiodic noise (per .08-.19, cent 8.0-8.4, hi -2..-5, lo -8..-22,
  zcr .40-.53) with its OWN envelope (rises -30 -> -19 by 7.47, decays to floor -45 at 7.66) = exhale/breath. CTC blank
  1.00 throughout. Gold ends the word at the end of voicing / the dip before the breath. System ended inside the breath
  where its decay crossed the word-ref threshold. The breath (-19..-21 re p99) is LOUDER than horrible's /h/ (-28..-33),
  so level cannot separate them.
  => KEY CONTRAST (this.start, horrible.start vs awful.end): aperiodic noise adjacent to a word belongs to the word iff
  the adjacent phone of that word is itself aperiodic (fricative / HH / stop release: 'this' DH, 'horrible' HH); if the
  adjacent phone is a sonorant/vowel ('awful' ...L) the noise is a breath and excluded; a separate envelope (dip then
  rise) supports it. Phone-ownership rule, no level threshold.
- and.start (gold 7.692 acc, sys 7.698): floor -45..-39 to 7.690, rise -23 at 7.700 (trn 4.9). ok.
- and|we (gold 7.844 acc, sys 7.856): voiced throughout (per .62-.73); loudness dip -12, cent min 5.45, hi min -22.6 at
  7.844-7.850 (/D/ flapped into /W/). Gold at the dip minimum; sys at separator->blank crossing (+12). => continuous
  voiced join: loudness/centroid minimum.
- we|all (gold 8.026 HUMAN, sys 8.050, +24): IY->AO, no dip. per rises to .72 at 8.032, lo -1.5 -> -2.5 (8.032) -> -4.1,
  cent 6.99 -> 6.28, mfcc_change max 3.25 at 8.032, CTC separator PEAK .98 at 8.032, separator ends 8.050. Human = the
  separator peak / mfcc peak; system = separator end. => vowel-vowel join: take the separator PEAK (spectral-change max),
  not its trailing edge.
- all|know (gold 8.256 acc, sys 8.244): L->N, separator peak .92 at 8.250, trn 3.3 + cent 6.55 at 8.262, fvel 2.6 8.268.
  Gold ok; sys -12 (separator rise). minor.
- know|like (gold 8.494/8.500, sys 8.488): OW->L, separator 1.00 8.494-8.512, dip -7, fvel 1.99/2.93 at 8.494/8.506. ok.
- like|the (gold 8.743/8.745 acc; sys 8.714 end, pause, 8.772 start): 'like' vowel decays -11 -> -34 by 8.708 (/K/
  closure, no audible release), floor -38..-40 8.720-8.762 (dB re floor ~0), 8.768 trn 16.8 glo 17-22 = burst of 'the'
  (DH realised as a stop), 8.774-8.786 frication (cent 8.6, zcr .55), voicing from 8.798. CTC 'T' 8.762-8.780. Gold
  split the ~50 ms closure silence in the middle; system gave it to a pause. Accepted, so the person tolerated mid-closure.
  => closure silence between an unreleased final stop and a stop-like onset (< ~80 ms) is not a pause; split it.
- the|shrew (gold 8.828 acc, sys 8.882, +54): 'the' vowel 8.798-8.828 (per .40-.49); 8.834 cent 6.0 -> 7.2, hi -15.7 ->
  -8.3, fvel 2.43; 8.846 cent 8.24, zcr .42, per .14 = /SH/. CTC separator 8.858-8.906, peak .98 at 8.882. Gold at the
  fricative onset; system at the separator peak = 50 ms inside /SH/. => CTC lag into a word-initial fricative (known).
- shrew|woman (gold 9.361/9.363 acc, sys 9.308, -53): UW->W, voiced throughout. Separator 9.324-9.356 (peak .97 at
  9.332-9.340). hi-ratio falls to its minimum -31/-32 at 9.356-9.364 (tightest lip rounding), loudness dips -12 at 9.372
  with trn 6.1, CTC 'W' 9.380-9.412. Gold = the constriction maximum (hi/loudness minimum), 20-30 ms AFTER the separator
  peak. System 9.308 = before the separator even rises. => vowel/glide join: the acoustic constriction (loudness + hi
  minimum) is the landmark; separator peak only when there is no constriction (we|all).
- woman.end (gold 9.706 acc, sys 9.702): /N/ murmur decays -11 -> -30 by 9.702, -39 at 9.720. ok.
- that's.start (gold 10.300 acc, sys 10.244, -56): 10.18-10.27 low murmur -31..-37 re p99 (+6..+12 over floor) that is
  PERIODIC (per .43-.70, cent 4.6-5.8, lo ~0) = pre-voicing / hum. 10.276-10.292 per .48 -> .07, cent 6.3 -> 8.0, trn
  5.4 at 10.284, glo 17-19 = /DH/ stop-like release; vowel rise -34 -> -19 at 10.300-10.316. CTC 'T' 10.260, 'H' 10.284,
  'A' 10.300. Gold = vowel rise (16 ms after the burst); system started inside the murmur. Burst at ~10.280 is the
  defensible start; murmur excluded. => low periodic pre-voicing/hum before a word: not part of the word.
- that's|just (gold 10.444 acc, sys 10.420, -24): /T S/+/JH/ merge into ONE fricative 10.396-10.456 (trn 6.6 at 10.396 =
  /T/ release; loudness -21 -> -3 (10.432) -> -10 (10.456); lo -8.5 -> -35 (10.432) -> -6; cent 8.1-8.5 flat). CTC
  separator 10.402-10.438 (peak .89 at 10.414), 'J' 10.444-10.456. mfcc_change rises 1.6 -> 2.61 (10.444) -> 3.15. Gold at
  the mfcc rise after the loudness peak / CTC 'J'; system at the separator. No clean landmark inside a merged fricative.
- just.end (gold 10.580 acc, sys 10.562, -18) / destroying.start (10.600 both): closure -39..-43 10.544-10.562, weak /T/
  release 10.568 (fvel 2.24, +5 dB), noise -35/-36 to 10.592, /D/ voicing (per .57) at 10.598. Gold in the release
  noise; sys before it. Release belongs to 'just'.
- destroying|a (gold 11.227/11.229 HUMAN, sys 11.245/11.247, +18): NG->AH, level flat -5..-8; separator 11.216-11.264
  (.50 at 11.228, 1.00 at 11.258); trn 3.6 11.222/11.234, 4.7 11.246; mfcc_change max 3.76 at 11.240; lo -0.2 (11.228)
  -> -1.2 (11.246). Gold at the separator half-rise / end of CTC 'G'; system at .88. No sharp landmark; gold is
  ~12 ms before the mfcc peak.
- a|man's (gold 11.330 acc, sys 11.322): separator 11.306-11.336; trn 4.8 + fvel 3.08 at 11.318 (M closure). ok.
- man's.end (gold 11.699 HUMAN, sys 11.678, -21): /Z/ 11.600-11.670 (zcr .65-.77, cent 8.6), -20 at 11.670, -36 11.680,
  -44 11.690, floor -45 at 11.700. Human = where the fricative reaches the floor; system at -35 re p99 (+9 over floor).
  Same final-fricative end convention as before (human at the floor, ~-45 re p99).
- uh.start (gold 11.810 HUMAN, sys 11.810): a small periodic bump 11.740-11.770 (per .61, -33) before it is excluded by
  both. ok.
- uh|his (gold/sys 12.014-12.019): trn 7.0 at 12.014, per .64, level -23 -> -14. ok. (CTC blank for 'uh' and 'his'.)
- his|psyche (gold 12.124/12.125 HUMAN, sys 12.136, +11): 'his' vowel 12.022-12.100 (per .5-.7). Fricative onset
  12.110 (cent 7.5, zcr .29) -> 12.118 (8.4, .53) -> full 12.126; one merged /Z S/ fricative to 12.238. CTC: no separator
  (<= .02), 'P' 12.166-12.198, 'S' 12.206-12.238 (silent P emitted inside the /S/). Human gave the WHOLE merged fricative to
  'psyche' (boundary at fricative onset). Contrast that's|just (accepted, split late at CTC 'J'). Merged cross-word
  fricatives: human-moved example = onset. (Zoom column-reading put the CTC P at 12.275 - 100 ms off; at.py says 12.166.
  Always verify with at.py.)
- psyche|inside (gold 12.568 acc, sys 12.586, +18): IY->IH, level flat. Separator peak .98 at 12.574; mfcc_change max 3.67
  at 12.586; trn 3.1 at 12.580. Gold = separator peak (as we|all); system on the trailing side at the mfcc max.
- inside|and (gold 13.024 acc, sys 13.018): flapped /D/, separator plateau .96-.99 13.012-13.030, hi min -30 at 13.000.
  ok.
- and|out (gold 13.118/13.123 acc, sys 13.130/13.135, +12): hi min -29.6 + fvel 2.31 at 13.118, separator .28 -> .87
  (13.130). Gold at the /D/ constriction landmark; sys at the separator peak. minor.
- out|just (gold 13.290/13.293 acc, sys 13.272/13.277, -18): no silence (voiced/weak closure -12..-14), separator
  13.266-13.296 (peak .95 at 13.278), trn 7.8 at 13.284 = the single /T+JH/ release, JH frication 13.290-13.302 (cent
  6.5 -> 7.6, zcr .30). Gold just after the burst; sys in the closure. Unreleased T + affricate: one release.
- just|destroying (gold 13.450/13.454 acc, sys 13.457/13.459): closure -35..-40 13.420-13.450, trn 3.5 glo 20.9 at 13.450,
  trn 14.1 + frication (cent 8.4, lo -28, zcr .56) from 13.456. Homorganic T+D = one release; both put the burst in
  'destroying'. Contrast that|guy's (T and G each released, T burst stays with 'that'). => the burst belongs to the stop
  it releases; a homorganic cluster has one release = the second word's.
- destroying|him (gold 14.010 acc, sys 14.022, +12): NG->HH, voiced throughout (per .5-.6; intervocalic /h/ voiced).
  Separator peak .91 at 14.010 = gold; sys at the separator's falling half (.55) + fvel 2.32. separator-peak again.
- him|from (gold 14.142/14.147 acc, sys 14.148): M -6 -> -17 at 14.142; trn 3.5 (14.148), 7.3 (14.154), cent 7.5, zcr .23 =
  /F/ onset 14.148-14.154. ok.
- from|top (gold 14.366/14.372 acc, sys 14.348, -18/-24): /M/ voiced to 14.348; 14.354-14.372 a short noise (trn 5.2 at
  14.360, cent 7.5-8.5, zcr .5, -14..-21) = nasal-release noise; closure -30/-33 14.378-14.388; /T/ burst trn 15.1 at
  14.392, aspiration to 14.416, CTC 'T' 14.400-14.416. Gold inside the release noise; sys at nasal end. The /T/ closure
  (14.378) is the principled start; minor.
- top|to (gold 14.562/14.564 acc, sys 14.574, +12): 'top' vowel decays to 14.568 (-7/-9, per .29-.36), trn 3.3 at 14.574
  (weak /P/ release?), frication 14.580-14.616 (cent 7.0 -> 8.6, zcr .58, hi -0.9 = alveolar-like), dip -27 at 14.616,
  2nd burst trn 7.7 at 14.624 (/T/), aspiration to 14.640, vowel 14.648. CTC P 14.544-14.556, separator 14.580-14.600,
  T 14.600-14.632. Two bursts; gold at the vowel offset puts the P release+frication into 'to' - opposite of that|guy's
  (accepted too). => accepted golds scatter on who owns a stop release; only the human-moved ones are informative.
- to|b (gold 14.680 HH, sys 14.672): 'to' vowel to 14.672, /B/ voice-bar closure 14.680-14.696 (-8/-9, per .38-.59, lo
  -.2..-.5, cent 5.4-5.6), release trn 2.3/3.1 at 14.696-14.704, IY from 14.712. Gold at the closure start. ok.
- b|you (gold 14.773/14.775 HUMAN, sys 14.745/14.747, -28): letter-name 'B' (IY) -> Y UW, continuous vowel/glide, level
  flat -2/-3. Separator 14.760-14.784, peak .83 at 14.776; CTC emitted a spurious 'H' at 14.744-14.752. Gold = separator
  peak; system 25-30 ms early (at the spurious 'H'). separator-peak for V/glide joins again.
- you|see (gold 14.836 HUMAN, sys 14.899, +63): 'you' UW per .56-.64 to 14.832; 14.840 cent 6.8 per .35; 14.848 cent 7.9
  per .19 zcr .40 -> /S/ from ~14.844. CTC 'U' runs 14.824-14.856 (10 ms into the /S/), separator 14.880-14.912 (peak .98
  at 14.896). Gold at the fricative onset; system at the separator peak, 55 ms inside /S/. => 4th case (no|saving,
  the|shrew, you|see): CTC separator lags 40-60 ms into a word-initial fricative. Rule: next word starts with a fricative
  -> boundary = aperiodic spectral onset found searching back from the separator.
- see|it (gold 15.110 acc, sys 15.134, +24): IY->IH, level flat (-1..0). Separator 15.110 (.07) -> peak .92 at 15.134;
  cent 7.15 -> 6.32 and hi -11 -> -19.6 over 15.110-15.128 (formant transition); mfcc max 2.33 at 15.134. Gold at the
  START of the transition, sys at its end / separator peak. V-V joins scatter +-25 ms in accepted gold.
- it|he (gold 15.298/15.299 HUMAN, sys 15.248/15.249, -50): 'it' vowel to ~15.21, short closure -27 at 15.220, /T/ burst
  trn 20.8 at 15.228, STRONG aspiration 15.236-15.276 (-7..-10, cent 8.5-8.7, zcr .6-.75, lo -14..-19), weaker noise
  15.284-15.308 (-13..-19, lo -5..-10), loudness minimum -18/-19 at 15.300-15.308, hi starts falling (-2 -> -4.6) at 15.300,
  IY of 'he' from 15.324 (per .34 -> .51). CTC separator 15.244-15.276 (peak .98 at 15.252), 'H' 15.284-15.316. HUMAN put
  the /T/ burst + strong aspiration into 'it' and cut at the loudness minimum before 'he' (whose /h/ is ~25 ms). System
  cut at the separator peak = inside the /T/ aspiration. => human-moved confirmation: a released final stop keeps its burst
  AND aspiration; boundary = loudness minimum between the aspiration and the next word.
- he|used (gold 15.393/15.395 acc, sys 15.403/15.405, +10): IY->Y, separator .75 -> .97 (15.388-15.396), peak .99 15.412.
  ok.
- used|to (gold 15.614/15.618 acc, sys 15.620/15.623): /Z D/ decays to closure -37 at 15.608, /T/ release trn 1.8 -> 4.0
  -> 6.8 at 15.614-15.626. ok.
- to|be (gold 15.702/15.707 acc, sys 15.708): /B/ voice bar 15.690-15.714 (per .5-.6, cent 5.1, hi -40, -9..-13),
  release trn/glo 19.9/fvel 2.59 at 15.714. Gold mid voice bar. ok.
- be|fun (gold 15.806/15.807 HUMAN, sys 15.838/15.839, +32): IY to 15.796; 15.802 per .31, hi -12.8, fvel 2.44; 15.814
  cent 7.9, hi -4.1 = /F/ onset. CTC separator peak .99 at 15.838. Gold = fricative onset; system = separator peak 30 ms
  inside /F/. 5th instance of the fricative-lag class.
- fun|he's (gold 16.196/16.198 HUMAN, sys 16.178, -20): N->HH(voiced). Separator .46 (16.178) -> peak .83 (16.190); trn
  5.6 + lo -0.9 -> -4.1 + cent 7.3 at 16.196. Human = the acoustic event just after the separator peak; sys at half-rise.
- he's.end (gold 16.375 acc, sys 16.348, -27): /Z/ zcr .7 to 16.344, -17 -> -28 -> -35 -> -42 -> -47 (16.376 floor).
  Gold at the floor (accepted: the old system also ended final fricatives at the floor); sys at -17..-28 re p99.
- kinda.start (gold 16.396 HUMAN, sys 16.398): closure 16.376-16.392 at floor, /K/ burst trn 23.6 at 16.400. ok.
- kinda|less (gold 16.624/16.626 HUMAN, sys 16.636/16.639, +13): AH->L, no separator (sep .00). trn 5.1 at 16.612, lo
  -3.2 + cent 6.65 at 16.618, hi falls -13.7 (16.618) -> -25.7 (16.636 = L constriction). Gold at the start of the hi
  fall, sys at the hi minimum. minor.
- less|fun (gold 16.888/16.893 acc, sys 16.838, -53): /S/+/F/ = one fricative 16.78-16.896 (cent 8.3-8.7 throughout).
  Loudness -3 (16.800) -> -13 (16.840) -> -22 (16.856) -> -28 (16.888), vowel -8 at 16.904. lo -26 (16.840) -> -9.8
  (16.872). CTC 'S' 16.800-16.816, 'P' 16.864-16.880 (for F). The weaker -22..-28 tail with rising lo (16.852-16.896) is
  the /F/; principled cut ~16.850. Gold (accepted) gives almost all of it to 'less' (10 ms /F/); system 12 ms early of
  16.850. Accepted gold unreliable here.
- fun.end (gold 17.046 acc, sys 17.172, +126): /N/ murmur to 17.040 (cent 4.1-4.6, lo 0, -13 -> -27); 17.050 trn 7.1,
  cent 7.9, dip -33 = onset of aperiodic noise 17.050-17.260 (-22..-33, cent 7.7-8.2, per .12-.27) decaying to floor
  -48/-52 at 17.270 = exhale. Gold at the nasal end; system inside the breath. Same as awful.end: sonorant-final word +
  noise with its own onset => breath, excluded.
- now.start (gold 17.303 acc, sys 17.300): floor -52 at 17.280, /N/ onset -38 (17.290), -30, -16. ok.
- now|he's (gold 17.558/17.563 HUMAN, sys 17.528/17.532, -31): AW->HH(voiced), level flat -1..-3. Separator peak .99 at
  17.528 (= system). CTC 'H' 17.546-17.576; hi min -22.9 at 17.558, trn 3.5 + mfcc max 2.94 at 17.564. Human = inside the
  CTC 'H' at the mfcc peak, 30 ms after the separator peak. With fun|he's (human 6 ms before CTC 'H' onset) and b|you
  (human 11 ms before CTC 'Y' onset): for V->glide/h joins the next word's FIRST CTC LETTER onset (+-12 ms) tracks the
  human better than the separator peak.
- he's|just (gold 17.703/17.705 acc, sys 17.674, -30): /Z/ 17.640-17.672 (zcr .5, cent 8.4), decays -7 -> -35 by 17.704,
  /JH/ burst trn 6.7 at 17.712. Gold = closure minimum before the burst (final-fricative decay stays with 'he's'); sys at
  the start of the decay.
- just|miserable (gold 17.896/17.898 acc, sys 17.926, +29): /T/ burst trn 11.9 at 17.878, aspiration 17.884-17.902 (-14..
  -23), /M/ onset 17.908 (-11, cent 5.4, lo -0.1, hi -25). Separator 17.884-17.938, peak 1.00 17.896-17.908. Gold at the
  aspiration end ~ M onset; sys 18 ms inside the /M/. Principled: nasal onset 17.905.
- miserable.end (gold 18.482 acc, sys 18.482): /L/ decays -14 -> -20 (18.480) -> -35 (18.496); low noise after (cent
  7.2-7.8, -33..-36) excluded by both. ok.
- i.start (gold 18.848 HUMAN, sys 18.874, +26): floor -49/-51 at 18.820-18.828, weak voiced rise -44 (18.836), -38
  (18.844, per .28), -33, -24 (18.860), -15 (18.876), -7 (18.884). CTC blank ('i' not recognised). Human at the first rise
  off the floor (+10 dB); system ~25 ms later at -26/-15 re p99. => vowel-initial onset: first sustained rise off the floor.
- i|and (gold 19.001/19.002 HUMAN, sys 18.970 end, pause, 19.006 start): 'i' vowel to 18.940, decays -12 -> -31 (18.980),
  dip -36/-35 at 18.988-18.996 (aperiodic, cent 7.6-8.0, still +12 over floor), glottal attack trn 8.0 glo 17.8 at 19.004,
  -7 at 19.012. Human: no pause, the tail stays with 'i' until the attack; system inserted a 36 ms pause at -24 re p99.
  Same as a|a #2. => a dip < ~50 ms that stays above floor is not a pause; cut at the next attack onset.
- and|it's (19.132 both). ok.
- it's|and (gold 19.314 HUMAN, sys 19.308): /S/ zcr .62 -> .36 (19.302), vowel onset cent 6.8 lo -2.1 at 19.308, trn 5.3
  19.320. ok (-6).
- and|you (gold 19.438/19.442 HUMAN, sys 19.444): separator peak .77 at 19.432, mfcc 2.79 at 19.444, trn 7.2 at 19.450. ok.
- you|every (gold 19.530/19.534 HUMAN, sys 19.572/19.576, +43): 'you' CTC 'U' to 19.518; loudness -5 -> -14 (19.518) ->
  -19 (19.530, minimum) -> -14 -> -8 (19.566) -> -1 (19.578); creaky/glottal pulses trn 3.5 (19.536), 6.0 (19.554), 6.2
  (19.566), 6.4 (19.578) = glottalised onset of vowel-initial 'every'. Separator only at 19.560-19.578 (peak .98 at
  19.572) = system. Human = loudness minimum before the creaky attack; CTC separator lags the creak by 40 ms. (glottal-
  attack class, confirmed human-moved.)
- every|time (gold 19.756/19.758 HUMAN, sys 19.762/19.767, +8): IY -5 -> -11 at 19.750 (lo -1.3 -> -0.6), -15/-17
  closure (voiced), /T/ burst trn 5.8 cent 8.3 at 19.774. Gold at the closure start. ok.
- time|you (gold 19.954/19.960 HUMAN, sys 19.972, +15): M->Y, separator 1.00 plateau 19.954-19.972, trn 3.1 at 19.954.
  Gold at plateau start; sys at plateau end. minor.
- you|hear (gold 20.094/20.100 HUMAN, sys 20.150/20.152, +52): UW per .46 to 20.094; 20.102 per .16, cent 5.4 -> 6.9, hi
  -21 -> -9.4 = /HH/ onset; aperiodic /h/ 20.102-20.20 (cent 7-8.5, -11..-18). CTC separator 20.102-20.142 (peak .93
  20.134) lies INSIDE the /h/; system at blank rise 20.150. Human = aperiodicity onset. (fricative/HH-lag class, 6th.)
- hear|her (gold 20.566/20.570 acc, sys 20.548, -20): R->HH(voiced), separator peak 1.00 20.536-20.548, mfcc 2.12 + hi
  rise at 20.584. Gold 18 ms after the separator peak (as now|he's +30, fun|he's +6): V->/h/ joins sit after the peak.
- her|you're (20.824/20.830 both): separator 1.00 20.818-20.830. ok.
- you're.end (gold 21.151 acc, sys 21.168, +17): voiced R -19..-27 to 21.164, -31 .. -42 (21.196) with rising cent (noise)
  = clip end. minor.

### 009-5 summary (75 tokens, ~150 boundaries, all read)
System errors >= 25 ms, by class (HUMAN = human-moved gold):
 A. Weak aperiodic word onset (DH/TH noise, HH) contiguous with the word cut off by the word-ref -20 dB pause test:
    this.start +139 (H), horrible.start +290 (H), you|hear +52 (H). Human starts at the spectral onset of the noise.
 B. Breath after a sonorant-final word included: awful.end +147, fun.end +126 (acc). Noise with its own onset/envelope
    after N/L = breath; noise adjacent to an aperiodic phone (A) = speech. Phone-ownership decides, not level.
 C. CTC separator lags 30-60 ms into word-initial fricatives: no|saving +42, the|shrew +54, you|see +63 (H), be|fun +32 (H),
    you|hear +52 (H). Cut at the aperiodic onset searching back from the separator.
 D. Short dip / decaying voiced tail treated as pause: a|a#2 -33 (H), i|and -31 (H), here.end +130 (click+bump, the other
    direction). A dip < ~50 ms that never reaches floor is not a pause; cut at the next attack.
 E. Vowel-initial / glottal attack: you|every +43 (H), a|a#1 +56 (H, no letters), i.start +26 (H). Loudness minimum before
    the attack; first rise off the floor.
 F. Released final stop keeps burst+aspiration: it|he -50 (H), that|guy's -45 (acc), that|woman +25 (acc). Homorganic
    T+D: single release goes to the 2nd word (just|destroying). Accepted golds scatter (top|to).
 G. Final fricative end at the floor: man's.end -21 (H), he's.end -27, he's|just -30 (acc).
 H. V/glide/h joins: b|you -28 (H), now|he's -31 (H), shrew|woman -53 (acc), we|all +24 (H), fun|he's -20 (H). The next
    word's first CTC letter onset or the constriction landmark (hi/loudness min) beats the separator edge; for V->/h/ the
    human sits 6-30 ms AFTER the separator peak.
 I. Pre-voicing hum before a word excluded: that's.start -56 (acc); short closure not a pause: like|the (acc, mid-closure).
 J. Merged cross-word fricatives ambiguous: his|psyche (H, all to 2nd word), that's|just (acc, late), less|fun (acc, odd).

## 009-6 DEEP RE-READ (supersedes the 009-6 skim). Tool: scratchpad joins.py (numeric table per boundary) + zoom.py.
Clip note: dB over the 2-s floor is only 11-20 in loud speech here (loud, continuous background or close-mic); use re p99.
- you.start (gold 0.326 HUMAN, sys 0.420, +94): clip opens mid-speech: 0.00-0.07 voiced tail (untranscribed), 0.08-0.26
  strong /S/ (cent 8.1-8.3, lo -23..-40, -1..-16 re p99, CTC 'S' .58 at 0.20), dip -15 at 0.270, voicing from 0.280 (per
  .60 -> .77, cent 6.0-6.3, lo -0.4..-1.0) decaying -8 -> -17 to 0.39, CTC 'Y' 0.404-0.416, vowel -7 at 0.434. Human
  started 'you' 46 ms into the voiced stretch; system at the CTC 'Y' end. Phone ownership: the /S/ belongs to the
  untranscribed previous word; the voiced stretch after it is the /Y/ of 'you' -> principled start 0.275-0.28 (S end, dip).
  => clip-initial foreign speech: start the first word where the foreign segment's phone class ends.
- you|know (gold 0.479/0.481 acc, sys 0.493/0.494, +14): UW->N voiced; hi falls -30 -> -41.4 (0.478) -> -43.9 (0.490 min);
  weak separator .28 max at 0.496-0.502. Gold at the hi fall, sys at the hi minimum. minor.
- know|how (gold 0.559/0.561 acc, sys 0.596, +36): voiced /h/: per .71 -> .41 (0.558 min) -> .77 (0.582); lo min -12.1 at
  0.552; weak separator .14 at 0.570-0.576; CTC 'H' only as 2nd candidate at 0.600-0.618. Gold at the periodicity minimum
  (/h/ centre; onset ~0.546); system 20+ ms after the /h/ in the vowel. => V->/h/: the periodicity dip marks the /h/.
- how|you (gold 0.671 HUMAN, sys 0.674): per dip .56-.61 + cent 7.1 at 0.670-0.676, separator .09 -> .91 (0.694). ok.
- you|go (gold 0.799/0.801 acc, sys 0.800): /G/ voice-bar closure from 0.792 (per .72-.76, cent 5.5, lo -0.1, -8/-9),
  separator .28 -> .87 at 0.798-0.816. ok.
- go|to (gold 0.916/0.917 HUMAN, sys 0.928, +12): flapped/voiced T (per .72-.81, -1..-4); hi -36 -> -42.2 (0.914) -> -47.3
  (0.932 min); separator .78 (0.914) -> .93 (0.932). Human at the start of the constriction, sys at its minimum. minor.
- to|somebody's (gold 1.008/1.010 acc, sys 1.014): OW -> /S/ onset 1.014-1.020 (cent 6.4 -> 7.2, hi -10.9 -> -6.6, zcr
  .17 -> .25); separator 1.014-1.038 sits AT the fricative onset here (no lag). ok.
- somebody's|website (gold 1.359/1.361 acc, sys 1.352/1.353, -7): /Z/ 1.320-1.344 (zcr .16-.20, cent 6.4-7.2, -18..-20)
  -> /W/ 1.350 (zcr .04, hi -25 -> -40). Z->W change at 1.344-1.350; system nearer. ok.
- website|and (gold 1.736/1.738 acc, sys 1.772/1.774, +36): 'site' /S/ 1.52-1.575, AY vowel 1.59-1.755 (-3..-7, cent
  7.5-7.9, per .45-.70), decay -10 (1.742) -> -14 (1.754) -> -21 (1.760); weak voiced /T/ closure 1.760-1.778 (-21..-23,
  per .29-.42), no burst; reduced 'and' 1.778-1.81 (-19..-22, lo -0.8..-1.5, hi -31..-36, CTC 'A' 1.784-1.796, 'N' 1.802).
  Accepted gold is 20 ms INSIDE the AY vowel; system at the end of the T closure / CTC 'A' onset. Acoustics favour the
  system (1.772-1.778). => accepted gold wrong by ~40 ms here.
- and|it (gold 1.822/1.823 acc, sys 1.858/1.859, +35): trn 5.0 at 1.810, loudness -19 -> -14 (1.816), cent 6.0 -> 7.0-7.4,
  lo -0.8 -> -3.8..-4.6 = N -> IH at ~1.810-1.816; CTC 'D' 1.822-1.834, separator 1.840-1.858 (peak .74 at 1.852). Gold at
  CTC 'D'; system at the separator end, 40 ms after the acoustic change. => letter-driven cut at the separator's trailing
  edge when the acoustic change is before the separator.
- it|says (gold 1.918/1.919 HUMAN, sys 1.956, +37): IH to ~1.900; voice-bar closure 1.906-1.936 (cent 5.4-5.6, hi -39..
  -44, per .50-.61, -17..-19), no burst; /S/ onset trn 5.2 at 1.942, cent 6.3 -> 7.2 (1.948) -> 8.3 (1.960). CTC 'T'
  1.900-1.936, separator 1.936-1.978 (peak .98 at 1.954). HUMAN split the unreleased /T/ closure in the middle (hi minimum
  1.918); system at the separator peak inside /S/ (even the S onset 1.942 would be +24). Like like|the: unreleased final
  stop + next word -> mid-closure; released stop -> after its release (it|he, that|guy's).
- says.end (gold 2.426 acc, sys 2.418): /Z/ -19..-24 to 2.418, -31 (2.424), -35, -38, -41 (2.448 floor ~-40..-47). Gold
  at the steep drop, floor 20 ms later. minor.
- this.start (2.932/2.934 both): floor -39..-47, /DH/ voiced onset -20 at 2.938 (hi -40.8). ok.
- this|person (gold 3.281/3.283 acc, sys 3.284/3.285): /S/ -17..-28 (zcr .28-.44) to ~3.290, /P/ closure not silent
  (-28..-35). ok.
- person|so (gold 3.614/3.616 acc, sys 3.613/3.615): /N/ (hi -40, cent 5.7) to 3.600; hi -32 -> -12.6 at 3.618, trn
  3.2 + fvel 2.8-3.0 at 3.618-3.630, cent 7.3 zcr .28 at 3.624 = /S/ onset. Separator weak (.05-.16) - system cut
  acoustically at the onset. ok.
- so|taylor (gold 3.787/3.793 acc, sys 3.768/3.769, -19/-24): OW decays -10 -> -21 (3.760-3.766, per .47-.53 = voiced
  tail) -> -26 (3.778) -> -32/-35 (3.784-3.790 closure) -> /T/ burst trn 16.9 at 3.796. Gold = closure start / just
  before the burst; system cut in the voiced tail at -21 re p99. Decaying voiced tail belongs to the word (class D).
- taylor|swift's (gold 4.089/4.091 acc, sys 4.106/4.108, +17): ER to 4.082; 4.088 -12, hi -36 -> -22.4, trn 4.1; cent
  6.8 zcr .18 (4.100); cent 8.0 per .16 (4.112) = /S/. Gold at the first landmark (hi jump + trn); system at separator .49,
  18 ms into the /S/. fricative-lag class (small).
- swift's.end (gold 4.544 HUMAN, sys 4.830, +286): /S/ decays -18 (4.512) -> -33 (4.542) -> -43 (4.582) -> floor -46.
  Low noise 4.60-4.68 (-39..-49). Then a 140 ms VOICED HUM 4.692-4.832 (-15..-32, per .45-.71, cent 5.1-5.4, hi -40..-46,
  lo -0.1, CTC blank) = untranscribed "mm". Floor again 4.852. Human ended at the /S/ decay (-33) and excluded the hum;
  system extended 'swift's' over the hum. => an island separated by ~100 ms of floor whose phone class (voiced nasal
  murmur) does not match the word's final phone (/S/) is not that word: exclude (untranscribed filler).
- you.start (gold 5.059 acc, sys 5.064): floor -47 to 5.040, click trn 10.1 at 5.046 (-38), voicing rise trn 6.1 at 5.064,
  -9 at 5.070. ok.
- you|know (gold 5.134/5.136 acc, sys 5.152/5.154, +18): UW (hi -41, lo -1.1) -> lo -3.0 (5.128), hi -30 (5.134); weak
  separator .30 -> .63 peak 5.152; CTC 'N' only .45 at 5.182; 'y'know' reduced (5.14-5.18 lo -4..-7, not nasal). Gold at
  the lo/hi change, sys at the separator peak. minor.
- know|needs (gold 5.286/5.288 acc, sys 5.258/5.260, -27): OW->N transition lo -2.9 (5.246) -> -1.5 (5.258) -> -0.2
  (5.282), hi -> -46 by 5.294; separator .53 (5.258) -> .62 peak (5.270) -> .39; CTC 'N' from 5.282. Gold = end of the
  transition = CTC 'N' onset; system = its start (separator rise). next-word-first-letter onset again.
- needs|to (gold 5.507/5.508 HUMAN, sys 5.514): /Z/ (cent 8.2-8.4, zcr .5) to 5.518, /T/ (flapped, per .38-.52, cent 7.4,
  lo -2.5) from 5.524; separator peak .88 at 5.512. ok.
- to|say (gold 5.548/5.550 HUMAN, sys 5.594/5.595, +45): 'to' vowel 5.542-5.554 (per .37-.52); /S/ onset 5.560 (cent 7.8,
  hi -4.6, trn 2.4, fvel 1.8) -> 5.572 (cent 8.2, zcr .50). Separator .84 at 5.590, peak .98 at 5.608. Human 12 ms before the
  fricative onset (vowel end); system 30 ms inside /S/. fricative-lag class, human-moved (7th).
- say.end (gold 5.844 acc, sys 5.860): EY decays -17 -> -23 (5.844) -> -27/-30 (5.856-5.862) -> -39 (5.886), per .37-.56.
  minor.
- a.start (6.300/6.304 both): glottal attack trn 10.3/16.2 at 6.300-6.306. ok.
- a|million (gold 6.390/6.392 HUMAN, sys 6.438, +47): AH (-7, lo -5.8) -> 6.378 per .26 lo -3.2 -> 6.390 lo -0.7 cent
  5.8 -> 6.396 lo -0.2, per .51, hi -40 = /M/ murmur. Separator .63 at 6.390, peak .96 at 6.414, .34 at 6.438. Human = the
  vowel->nasal change (lo -> 0, cent drop); system = separator trailing edge 48 ms into /M/. => letter-driven cut at the
  separator's far edge; the acoustic change sits at the separator's rising edge. The +-10 ms class search cannot reach it.
- million|number (gold 6.920/6.923 acc, sys 6.938/6.942, +19): N|N geminate. Separator plateau .91-.99 6.902-6.932; tiny hi
  bump -44.9 -> -37.1 at 6.920-6.926 (a slight release between the nasals); CTC 'N' from 6.944 (= system, the geminate
  estimator). Gold at the hi bump / separator middle. minor.
- number|one (gold 7.169/7.170, one.start HUMAN, sys 7.200, +30): ER->W. Separator .45 (7.162) -> .92 (7.174), plateau .87-.91
  to 7.192, .63 at 7.198; lo -4.5 -> -2.3 (7.168) plateau; flatness min -10.3 at 7.186-7.192. Human at the separator's
  leading edge / lo plateau start; system at the trailing edge. Same pattern as a|million and we|all.
- one|gold (7.380/7.382 acc, sys 7.378): separator .99 at 7.376-7.382, /G/ burst trn 5.9 at 7.400. ok.
- gold|records (7.640/7.644 acc, sys 7.634/7.636): CTC D 7.604-7.616, loudness dip -15 at 7.628-7.634, separator peak .98
  7.652, 'R' 7.664. ok.
- records|or (gold 8.179/8.180, or.start HUMAN, sys 8.171/8.173): /Z/ to 8.164 (cent 8.0-8.2, zcr .38-.47), 8.170
  transition, 8.176 vowel onset (cent 6.1, lo -1.8, -24 -> -17). ok.
- or.end (gold 8.324 HUMAN, sys 8.504, +180): 'or' vowel (per .64, cent 5.7, hi -51) to 8.316; 8.324 per .35, 8.332 trn
  5.4; 8.340-8.500 sibilant noise (cent 8.2-8.3, zcr .45-.53, lo -20..-28, -18..-25, per .2-.35; CTC 'S' .92-.95 at
  8.444-8.476!) decaying to floor -43 by 8.524. An untranscribed 's'/false start or exhale. Human ended 'or' at the end of
  voicing and excluded it; system included it. Phone ownership: 'or' ends in R (sonorant) -> the noise is not 'or'.
- you.start (gold 8.654 HUMAN, sys 8.608, -46): tiny voiced blip -45 at 8.578-8.590, silence -51/-53, 8.608 trn 17.4 (burst)
  + frication 8.614-8.644 (cent 8.2, zcr .4-.5, -24..-38; CTC 'T' .96 at 8.602-8.614!), 8.650 cent 7.3 lo -2.3 -> 8.656
  cent 5.9 lo -0.4 = /Y/ voicing onset (-18, -14, -11). Human started at the voicing onset, excluding the burst+noise;
  system started at the burst. Phone ownership: 'you' starts with a sonorant -> a preceding burst/frication is not 'you'.
- you|know (8.732/8.733 acc, sys 8.739/8.741): level flat; lo -3.1 -> -3.9..-6.4. ok.
- know|platinum (know.end 8.873 acc, platinum.start 8.887 HUMAN; sys 8.854 / 8.900): 'know' vowel decays -17 -> -30
  (8.872, per .49) -> -38 (8.884); /P/ closure 8.878-8.888; burst trn 9.2 at 8.890; aspiration 8.896-8.914 (CTC 'P'
  8.902). Human started 'platinum' just BEFORE the burst and left the 14 ms closure as a gap; system started after the
  burst (+13) and ended 'know' at -25 in the voiced decay (-19).
- platinum.end (gold 9.339 HUMAN, sys 9.258, -82) / and.start (gold 9.469 HUMAN, sys 9.259, -210): /M/ murmur (per .5-.76,
  cent 5.6-5.8, lo -0.2..-0.6) decays slowly -18 (9.24) -> -25 (9.29) -> -35 (9.322) -> -38 (9.340) -> -41..-46 (9.37-
  9.40), floor -46..-54 9.40-9.46, then weak noise 9.458 (hi -11) + trn 2.0 at 9.468, voicing -32 (9.478), -22 (9.488) =
  'and'. CTC separator .98 at 9.286-9.316, no letters for 'and' nearby. Human: M tail to 9.339 in 'platinum', gap, 'and'
  from its real onset 9.469. System started 'and' at 9.259 INSIDE the M murmur, so 'and' swallowed the murmur tail AND the
  60 ms floor gap (and = 9.259-9.713). => a floor gap >= ~50 ms between two words must be a boundary (pause); a voiced
  murmur contiguous with the previous word's final nasal belongs to it.
- and|things (gold 9.703/9.704 acc, sys 9.713/9.715, +11): /D/ closure -42/-43 9.690-9.702; /TH/ burst trn 14.2 at 9.708
  (stopped TH), frication to 9.714. Gold before the burst, sys at the frication. minor.
- things|and (gold 10.083/10.085 acc, sys 10.073/10.075, -10): /Z/ -> vowel: cent 8.2 -> 7.8 (10.066) -> 6.7 (10.078) ->
  6.0 (10.084); separator peak .93 at 10.054. Gold at the end of the transition, sys mid. ok.
- and|this (gold 10.197/10.199 acc, sys 10.173/10.175, -24): D->DH. Separator plateau .91-.92 10.172-10.190; hi min -44.1
  at 10.196 (voiced closure), DH release 10.208 (per .50, hi -28.6, glo 19.0); CTC 'T' 10.202, 'H' 10.220. Gold = release /
  next-word first letter; system = separator LEADING edge. (In a|million the system took the TRAILING edge.) The
  separator edge used is not systematic; the acoustic landmark (release / nasal onset / lo plateau) must decide.
- this|many (10.382-10.387 both): /S/ -17..-30, /M/ onset 10.388 (per .42, lo -1.0). ok.
- many|sold (gold 10.606/10.608 acc, sys 10.621/10.623, +15): IY to 10.606; hi -18.6 + trn 2.2 at 10.612, cent 7.3 zcr .24
  fvel 2.5 at 10.618 = /S/ onset ~10.612. Separator .28 -> .55 at 10.618-10.624. System 8 ms into /S/. minor.
- sold|in (10.984/10.986 acc, sys 10.989/10.991): separator .97 at 10.972, trn 2.4 at 10.984. ok.
- in|and (gold 11.114/11.115 HUMAN, sys 11.123/11.125, +10): separator .41 -> .96 at 11.100-11.112, plateau to 11.130;
  trn 2.4 at 11.112. Human at the separator rise/peak, sys mid-plateau. minor.
- and|spotify (gold 11.310/11.311 HUMAN, sys 11.364/11.365, +54): nasal (per .66-.73, hi -38..-41) to 11.298; closure-ish
  -17..-23 (per .36-.50) 11.304-11.328; trn 1.9/4.9/4.7 + fvel 2.6 at 11.322-11.334, cent 7.3 (11.334) -> 8.0 (11.340) =
  /S/ onset ~11.330. CTC blank here (no separator at all). Human at the nasal end (gave the /D/ closure to 'spotify');
  system 30 ms inside /S/ (lexical/prior placement). Fricative onset would be -20 from human.
- spotify|top (12.010-12.014 both; top.start 12.064 both at /T/ burst trn 8.9). ok.
- top|ten (gold 12.297/12.299 acc, sys 12.242 end, pause, 12.310 start): /P/ released ~12.21 (CTC 'P' 12.224-12.236),
  aspiration decays -22 -> -33 (12.266) -> -38 (12.296-12.302) (cent 6.8-7.2, lo -9..-18, per .25-.47), /T/ burst trn 21.2
  at 12.308. Gold: aspiration stays with 'top' up to the /T/ burst. System cut 'top' at -27 inside the aspiration and made
  a pause. Released-stop class F again.
- ten.end (gold 12.639 acc, sys 12.628): N decays -17 -> -32 (12.640) -> -39 (12.652); click trn 12.0 at 12.658 + noise
  after, excluded by both. ok.
- songs.start (13.107/13.110 both): transient trn 10.2 at 13.106 then /S/. ok.
- songs|on (gold 13.427/13.428 HUMAN, sys 13.451/13.453, +24): /Z/ fully voiced here (per .55-.72, zcr .04-.07), loudness
  min -13 at 13.414, rise -8 (13.426) -> -7; separator .35 (13.420) -> .62 (13.426) -> .99 (13.450); lo -1.5 -> -3.0 ->
  -7.9 (13.474). Human at the separator half-rise just after the loudness minimum; system at the separator peak.
- on|spotify (gold 13.568/13.570 acc, sys 13.575/13.577): N to 13.562; hi -25 (13.568) -> -12 (13.574, trn 2.8) -> cent 8.2
  zcr .44 (13.586) = /S/. No separator (blank .93-.99). ok.
- spotify|for (spotify.end 14.118 acc, for.start 14.165 acc; sys 14.098 / 14.099): AY decays -8 (14.072) -> -21 (14.102)
  -> -26 (14.114); /F/ frication 14.126-14.162 (cent 5.8 -> 7.7, hi -24 -> -8.4, per .32 -> .08, zcr .09 -> .31, -28..-33);
  vowel 14.168 (-24 -> -14). CTC separator 1.00 14.114-14.126, 'F' 14.144-14.156. SUSPECTED GOLD ERROR: accepted
  for.start 14.165 excludes the whole /F/ (a 47 ms hole in no word). Principled: spotify.end = for.start ~14.12. System's
  for.start 14.099 is 25 ms early (inside the vowel decay).
- for|this (gold 14.242/14.244 HUMAN, sys 14.236/14.239): separator .87 at 14.230, CTC 'T' 14.242. ok.
- this|many (gold 14.414/14.416 acc, sys 14.393/14.395, -21): /S/ (zcr .21-.24) to 14.374, cent 6.0 (14.380) -> 5.5
  (14.386), lo -> -0.2, hi -25 = /M/ onset ~14.383. Separator 1.00 at 14.410; CTC 'M' 14.422. Gold at the separator end /
  CTC M; the acoustic change is 10 ms before the system and 30 ms before the gold. minor, gold late.
- many|years (gold 14.640/14.642 acc, sys 14.611/14.613, -29): IY->Y continuous; separator 1.00 plateau 14.616-14.628, .62
  at 14.640; CTC 'Y' from 14.640. Gold = next word's first CTC letter onset; system = separator rise. (know|needs pattern.)
- years|and (gold 14.992/14.994 acc, sys 14.973/14.975, -19): /Z/ (cent 8.1-8.3, zcr .42-.52) to 14.972; transition
  14.978 (cent 7.9, lo -5.8) -> 14.984 (6.9, per .33) -> 14.990 (5.9, per .53). Gold at the end of the Z->vowel
  transition, system at its start. minor.
- and|blah #1 (gold 15.108 acc, sys 15.130, +21): N decays -16 -> -30 (15.102); /B/ closure 15.102-15.144 (-29..-38),
  burst trn 3.5/5.8 at 15.144-15.150. Gold at closure start, sys mid-closure. minor.
- blah|blah #1 (15.310 both): dip -12 at 15.298, /B/ release trn 2.3/2.9 at 15.304-15.310. ok.
- blah|blah #2 (gold 15.438/15.440 acc, sys 15.407/15.409, -31): AA decays -9 -> -18 (15.406) -> voiced /B/ closure
  -20..-22 (15.418-15.436, per .5-.6), release trn 5.8 at 15.436, /L/ rise. Gold at the RELEASE (closure given to the
  previous 'blah'); system at the closure START. Same for blah|blah #4 (gold 16.038 at release trn 7.2 16.042, sys 16.008 at
  closure start, -30). In and|blah #1 the gold took the closure start instead. Accepted golds: B-closure placement
  scatters between closure start and release (up to 30 ms).
- blah|and #1 (gold 15.638/15.639 acc, sys 15.614/15.617, -22): AA->AE, no acoustic change (level -10..-12, lo -6..-7,
  mfcc 1.0-1.7). Separator .60 at 15.614 (= system); CTC 'A' .53 15.620-15.638 (gold at its end). No evidence either way.
- and|blah #2 (15.716/15.719 acc, sys 15.727/15.729): N (hi -39..-43) -> closure -19..-30 from ~15.716; separator .84 at
  15.710. ok.
- blah|blah #3 (15.911/15.913 acc, sys 15.907/15.909): voiced B dip -13 at 15.900, CTC 'V'(=B) 15.900-15.918. ok.
- blah|and #2 (gold 16.265/16.267 acc, sys 16.290, +24): creaky region (per .13-.36, glo 19-21): AA decays -11 -> -27
  (16.258-16.264); glottal pulse trn 7.5 at 16.270 (-18/-16), dip -26 at 16.288, 2nd pulse trn 6.1 at 16.294, vowel -13
  at 16.294+. Gold at the loudness minimum before the FIRST glottal pulse; system at the second dip. Class E: vowel-initial
  word with creaky onset -> the first attack.
- and|blah #3 (gold 16.405/16.407 acc, sys 16.420/16.421, +15): N -16 -> -25 (16.404) -> -32 (16.422); /B/ burst trn
  3.8/5.4 at 16.428-16.434; separator .96 at 16.392. minor.
- blah|blah #5 (16.612/16.614 acc, sys 16.604): voiced B, CTC 'V' 16.602-16.614. ok.
- blah|blah #6 (gold 16.720/16.722 acc, sys 16.702/16.703, -18): AA -5 -> -17 (16.694), closure -16..-19 to 16.724, weak
  release trn 1.5 at 16.730, CTC 'B' 16.724-16.736. Gold at the closure end (as #2, #4); system at the closure start.
- blah.end (last; gold 16.898 acc, sys 17.086, +188): AA decays -23 -> -35 (16.892) -> -41 (16.908); trn 4.4 at 16.916 then
  aperiodic noise 16.92-17.11 (-27..-36, cent 7.4-7.9, per .12-.28, zcr .25-.36) = exhale. Gold at the vowel decay;
  system included the breath. Class B (breath after sonorant-final word).
- and.start (gold 17.315 acc, sys 17.320): glottal attack trn 19.9 at 17.314, -11 at 17.320. ok.
- and.end (gold 17.756 acc, sys 17.740, -16): N murmur (hi -40..-43) -15 (17.734) -> -22 -> -29 -> -32 (17.752) -> -36 ->
  -40 (17.764). Gold at -32/-36, system at -22. Nasal decay tail kept longer by gold. minor.
- caused.start (gold 18.136 acc, sys 18.140): /K/ burst transients 4.3-5.2 at 18.128-18.134, 12.0 at 18.140. ok.
- caused|the (gold 18.563/18.565 acc; sys 18.532 end, pause, 18.600 start): /Z/ 18.502-18.526 (cent 6.9-7.9, zcr up to
  .36, -16..-25); weak frication/closure 18.532-18.592 (-27..-36 = +13..+22 over floor, zcr .18-.29, per .23-.44); /DH/
  voicing onset -22 at 18.598 (per .47, lo -0.5), trn 6.1 at 18.604. Separator .91-.99 18.532-18.568, CTC 'T'(DH)
  18.604. Gold split the weak stretch in the middle; system made it a pause. A 60 ms stretch 13-22 dB over the floor
  between two words is not a pause (class D). Principled: the fricative/stop tail belongs to 'caused' -> ~18.595.
- the|senate (gold 18.754/18.757 acc, sys 18.788, +31): vowel to 18.748; hi -23 -> -15.7 + trn 2.7 at 18.754, cent 6.4
  zcr .13 at 18.760, cent 7.6 zcr .36 at 18.772 = /S/. Separator 1.00 18.754-18.772, .42 at 18.784 (= system). Gold at the
  fricative onset; system 30 ms inside /S/. fricative-lag class.
- senate.end (gold 19.285 acc, sys 19.270, -15): final T region: weak noise -28 -> -39 (cent 6.7-7.2, per .2-.4) to 19.298,
  floor -45 at 19.304. minor.
- to.start (gold 19.331 acc, sys 19.338): /T/ burst trn 16.1 at 19.334. ok.
- to.end (gold 19.853 acc, sys 19.846): long 'tooo' (522 ms); voiced decay -17 -> -28 (19.852) -> -35 (19.870) -> -39..-42
  (19.88-19.91, per .4-.6). minor.
- form.start (gold 20.067 acc, sys 20.046, -21): weak bump -30 at 19.930 (trn 3.4 at 19.920), hi -15 -> -10 at 19.940-
  19.950, /F/ frication 19.955-20.062 (cent 7.6-8.1, zcr .30-.45, -30..-36), vowel onset 20.068 (per .40, lo -2.4); CTC 'F'
  20.044-20.056. SUSPECTED GOLD ERROR (2nd, with spotify|for): accepted form.start at the vowel onset excludes the whole
  110 ms /F/. Principled start ~19.94-19.955. System also late (inside the F at CTC 'F'). In 009-5 be|fun the HUMAN-moved
  gold included the /F/, so the accepted exclusions look like tolerated old-system errors.
- form|a (20.364-20.369 both): separator 1.00 20.352-20.370, trn 4.6 at 20.364. ok.
- a|committee (gold 20.514/20.518 acc; sys 20.490 end, pause, 20.548 start): AH decays -11 -> -26 (20.490) -> -31 (20.502-
  20.514) -> -40 (20.532), per .23-.39 (weak voicing tail) to ~20.530; closure 20.532-20.542; /K/ burst trn 22.1 at 20.544.
  Gold in the tail ~15 ms before the closure; system ended at -26 re p99 (tail cut, class D) and started after the burst.
  Principled: end ~20.530, start = closure/just before the burst (platinum human convention).
- committee|to (gold 21.113 end / 21.131 start acc; sys 21.100 / 21.101): IY decays -14 -> -24 (21.110) -> -33 (21.128),
  per .6 -> .16; /T/ burst trn 16.3 at 21.134. Gold leaves the closure as a gap and starts 'to' just before the burst;
  system started 'to' 30 ms early in the vowel tail (separator plateau). minor-ish.
- to|investigate (gold 21.277/21.278 HUMAN, sys 21.270): UW->IH, separator plateau 1.00 21.274-21.292. Human at the plateau
  start. ok.
- investigate|ticketmaster (gold 22.057/22.059 acc; sys 22.020 end, pause, 22.106 start): EY voiced (per .59-.72) decaying
  -23 -> -34 (22.048); per .48 -> .32 over 22.054-22.066 with a weak final-T transient trn 3.7 at 22.060; closure -38..-42
  22.072-22.100; ticketmaster /T/ burst trn 15.2 at 22.102. Gold at the end of voicing (closure to the next word); system
  ended at -27 in the voiced decay (-37 ms) and started after the burst (+47). Class D + stop-onset convention.
- ticketmaster.end (22.878-22.884 both): ER decays -28/-33. ok.  because.start (gold 23.272 acc, sys 23.278): B voicing
  -38 at 23.270, burst trn 9.6 at 23.276. ok.
- because|of (gold 23.662/23.664 acc, sys 23.654/23.656): /Z/ (cent 7.6-7.9, zcr .26-.34) to 23.636, vowel from 23.642
  (cent 6.8, lo -1.4); separator 1.00 23.636-23.648. Both ~15 ms late. ok.
- of|the (gold 23.770/23.772 acc, sys 23.752/23.755, -17): V->DH voiced continuous (per .6-.7), separator plateau .92-1.00
  23.734-23.764, trn 4.2 at 23.758, CTC 'T'(DH) 23.782. No sharp landmark. minor.
- the|way (gold 23.898/23.900 acc, sys 23.884/23.886, -14): separator 1.00 plateau 23.896-23.908 (gold at its start), hi
  -42 -> -50 (23.914). minor.
- way|ticketmaster (end 24.258/24.264, start 24.316 both at the /T/ burst 24.306-24.318). ok.
- ticketmaster|handled (ticketmaster.end 25.057 acc, handled.start 25.087 acc; sys 25.018 both, -39/-69): ER voiced (per
  .45-.56) decaying -9 -> -24 (25.046); 25.052 per .30, cent 6.8; 25.058-25.082 breathy /HH/ (per .11-.28, cent 7.0-7.5,
  lo -3.6..-15, -31..-34; CTC 'H' 25.064-25.094); vowel from 25.094-25.100. SUSPECTED GOLD ERROR (3rd): accepted gold
  leaves the /h/ in no word (25.057-25.087). Principled: 25.052-25.057 (= gold end). System 35 ms EARLY at the separator's
  trailing edge (separator 1.00 24.998-25.010) - here the separator precedes the acoustic change.
- handled.end (25.544 both): decays -33 -> -38 -> -45. ok.

### 009-6 summary (78 tokens, all boundaries read)
Largest system errors and their classes (H = human-moved gold):
 * Islands / non-word sound attached to a word: swift's.end +286 (H, voiced hum after ~100 ms of floor), or.end +180 (H,
   sibilant 's'-noise after a sonorant-final word), blah.end +188 (exhale), you.start -46 (H, burst+frication before a
   sonorant-initial word), you.start (clip start) +94 (H, clip opens with foreign /S/ + voicing).
 * Floor gap not used as a boundary: platinum|and -82/-210 (H): 'and' started inside the previous word's /M/ murmur.
 * Voiced decay tail / short weak stretch cut into a pause: so|taylor, a|committee, investigate|ticketmaster, caused|the,
   top|ten (aspiration), -19..-55 on the end side and +30..+47 on the start side.
 * CTC separator inside a word-initial fricative: to|say +45 (H), the|senate +31, and|spotify +54 (H, no separator at all
   - prior placement), it|says +37 (H), taylor|swift's +17.
 * Separator edge chosen instead of the acoustic landmark: a|million +47 (H), number|one +30 (H), and|it +35, website|and
   +36 (gold 20 ms inside the vowel), know|needs -27, many|years -29 (gold = next word's first CTC letter), and|this -24,
   ticketmaster|handled -39/-69 (separator 35 ms BEFORE the acoustic change).
 * V->/h/: know|how +36 (periodicity dip marks the /h/).
Suspected gold errors (accepted): spotify|for (F excluded), to|form (F excluded), ticketmaster|handled (h in no word),
website|and (end 20 ms inside the vowel). Scatter: /B/ closures in blah|blah between closure start and release.

## 009-7 DEEP RE-READ (supersedes the 009-7 skim quoted by the user). Tool: joins.py per boundary.
- uh.start (0.002/0.006): clip start. ok.
- uh|and (uh.end 0.237 HUMAN, and.start 0.238 acc; sys 0.206 end, pause, 0.278 start): 'uh' (breathy, per .45-.58,
  -16..-19) drops to -23 at 0.206; 0.212-0.266 sits AT the local floor (dB over floor -2..+3, -22..-27 re p99); rise -20
  (0.272) -> -14 (0.284) -> -11. System = acoustic edges (drop / rise) with a 72 ms pause; the HUMAN moved uh.end to meet
  and.start mid-gap, i.e. they wanted no pause for a ~60 ms floor gap. Contrast platinum|and (human left a ~130 ms gap).
  => candidate: floor gaps shorter than ~80-100 ms are split, not pauses (to be checked against all data).
- and|congresswoman (gold 0.456/0.458 acc, sys 0.468/0.469, +12): N decays -11 -> -22 (0.468); trn 4.3 at 0.474, -28 at
  0.480 (closure), trn 5.1 at 0.492 (/K/). minor.
- congresswoman|but (0.922/0.924 acc, sys 0.928): N, separator .90 at 0.922, /B/ release trn 6.6 at 0.928. ok.
- but|when (gold 1.062/1.063 HUMAN, sys 1.066/1.071): loudness -8 -> -11 at 1.060-1.066, separator .31 -> .81. ok.
- when|i've (gold 1.216/1.218, sys 1.228, +10): N->AY; lo -1.5 -> -4.6 (1.216) -> -7.3; separator .87 -> .96 (1.228).
  Gold at the lo change, system at the separator peak. minor.
- i've|spoken (gold 1.345/1.347 HUMAN, sys 1.388/1.389, +42): /V/ voiced (per .78) to 1.332; 1.338 hi -15.5, trn 2.8;
  1.344 cent 7.2, hi -8.6, per .47; 1.350 cent 8.4, zcr .50 = /S/ onset ~1.342. CTC spells an 'E' (.49-.96) INSIDE the /S/
  1.344-1.374, then separator 1.380-1.398 (peak .97 at 1.392), then 'S' 1.404. Human = fricative onset; system at the
  separator 45 ms into /S/. fricative-lag class + CTC misrecognition moving the separator.
- spoken|to (gold 1.700/1.701 HUMAN, sys 1.714, +14): /N/ murmur (per .8) to ~1.716, no silent closure, /T/ burst trn 12.5
  at 1.722; separator .92-.99 1.692-1.710. Human 20 ms before the burst at the separator rise; system at its peak. minor.
- to|people (gold 1.782/1.784 acc, sys 1.778 / 1.812, +28 on the start): UW decays -14 -> -34 (1.778); closure -36..-40
  1.784-1.802; /P/ burst trn 5.9 at 1.808; aspiration 1.814-1.832. Gold starts 'people' at the closure start; system after
  the burst (the burst must belong to the P-word under any convention).
- people|over (gold 2.036/2.039 HUMAN, sys 2.132/2.135, +96): /L/ (per .67-.78) to ~2.030; at 2.036-2.042 lo -4.9 -> -9.3,
  hi -30 -> -36; 2.054-2.132 CREAKY voicing (per .22-.43, glo 16-20, trn 6.5 at 2.072, -8..-13); modal voicing from 2.138
  (per .54 -> .81), CTC 'O' only at 2.162; separator .95-.99 2.036-2.066. Human started vowel-initial 'over' at the onset
  of the creak; system at the modal-voicing onset/blank end. Class E (creaky attack belongs to the vowel-initial word).
- over|the (gold 2.348/2.354 acc, sys 2.336/2.339, -16): R->DH, separator peak .94 at 2.330, CTC 'T'(DH) 2.342-2.360, hi
  rises -27.9 -> -22.8 at 2.336-2.348. minor.
- the|past (gold 2.422/2.425 acc, sys 2.429): vowel decays to -37 (2.416), /P/ burst trn 6.0 at 2.422. ok.
- past|week (2.724-2.730): /S T/ frication to 2.716, W onset 2.734 (per .48, cent 6.5). ok.
- week.end (gold 2.898 HUMAN, sys 3.066, +168): IY voiced tail -33/-36 (per .55-.61) to 2.876; /K/ release trn 7.1 at
  2.884; decay -38 -> -47 (floor) 2.892-2.908; new onset trn 3.0/4.8 at 2.916-2.924 -> noise 2.93-3.09 (-21..-33, cent
  7.1-7.9, per .13-.47) = exhale. Human ended after the K release decay; system included the breath. Here the word ends
  in an aperiodic phone (K release) but the breath is a SEPARATE event (floor dip + new onset) -> excluded. => the breath
  rule must use the separate envelope (dip to floor + new onset), not only the adjacent phone class.
- there.start (gold 3.274 acc, sys 3.246, -28): floor -53..-60 to 3.270; /DH/ burst trn 23.3 at 3.276. System started 30 ms
  early inside silence (CTC 'T' 3.264-3.276). Start should snap to the burst.
- there|was (gold 3.402/3.404 acc, sys 3.425/3.427, +23): R->W, separator .50 (3.402) -> .96 (3.414), plateau to 3.432;
  hi minimum -45.8 at 3.414. Gold at the separator leading half-rise; system at the trailing edge.
- was|some (gold 3.562/3.564 acc, sys 3.518/3.519, -44): /Z/ voiced 3.486-3.504, then ONE continuous sibilant 3.510-3.600
  (cent 7.9-8.7, zcr .43-.70, -15..-19). lo has two minima (-20.9 at 3.528-3.534, -22.7 at 3.564) with a local max -15.2 at
  3.552; tiny loudness dip -19 at 3.546-3.558; separator .37 -> .96 (3.552) -> .69; CTC 'S' 3.582. Gold splits at the
  separator / lo local max; system gave the whole fricative to 'some' (as the human did in his|psyche, where there was NO
  separator). => merged cross-word fricative: split at the separator peak / lo local max when one exists, else onset.
- some|they (3.768-3.775 both): M->DH voiced, separator .90 at 3.756, hi min -52.6 at 3.744. ok.
- they|were (gold 3.862/3.865 acc, sys 3.886/3.889, +24): EY->W, hi -36.5 (3.862) -> -45.0 (3.874) = W constriction onset;
  loudness -9 -> -14 (3.886); weak separator (.26 max); CTC 'W' .52 at 3.880. Gold at the start of the hi fall; system at
  the CTC 'W' / loudness minimum. minor.
- were|just (gold 3.962/3.965 acc, sys 3.986/3.989, +24): ER voiced to 3.938 (-25); 3.944 per .14 trn 3.0 (closure/burst);
  JH frication 3.950-3.990 (cent 7.6-8.2, zcr .36-.48, trn 4.3 at 3.956); vowel 3.992 (per .51). Separator .42 (3.962) ->
  .92 (3.992). Gold inside the affricate (15 ms after onset), system at its END. Principled: closure/burst ~3.942 (system
  +46). fricative/affricate-lag class.
- just|saying (gold 4.103/4.105 acc, sys 4.082, -21): merged /S T/+/S/ fricative 4.062-4.122 (cent 8.5-8.8, zcr up to .75);
  loudness dip -24 + lo -16.4 at 4.080; separator .47-.83 4.068-4.098; CTC 'S' 4.104-4.116. Gold at CTC 'S' onset, system
  at the separator/loudness dip. Merged-fricative scatter.
- saying.end (4.316/4.319-4.320): decays -28/-31. ok.  the.start (4.620-4.622 both): burst trn 7.1/12.1. ok.
- the|kenyan (gold 4.715/4.717 acc; sys 4.700 end, pause, 4.756 start): AH decays -10 -> -31 (4.700) -> -36 (4.706-4.712)
  -> closure -41..-50 (4.718-4.748) -> /K/ burst trn 20.4 at 4.754. Gold gives the closure to 'kenyan' (start at the
  closure start); system made the closure a pause and started after the burst (+39). Start-after-burst is wrong under any
  convention.
- kenyan|forces (gold 5.124/5.126 acc, sys 5.118/5.120): N to 5.106; hi -32 -> -19 -> -11.6 over 5.112-5.124 = /F/ onset
  ~5.117; separator rises exactly there. ok.
- forces.end (gold 5.773 acc, sys 5.790, +17): /Z/ (zcr .43-.80) to 5.772, then a 12 ms voiced bump 5.778-5.790 (per .31-.34,
  cent 6.2-6.6, -22..-28), floor from 5.802. Gold at the frication end, system includes the voiced bump. minor.
- and.start (5.838-5.842 both): glottal attack trn 9.9 at 5.844. ok.
- and|benin (gold 5.964/5.967 acc, sys 5.994/5.997, +30): merged voiced D+B closure 5.940-6.018 (per .7-.8, hi -50..-56);
  separator .38 (5.958) -> .91 (5.976) -> .48 (5.994); /B/ release trn 4.3/10.1 at 6.018-6.024, CTC 'B' 6.000-6.018. Gold at
  the separator rise, system at its trailing edge; the separator peak (5.973) would be ~6 ms from gold.
- benin|actually (6.318-6.324 both): N->AE lo -1.5 -> -3.7 at 6.324. ok.
- actually|was (gold 6.588/6.590 HUMAN, sys 6.600/6.604, +14): IY->W, hi -27 -> -37 (6.594) -> -40.7 (6.606); separator
  .21 -> .49 (6.600-6.612). Human mid hi-fall; system at separator rise. minor.
- was.end #1 (gold 6.746 HUMAN, sys 6.736, -10): /Z/ -21 (6.728) -> -26 -> -34 -> -40 (6.746) -> -50 (6.764 floor). Human at
  -40 re p99 (final-fricative end near floor, class G).
- was.start #2 (6.794/6.800). ok.
- was|also (was.end 7.088 / also.start 7.101 acc, sys 7.100/7.101): /Z/ to 7.058, voiced release 7.064-7.082 (per .30-.34),
  dip -42 at 7.094, also rises from 7.100. Both around the dip. ok.
- also.end (7.548-7.552 both), uh.start (7.940/7.946, attack trn 15.7 at 7.952). ok.
- uh.end (gold 8.271 HUMAN, sys 8.252, -19): 'uh' decays -9 -> -25 (8.252) -> -33 (8.264) -> -40 (8.270) -> -41..-46
  (8.276-8.294, per .41-.60 still weakly voiced) -> floor -51..-54 (8.300). Human at -40 re p99; system at -25 (class D:
  voiced decay tail kept down to ~-40).
- pointed.start (8.330-8.333 both): /P/ burst trn 7.1/19.1 at 8.330-8.336. ok.
- pointed|out (gold 8.672/8.674 acc, sys 8.684/8.685, +11): D -> vowel-initial 'out', loudness rises -13 -> -3 over 8.660-
  8.678; separator .67-.96 8.666-8.678. minor.
- out.end (gold 8.904 acc, sys 8.854, -50): /T/ strongly fricated release 8.824-8.854 (cent 8.1, zcr .41-.45, -10..-23),
  decays -33 -> -45 (8.860-8.878); NEW onset trn 2.9/3.0 at 8.884-8.896 -> noise -29..-33 (cent 6.8-7.6, per .11-.27) =
  breath. Principled end = the dip 8.878 between release and breath (gold +26 into the breath, system -24 inside the
  release). The release must be kept (class F); the breath (separate onset) excluded.
- that.start (9.120/9.123 both): /DH/ burst trn 19.5 at 9.126 after silence. ok.
- that|they (gold 9.256/9.259 acc; sys 9.232 end, pause, 9.272 start): vowel -5 -> -31 (9.232); weak voiced segment 9.238-
  9.262 (-34..-39, per .36-.57, cent 5.8-6.2 = voicing into the unreleased /T/ closure); silence -45 at 9.268; /DH/ burst
  trn 15.5 at 9.274. Gold = end of the voiced segment (it belongs to 'that'); system cut at -31 and paused. Class D.
- they|would (gold 9.448/9.450 acc, sys 9.394/9.397, -53): EY->W voiced continuous; separator plateau 1.00 9.394-9.418,
  blank 9.424-9.436, hi minimum -55.8 (W constriction) at 9.430-9.436, CTC 'W' 9.442-9.454. Gold = CTC 'W' onset (12 ms
  after the constriction max); system = separator plateau START, 50 ms early. => for V->glide joins the next word's first
  letter onset / constriction landmark beats the separator (b|you, know|needs, many|years, now|he's again).
- would|not (9.628-9.633 both): /D/ closure -34..-41 9.604-9.622, release trn 11.9 at 9.622, N onset 9.634. ok.
- not|be (gold 9.844/9.850 acc; sys 9.820 end, pause, 9.880 start): vowel decays to -42 (9.820); silence -46..-54 9.826-9.874
  (unreleased /T/ + /B/ closure); /B/ burst trn 7.3/15.5 at 9.874-9.880. Gold split the 55 ms closure mid-way (like
  like|the acc, it|says HUMAN); system made it a pause (-28/+30).
- be|able (gold 10.032/10.035 acc, sys 9.990/9.993, -42): IY -> EY; separator 1.00 9.996-10.008; loudness dip -10 -> -29
  (10.032) with per .32 at 10.026 and trn 2.8/5.3 at 10.032-10.038 = GLOTTAL STOP before vowel-initial 'able'. Gold at the
  dip bottom; system at the separator start, 40 ms early. Class E.
- able|to (gold 10.348/10.352 acc, sys 10.348 end / 10.382 start, +30): L decays -8 -> -29 (10.348) -> -34 (10.354);
  transients 6.7/5.4 at 10.360-10.366, dip -37 at 10.378, /T/ burst trn 13.2 at 10.378, frication to 10.408. Gold starts
  'to' at the closure start; system after the burst (again start-after-burst).
- to|do (gold 10.500/10.502 acc; sys 10.516 end / 10.548 start, +46): UW to 10.506 (-17); decay -23 -> -37 (10.530) -> -42
  (10.542); /D/ burst trn 9.0-10.6 at 10.542-10.548. Gold at the separator plateau start (1.00 10.494-10.512), i.e. the
  UW decay + closure go to 'do'; system started after the burst. (start-after-burst again.)
- do.end / what.start (10.822-10.828 / 10.942-10.946 both). ok.
- what.end (gold 11.149 acc, sys 11.136, -13): -13 (11.124) -> -26 (11.136) -> -41 (11.148). minor.  is.start (11.202). ok.
- is|necessary (gold 11.374/11.377 acc, sys 11.386/11.387, +10): voiced /Z/ -> N: cent 7.9 -> 5.2, hi -13.8 -> -35.5 over
  11.374-11.392. Gold at the start of the transition, system mid. minor.
- necessary|in (gold 12.158/12.160 acc, sys 12.176/12.181, +20): creaky IY -> IH (per .17-.39, glo 17.5-20.8); dips -24 at
  12.140 and -27 at 12.182; glottal pulses trn 4.7/3.9/3.4/5.8 at 12.146/12.164/12.188/12.194; separator 1.00 to 12.152,
  .73 at 12.158. Gold between the dips at the separator's fall; system at the 2nd dip. Creaky-region scatter.
- in|haiti (gold 12.330/12.333 acc, sys 12.341/12.343, +10): separator plateau 1.00 12.312-12.330, voiced /h/ (per .66),
  hi -26 -> -21.8 at 12.336. minor.
- haiti.end (gold 12.814 acc, sys 12.932, +118): IY decays -12 -> -25 (12.816) -> -40 (12.832); new onset trn 6.7/5.0 at
  12.840-12.856 -> noise -27..-33 (cent 7.2-7.9, per .16-.32) = breath. System included it. Class B.
- that.start (gold 13.073 acc, sys 13.046, -27): breath tail to ~13.03; low periodic murmur at floor (-46..-52, per .30-.46,
  cent 4.8-5.5) 13.040-13.064; minimum -57 at 13.070; /DH/ burst trn 19.5 at 13.076. System started in the floor murmur;
  should snap to the burst. (pre-voicing/hum excluded, class I.)
- that|it (13.196-13.201 both): separator .83-.97. ok.
- it|is (gold 13.314/13.317 acc, sys 13.325/13.327, +10): flap T; separator .62 (13.314) -> .99 (13.332). minor.
- is|only (gold 13.439/13.441 acc, sys 13.498/13.503, +62): /Z/ (zcr .67-.82) to 13.432; voicing from 13.438-13.444 with
  glottal pulses (per .31-.70, glo up to 20.0, trn 8.3 at 13.474); dip -26 at 13.492; trn 6.1 at 13.504 and modal vowel
  -12 from 13.504. Separator 1.00 13.456-13.468. Gold = start of the glottalised onset (= fricative end); system = end of the
  glottal stop (modal-voicing onset). Same as people|over (HUMAN): the creaky/glottal onset belongs to the vowel-initial
  word; boundary at its START (after a vowel: the loudness minimum before it, you|every).
- only|a (gold 13.752/13.755 acc, sys 13.788/13.791, +36): IY -> AH; separator .48 (13.752) -> 1.00 (13.776-13.788) -> .63
  (13.800); hi -24 -> -20 (13.758) -> -31 (13.800); CTC 'A' 13.800-13.818. Gold at the separator leading edge; system at the
  trailing edge (= next word's CTC letter). No sharp acoustic landmark; scatter.
- a|force (a.end 13.810 acc / force.start 13.811 HUMAN; sys 13.868 / 13.892, +58/+81): AH voiced to 13.816; F onset 13.822
  (hi -19.3, fvel 2.1) -> 13.834 (cent 7.4, per .33) -> 13.840 (cent 7.8, per .15, zcr .30); separator 1.00 13.834-13.852.
  Human at the vowel end just before the F; system 50-70 ms inside the F. fricative-lag class, human-moved (8th).
- force|like (gold 14.226/14.232 acc, sys 14.220/14.223): /S/ to 14.220, L onset 14.238 (cent 6.1, lo -0.5, per .42). ok.
- like|the (gold 14.398/14.400 acc; sys 14.386 / 14.424): /K/ closure -32..-42 14.380-14.416; fricated /DH/ 14.416-14.440
  (trn 3.6 at 14.422, cent 7.0-7.8); vowel 14.446. Gold mid-closure (accepted mid-closure convention again); system started
  'the' 8 ms after the DH onset. minor.
- the|u (gold 14.532/14.535 acc, sys 14.538/14.541): separator .97-.99 14.514-14.532. ok.
- u|s (gold 14.691 HUMAN both, sys 14.764/14.765, +73): letter-name 'u' (Y UW) then 's' (EH S). Separator 1.00 14.678-14.690;
  lo -8.4 at 14.690 then back up; hi -42.8 (14.690) -> -32.8 (14.702) -> -17.2 (14.732) = UW -> EH formant change starting
  14.690; /S/ frication only from 14.780. Human = separator end / start of the EH transition; system put the EH vowel into
  'u' and cut just before the /S/. Letter-name vowel class (known): the letter 's' owns its /EH/.
- s|military (gold 14.878/14.883 acc; sys 14.848 / 14.890): /S/ decays -16 -> -38 (14.848) -> -53 (14.872-14.878 floor); M
  onset -47 (14.884) -> -31 (14.890). Gold ends the fricative at the floor (class G); system at -38 re p99 (-33).
- military|that (gold 15.392/15.399 acc, sys 15.368/15.371, -28): IY -10 (15.374) -> -21 (15.392) -> -30 (15.398); /DH/
  trn 5.0 at 15.404; separator .98-1.00 15.374-15.398. Gold at the DH onset; system at the separator leading edge while
  the vowel is still at -10. separator-edge class.
- that|will (gold 15.556/15.561 acc, sys 15.538/15.541, -19): vowel -10 -> -36 (15.526) = short /T/ closure; W onset 15.532
  (-17, hi -46, per .39); separator .47-.93 15.532-15.550, CTC 'W' 15.562. System at the acoustic W onset; gold 25 ms later
  at CTC 'W'. accepted gold late; minor.
- will|be (gold 15.750/15.753 acc, sys 15.738/15.741, -12): L decays -13 -> -29 (15.738) -> -34 (15.744 closure); /B/ burst
  trn 17.7 at 15.750. Gold at the burst, system at the closure start. minor.
- be|able #2 (gold 15.869/15.871 acc, sys 16.012, +143): 'be' IY to ~15.854 (-6); glottal attack trn 10.2 + cent 6.9 at
  15.870; separator .47 -> 1.00 15.862-15.894; then a CREAKY weak stretch 15.878-15.966 (-12..-16, per .23-.75) before the
  loud EY 15.974-16.13 (CTC 'A' only at 16.048-16.098; 'B' 16.208-16.218; 'L' 16.268). Gold = glottal attack + separator;
  system cut 36 ms before CTC 'A', giving the creaky onset to 'be' (be = 270 ms). => the next-word-first-letter estimator
  FAILS when a vowel-initial word starts with creak; the separator + glottal attack are the evidence. (Opposite of
  they|would where the letter onset was right and the separator wrong - the acoustic landmark type must decide.)
- able.end (16.442-16.446 both), to.start (16.956/16.962, burst trn 18.4 at 16.956). ok.
- to|overtake (to.end 17.236 acc / overtake.start 17.279 acc; sys 17.238 / 17.286): to decays -9 -> -21 (17.236) -> weak
  -31..-41 (per .16-.53); overtake glottal attack trn 8.9 at 17.284. ok.
- overtake.end (gold 18.112 HUMAN, sys 18.076, -36): /K/ release+aspiration 18.046-18.070 (cent 7.6-8.1, zcr .27-.43, -21..
  -24), decay -27 -> -36 (18.076-18.106), -41 (18.112), floor -46 (18.118). Human keeps the aspiration decay to the floor;
  system cut at -27. Class F (released stop keeps its aspiration), human-moved.
- uh.start (gold 18.421 HUMAN, sys 18.430, +9): floor, glottal attack trn 22.9 at 18.432. minor.
- uh|the (uh.end 18.694 HUMAN, the.start 18.695 acc; sys 18.640/18.642, -52): 'uh' -12 to 18.634; weakening voiced tail -15
  .. -38 (18.640-18.688, per .11-.56); /DH/ realised as a stop: burst trn 14.8 at 18.694; vowel 18.718. Separator 18.634-
  18.664 (peak .76 at 18.652). Human kept the weak voiced tail in 'uh' and started 'the' at the burst; system at the
  separator 50 ms early. Class D (voiced tail) + stop-onset at the burst.
- the|gangs (18.776-18.784 both): closure -31..-33, /G/ burst trn 4.7/14.0 at 18.782-18.788. ok.
- gangs|that (gold 19.122/19.127 acc, sys 19.080/19.082, -43): /Z/ frication 19.068-19.110 (cent 6.8-8.6, zcr up to .66,
  loudness -15 -> -28); fricated /DH/ plateau -31..-33 from 19.116 (cent drops 8.6 -> 7.9 at 19.122); CTC 'S' 19.050-19.074,
  separator 19.080-19.122 (peak .97 at 19.092), 'T'(DH) 19.122. Here the separator starts EARLY, right after CTC 'S', and
  covers the rest of the /Z/; system cut at its leading edge, giving the Z to 'that'. Gold at the Z->DH change. => a
  word-final fricative runs through the separator; cut at the fricative's end / next phone onset.
- that|are (gold 19.220/19.223 acc, sys 19.232/19.235, +12): T -> vowel-initial 'are'; loudness min -11/-10 at 19.220-
  19.226 (trn 1.8), vowel from 19.232. Gold at the minimum (class E). minor.
- are|there (19.366-19.370 both): /DH/ burst trn 20.0 at 19.376. ok.
- there|and (gold 19.638/19.641 acc, sys 19.656/19.660, +20): R -10 -> -17 (19.632-19.644) -> -27 (19.656) -> -33 dip
  (19.662) -> glottal attack trn 3.8/3.5 at 19.668-19.674. System at the dip (class E); gold 22 ms earlier at the
  separator's fall. accepted gold early.
- and|restore (gold 19.818/19.820 acc, sys 19.800/19.802, -18): voiced; separator plateau .93-1.00 19.794-19.812, CTC 'R'
  19.842. Gold at the separator fall, system at the plateau. minor.
- restore|law (gold 20.252/20.253 acc, sys 20.222/20.224, -29): R->L, separator plateau 1.00 20.216-20.252; hi minimum
  -52.4 (L constriction) at 20.246; CTC 'L' 20.264. Gold = constriction max / plateau end; system = plateau start.
- law|and (gold 20.488/20.493 acc, sys 20.440/20.442, -48): 'law' vowel to 20.428; creaky stretch 20.434-20.488 (per .15-.35,
  glottal pulses trn 11.3/11.4 at 20.446/20.470, dips -27/-31/-36 at 20.440/20.464/20.488); 'and' vowel from 20.500 (CTC
  'A'). Gold gives the creak to 'law' (last dip); system gives it to 'and' (first dip) = the human-moved convention
  (people|over, you|every). Accepted-gold scatter on creak ownership (blah|and#2 and is|only accepted golds side with the
  system/human convention).
- and|order (gold 20.594/20.596 acc, sys 20.612/20.616, +20): voiced; separator plateau 1.00 20.594-20.612; gold at the
  plateau start, system at the end. scatter.
- order.end (gold 20.950 acc, sys 20.940): ER decays -22 -> -28 (20.946), clip end. ok.

### 009-7 summary (73 tokens, all boundaries read)
Large system errors by class (H = human-moved):
 * Breaths / separate noise events included: week.end +168 (H, exhale after the K release, separate onset), haiti.end +118,
   out.end -50 (end cut inside the T release; gold ran into the breath).
 * Creaky / glottal onsets of vowel-initial words: people|over +96 (H), is|only +62, be|able#2 +143 (creaky onset given to
   'be', system cut near CTC 'A'), be|able#1 -42 (glottal dip); law|and -48 (accepted gold gives creak to 'law').
 * Fricative/affricate lag: i've|spoken +42 (H, CTC spelled an 'E' inside /S/), a|force +58/+81 (H), were|just +24;
   opposite direction: gangs|that -43 (separator starts right after CTC 'S', Z given to next word).
 * Separator-edge vs landmark: they|would -53 (letter onset right), restore|law -29, military|that -28, only|a +36,
   there|was +23, and|benin +30; letter-name u|s +73 (H).
 * Voiced decay tails / short gaps cut as pauses: uh|the -52 (H), that|they, the|kenyan, not|be (mid-closure), uh.end -19
   (H), overtake.end -36 (H, aspiration), s|military -33 (fricative to floor), uh|and (H: 60 ms floor gap split, no pause).
 * Stop-initial words started AFTER the burst: to|people +28, the|kenyan +39, able|to +30, to|do +46 (gold: at/before burst).
 * Merged cross-word fricatives: was|some -44 (gold splits at separator/lo max), just|saying -21.

## 009-9 DEEP READ
- what.start (gold 0.151 acc, sys 0.322, +171): floor -56..-59 to 0.128; attack trn 14.4 at 0.152 (-28) then 150 ms of
  low voiced sonorant 0.160-0.300 (per .62-.75, cent 5.3-5.8, hi -37..-47, lo -0.2..-1.2, rising -22 -> -13) = a long /W/
  onset; CTC 'W' only at 0.304-0.312, vowel -7 at 0.320. Gold starts at the attack; system at CTC 'W' / vowel rise.
  => a voiced sonorant stretch contiguous with a sonorant-initial word (W/M/N/L/R/Y) belongs to it from its attack.
- what|they're (gold 0.476/0.481; sys 0.464 end, pause, 0.502 start): /T/ 0.434-0.458 (cent 7.1-7.4, lo -11); drop -25 at
  0.464; /DH/ voiced closure 0.470-0.512 (-25..-31, per .26-.65); DH release hi -23.6 at 0.518, trn 3.5/6.0 at 0.524-0.530.
  Separator peak .98 at 0.476 (gold). System made the 40 ms DH closure a pause. Class D/I (short gap not a pause).
- they're|thinking (gold 0.680/0.683, thinking.start HUMAN; sys 0.692 end, pause, 0.744 start, +61): R decays -15 -> -32
  (0.680); /TH/ onset 0.680-0.686 (cent 6.7 -> 7.5, hi -13 -> -6.3, zcr .15 -> .23), weak TH -28..-34 to 0.740; CTC 'T'
  0.740-0.758; vowel 0.758. Human = TH onset; system turned the whole /TH/ into a pause. Class A (weak initial fricative).
- thinking|in (1.080/1.081 HUMAN start, sys 1.086/1.087): separator .79-.96. ok.
- in|that (1.208-1.212 both): separator .92-.99, DH release 1.220-1.238. ok.
- that|room (gold 1.384/1.386, sys 1.392/1.393): separator 1.00 at 1.394. ok.
- room|and (gold 1.634/1.636, sys 1.642/1.643): M->AE, separator .96 at 1.632, lo -4.6 -> -13.9 at 1.632-1.644, trn 3.2. ok.
- and|again (gold 1.756/1.759 acc, sys 1.774/1.778, +20): loudness min -14 at 1.744-1.756, attack trn 4.1 at 1.762, -8 at
  1.774; separator .39 -> .96 (1.762-1.792). Gold at the loudness minimum (class E); system at the separator. minor.
- again.end (gold 2.079 acc, sys 2.052, -27): /N/ murmur -19 -> -25 (2.046-2.064, per .48-.54) -> -30 (2.076) -> -38
  (2.094). Gold keeps the nasal decay to -30; system cut at -25. Class D (nasal murmur tail).
- if.start (2.482/2.486 both): weak attack trn 5.5 at 2.464, trn 6.6 at 2.488. ok.
- if|you (gold 2.590/2.593 acc, sys 2.602/2.605, +12): /F/ 2.566-2.602 (cent 7.2-8.3, zcr up to .57), Y onset 2.608 (per
  .25 -> .49, hi -7 -> -19); separator peak .98 at 2.596. System at the F->Y change; gold 12 ms inside the F. minor.
- you|really (gold 2.718/2.721 acc, sys 2.754/2.755, +34): UW -5 -> -8 (2.718, end of CTC 'U') -> -11 (2.736-2.748) ->
  -16 (2.760-2.766 minimum) -> -14; hi -36 -> -23 (2.766); separator .52-.93 at 2.742-2.754. No clear landmark (UW->R); gold
  at the start of the decline, system at the separator peak, loudness minimum 2.766. scatter.
- really|do (3.002-3.009 both): voiced /D/ closure 3.008-3.026, burst trn 7.8 at 3.032. ok.
- do|think (gold 3.202/3.204 acc; sys 3.170 end / 3.212 start): 'do' decays -8 -> -28 (3.170) -> -32 (3.188) -> -34; weak
  /TH/ from ~3.186 (hi -18.5 -> -9.9), strong from 3.200 (trn 3.4, cent 7.6, hi -5.5); CTC 'T' 3.200-3.218; vowel 3.230.
  Gold keeps the decay (and the weak TH start) in 'do' to the strong TH onset; system cut at -28 (-32) and started +8.
- think|that (3.372-3.379 both): separator .98 at 3.372, DH frication from 3.384. ok.
- that|oregon's (gold 3.480/3.483 acc, sys 3.516/3.517, +34): 'that' -7 -> -16 (3.468-3.486, loudness minimum), -13
  (3.492), -8, -6 = 'oregon's' vowel; separator .54-.88 3.486-3.516. Gold at the loudness minimum before the vowel-initial
  word (class E); system at the separator's trailing edge with the vowel already at -6.
- oregon's|gonna (oregon's.end 3.867 acc / gonna.start 3.869 HUMAN; sys 3.852/3.855, -14): /Z/ (zcr .38-.54) to ~3.852;
  voiced /G/ closure 3.858-3.870 (per .54, cent 5.6); burst trn 3.2/4.0/6.6 at 3.870-3.882. Human started 'gonna' at the
  burst (closure to 'oregon's'); system at the Z end. minor.
- gonna|beat (gold 4.068/4.070, beat.start HUMAN; sys 4.056/4.058, -12): vowel -20 to 4.050, -24 (4.068), voiced /B/ closure
  4.074-4.086 (per .59 -> .21), burst trn 11.1/15.9 at 4.092-4.098. HUMAN start at the closure start (22 ms before the
  burst). With platinum (human, just before the burst): human stop onsets lie inside the closure, never after the burst.
- beat|washington (4.228-4.234 both): separator .77-1.00, hi -41 -> -45. ok.
- washington|that's (gold 4.644/4.646 acc, sys 4.655/4.656, +10): N decays -16 -> -23; DH: hi jump -18 + trn 2.5 at 4.656,
  release trn 9.6 at 4.668. minor.
- that's|fine (gold 4.880/4.883 acc; sys 4.840 end / 4.896 start): loud /S/ (-17..-24, cent 8.4-8.5) to 4.838; weak
  frication 4.844-4.910 (-30..-39, cent 7.9-8.4, lo -15..-22) = /F/; separator 1.00 4.856, CTC 'F' .43 at 4.880, 1.00 at
  4.904-4.916; vowel 4.916. Principled: S->F at the level drop 4.841 (= system end). Gold (accepted) at CTC 'F' onset,
  40 ms into the weak F; system's start (4.896) excludes most of the F (weak-initial-fricative class A).
- fine.end (gold 5.180 acc, sys 5.166, -14): N -23 -> -29 (5.178) -> -37 (5.190). minor.
- but.start (gold 5.809 acc, sys 5.796, -13): silence -55..-62; /B/ burst trn 17.8 at 5.808 (CTC 'B' at 5.784-5.796 PRECEDES
  the burst). System 12 ms early in silence; snap to the burst.
- but|put (gold 5.920/5.924 acc; sys 5.908 / 5.956): 'but' decays -22 -> -30 (5.920) -> -36 -> -42 (5.950); /P/ burst trn
  10.5 at 5.956. Gold starts 'put' at the closure start, system at the burst (+34). stop-onset convention.
- put|em (gold 6.074/6.077 HUMAN, sys 6.080/6.085): separator .98 at 6.074 (T flapped, loud). ok.
- em|at (6.176-6.180 both): M -> AE, glottal trn 4.4 at 6.176, separator .77-.93. ok.
- at|number (gold 6.258/6.259 HUMAN, sys 6.282, +23): flapped T dip -18 at 6.240; N murmur established by 6.252-6.258 (per
  .80, hi -32.3 -> -32.9, lo -0.6); separator .28 (6.258) -> 1.00 (6.282). Human at the N murmur onset; system at the
  separator's far edge, 25 ms into the N (a|million pattern).
- number|eight (gold 6.558/6.560 HUMAN, sys 6.546/6.548, -12): separator .83-.99 6.540-6.552; per .71 -> .33 (6.558-6.570)
  with glottal trn 3.6/3.1 at 6.564-6.570 (glottalised onset of 'eight'). Human at the glottalisation onset, system at the
  separator's leading half. minor.
- eight|and (gold 6.701/6.703 acc, sys 6.724/6.726, +23): EY -5 -> -14 (6.700) -> -20 (6.712-6.724 closure, lo -1.8..-4.9) ->
  glottal attack trn 3.1/4.2 at 6.724-6.730 -> -8. Gold at the start of the dip, system at its end (the attack). Principled
  mid-closure ~6.715 (it|says convention); both +-12.
- and|when (6.806-6.814 both): separator .97 at 6.812. ok.
- when|they (gold 6.944/6.947 HUMAN, sys 6.932/6.934, -12): separator 1.00 at 6.932; DH release hi -28 -> -19 + trn 6.5 +
  glo 22.1 at 6.944-6.950. Human at the release, 12 ms after the separator peak.
- they|win (gold 7.082/7.089 acc, sys 7.064/7.066, -21): EY->W; hi minimum -42.4 at 7.070; separator plateau 1.00 7.076-7.088;
  CTC 'W' 7.100. Gold at the plateau end (between constriction max and CTC letter); system at the separator rise.
- win|put (gold 7.316/7.320 acc, sys 7.286/7.288, -30): /N/ decays -12 -> -16 (7.286) -> -23 (7.304) -> -27 (7.316);
  /P/ closure -31..-33 7.322-7.334; burst trn 6.8 at 7.340. Gold at the end of the nasal decay; system at the separator's
  leading edge while N is at -16. Class D (nasal tail).
- put|em (7.456-7.459 both). ok.
- em|up (em.end 7.549 HUMAN / up.start 7.551 acc; sys 7.568/7.569, +18): M (per .72) to 7.536; per .50 + glottal attack trn
  1.9/5.6 glo 19.9 at 7.548-7.554; -11 -> -3. Human at the glottal attack onset (class E); system mid separator rise.
- up|at (gold 7.684/7.685 HUMAN both; sys 7.702, +17): 'up' decays -24 -> -33 (7.684); /P/ burst trn 8.4 at 7.690; release
  noise 7.696-7.708; 'at' vowel from ~7.714-7.720 (CTC 'A' 7.720). HUMAN put the boundary just BEFORE the /P/ burst, i.e.
  the release goes to vowel-initial 'at' (resyllabified "u-pat"). Contrast it|he (human: release stays with 'it' when the
  next word starts with /h/). Possible liaison rule: final stop + vowel-initial word -> release to the next word. (1 case)
- at|number (gold 7.766/7.768 HUMAN, sys 7.796/7.798, +30): weak 'at' (-24..-27); CTC 'T' 7.742-7.754; /T/ burst trn 16.0 at
  7.760; then rise -20 -> -4 (7.766-7.796) with lo -2..-8 (weak N); separator .52-.95 at 7.784-7.814. Human 6 ms after the
  burst (release to 'at'); system at the separator peak, 30 ms later.
- number|four (gold 8.018/8.020 HUMAN, sys 8.012 / 8.044, +24 on start): ER decays -7 -> -29 (8.018); /F/ onset 8.015-8.020
  (cent 6.8 -> 8.0, hi -11.8 -> -4.4, zcr .17 -> .46); separator peak .92 at 8.036. Human at the F onset; system started
  'four' at the separator's trailing half, 24 ms inside the F. fricative-lag class (9th, human).
- four.end (8.238-8.242 both); like.start (gold 8.272 acc, sys 8.280): L onset per .51 at 8.274, trn 3.9 at 8.280. ok.
- like.end (8.496-8.498 both): K-release noise 8.502-8.520 excluded by both. ok.
- it-.start (9.114-9.118 both, burst trn 14.9). it-.end (gold 9.242 HUMAN, sys 9.228, -14): voiced decay -22 -> -26 (9.222)
  -> -35 -> -41 (9.238) -> -47 (9.246). Human at -41 re p99 (class D: voiced tail kept to ~-40/-45).
- hum 9.262-9.320 (per .5-.7, -43..-51) between 'it-' and 'it's' excluded by both. good.
- it's.start (gold 9.347 acc, sys 9.352): weak onset trn 5.9 at 9.334, burst trn 14.6 at 9.350. ok.
- it's|fine (it's.end 9.585 acc / fine.start 9.585 HUMAN; sys 9.574 / 9.740, +155): strong /S/ (-15..-24, cent 8.5, lo
  -25..-39) to 9.574; then 170 ms of WEAK frication 9.580-9.754 (-26..-42, cent 7.8-8.3, zcr .30-.50, lo -13..-28) = a
  prolonged /F/; CTC 'F' only at 9.722-9.754; vowel -6 at 9.762. Human started 'fine' right after the strong S (the whole
  weak F belongs to 'fine'); system started at CTC 'F' and left a 165 ms pause. Class A (weak initial fricative), human.
- fine.end (gold 10.275 acc, sys 10.264, -11): N -19 -> -25 (10.264) -> -31 (10.276) -> -38. minor.
- if.start (gold 10.483 acc, sys 10.488): glottal attack trn 9.6 at 10.470 (-48), 11.6 at 10.488 (-19). ok.
- if|you (if.end 10.738 HUMAN / you.start 10.739 HUMAN; sys 10.672 end, pause, 10.732 start): CTC 'F' 10.642-10.654 during
  the IH->F transition; weak /F/ frication 10.678-10.728 (cent 7.5-8.3, zcr .32-.48, -24..-30); /Y/ onset 10.732 (per .26
  -> .43). System ended 'if' BEFORE its own final F (-66) and made the F a pause; human keeps the F in 'if' up to the Y
  onset. Class A mirror: a weak word-FINAL fricative is not a pause either.
- you|want (gold 10.968/10.972 acc, sys 10.956/10.959, -13): separator .98 at 10.974, hi minimum -43.4 at 10.980. minor.
- want|to (want.end 11.178 acc / to.start 11.180 acc; sys 11.190/11.193, +13): N/T decays -19 -> -31 (11.178) -> -38;
  /T/ burst trn 11.9-12.0 at 11.190-11.196. Gold at the closure start, system at the burst. minor.
- to|reward (11.298-11.301 both), reward|them (gold 11.784/11.788, sys 11.778/11.780; DH release trn 13.1 at 11.808). ok.
- them|for (them.end 11.955 HUMAN / for.start 11.956 HUMAN; sys 11.968 / 12.062, +106): M (per .65) to 11.940; 11.948-11.956
  -15 -> -22, per .30; trn 5.7 at 11.964; weak /F/ 11.965-12.080 (cent 7.0-8.2, zcr .20-.47, -24..-35); CTC 'F' only at
  12.044-12.076; vowel 12.084. Human starts 'for' at the F onset; system at CTC 'F' with a 94 ms pause over the F. Class A
  (human, weak initial F).
- for|getting (gold 12.290/12.296 acc, sys 12.254/12.257, -39): R -1 -> -8 (12.254) -> -19 (12.284-12.290, per .47-.56 still
  R); voiced /G/ closure 12.290-12.314 (per .6-.69, hi -42..-49); burst trn 17.2 at 12.320. Gold at the closure start;
  system at the separator's leading edge 35 ms into the R. separator-edge class.
- getting|that (12.590-12.595 both), that|win (12.804-12.809 both): separators 1.00. ok.
- win.end (13.240-13.246 both): N -21 -> -29 -> -38; weak hum/breath -38..-43 13.258-13.322 excluded by both. when.start
  (13.377/13.382 both, W onset -36 at 13.370). ok.
- when|they (gold 13.642/13.644 acc, sys 13.630/13.633, -11): separator peak 1.00 at 13.630, hi min -32.3 at 13.648, CTC
  'T'(DH) 13.660. minor.
- they|get (gold 13.792/13.799 acc, sys 13.792 / 13.828, +29 on start): EY decays -8 -> -23 (13.792); voiced /G/ closure
  13.804-13.822 (per .58 -> .37); burst trn 9.5 at 13.834. Gold starts 'get' at the closure start; system just before the
  burst. stop-onset convention (both are inside the closure-to-burst span).
- get|the (gold 13.990/13.996 acc; sys 13.966 end / 14.006 start): vowel -9 -> -27 (13.954); /T/ closure/weak release noise
  -29..-37 (13.960-13.996, cent 7.0-7.5); /DH/ voicing 14.002 (per .48, lo -1.8); CTC 'T'(DH) 14.020. Gold keeps the T
  closure/noise in 'get' up to the DH voicing; system cut at -32 and left a 40 ms gap. Class D/F.
- the|win (gold 14.132/14.134 HUMAN, sys 14.120/14.123, -12): separator .38 (14.120) -> .97 (14.132). Human at the peak.
- win|but (gold 14.460/14.464 acc, sys 14.454 / 14.478): N murmur and voiced /B/ closure indistinguishable (per .5-.67, hi
  -38..-45); separator falls .61 (14.460) -> .02 (14.472); CTC 'B' 14.484. minor.
- but|it's (gold 14.574/14.577 acc, sys 14.592/14.593, +17): /T/ dip -15/-13 at 14.568-14.574 (per .13); glottal attack trn
  4.9 at 14.580; vowel -4 from 14.586. Gold at the dip (class E); system at the separator peak .97. minor.
- it's|like (14.754-14.761 both): /S/ to 14.754, L onset 14.760. ok.
- like|they (gold 14.926/14.931 acc; sys 14.908 / 14.948): decay -26 -> -35 (14.926) -> floor -38/-39 (14.932-14.950);
  /DH/ burst trn 13.8 at 14.962. Gold mid-closure; system: gap 14.908-14.948. class D/I.
- they|b- (they.end 15.126 acc / b-.start 15.143 HUMAN; sys 15.062 / 15.063, -64/-81): 'they' EY -4 -> -18 (15.060) then a
  decaying voiced tail -19..-32 (15.066-15.138, per .45-.68, cent 5.4-5.8); CTC reads it as "'VE" (apostrophe 15.042, 'V'
  .74 15.060-15.078, 'E' .77 15.084-15.096 - the speaker's "they've"), separator 15.102-15.138; the fragment 'b-' = burst
  trn 6.7 at 15.150 (-36 -> -22) + ~45 ms voicing to 15.196. Human: tail stays with 'they', 'b-' starts just before its
  burst. System anchored 'b-' on the CTC 'V' (15.063) and gave it the tail of 'they'. => a fragment starting with a stop
  must sit on a closure+burst; don't map it onto letters of an unrelated voiced tail.
- b-|it (b-.end 15.192 HUMAN / it.start 15.197 HUMAN; sys 15.146/15.147, -51): 'b-' voiced 15.150-15.180 (per .39-.73); dip
  -29 at 15.186-15.192 with glottal trn 3.7/2.5; 'it' rises -26 -> -11 (15.198-15.216). Human at the dip before the
  glottal attack of 'it' (class E). System misplaced because 'b-' was anchored on the CTC 'V' of 'they'.
- it|seems (gold 15.274/15.276 acc, sys 15.298/15.303, +27): IH -7 -> -20 (15.274); /S/ onset 15.278-15.280 (cent 7.4, hi
  -6.4, zcr .30). Separator only from 15.298. Gold at the S onset; system 20 ms inside. fricative-lag class.
- seems|like (gold 15.560/15.562 acc, sys 15.566/15.571): /Z/ to 15.560, L onset 15.566. ok.
- like|they've (gold 15.696/15.698 acc, sys 15.708/15.713, +14): decay -24 -> -31 (15.696); voiced closure -32 15.702-15.720;
  DH release trn 5.8/5.9 at 15.726-15.732. Gold at the closure start, system mid-closure. minor.
- they've|been (gold 15.897/15.899 acc, sys 15.866/15.869, -30): V/E region -20 -> -25 (15.860); voiced /B/ closure -27/-28
  15.872-15.890; burst trn 11.1 at 15.896. Gold at the burst (closure to 'they've'); system at the separator's rise.
- been|rewarding (16.046-16.052 both): separator plateau 1.00. ok.
- rewarding|them (gold 16.664/16.665 acc, sys 16.646/16.648, -17): separator 1.00 at 16.634, plateau to 16.658; DH release
  per .78 -> .57, hi -38.7 -> -24.1 at 16.670-16.676; CTC 'T'(DH) 16.664. Gold at the release / CTC letter; system in the
  plateau. separator-edge class.
- them.end (16.908-16.915 both): M decays -19 -> -34; voiced low tail -34..-37 16.920-16.938 excluded by both. ok.
- because.start (17.338-17.342 both, burst trn 13.9). ok.
- because|they (gold 17.683/17.685 acc; sys 17.644 end / 17.690 start): /Z/ frication (cent 7.6, zcr .18-.31) to 17.632;
  voiced murmur 17.644-17.692 (per .58-.68, cent 5.1-6.0, lo ~0, -23..-28 = Z voicing + DH voiced closure); DH release trn
  10.4 at 17.698. Gold 15 ms before the release; system cut at the frication end and left a 46 ms gap. Class D/I.
- they.end (17.836-17.839 both). think.start (gold 18.031 acc, sys 18.010, -21): weak noise -38..-40 (cent 8.0-8.2) to
  18.004; trn 3.5 at 18.010 (-33) = /TH/ onset; CTC 'T' 18.004-18.040; vowel 18.052. System at the TH onset, gold 20 ms later.
  accepted gold late; minor.
- think|they're (think.end 18.214 acc / they're.start 18.329 HUMAN; sys 18.206 / 18.238, -91): /K/ decay -15 -> -31
  (18.182-18.214); strong burst trn 17.2 at 18.238 (-19, cent 8.3); aperiodic noise 18.246-18.326 (-16..-32, cent 7.6-8.3,
  zcr .35-.52, per .07-.17); CTC 'T','H' 18.286-18.326; voicing/vowel 18.334+. HUMAN left the burst + 90 ms noise in NO
  word and started 'they're' at the voicing. System started 'they're' at the burst (the burst cannot start a DH-word).
  Contrast week.end (human kept the K release). Scatter on a long burst+noise between words.
- they're|going (18.472-18.482 both, G burst trn 10.9). going|to (18.702-18.710 both, T burst trn 19.4 at 18.720).
  to|win (18.790-18.800 both, separator 1.00). win|a (18.936-18.944, glottal trn 4.7 at 18.942). ok.
- a|game (gold 19.018/19.021 acc, sys 19.030/19.032, +11): voiced /G/ closure 19.000-19.024 (per .35-.68); burst trn 8.8 at
  19.036. Gold in the closure, system just before the burst. minor.
- game|in (19.220-19.223 both), in|the (gold 19.300/19.302 HUMAN, sys 19.306/19.308; DH release trn 2.9-3.4 at 19.318). ok.
- the|future (gold 19.360/19.361 HUMAN, sys 19.402, +41): AH decays -14 -> -24 (19.360); /F/ onset 19.366-19.378 (cent 5.7
  -> 7.8, hi -22.5 -> -4.7, trn 5.4 at 19.372). Separator .55 at 19.402. Human at the F onset; system 30 ms inside the F.
  fricative-lag class (human, 10th).
- future.end (19.852-19.857 both). ok.

### 009-9 summary (79 tokens, all boundaries read)
 * Weak fricatives cut into pauses (class A, all human-moved): it's|fine +155 (170 ms prolonged F), them|for +106, they're|
   thinking +61 (TH), if|you -66 (word-FINAL F given to a pause), that's|fine (accepted gold also 40 ms into the F).
 * Fricative lag at word-initial fricatives: number|four +24 (H), the|future +41 (H), it|seems +27.
 * Long sonorant onset missed: what.start +171 (150 ms voiced W onset before CTC 'W').
 * Fragment mis-anchored: they|b- -64/-81, b-|it -51 (b- mapped to CTC 'V' of the previous word's tail).
 * Separator edges / consonant landmarks: at|number +30 (H), for|getting -39, they've|been -30, win|put -30 (nasal tail),
   that|oregon's +34 (class E loudness min), em|up +18 (H glottal attack), you|really +34.
 * Voiced tails / short gaps as pauses: what|they're, get|the, like|they, because|they (-39 end), again.end -27.
 * Stop-release assignment scatter: up|at (H: release to vowel-initial next word), at|number (H: release to 'at'),
   think|they're (H: burst + noise in no word).

## 009-10 DEEP READ
- leather.start (0.032/0.038): rise -46 -> -30. ok.
- leather|blazer (leather.end 0.650 acc / blazer.start 0.675 acc; sys 0.644 / 0.682): ER decays -17 -> -33 (0.674);
  /B/ burst trn 15.6 at 0.674. System starts 7 ms after the burst. minor.
- blazer|and (1.326-1.331 both): ER->AE, no separator, lo -8 -> -16 at 1.338-1.344. ok.
- and|like (gold 1.480/1.482 HUMAN, sys 1.486/1.490): separator .99 at 1.474. ok.
- like|lean (gold 1.704/1.705 HUMAN, sys 1.722/1.726, +21): /K/ release noise 1.674-1.692 (cent 7.5, zcr .25-.30); /L/
  onset 1.698 (per .48, cent 6.3); separator .63 (1.704) -> 1.00 (1.716-1.728). Human 6 ms after the L onset; system at the
  separator plateau. separator-edge vs consonant landmark.
- lean|more (2.000-2.009 both), more|matrix (2.200-2.203 both). ok.
- matrix|then (matrix.end 2.739 acc / then.start 2.782 acc; sys 2.728 / 2.776): /S/ (zcr .64-.70) decays -16 -> -35
  (2.758-2.776, still sibilant, zcr .41-.60); trn 3.7 at 2.788; DH release trn 10.2 at 2.806. minor.
- then|you (gold 2.900/2.903 acc, sys 2.930/2.935, +32): N murmur (per .8, lo -0.8..-1.8) throughout; separator .24 (2.900)
  -> .95 (2.930); hi rises -40 -> -24 over 2.936-2.954 (Y); CTC 'Y' 2.960. System at the separator end / hi-rise start;
  gold at the separator's start. No clean landmark; gold likely early.
- you|can (you.end 3.072 / can.start 3.079 acc; sys 3.066/3.069): UW decays -7 -> -22 (3.066-3.072); closure -28; /K/ burst
  trn 8.6 at 3.096. ok.
- can|get (gold 3.240/3.244 acc, sys 3.252/3.253): voiced, separator .83-.99, /G/ release trn 10.2 at 3.258. ok.
- get|little (gold 3.384/3.386 acc, sys 3.402/3.403, +17): vowel decays -12 -> -26 (3.390); L onset 3.396-3.402 (per .65,
  lo -1.3). Gold at the loudness minimum (T closure), system at the L onset. minor.
- little|bite (little.end 3.647 / bite.start 3.702 acc; sys 3.636 / 3.692): L decays -16 -> -28 (3.642); voiced murmur
  -30..-37 (per .5-.77) 3.648-3.696 (L tail + B prevoicing); /B/ burst trn 21.5 at 3.702. Both leave the murmur as a gap;
  system -10/-10. minor.
- bite|sized (gold 3.912/3.915 acc, sys 3.942/3.947, +32): /S/ onset 3.910-3.918 (hi -35 -> -9, cent 6.7 -> 7.3, trn 4.1),
  cent 8.2 zcr .47 at 3.924. Separator .48 at 3.942. Gold at the S onset; system 28 ms inside. fricative-lag class.
- sized|pieces (gold 4.316/4.320 acc; sys 4.298 / 4.362): /Z/ (cent 8.7, zcr .69-.79) to ~4.286; weak voiced/fricated /D/
  4.292-4.346 (-27..-33, per .2-.68); /P/ burst trn 13.1 at 4.358. Gold mid-D; system gap over the D and start after the
  P burst (+42). Class D/I + start-after-burst.
- pieces|of (4.776-4.782 both): /Z/ to 4.770, vowel onset 4.776. ok.
- of|like (gold 4.930/4.935 acc, sys 4.894/4.896, -37): /V/ voiced 4.864-4.924 (per .33-.56, -15..-25, dip -25 at 4.900);
  L onset trn 1.6/6.1 at 4.924-4.930, -13, per .63; separator 4.882-4.936 (peak .84 at 4.912) INSIDE the V; CTC 'L' 4.942.
  Gold at the L onset; system mid-separator in the V. separator-vs-landmark.
- like.end (gold 5.101 acc, sys 5.324, +223): vowel decays -19 -> -28 (5.090-5.100); weak /K/ release trn 2.9 at 5.130; voiced
  low -33..-36 5.140-5.170; -42 at 5.180; new onset trn 5.6 at 5.190 -> noise 5.20-5.35 (-30..-37, cent 7.7-7.9, zcr .28-.36)
  = breath. Gold ends before the K release; system included release + breath. Class B.
- j.start (gold 5.641 acc, sys 5.636): /JH/ burst trn 19.5 at 5.630, frication from 5.636. ok.
- j|crew (gold 5.896/5.898 acc, sys 5.848/5.851, -47): letter 'j' EY to 5.842 (-6); decay -10 -> -18 (5.854); voiced tail
  -17..-24 5.854-5.908 (per .44-.80, EY offglide + voiced K closure); /K/ burst trn 3.6 at 5.914. Gold 16 ms before the
  burst; system cut at the start of the decay (-10 re p99). Class D.
- crew|from (6.176-6.182 both): /F/ onset hi -30 -> -17 + trn 1.9 at 6.176, zcr .21 at 6.188. ok.
- from|that (gold 6.382/6.386 acc, sys 6.376/6.378): separator .94 at 6.370, DH release trn 2.1-2.8 at 6.400-6.406. ok.
- that|era (that.end 6.630 acc / era.start 6.644 acc; sys 6.600 / 6.648): 'that' tail 6.570-6.636 (-16..-30, per .49-.76,
  glottalised T); glottal attack trn 16.0 at 6.648 for 'era'. System ended 'that' at the separator's end (-24) leaving a
  48 ms gap over the voiced tail. Class D.
- era.end (gold 7.355 acc, sys 7.310, -45): AH decays -11 -> -24 (7.310) and stays voiced (per .7-.8) -25..-34 through
  7.382+. Gold at -26; system at -24 re p99 (word-ref threshold). Class D.
- where.start (7.822 both), where.end (8.570-8.574 both), maybe.start (8.812 both). ok.
- maybe|it's (gold 8.998/9.001 HUMAN, sys 9.016/9.019, +18): IY->IH; separator .35 (8.998) -> .89 (9.010) -> .82 (9.016); lo
  -6.5 -> -13.0. Human at the separator's leading half, 12 ms before the peak; system after the peak.
- it's|like (9.134-9.139 both). ok.
- like|a (gold 9.244/9.247 acc, sys 9.268/9.271, +24): /K/ release trn 6.4 at 9.232 (cent 7.7, zcr .23-.30); voicing onset of
  'a' at 9.244 (per .44, lo -1.6), trn 4.4 at 9.250; CTC 'E' until 9.256, separator 9.256-9.292. Gold at the vowel onset
  (release stays with 'like'); system at the lagging separator.
- a|kitten (a.end 9.328 / kitten.start 9.387 acc; sys 9.328 / 9.394): AH decays to -30 (9.328), voiced tail -33..-36 to
  9.358, closure -38..-46, /K/ burst trn 12.4 at 9.388. ok.
- kitten|heel (9.822-9.829 both): N -> voiced /h/ (per .78 -> .64, hi -35 -> -25). ok.
- heel|slingback (gold 10.266/10.268 acc, sys 10.272/10.277): L decays -6 -> -19; /S/ onset 10.266-10.278 (hi -22 -> -5.8,
  trn 2.2-4.2). Separator 1.00 already over 10.236-10.290 (early here). ok.
- slingback|kitten (slingback.end 10.758 / kitten.start 10.808 acc; sys 10.740 / 10.814): weak /K/ closure+noise -22..-30
  10.710-10.758, closure -27..-37 to 10.806, kitten /K/ burst trn 11.9 at 10.812. minor.
- kitten|heel #2 (gold 11.200/11.207 acc, sys 11.188/11.191, -16): N (per .8, hi -42..-53) -> /h/ per .79 -> .48, lo -0.1 ->
  -0.9, cent 5.5 -> 6.5 at 11.212-11.218; CTC 'H' 11.224. Gold nearer the /h/ onset. minor.
- heel|with (gold 11.448/11.450 acc, sys 11.424/11.427, -23): L -> W; separator .14 (11.424) -> .92 (11.454); hi -53 -> -59
  (W constriction) at 11.460; CTC 'W' 11.460. Gold at the separator peak, system at its start. separator-edge.
- with|your (gold 11.590/11.592 acc; sys 11.578 / 11.614): /TH/ frication 11.548-11.578 (cent 6.5-7.9, zcr up to .45, CTC 'H');
  weak low stretch -31..-33 11.578-11.608 (per .33-.51); /Y/ + trn 6.7 at 11.614; vowel 11.632. Separator peak .88 at
  11.590 (gold). System made a 36 ms gap. Class D.
- your|straight (gold 11.692/11.695 acc, sys 11.740/11.743, +48): R (per .67-.83) decays to -15 (11.692); /S/ onset 11.698
  (cent 6.9, hi -21.4, trn 3.6) -> 11.704 (cent 7.5, zcr .26). Separator plateau 1.00 11.734-11.752. Gold at the S onset;
  system 45 ms inside the S. fricative-lag class.
- straight|leg (gold 12.064/12.071 acc, sys 12.058 / 12.082): /T/ weak noise to 12.058, closure -37..-42, L onset 12.082. minor.
- leg.end (gold 12.303 acc, sys 12.308): vowel -19/-20 to 12.296; voiced /G/ closure 12.314-12.356 (per .45-.74, -35..-41;
  CTC 'D'(G) 12.302-12.338); floor 12.368; pant /P/ burst 12.386. Gold AND system end 'leg' at the vowel offset, leaving the
  voiced G closure (40 ms) in no word. Principled end would be ~12.356; accepted-gold convention excludes it (flag).
- pant|you (12.748-12.751 both), you|know (gold 12.878/12.879 HUMAN, sys 12.896/12.901, +20): N onset at 12.878-12.884 (lo
  -0.7 -> -0.1, hi -32.5 -> -40.8); separator .34 -> .89 (12.890). Human at the N onset; system at the separator peak.
- know|i (gold 13.118/13.121 HUMAN, sys 13.148/13.153, +30): OW -> AY; separator 1.00 13.094-13.112 (.79 at 13.118); creaky
  onset of 'i' per .74 -> .19-.34 (13.106-13.160), lo -13 -> -22.6 at 13.130; modal voicing from 13.166. Human at the
  separator's falling edge / creak onset; system at the end of the creak. Class E (creak belongs to the vowel-initial word).
- i|mean (gold 13.230/13.231 HUMAN, sys 13.236/13.239): M onset lo -2.6 -> -0.7 at 13.230-13.236. ok.
- mean.end (gold 13.562 acc, sys 13.544, -21): N -14 -> -21 (13.544) -> -28 (13.562) -> -34 -> -42 (13.580). Class D (nasal tail).
- so.start (gold 13.780 acc, sys 13.792, +12): /S/ onset trn 7.7/9.9 at 13.768-13.774 (zcr .45), -44 at 13.780, -27 at 13.792.
  System 18 ms after the S onset (weak-onset lag). minor.
- so|it (gold 14.018/14.019 HUMAN, sys 14.042/14.045, +24): OW -> IH; separator .94 (14.012) -> .99 (14.030) -> .52 (14.042);
  lo minimum -16.3 at 14.018. Human at the plateau start / lo minimum; system at the falling edge.
- it|kinda (gold 14.154/14.157 HUMAN, sys 14.158/14.161): separator .87-.97, /K/ burst trn 6.4/7.3 at 14.160-14.166. ok.
- kinda|depends (gold 14.508/14.511 HUMAN both, sys 14.472/14.475, -36): voiced throughout (per .8+); separator 1.00 plateau
  14.472-14.490; voiced /D/ closure -8..-11 14.472-14.506; /D/ release trn 7.1 + hi -24 -> -8.6 at 14.508. HUMAN put the
  boundary AT THE RELEASE (the loud voiced closure goes to 'kinda'); system at the separator start. Human stop-onset
  convention: burst when the closure is voiced/loud (kinda|depends, oregon's|gonna, platinum), closure start when it is a
  quiet gap (gonna|beat? 22 ms).
- depends|how (gold 15.230/15.234 HUMAN both, sys 15.206/15.209, -25): /Z/ 15.182-15.212 (cent 7.2-8.1, zcr .23-.43); short
  voiced bit 15.218-15.224; /h/ 15.230-15.260 (zcr .45-.52, lo -2.2 -> -9.2). Separator plateau 1.00 15.176-15.212 sits in
  the Z (early). Human at the /h/ onset; system inside the Z.
- how|far (gold 15.629/15.630 HUMAN both; sys 15.678 end / 15.736 start, +49/+106): AW decays -12 -> -24 (15.630); gradual
  /F/: hi -28.9 (15.630) -> -15.7 (15.646) -> -6.0 (15.670), zcr .07 -> .30 -> .50 (15.686), -24..-31; CTC 'F' only at
  15.726-15.734. Human at the start of the F transition; system ended 'how' mid-F and started 'far' at CTC 'F' with a 58 ms
  pause over the F. Class A + fricative lag (human).
- far|you (gold 15.972/15.973 HUMAN, sys 15.984/15.989, +12): separator .74 (15.966) -> 1.00 (15.978-15.990). Human at the
  rise, system at the plateau end. minor.
- you|wanna (gold 16.136/16.138 acc, sys 16.124/16.127, -11): separator .99 at 16.136, hi min -50.5 at 16.154. minor.
- wanna|go (gold 16.414/16.415 acc; sys 16.420 / 16.466, +51 on start): vowel -20 -> -30 (16.414); voiced /G/ closure -37..-48
  16.432-16.456 (per .63-.75); burst trn 16.6 at 16.462. Gold at the closure start; system after the burst.
- go|with (gold 16.832/16.834 acc, sys 16.718, -114/-116): OW loud (-5..-11) to ~16.774; /W/ constriction 16.782-16.822
  (-18..-22, per .65-.74, hi -58..-62 = lowest); W release/'with' vowel from 16.830 (CTC 'W' 16.822-16.854). Separator 1.00
  at 16.718-16.726, i.e. 60 ms BEFORE the constriction, during the vowel. Principled: constriction onset ~16.780 (gold +52 at
  the constriction end, system -62 at the separator). => the CTC separator can precede the acoustic boundary by 60 ms;
  must be checked against the constriction landmark.
- with|it (with.end 17.097 HUMAN / it.start 17.098 HUMAN; sys 17.026 / 17.084): weak voiced DH 17.002-17.050 (-33..-38, per
  .7-.8), weak frication 17.056-17.074 (-40..-46, cent 7.6-8.3); glottal attack trn 3.7/8.6 at 17.086-17.092 for 'it'.
  Human at the attack; system ended 'with' 70 ms early and left the weak DH as a gap. Class A (final) + E.
- it|but (it.end 17.455 acc / but.start 17.508 acc; sys 17.348 / 17.408, -107/-100): 'it' /T/ ~17.34; voiced HUM 17.36-17.46
  ("mm": -17..-33, per .63-.90, hi -55..-63, lo 0, loudest 17.412-17.444); B pre-voicing -37..-40 17.468-17.498; /B/ burst
  trn 20.9 at 17.506. Accepted gold puts the hum INTO 'it' (end 17.455); system gives it to 'but' (start 17.408 at the hum
  onset). Human-moved convention (swift's) excludes hums: principled it.end ~17.35 (= system), but.start 17.50 (= gold).
  System's but.start is wrong under any convention.
- but|i (gold 17.680/17.682 HUMAN, sys 17.692/17.697, +15): creaky (per .23-.47); separator .91-.98 17.650-17.674; glottal
  trn 6.3 at 17.680 (human), 4.0 at 17.692 (system). Class E (first attack).
- i.end (17.932-17.946 both); i.start (18.422-18.424 both; click trn 6.8-12.4 at 18.398-18.404 excluded). ok.
- i|don't (gold 18.602/18.607 HUMAN, sys 18.554/18.556, -50): AY -8..-11 to 18.560; voiced /D/ closure -20..-23 18.572-18.590
  (per .42-.60); /D/ release ~18.596-18.602 (per .57 -> .66), CTC 'D' 18.584-18.596, 'O' 18.620. Separator peak .96 at 18.554
  (system). Human at the D RELEASE (voiced closure to 'i'), as in kinda|depends.
- don't|know (18.762-18.776 both): separator .91-.98. ok.
- know|i (know.end 19.102 HUMAN / i.start 19.108 HUMAN; sys 19.024/19.026, -81): separator 1.00 over 18.994-19.030; OW loud
  (-4..-6) to 19.024 then a CREAKY DECAY 19.030-19.100 (-9 -> -23, per .19-.45) with pulses (trn 8.5 at 19.090); minimum
  -26 at 19.102-19.108; glottal attack trn 8.7/9.6 at 19.108-19.114 and loud 'i' (-10). HUMAN gave the falling creak to
  'know' and started 'i' at the attack. With people|over and you|every (creak with a RISING envelope went to the next
  word): => glottalised stretches are assigned by envelope direction; boundary = the deepest loudness minimum between the
  previous nucleus and the next vowel-initial nucleus (know|i -26, you|every -19, b-|it -29, law|and -36 acc).
- i|like (gold 19.305/19.306 HUMAN, sys 19.288/19.290, -16): separator .99 19.294-19.312; L constriction hi -43 -> -55 at
  19.306-19.324. minor.
- like.end #2 (gold 19.997 HUMAN, sys 19.764, -233): vowel decays -13 -> -27 (19.762); voiced /K/ closure -23..-30 19.77-
  19.822; /K/ release trn 7.4 at 19.832; aperiodic noise 19.842-19.992 (cent 7.8-8.2, zcr .29-.43, -24 -> -37, per .14-.35)
  decaying SMOOTHLY (no dip, no new onset) to the floor (-49 at 20.012). Human kept the release + the whole continuous
  aspiration in 'like'; system cut before the closure. With week.end (human: release kept, separate breath after a floor
  dip excluded) => rule: noise continuous with a release (no dip back toward floor, no new onset) belongs to the word;
  noise after a dip / with its own onset is a breath.
- referencing.start (20.512-20.514 both). referencing|back (gold 21.172/21.177 acc, sys 21.148/21.151, -26): NG decays -10 ->
  -16 (21.148); voiced /B/ closure -20..-23 21.154-21.184 (per .58-.86); burst trn 12.9 at 21.196. Gold in the voiced closure,
  system at the separator. minor.
- back|i (back.end 21.512 HUMAN / i.start 21.513 HUMAN; sys 21.452 / 21.498): /K/ release + aspiration 21.422-21.488 (cent
  7.1-7.5, -14 -> -30); glottal pulses trn 6.3/5.5 at 21.494-21.500, dip -21/-23; attack trn 4.5 at 21.518, vowel -12 at
  21.524. Human at the attack (aspiration + pulses to 'back'); system ended 'back' inside the aspiration (-60) and started
  'i' at the first pulse (-15). Class F + E.
- i|th- (i.end 21.648 HUMAN / th-.start 21.648 HUMAN; sys 21.578 / 21.578): 'i' loud to 21.582; voiced decay/creak -15..-33
  21.588-21.660; /TH/ frication 21.666-21.700 (trn 5.2 at 21.666, cent 7.9-8.0, zcr .25-.32); weak -38..-47 to 21.740; 'it's'
  attack trn 5.8 at 21.748. Human: 'i' keeps the decay, 'th-' = 21.648-21.749 (covers the TH). System put the fragment
  'th-' on the voiced decay of 'i' (21.578-21.636) and left the TH in a gap (fragment mis-anchoring, cf. they|b-).
- th-|it's (gold 21.749/21.750 HUMAN, sys 21.636 / 21.752). it's.start ok (+2).
- it's|nostalgic (21.942-21.950 both): /S/ to 21.936, N onset 21.948. ok.
- nostalgic|and (gold 22.664/22.669 acc, sys 22.658/22.660): /K/ release trn 10.3 at 22.658; 'and' glottal attack trn 5.7 at
  22.682. ok.
- and|it's (gold 22.752/22.755 acc, sys 22.764/22.768, +13): lo -1.9 -> -11.1 at 22.746-22.758; separator .29-.86 22.758-22.770.
  minor.
- it's|kinda (gold 22.952/22.957 acc, sys 22.922 / 22.958): /S/ decays -23 -> -33 (22.922) -> -48 (22.952 floor); /K/ burst
  trn 7.8 at 22.958. Gold ends the S at the floor (class G); system at -33 (-34).
- kinda|fun (kinda.end 23.208 HUMAN / fun.start 23.209 HUMAN; sys 23.234 / 23.300, +26/+91): vowel -11 -> -20 (23.206); /F/
  onset 23.206-23.218 (hi -18 -> -6.4, cent 6.9 -> 7.7, zcr .16 -> .31), weak F -26..-40 to 23.320; CTC 'F' .72 already at
  23.182-23.212, separator 23.218-23.254, 'F' again 23.284-23.314; vowel 23.326. Human at the F onset; system ended 'kinda'
  inside the F and started 'fun' at the 2nd CTC 'F' with a 66 ms pause over the F. Class A (human).
- fun|and (gold 23.602/23.607 HUMAN, sys 23.590/23.592, -13): separator .96-.99 23.572-23.590; lo -1.6 -> -8.1 over 23.602-
  23.614 (N -> AE). Human at the lo change after the separator. minor.
- and|i'm (gold 23.756/23.758 HUMAN, sys 23.768/23.770, +13): creaky 'and' (per .26-.41), separator .93 at 23.732, trn 4.1 at
  23.738, flat level. No landmark. minor.
- i'm|always (gold 23.940/23.942 HUMAN, sys 23.946/23.948): M -> AO lo -0.6 -> -3.5 over 23.940-23.958. ok.
- always|really (gold 24.240/24.241 HUMAN, sys 24.222/24.224, -17): /Z/ (zcr .42-.57) to 24.216; R onset 24.222 (cent 7.5,
  per .47) -> R established 24.240 (per .76, hi -23, CTC 'R' 1.00). Human at the established R, system at the transition
  onset. minor/scatter.
- really|open (gold 24.486/24.488 acc, sys 24.516/24.520, +32): separator 1.00 24.456-24.474; dip -19 at 24.480, glottal trn
  1.8/4.3 at 24.480-24.486; 'open' vowel -10 from 24.504. Gold at the dip/attack (class E); system at the blank rise.
- open|to (open.end 24.906 acc / to.start 24.922 acc; sys 24.880 / 24.883): N decays -13 -> -27 (24.898) -> -32 (24.904); T
  transients trn 6.5 at 24.910 and 6.8 at 24.922; aspiration 24.928+. System ended at the separator end (-22), 24 ms early
  (class D nasal tail), and started 'to' 40 ms before the burst.
- to.end (gold 25.376 acc, sys 25.352, -26): UW decays -14 -> -16 (25.352) -> -25 (25.376) -> -34. Clip end; class D.

### 009-10 summary (75 tokens, all boundaries read)
 * Breath/noise after words: like.end#1 +223 (breath after a floor dip: exclude), like.end#2 -233 (HUMAN kept 160 ms of
   aspiration CONTINUOUS with the K release: include). => continuity of the release noise decides.
 * Weak fricatives turned into pauses (class A, human): how|far +106, kinda|fun +91, with|it -71 (final DH), sized|pieces.
 * Fricative lag: your|straight +48, bite|sized +32.
 * Hum between words: it|but (accepted gold put the hum in 'it'; system put it in 'but': -107/-100).
 * Fragment 'th-' mapped onto the previous word's voiced decay (i|th- -70/-113); cf. they|b- in 009-9.
 * Glottal/creaky joins: know|i -81 (H, falling creak kept with 'know'), back|i (H), but|i (H), really|open +32.
 * Separator far from landmark: go|with -114 (separator 60 ms before the W constriction), of|like -37, heel|with -23,
   i|don't -50 (H: at the D release), kinda|depends -36 (H: at the D release).
 * Decaying voiced/nasal tails cut: j|crew -47, era.end -45, that|era, mean.end, open|to, to.end, it's|kinda (S to floor).
 * Stop starts after the burst: wanna|go +51.
 * Suspected accepted-gold issue: leg.end excludes the voiced G closure.

## 009-11 DEEP READ
- either.start (0.001/0.006). ok.  either|you (gold 0.414/0.417 HUMAN, sys 0.402/0.405, -12): separator .99 at 0.378-0.390,
  .65 at 0.402, .25 at 0.414. Human at the separator's tail. minor.
- you|see (gold 0.538/0.541 HUMAN, sys 0.580/0.584, +44): UW to 0.532; gradual /S/ onset: hi -36.7 (0.538) -> -22.8 (0.556)
  -> -10.7 (0.568), trn 2.5/3.2 + fvel 2.6-2.9 at 0.544-0.556, zcr .23 at 0.568. Human at the start of the hi rise; system
  at the separator rise, 30-40 ms into the S. fricative-lag class (human).
- see|it (gold 0.756/0.757 HUMAN, sys 0.786/0.790, +33): IY -> IH; centroid 5.6 -> 6.0 and loudness -5 -> 0 over 0.756-0.792;
  lo changes only from 0.792; separator .44 (0.780) -> .97 (0.792). Human at the START of the transition, system at its end
  (separator peak). V-V scatter, human early.
- it|a (gold 0.848/0.850 HUMAN, sys 0.890/0.894, +45): 'it' -2 (0.818), flapped /T/ dip -12 at 0.836 (per .35), trn 2.0 at
  0.848, 'a' vowel rising -9 -> -5 (0.854); CTC 'T' 0.842-0.854, separator .67-1.00 0.866-0.890. Human just after the flap;
  system at the separator end 40 ms into 'a'. separator lag.
- a|lot (0.950-0.957 both): separator .91-.99. ok.
- lot|on (gold 1.220/1.222, lot.start... end acc; sys 1.256, +34): /T/ (CTC 1.190-1.196); dip -13 at 1.214 (per .43);
  glottal attack trn 3.5 at 1.226, -7 at 1.232. Gold at the dip/attack (class E); system at the separator's falling edge.
- on|s-|in (on.end 1.658 acc; s- = 1.861-2.022 HUMAN; in.start 2.058 acc | sys on.end 1.406, s- 1.407-1.662, in.start 1.898):
  'on' = long nasalised vowel -9..-11 (1.23-1.57, per .7, lo 0) decaying -15 (1.574) -> -30 (1.656) -> -49 (1.716) -> floor
  -62..-66 (1.74-1.86); fragment 's-' = burst trn 14.4/15.7 at 1.872-1.876 + /S/ frication 1.876-2.004 (cent 8.0-8.4, zcr
  .42-.58) decaying to -51 at 2.022; 'in' glottal attack trn 6.4/11.8 at 2.044-2.060, -13 at 2.068. System placed 's-' (no
  phones: '*') on the nasal tail of 'on' and let 'in' swallow the S (-455/-160). => a fragment 'X-' must get the phones of
  its letters (s- -> /S/); it then matches the frication. Same family as they|b-, i|th-.
- in|social (gold 2.196/2.199 HUMAN, sys 2.213/2.215, +16): N (per .69) to 2.190; /S/ onset 2.200-2.214 (hi -32 -> -8.7, trn
  3.7 at 2.202, zcr .19 -> .36). Human at the onset; system 14 ms in. minor fricative lag.
- social|media (gold 2.588/2.590 HUMAN, sys 2.606/2.611, +20): L -> M, no clear landmark (hi -45 -> -58 over 2.588-2.624,
  separator .07 (2.594) -> .95 (2.612)). Human at the CTC 'L' end, system mid-separator. scatter.
- media|where (gold 2.956/2.961 acc, sys 2.938/2.941, -20): separator peak .97 at 2.956; W constriction hi -55.5 at 2.968.
  System at the separator rise. separator-edge.
- where|it's (gold 3.176/3.180 acc, sys 3.158/3.161, -20): R -> IH; separator .99 at 3.152; CTC 'I' 3.164-3.176. scatter.
- it's|like (3.328-3.337 both): /S/ to 3.322, L onset 3.334-3.340. ok.
- like|the (like.end 3.626 HUMAN / the.start 3.671 HUMAN; sys 3.601 / 3.603): /K/ release 3.570-3.588; then 100 ms voiced
  stretch 3.600-3.700 (-11..-16, per .6-.76, cent 5.2-5.7, lo ~0) with a slight darkening at 3.666-3.684 (hi -36 -> -44, DH
  constriction?); CTC blank. Human: 'like' keeps 25 ms of it, gap, 'the' from 3.671. Hesitation region; system at the
  voicing onset for both (-68 on the start).
- the|they (the.end 3.924 HUMAN, sys 3.852, -72; they.start 3.924/3.925 both): 'the' decays -15 -> -32 (3.852) -> -47 (3.876)
  -> floor -48..-55 3.882-3.912; DH burst trn 3.1/8.4 at 3.912-3.918. Human gives the decay AND the 36 ms floor gap to 'the'
  (no pause); system ended at -32. Class D (short gap not a pause).
- they|did (they.end 4.258-4.261 both; did.start 4.305 acc / 4.306 sys at the /D/ burst trn 6.7/15.5). ok.
- did|this (gold 4.502/4.507 acc, sys 4.472/4.474, -31): voiced D -> DH (per .8); separator .94-1.00 4.472-4.490; hi min -52 at
  4.484; DH release hi -42.6 -> -23 with trn 3.1-4.8 at 4.490-4.514; CTC 'T' 4.502. Gold at the release; system at the
  separator start (voiced-closure -> release convention, cf. kinda|depends HUMAN).
- this|to (gold 4.708/4.713 acc, sys 4.690/4.692, -19): /S/ (zcr .65-.77) weakening -10 -> -33 (4.708 minimum) -> -29..-31 with
  continuing frication (T merged); vowel 4.738. Gold at the loudness minimum. minor.
- to|themselves (4.808-4.817 both), themselves|or (5.406-5.409 both). ok.
- or|or (gold 5.582/5.585 acc, sys 5.636/5.638, +53): first R -11..-16 (per .45-.61) to 5.594; glottal dip 5.600-5.612 (per
  .26-.38, -17/-18); second 'or' rising -15 -> -7 from 5.618. Gold 20 ms before the dip, system 30 ms after it on the
  rising vowel. Principled: the dip ~5.603.
- or|um (or.end 6.039 acc / um.start 6.041 HUMAN; sys 5.913/5.914, -125): 'or' loud -5..-8 5.882-5.978 (lo -3.6 -> -10.6);
  breathy/glottal dip 5.986-6.034 (-11..-24, per .28-.53, trn 2.7/4.7 at 5.986-5.994; minimum -24 at 6.026); 'um' onset trn
  5.9 at 6.042. CTC separator 1.00 at 5.898-5.930 = 110-140 ms BEFORE the dip, during the loud vowel. Human at the attack
  after the dip; system at the separator. => separator can be off by >100 ms in repetition/filler regions; the glottal
  dip is the landmark (class E).
- um.end (6.658-6.670 both), you.start (7.016-7.022 both). ok.
- you|know (7.192-7.201 both): N onset hi -33.8 -> -41.5 at 7.198. ok.
- know|this (gold 7.500/7.507 acc, sys 7.446/7.449, -55): separator plateau 1.00 7.416-7.452; hi min -49.6 at 7.482 (voiced DH
  closure); DH release trn 5.1 at 7.494, hi -39 -> -23 (7.494-7.512), CTC 'T' 7.500. Gold at the release; system at the
  separator plateau 50 ms early (voiced-closure -> release convention).
- this|this (this.end 7.724 acc / this.start 7.727 acc; sys 7.720 / 7.754): /S/ (zcr .74-.81) decays -13 -> -32 (7.724); DH
  voicing from 7.736-7.742 (cent 7.3 -> 6.2, per .32). System started the 2nd 'this' 25 ms into its DH. minor.
- this|idea (gold 7.946/7.949 acc, sys 7.982, +35): /S/ to 7.934; vowel onset 7.940-7.946 (per .45 -> .58, cent 8.1 -> 6.2).
  Separator .67 (7.946) -> .96 (7.952) -> .40 (7.982). Gold at the vowel onset; system at the separator's trailing edge.
- idea|that (8.504-8.513 both): separator 1.00, DH lo -> -0.3 at 8.510. ok.
- that.end (gold 8.736 acc, sys 8.724): /T/ release noise -14..-32 to 8.724, -41/-45 at 8.730-8.736, floor 8.748. minor.
- you're.start (8.808/8.814 both): Y onset -43 (8.802, per .47), trn 7.8 at 8.820. ok.
- you're|knowingly (gold 9.094/9.095 HUMAN, sys 9.153/9.155, +59): R -> N; dip -12 at 9.082 with lo -> 0 and hi -52 -> -58
  (N onset ~9.080-9.088); separator plateau 1.00 9.094-9.130; trn 5.9 at 9.100. Human at the N onset / plateau start;
  system at the plateau's trailing edge 60 ms later.
- knowingly|doing (9.806-9.815 both): separator .98-1.00, voiced D closure hi -44 -> -57. ok.
- doing|something (10.152-10.157 both): /S/ onset hi -13.9 + trn 6.4 at 10.158. ok (separator on the onset here).
- something.end (10.578-10.581 both), i.start (gold 10.641 acc, sys 10.644; glottal attack trn 11.2 at 10.644). ok.
- i|wasn't (gold 10.780/10.783 acc, sys 10.768/10.771, -12): separator .99 10.774-10.786, W hi -29 -> -38. minor.
- wasn't.end (gold 11.362 HUMAN, sys 11.236, -126): N (per .7) to ~11.220; /T/ release trn 8.8 at 11.222; LONG fricated
  release/aspiration 11.238-11.342 (cent 6.6-8.6, zcr up to .65, -22 -> -41) decaying contiguously to the floor (-52..-59
  from 11.350). Human keeps the whole release to the floor; system cut at the release. Class F, human-moved (strong).
- it.start (11.476-11.482 both, trn 9.8/12.6). it|was (it.end 11.606 acc / was.start 11.609 acc; sys 11.594 / 11.636):
  unreleased /T/ dip -34..-37 11.606-11.630; W rising from 11.630 (hi min -46.6 at 11.642). Gold at the dip start; system
  made a 42 ms gap. minor (class I).
- was|very (gold 11.892/11.895 acc, sys 11.982/11.987, +92): /Z/ 11.862-11.880 (cent 7.0-7.8, zcr .16-.31); Z->V change at
  11.886 (zcr .16 -> .03, cent 7.0 -> 5.5, lo -> -0.1, per .68); weak voiced /V/ 11.892-11.994 (-13..-19, cent 5.1-5.3, hi
  -25..-28); CTC 'V' only at 12.000-12.012; separator 1.00 at 11.862-11.892 (on the Z). Gold at the spectral change;
  system at CTC 'V' 90 ms later (the V given to 'was'). Weak voiced fricative + letter-onset lag.
- very|much (gold 12.338/12.340 acc, sys 12.356/12.361, +21): IY -> M; separator .49 -> .92 (12.338-12.356); hi min -50.5 at
  12.350. minor.
- much|subconscious (12.818-12.823 both): CH -> S change cent 8.1 -> 8.4, zcr .45 -> .52 at 12.812. ok.
- subconscious.end (gold 13.796 acc, sys 13.776, -20): /S/ -16..-18 to 13.770, -26 (13.786), -34 (13.794), -43, -53 (13.810
  floor). Gold near the floor (class G); system while the S is still at -18/-23.
- and.start (13.895/13.900 both, attack trn 16.7 at 13.898). ok.
- and|then (gold 14.086/14.091 acc, sys 14.056/14.059, -32): separator 1.00 plateau 14.056-14.068; DH release hi -47.9 -> -38
  with trn 3.5 at 14.116 (CTC 'T' 14.104). Gold between the plateau and the release; system at the plateau start.
- then.end (gold 14.579 HUMAN, sys 14.544, -35): N decays -13 -> -25 (14.544) -> -36 (14.568) -> -41 (14.574-14.580) -> -49.
  Human at -41 re p99; system at -25. Class D (human).
- the.start (15.260 both), the|m- (15.432-15.437 both). m-.end (gold 15.552/15.556 HUMAN, sys 15.534, -22): M decays -10 ->
  -25 (15.534) -> -39 (15.546) -> -44 (15.552). Human near the floor, system at -25. Class D (human).
- i.start (15.936 both), i|do (gold 16.074/16.079 acc, sys 16.068/16.070). ok.
- do|think (gold 16.326/16.328 HUMAN, sys 16.284/16.287, -42): UW loud to 16.308; /TH/ onset 16.320-16.338 (hi -24 -> -10.7,
  -8 -> -22, cent 5.4 -> 6.7); separator .32 (16.284) -> .99 (16.314) EARLY, during the vowel. Human at the TH onset; system
  at the separator rise 40 ms early. (the separator can precede the fricative onset too.)
- think.end (gold 16.562/16.564 acc, sys 16.550/16.552). ok.
- getting.start (gold 16.751 acc, sys 16.664, -87): /K/ closure -40 16.574-16.63; then a 70 ms voiced HUM 16.634-16.712
  (-20..-38, per .5-.68, cent 5.0-5.3, hi -40..-56, lo 0) decaying to -45 at 16.742; /G/ burst trn 6.5/17.7 at 16.748-16.754.
  Gold starts at the G burst (hum excluded); system started at the hum. Class I (hum excluded, cf. swift's.end HUMAN).
- getting|out (gold 17.062/17.064 HUMAN, sys 17.110/17.114, +50): NG (per .76) to 17.050; glottal attack trn 7.1 at 17.056,
  hi -39 -> -32, lo -0.1 -> -1.7 over 17.062-17.098; separator .61-1.00 17.050-17.092. Human just after the attack; system at
  the separator end. Class E.
- out|of (gold 17.328/17.331 HUMAN, sys 17.334/17.337): /T/ release trn 6.5 at 17.316; separator .48-1.00. ok.
- of|it (17.472-17.475 both). ok.  it.end #1 (gold 17.620 acc, sys 17.602, -20): /T/ -22..-32 to 17.596, -42 (17.602) -> -52
  (17.620 floor). minor.
- it.start #2 (17.972-17.978 both, burst trn 17.5). it|takes (it.end 18.122 acc / takes.start 18.201 acc; sys 18.098 / 18.202):
  vowel decays to the floor -53..-58 (18.098-18.122); a voiced blip -33..-38 18.138-18.154 in the gap (excluded by both);
  /T/ burst trn 10.3 at 18.194. minor.
- takes|personal (takes.end 18.572 acc / personal.start 18.630 acc; sys 18.554 / 18.630): /S/ decays -13 -> -36 (18.572) ->
  floor 18.584-18.614; /P/ burst trn 21.1 at 18.632. System ended the S at -22 (class G). minor.
- personal|responsibility (gold 19.072/19.074 acc, sys 19.048/19.050, -24): L -> R; separator plateau 1.00 19.054-19.072; R
  constriction hi -55.6 at 19.084-19.090; CTC 'R' 19.084. Gold at the plateau end; system at its start. separator-edge.
- responsibility|and (19.904-19.970 both): IY decays -15 -> -28 (breathy, per .24-.45) -> floor -54 (19.946); attack trn 13.6
  at 19.958. ok.
- and|is (gold 20.242/20.244 HUMAN, sys 20.230/20.232, -12): separator .98-.99 20.200-20.230; D release trn 4.8-5.0 at
  20.212-20.218; IH formants lo -1.5 -> -3.5 at 20.242-20.254. Human at the formant change; system at the separator end. minor.
- is.end (gold 20.700/20.703 HUMAN, sys 20.658, -45): /Z/ -16 -> -23 (20.658) -> -35 (20.688) -> -43 (20.700) -> -52 (20.718
  floor). Human near the floor; system at -23. Class G (human).
- takes.start (gold 20.874 acc, sys 20.880): /T/ burst trn 14.3 at 20.860 (both 14-20 ms after it). minor.
- takes|that (takes.end 21.286 HUMAN / that.start 21.287 HUMAN; sys 21.270 / 21.328, +41): /S/ (zcr .67-.78) to 21.274; S->DH
  change 21.280-21.286 (lo -1.6 -> -0.9, per .32); weak voiced DH -22..-26 21.292-21.316; CTC 'T'(DH) 21.322. Human at the
  S->DH change; system left the weak voiced DH as a 58 ms gap. Class A (weak voiced initial fricative), human.
- that.end (gold 21.605 acc, sys 21.572, -33): 'that' decays -7 -> -24 (21.570) -> -36/-37 (per .20-.63) -> -41 (21.600) ->
  -54 (21.630). Gold at -41, system at -24. Class D.
- th-.start (gold 21.636 HUMAN, sys 21.834, +198) / th-.end (gold 21.767 HUMAN, sys 21.928, +160) / uh.start (gold 21.825
  acc, sys 21.928, +104): fragment 'th-' = burst trn 12.4 at 21.638 + /TH/ frication 21.646-21.750 (cent 8.0-8.7, zcr up to
  .69, -26..-38) decaying to the floor -53 at 21.766; floor to 21.816; 'uh' attack trn 5.9/9.1 at 21.826-21.834. System left
  the weak TH as a gap and put 'th-' (given letter-name phones T IY EY CH) on the 'uh' onset. Fragment + weak-fricative
  classes combined (cf. i|th- in 009-10).
- uh|intention (22.090-22.176 both): uh decays to the floor -54 (22.126); prevoicing trn 2.2/4.8 at 22.156-22.162; attack
  trn 9.9/11.3 at 22.168-22.180. ok.
- intention|and (gold 22.992/22.994 acc, sys 22.988 / 23.032, +38 on start): N decays -17 -> -26 (22.980); creaky stretch
  22.980-23.030 with pulses trn 5.9/4.0/6.7/5.4 and dips -36 (22.992), -42 (23.010); vowel -22 from 23.046. Gold at the
  first dip; system after the last pulse. Deepest dip 23.010. Creak scatter (class E).
- and.end (23.488-23.497 both), kind.start (23.864 both). ok.
- kind|of (24.160-24.163 both): trn 11.4 at 24.148, separator .98 at 24.154. ok.
- of|you (gold 24.294/24.300 acc, sys 24.282/24.284, -14): separator .96 at 24.276; CTC 'Y' 24.300 (= gold). minor.
- you|have (gold 24.406/24.409 HUMAN, sys 24.430, +22): UW to ~24.394; /h/ onset: per .57 -> .24 (24.406), dip -15; breathy
  voiced /h/ 24.406-24.436 (per .09-.34); separator .39 (24.430) -> .93 (24.454). Human at the periodicity drop (/h/ onset,
  cf. know|how); system at the separator rise.
- have|to (have.end 24.727 acc / to.start 24.729 acc; sys 24.688 / 24.744): devoiced /V/ frication 24.656-24.698 (cent
  8.2-8.6, zcr .47-.65, -30..-33) decaying to the floor -55..-57 (24.716-24.734); /T/ burst trn 14.1 at 24.740. System ended
  'have' inside its V (-39, class G) and started 'to' after the burst (+15).
- to|knowingly (gold 24.820/24.822 HUMAN, sys 24.856/24.860, +38): N onset hi -42.9 -> -46 at 24.820-24.844, separator .36
  (24.820) -> .99 (24.850) -> .87 (24.856). Human at the N onset; system at the separator's falling edge.
- knowingly|get (25.436-25.442 both): separator .98-.99, voiced G closure. ok.
- get|out (gold 25.636/25.639 acc, sys 25.684, +46): /T/ (per .33) to 25.612; release trn 3.5 at 25.618; 'out' vowel from
  ~25.624 (-9); separator .59-.97 25.630-25.654. Gold 15 ms after the release; system at the separator's end. separator lag.
- out|of (gold 25.856/25.859 acc, sys 25.886/25.889, +30): /T/ dip -9/-10 at 25.856-25.862 (per .52); glottal trn 3.8/3.3 at
  25.868-25.874; separator plateau .80-.98 25.886-25.898. Gold at the dip (class E); system on the plateau.
- of|it (26.010-26.014 both). ok.
- it.end (gold 26.168 acc, sys 26.214, +46): vowel decays to the floor -58 by 26.154; silent closure 26.154-26.196; ISOLATED
  late /T/ release burst trn 18.4 at 26.202 (-34/-37) decaying to -50 by 26.238. Accepted gold excludes the isolated release
  (as like.end#1 and think.end, both accepted); human-moved golds keep releases that are CONTIGUOUS with the word (week.end,
  wasn't.end, like.end#2). Isolated post-closure release at phrase end: ambiguous, accepted gold excludes.
- i.start (gold 26.482 acc, sys 26.470, -12): onset -44 at 26.468 (trn 4.7) rising. minor.
- i|don't (26.578-26.587 both): separator 1.00, voiced D closure. ok.
- don't|know (26.834-26.842 both), know|a (gold 26.980/26.984 acc, sys 26.992/26.997, +12; separator .37 -> 1.00), a|lot
  (gold 27.070/27.073 acc, sys 27.082/27.084, +11), lot|of (gold 27.220 acc at the T dip -15, sys 27.232, +11). minor.
- of|people (gold 27.338/27.344 acc, sys 27.314/27.316, -26): V decays -20 -> -36 (27.314); /P/ burst trn 13.4/14.5 at
  27.314-27.320; aspiration -25..-30 to ~27.344; vowel 27.350. Accepted gold puts the P burst + aspiration into 'of' (start
  of 'people' 30 ms after the burst) - against every human-moved stop onset. Suspected accepted-gold error; system (at the
  burst) is principled.
- people|who (gold 27.594/27.596 HUMAN, sys 27.606/27.610, +14): L -> voiced /h/; periodicity dip .53 at 27.594 (human);
  separator .70-.99 27.606-27.618. V->/h/ periodicity-dip convention. minor.
- who|just (27.800-27.806 both): JH burst trn 9.6 at 27.806. ok.
- just.end (gold 28.176 HUMAN, sys 28.146, -30): /S T/ frication decays -20 -> -43 (28.146) -> -50 (28.158) -> -54 (28.176
  floor). Human at the floor, system at -43. Class G (human).

### 009-11 summary (82 tokens, all boundaries read)
 * Fragments mis-anchored: on|s-|in (-455/-360/-160: 's-' put on the nasal tail, 'in' swallowed the S), that|th-|uh
   (+198/+160/+104: 'th-' put on the 'uh' onset, the weak TH frication left as a gap).
 * Released final stop kept (class F, human): wasn't.end -126 (110 ms contiguous release to the floor).
 * Weak voiced/initial fricatives cut: was|very +92 (V), takes|that +41 (DH), have.end -39.
 * Separator far off in repetition/filler: or|um -125 (separator 110-140 ms before the glottal dip), or|or +53.
 * Hum before a word excluded by gold: getting.start -87.
 * Class E (glottal/creak) and separator lag: getting|out +50, it|a +45, lot|on +34, out|of +30, get|out +46, is... 
 * Fricative lag: you|see +44 (H), in|social +16.
 * Voiced-closure stop onsets at the release: did|this -31, know|this -55, and|then -32.
 * Final fricative/nasal to floor (classes D/G, human): is.end -45, then.end -35, m-.end -22, just.end -30.
 * Suspected accepted-gold errors: of|people (P burst given to 'of'), it.end (isolated release excluded; ambiguous).

### BUNDLE 009 CONSOLIDATED (clips 0-11, ~960 boundaries). Principled rules the human-moved golds support:
 R1 weak aperiodic word-initial phones (F, TH, DH, V, HH, S onset) contiguous with the word belong to it; boundary at the
    spectral/aperiodicity onset; the word-ref -20 dB pause test must not cut them (this, horrible, fine, for, far, fun,
    thinking, very, that).
 R2 same for weak word-FINAL fricatives/aspiration (if, with, have) and released stops: keep releases contiguous with
    the word down to the floor (it|he, wasn't, like#2, overtake, week).
 R3 breaths/hums/clicks that are separate events (dip toward floor + own onset, or voiced nasal murmur not matching the
    adjacent phone) are excluded (awful, fun, week, swift's, or, getting, blah, like#1, haiti).
 R4 the CTC separator is NOT a boundary estimate by itself: it lags 30-60 ms into word-initial fricatives, can lead the
    acoustic change by 40-140 ms (go|with, do|think, or|um, ticketmaster|handled, know|this), and its leading/trailing edge
    choice is arbitrary. Use it only to find the region; place the boundary on the acoustic landmark of the phone pair:
    fricative onset/offset, nasal onset (lo -> 0, cent drop), constriction maximum (hi/loudness minimum) for glides,
    periodicity dip for /h/, release burst for voiced-closure stops, loudness minimum before a glottal attack.
 R5 glottal/creaky stretches: boundary at the deepest loudness minimum between the nuclei; falling creak = previous word,
    rising creak = next (vowel-initial) word.
 R6 short floor gaps (< ~60-80 ms) and decaying voiced tails are not pauses; end voiced/nasal tails near -40 re p99 or
    the floor (human-moved: uh, it-, then, m-, mean, again, era...).
 R7 final fricatives end where they reach the floor (~-45 re p99): man's, is, just, s|military, it's|kinda, he's.
 R8 stop-initial word starts inside the closure or at the burst, never after the burst; homorganic clusters share one
    release (second word); a released final stop keeps its burst when the next word starts with a consonant.
 R9 fragments ('b-', 's-', 'th-', 'm-') get the phones of their letters (s- = /S/, th- = /TH/) and must sit on matching
    acoustics (burst/frication), not on another word's tail.
 R10 letter names own their vowels ('s' = EH S, 'u' = Y UW, 'b' = B IY, 'j' = JH EY).
 R11 clip-initial foreign speech: start the first word where the foreign segment's phone class ends.

## 026-0 DEEP READ (golden labels 7; 85 tokens, 29.3 s)
(flags: first char = start, second = end; H = human-moved)
- START and g .070 s .074: onset .068-.070 (dB -68→-51, trn 9.7). Both OK.
- and|so: "and" N decays -6(.284)→-22(.308)→-28(.314)→-35(.320); then a weak voiced D-closure bar -37..-40 dB, per .37-.48,
  .320-.342, dBfl +27..+33 (NOT floor). S of "so" = .346-.406: per drops .47→.28(.346)→.16(.354)→.11, zcr .10-.16,
  cent 6.0-6.8 (weak, non-sibilant S: hi only -36..-48), CTC S .362-.378; vowel onset .410 (dB -31→-8, glo 19.7 @.402).
  → no pause here; and.end ≈ .342 (keeps D closure, R2/R8), so.start ≈ .344 (aperiodicity onset, R1).
  Gold .314/.373 (accepted) leaves a 59 ms non-pause gap and starts "so" 29 ms inside the S. System .308/.356
  (-20 dB pause test cuts the voice bar; start at S is 12 ms late). Gold error suspected: so.start +29.
- so|why g .639/.641 s .552: OW nucleus .410-.520 (dB 0..-4, lo -10..-12). Rounding offglide .498-.546 (lo -3.8→-0.6,
  cent 6.0→5.5). Then a dead-flat 80 ms plateau .554-.634: dB -15/-17, lo -0.0/-0.1, cent 5.25-5.34, hi -62..-65,
  ssl .11-.18 (steady). fvel bump 1.7-1.8 at .594-.602 inside plateau; loudness min -17 at .594; hi min -65.4 @.570.
  Rise into AY from .642 (fvel 2.3, CTC W .642-.674, H .682). SEP peak .538-.554.
  The [ʊ]-offglide of OW and the W constriction are acoustically one segment. R4 (constriction max) → ~.594.
  Gold = plateau END (onset of AY), system = plateau START (separator peak). Genuinely ambiguous, ±45 ms either way.
  Old-gold convention here: the W plateau belongs to "why" entirely.
- why|not (why.e H, not.s H) g .984/.985 s .988: nasal onset lo -3.0→-0.1 (.980→.992), cent 6.10→5.65, hi -40→-53.
  Human gold is exactly at the nasal onset (R4 confirmed). System +4 OK.
- not.end g .1.415 (accepted) s 1.888 (+473): AA to 1.376; sharp drop -6→-16→-25→-32 at 1.376-1.412 with a per dip
  .34-.37 at 1.400-1.412 (glottal-stop T [ʔ]), then a falling voiced tail per .81→.67 -34(1.424) -40(1.436) -47 -52
  -54(1.472) -57(1.484, per .44), floor ~1.52. CTC: N 1.04-1.08, O 1.22-1.26, T 1.304-1.316, SEP 1.364-1.412.
  → not.end ≈ 1.436 (-40, R5 falling creak/voicing to prior word, R6 tail to -40). Gold 1.415 is -20 (small).
  After a 150 ms floor gap (1.52-1.674): a LOUD untranscribed vocalization 1.684-1.914: trn 25 onset, voiced
  -1..-6 (1.694-1.724), aperiodic h-like -31..-35 per .08-.34 zcr .13-.24 cent 6.5-7.3 (1.744-1.794), voiced -1..-5
  (1.804-1.854), decay to -47 @1.914. = "ha-ha"/"uh-huh" laugh. CTC blank .93-.99 and SEP 0.00 over the whole event.
  System swallowed it into "not" (end 1.888). R3: loud segment with CTC blank≈1 and no letters, separated by a floor
  gap, is non-lexical and belongs to no word.
- START have g 2.376 s 2.378: HH onset trn 14.8, dB -61→-40 at 2.376, per .11 zcr .13; voicing at 2.382. Both OK.
- have|all g 2.799/2.801 s 2.829/2.831 (+30): V constriction 2.780-2.814 (dB -12→-16, min -16 at 2.804-2.810, per .57-.74,
  cent 5.6-5.7, lo -0.3..-0.6); rise 2.816 (-13) 2.822(-10) 2.828(-9) 2.834(-4); lo -0.4→-1.4→-4.6 at 2.822-2.834;
  trn 3.5 at 2.816 & 2.828, glo 15.6/16.6 (glottal attack of "all"). CTC E .768-.798, SEP 1.00 2.816-2.828.
  V offset / loudness-min ≈ 2.807-2.814. Gold -10 (at V middle), system +18..+22 (placed on SEP plateau, already
  7 dB up into AO). Error class: separator-edge placement; should be loudness min before glottal attack (R4/R5).
- all|this g 3.031/3.033 s 3.042/3.043: L → DH realized as dental stop: flat -13/-15 3.012-3.054, hi min -66.4 at 3.030
  (tongue to teeth), release trn 6.1 at 3.048, CTC T(H) 3.060. Closure 3.030-3.048. Both inside closure → OK (R8).
- this.end g 3.227 s 3.220: CTC S 3.190-3.216 fires on the voiced part. Acoustic [z]: 3.208-3.240 per .34-.64, lo -5..-9
  (vs vowel -0.3), hi -36..-42, cent 6.2-6.3, -31..-45 dB; devoiced tail 3.244-3.278 zcr .13-.19, cent 6.3-6.55, -47..-50;
  frication ends 3.278-3.280 (zcr .18→.12, cent 6.2→5.15). Then 3.320-3.376 low hum (cent 3.7-4.8, lo 0, -51..-62) = not
  speech. Floor 3.384. → this.end ∈ [3.240 (-45, R7 literal), 3.278 (frication end)]. Gold -13..-51, system -20..-58.
  Accepted gold truncates the weak final fricative (R7 class).
- START advice g 3.527 s 3.530: pre-voicing hum 3.502-3.514 (-60, +8 fl, cent 3.8-4.5, lo 0) then glottal attack trn 24.1
  at 3.526, -56→-28. Onset 3.524. Both OK.
- advice.end g 4.088 s 4.106: AY decays -11(4.048)→-29(4.068)→-40(4.078). S FRICATION 4.084-4.234 (150 ms): zcr .18-.32,
  cent 6.7-7.5, hi -20..-36 (vowel -55..-60), -38..-54 dB. Ends 4.234-4.238 (zcr .30→.08, cent 7.44→6.33→5.02).
  Then low hum 4.24-4.28 (cent 4-5, lo 0), floor 4.288. CTC: C 4.048-4.058, E 4.088-4.098, SEP 1.00 4.138-4.148 (inside S).
  → advice.end ≈ 4.236. GOLD (accepted) ends at the S ONSET: -148 ms error. System -130. Largest accepted-gold error so
  far in 026; same class as R7 (human-moved golds in 009 include such S down to the floor).
- START and g 4.355 s 4.352: onset trn 13.8-16.4 at 4.344-4.348, -68→-53→-28. Onset ≈ 4.345. Gold +10, system +7 (minor).
- and|support g 4.489/4.576 s 4.488/4.554: N decays -12(4.470)→-27(4.488)→-40(4.500)→-45(4.512); D-closure voice bar
  4.512-4.536 per .44-.66 at -45..-48 (dBfl +19..+22, not floor); S of "support" 4.542-4.590 (per .16-.34, zcr .14-.18,
  hi -22..-36, cent 6.4-7.0, trn 5.3 at 4.548); vowel onset 4.596 (-37→-20→-10). CTC S 4.542-4.554.
  → no pause; and.end ∈ [4.500 (-40), 4.540], support.start ≈ 4.544. Gold support.start +32 (mid-S; accepted-gold error,
  same as so.start at .373). System +10. Both end "and" at -27 dB — old-gold convention: "and" ends where the N falls
  ~25 dB, excluding the D voice bar (also at and|so). Note for design: in both cases the voice bar is ≤ -40 dB and inaudible.
- support.end g 5.133 s 5.122: R → T closure: -8(5.080)→-19→-27(5.110)→-42(5.120), closure 5.12-5.19 decaying to -60 (fl +7).
  T RELEASE: trn 3.0 (5.200), 9.0 (5.210); aspiration 5.210-5.255 at -35..-39, zcr .27-.33, cent 7.2-7.8, hi -15..-23;
  ends 5.260-5.270 (zcr .17→.09, cent 6.6→4.6). CTC SEP 5.16-5.20, then blank (letters stop before the release).
  → released final stop keeps its burst (R2/R8): support.end ≈ 5.265. Gold -132 (accepted), system -143.
  (5.330-5.350 small click/breath onset, excluded.)
- through.start g 5.554 s 5.510 (-44): floor -67 until 5.532; TH onset 5.544-5.550 (-62/-58, trn 6.7 at 5.550), frication
  5.550-5.576 (zcr .19-.39, cent 6.8-7.8, -54..-40), R/vowel 5.580. CTC T 5.502-5.514, H 5.520-5.556 — CTC emits the
  TH letters 30-45 ms BEFORE any energy. System followed CTC into floor silence. Gold +4..+10 after onset (OK).
  Rule: a word cannot start in floor silence (dBfl ≈ 0); snap to first frame leaving the floor.
- through|the g 5.710/5.712 s 5.706/5.707: UW decays -5→-19(5.692); DH closure 5.692-5.716 (voice bar per .72-.76, min -27);
  burst trn 7.7 at 5.716; CTC SEP 5.698-5.722, T 5.722. Both in closure (R8) — OK.
- the|process g 5.817/5.819 s 5.802/5.836: AH decays -20→-42(5.796); P closure 5.796-5.824 (min -47 at 5.814); P burst trn
  7.9 at 5.826 (3.2 at 5.820, 5.7 at 5.832); aspiration 5.832-5.862 (per .15-.26, lo -10..-12). Gold in closure 7 ms before
  burst — OK. System: the.end at closure start (leaves a 34 ms unowned closure), process.start 10 ms AFTER the burst
  (R8 violation, +17).
- process.end g 6.429 s 6.404: first S 6.180-6.210; EH 6.220-6.385 (per only .25-.54 — creaky); drop -25(6.380)→-40→-49→
  -55→-58(6.420); no sibilant after the vowel (zcr .03-.09, cent 4.8-5.4). Small bump 6.440-6.460 (trn 4.7, -43, cent 5.7,
  zcr .08) — lenited S or click, unclear. 6.52-6.55 dip (fl +9); 6.57-6.69 weak frication -52..-57, zcr .13-.25,
  cent 5.9-7.0, own onset after the dip = breath (R3). → process.end ∈ [6.40, 6.47]; gold/system both inside. OK.
- START i g 7.007 s 7.010: floor noise to 6.988, faint pre-voicing 6.994-7.000 (+5..+8, glo 16.4), glottal attack trn 21.8 at
  7.006, -57→-24. Onset 7.004. OK.
- i|am g 7.199/7.201 s 7.142/7.143 (-57): V-V, loudness flat -0..-3, per .72-.85. AY glide: cent 6.8(7.11)→6.11(7.200) then
  back up to 6.32 (7.240-7.264); lo peaks -4.7 at 7.200; fvel bump .79 at 7.200 then 1.48-1.63 at 7.216-7.232; ssl rises
  .08→.26-.29 at 7.200-7.216; CTC I 7.104-7.112, SEP 7.184-7.216 (peak .86 at 7.192), A 7.264, M 7.304. Turning point
  = 7.200-7.210. Gold exactly on it. System cut 30 ms after the I emission, ignoring SEP + spectral turning point.
  Error class: V-V join, must use SEP region + centroid/lo turning point + fvel/ssl peak.
- am|frequently g 7.394/7.476 s 7.366/7.474: M 7.304-7.360 (lo -0.0..-0.2, cent 5.55, per .78-.88); M offset 7.362-7.368
  (per .52→.38, trn 3.9-4.1, hi -55→-38→-27.5). Frication runs continuously 7.368-7.512+: part A 7.376-7.440 (-25..-36,
  cent 6.4-7.0, zcr .13-.21, lo -2..-10), dip -40 at 7.456 (dBgf +28, not floor), part B 7.456-7.51 (-40→-26, cent
  6.9-7.5, zcr .19-.25, lo -5..-21). CTC F 7.480-7.496.
  → am.end ≈ 7.364 (system right; gold +30 inside the frication). frequently.start: R1/R3 say 7.368 (no dip toward the
  floor separates A from the F); alternative = the -40 dip at 7.456 if A is an exhale. Gold/system (7.476/7.474) sit
  20 ms after the dip — both late even under the alternative. Ambiguous; lean 7.368.
- frequently|the g 7.974/7.976 s 7.968: IY decays -9(7.960)→-14→-18(7.972); DH closure 7.966-7.998 (voice bar per .55-.80,
  lo -0.1..-0.5, -18..-20); burst trn 8.0 at 8.002; CTC SEP 7.954-7.972, T 8.002. Both in closure — OK.
- the|first g 8.097/8.099 s 8.076/8.120: AH decays -11→-26(8.070); F onset 8.074-8.078 (hi -50.6→-30.5, zcr .03→.13, per
  .50→.20); F frication 8.08-8.156 (zcr .14-.27, cent 6.9-7.5); ER from 8.164. CTC F 8.124-8.136.
  → boundary ≈ 8.076. System the.end exact; system first.start +44 (follows CTC F emission; leaves a gap inside the F).
  Gold +22 inside the F (accepted). Pattern: old gold starts fricative-initial words 20-30 ms into the frication
  (so .373, support 4.576, first 8.099).
- first|one g 8.356/8.396 s 8.342/8.402: ER/R to 8.276; weak S 8.292-8.324 (-30..-49, zcr .08-.13, cent 5.6-6.1); T burst
  trn 9.4 at 8.332 (7.3 at 8.330); aspiration/affrication 8.336-8.390 (zcr .19-.39, cent 7.1-7.8, hi -12..-32, -36..-50);
  ends 8.390 (zcr .12, cent 6.2); W onset 8.394-8.396 (cent 5.8, lo -0.9, hi -42.7), loud W 8.402 (-20).
  (dBfl is 0 here: the 2-s local floor IS this closure — dBfl is useless in continuous speech > 2 s.)
  → first.end ≈ 8.390 (R8, released final T keeps aspiration before a consonant). Gold -34, system -48.
  one.start 8.394: gold +2, system +8 — OK.
- one|to g 8.575/8.577 s 8.573/8.575: N end 8.572-8.578 (per .57→.30), closure 8.578-8.586 (min -41), T burst trn 9.7 at
  8.590. Both at closure start — OK.
- to|tell g 8.731/8.733 s 8.716/8.764 (+31): UW decays -25(8.710)→-31→-40(8.722)→-51(8.734); closure 8.720-8.738; T burst
  trn 11.3 at 8.740 (5.1 at 8.746), then irregular aspiration 8.746-8.79 (trns at 8.764, 8.776; zcr .19-.21 from 8.782).
  CTC T 8.764-8.776 (lags the burst by 24 ms). Gold in closure — OK. System to.end at closure onset OK, but tell.start
  24 ms AFTER the burst (followed CTC T) — R8 violation.
- tell|clients g 8.980/8.982 s 8.956/8.996: L decays -8(8.938)→-23(8.950)→-36(8.962); closure 8.962-8.990 (-41..-45, per
  .31-.40); weak K release ~8.990-8.994 (per dips .10, zcr .11, cent 6.7, no transient); rise -37(8.998)→-29(9.004); CTC C
  9.004-9.016. Gold in closure OK; system tell.end at closure onset OK, clients.start ~4 ms after release (marginal OK).
- clients|as g 9.375/9.377 s 9.380/9.418 (+41): N 9.288-9.304 (lo -0.3..-0.7); T unreleased (per .48→.34, no trn);
  NO final S frication anywhere (zcr .02-.06 to 9.39, cent 4.8-5.9) — "clients" ts elided; voiced tail -40..-50
  9.352-9.392 (per .18-.69, lo -0.1..-0.3); floor -50/-51 at 9.384-9.400 (dBgf +16). CTC S 9.344-9.376 on the tail.
  "as" onset: breathy aperiodic 9.398-9.410 (zcr .11, trn 2.9-3.2, hi -29.5, cent 5.9-6.2, per .12-.25), vowel 9.416-9.424
  (trn 7.1, -39→-13). → clients.end ≈ 9.388, as.start ≈ 9.398 (R1: breathy onset belongs to the word).
  Gold as.start -21 (inside clients' tail), system +20 (at vowel). clients.end both OK.
- as|they're g 9.604/9.607 s 9.574/9.614: AE→Z: voiced low plateau 9.544-9.562 (per .65-.71, lo 0..-0.9), no frication;
  decay -24(9.568)→-30→-39→-45→-47(9.592); devoiced Z tail zcr .06-.13 9.580-9.616; LOCAL FLOOR (dBfl -2..0, -52..-54)
  9.592-9.628 = DH closure; DH release trn 2.4-3.0 at 9.628-9.634, vowel 9.640. → as.end ≈ 9.595 (R7), they're.start
  ∈ [9.598, 9.630] (R8). Gold OK both. System as.end -21 (cut Z tail at -30 dB; pause test), they're.start OK.
- they're|going (going.s H) g 9.762/9.763 s 9.785/9.787 (+24): R → G: voiced closure = loudness min -21 at 9.754-9.760
  (per .69-.76, per min .62 at 9.766); transients 3.9 (9.766), 2.2, 6.2 (9.778), 5.1 (9.784); rise -17→-8 by 9.796.
  CTC E 9.742-9.778, SEP 9.778-9.802 (peak .87 9.790), G 9.802. HUMAN gold = loudness min / first transient (9.762).
  System = second transient / SEP rise (+24, after the burst onset). Confirms R4/R8 (voiced-closure stop: boundary at
  closure minimum, before the burst).
- going|through (through.s H) g 10.026/10.052 s 10.006/10.050: NG decays -23(10.000)→-28→-41(10.012); weak voiced tail
  10.012-10.042 (-41..-46, per .48-.66); TH onset 10.046-10.048 (trn 6.4, zcr .05→.11, hi -38→-31, per .56→.34→.13);
  frication 10.048-10.08+ (zcr .13-.40, cent 6.4-7.8). Human through.start 10.052 = TH onset +4. System OK (+2).
  going.end: human left 10.026 (26 ms gap before its own through.start) — humans do not enforce contiguity for voice
  tails ≤ -41 dB. going.end ∈ [10.012, 10.046]; both inside/near.
- through.end g 10.383 s 10.374: UW decays -19(10.368)→-27→-38(10.380)→-43; voiced tail 10.386-10.412 (-43..-47, per .55-.63);
  -54 at 10.420; then own onset (trn 7.7 at 10.430) and 170 ms of hiss 10.47-10.64 (zcr .23-.39, cent 7.3-7.85, hi -17..-31,
  -44..-53) = exhale breath, untranscribed, CTC blank 1.00 (R3). Floor -65 from 10.69. → through.end ∈ [10.383, 10.415].
  Both OK.
- START this g 10.936 s 10.934: floor -70; onset 10.926-10.928 (trn 2.7), DH release 10.934 (trn 6.7, -36), 10.940 (trn 9.5,
  -20). Both +8 after first energy, at the release (word-initial stop with no preceding closure: start at release) — OK.
- this|is g 11.079/11.081 s 11.099/11.101 (+20): S of "this" unfricated (zcr .02-.03, cent 5.3, per .79-.81) = voiced
  constriction, hi -55..-60 (lower than IH's -49..-51); loudness min -18 at 11.090-11.102; hi rises from 11.102
  (-55.1 → -50.9 at 11.114); trn 3.0 at 11.120. CTC S 11.060-11.078, SEP 11.102-11.120 (peak .57). → boundary ≈ 11.100
  (loudness min + hi rise, R4/R5). System exact; gold -20 (accepted).
- is|a g 11.199/11.201 s 11.223/11.225 (+24): Z of "is" unfricated plateau 11.168-11.198 (-16/-17, lo -0.5, cent 5.5);
  from 11.204 the AH rises with a glottal attack (trn 2.4-4.6 11.204-11.222, glo 14.5-15.9, lo -0.6→-4.3, cent 5.5→5.9).
  CTC S 11.168-11.198, SEP 11.204-11.234 (peak .95 11.216). → boundary 11.200 (minimum before glottal attack). Gold exact;
  system = SEP peak mid-rise (+24). R4/R5 confirmed.
- a|red (a.e H, red.s H) g 11.306/11.307 s 11.327/11.329 (+22): AH → R: loudness -4(11.280)→-9(11.304)→-11(11.316)→-12
  (11.340, min); hi -56.4(11.304)→-57.0→-61.7(11.316)→-65.4(11.322)→-65.5(11.340); lo -3.1→-2.0→-1.3; cent 5.9→5.7.
  CTC A 11.280-11.298, blank 11.304-11.316, SEP 11.322-11.352. HUMAN = 11.306: the START of the R transition (end of A
  emission, loudness-drop midpoint 11.297 / hi-drop midpoint 11.315 average), 35 ms BEFORE the constriction max.
  System = SEP onset/constriction reached (+22). REFINES R4: for V→R (and likely V→L/W), human cuts at the transition
  midpoint (half-way between vowel and constriction values), not the constriction maximum.
- red|flag g 11.564/11.566 s 11.546/11.612 (+46): EH→D closure -21(11.540)→-28(11.552)→-34(11.558); D released straight into
  F: trn 5.2 at 11.564, hi -51.5→-39.6→-33.4, zcr .03→.08→.15, per .63→.28 (11.552-11.564); F frication 11.564-11.630
  (zcr .13-.23, cent 6.9-7.5). CTC F 11.624-11.636. → boundary ≈ 11.560. Gold OK. System red.end -18 (OK-ish, leaves the
  closure unowned); flag.start +46 at the CTC F letter, mid-frication (R1 violation).
- flag|let's g 11.897/11.899 s 11.902/11.903: G voiced closure -26..-28 (per .57-.75) 11.866-11.890, release trn 5.1 at 11.890,
  L rises -25(11.896)→-19→-14. Boundary 11.892-11.896. Both OK.
- let's.end (false start) g 12.093 s 12.090: EH to 12.002; decay -19(12.010)→-33(12.026); lenited T/S 12.026-12.058
  (-33..-44, zcr .06-.10, cent 5.7-6.2, lo -2.7..-6.9, partly voiced) — no burst, no sibilant; decay -48..-55 to 12.090;
  low hum 12.100-12.132 (cent 4.2-4.8, lo ~0) excluded; floor 12.140. Both OK.
- START let's g 12.238 s 12.236: pre-voicing 12.212-12.236 (-68→-58, per .55-.67, cent 5.6) = the quiet start of the L;
  main rise -52→-26 at 12.236-12.244. Onset ∈ [12.216, 12.238]; both at main rise. Minor (R1 says 12.216).
- let's|walk g 12.448/12.450 s 12.451/12.453: S 12.418-12.436 (zcr .23→.10, cent 7.4→6.3, hi -18.6→-31.5); W onset
  12.442 (per .31, hi -43, lo -1.2), loud 12.454. Boundary ≈ 12.442. Gold +7, system +10 (minor).
- walk|away g 12.691/12.693 s 12.697/12.699: K burst trn 10.0 at 12.672, aspiration 12.672-12.688 (zcr .13-.14), vowel onset
  with trn 5.0 at 12.690. Both OK (release to "walk", vowel onset for "away").
- away.end g 12.994 s 12.986: EY ends with a breathy devoiced offset 12.956-12.975 (zcr .20-.23, cent 7.0-7.4, -29..-37),
  then -31..-41 12.980-12.992, -45 12.998, -52 13.010, -57 13.016. End ∈ [12.992, 13.012]. Both OK.
- START um g 13.491 s 13.496: glottal attack trn 19.9 at 13.496 (-68→-46), glo 14.4 at 13.490. Both OK.
- um.end g 14.030 s 14.004 (-26): M decays -18(13.974)→-26(14.004)→-33(14.022)→-37(14.028)→-42(14.034)→-51(14.040), per stays
  .68-.83 to 14.034. R6 (-40) → 14.032. Gold exact; system cut at -26 dB (pause test). R6 class.
- START you (you.s H) g 14.630 s 14.312 (-318): after "um" floor, a VOICED ISLAND 14.302-14.412: -51→-27(14.312, trn 3.3)
  →-13..-20 (14.322-14.372) →-44 (14.402-14.412); lo -0.0..-0.3, cent 5.3-5.5, hi -54..-64, per .60-.75 = closed-mouth hum
  "mm", 100 ms; weak low tail 14.44-14.47 (-55, cent 4.1-4.4); floor 14.48-14.61. CTC blank 1.00 over the island, SEP 0.
  Y onset 14.620-14.626 (-66→-61, per .36, glo 14.9), -47 (14.632, trn 3.0), -34 (14.642, trn 6.0); CTC Y 14.642.
  HUMAN = 14.630: excludes the hum. System started the word at the island (R3 class, like the laugh at 1.68).
  Signature: CTC blank≈1/SEP=0 over a voiced island + floor gap ≥ 150 ms before the word's first letter.
- you|know (you.e H, know.s H) g 14.755/14.756 s 14.759/14.761: UW -5/-6 to 14.724, then -7..-11 dip 14.732-14.772 (min -11
  at 14.756-14.772, hi -44.6→-51.1), re-rise -9/-8 (14.780-14.788). No lo→0 nasal signature anywhere (lo -1.3..-4.2); per
  drops .75→.45 later (14.804-14.844). CTC U 14.700-14.716, SEP 14.740-14.764 (peak .76 at 14.756), K(N) 14.764, N
  14.780-14.812. HUMAN = SEP peak = onset of the loudness dip. System +4 OK. (Casual "y'know": the nasal is weak;
  the SEP peak is the best landmark when no acoustic class change exists.)
- know.end g 14.902 s 14.898: OW→W offglide -13→-24(14.892)→-34(14.900)→-47(14.908). Both OK (R6 ~-40 = 14.904).
- START so g 15.097 s 15.090: faint noise -55 (zcr .09-.11, cent 5.8-6.4) 15.038-15.062 over a -55..-60 low hum since 14.93;
  S proper from 15.086 (zcr .13, cent 6.3) → 15.098 (-44, zcr .25, trn 5.2); vowel 15.126 (trn 9.5). Onset ≈ 15.086-15.090.
  Both OK (gold +8).
- so|i g 15.209/15.211 s 15.227/15.229: V-V "so I". lo -5.9 (15.134, O) → -11.8 (15.190-15.198, [a] target of I) → -8.7
  (15.238, [ɪ]); cent rises monotonically 6.13→6.62 (no turning point); ssl peak .464 at 15.174; hi dip -58 at 15.222.
  CTC O 15.142-15.158, SEP 15.206-15.238 (peak .99 15.214), I 15.246. Acoustic O→a change ≈ 15.155-15.175 (lo midpoint /
  ssl peak); SEP 40 ms later, AFTER the [a] target. Gold = SEP rise (15.210), system +18. Ambiguous; if the [a] target
  belongs to "I", both are 35-55 ms late.
- i|guess g 15.325/15.327 s 15.265/15.267 (-60): AY loud (0 dB) to 15.276, decays -5(15.288)→-15(15.300); G voiced closure
  15.300-15.324 (per .51-.69, lo -0.2..-0.8, min -24); burst trn 7.4 at 15.324 (+4.3 at 15.330, hi -35.5), vowel 15.342.
  CTC I 15.240-15.258, SEP 15.282-15.318, G 15.324. Gold = burst (R8 OK). System cut INSIDE THE VOWEL at 0 dB, 35 ms
  before the closure — same as i|am: "i" is cut ~25-30 ms after its CTC letter regardless of acoustics.
- guess.end g 15.515 s 15.496: S voiced 15.478-15.496 (per .61-.74) then devoiced frication 15.502-15.576 (zcr .14-.20,
  cent 6.8-7.1, -40..-46); ends 15.576-15.588 (zcr .12→.03, cent 5.69→4.83). Then a 50 ms nasal hum 15.600-15.648 (-33..-39,
  per .68-.83, lo 0, cent 5.6-5.8; CTC blank) = "mm", excluded (R3); floor 15.66-15.73.
  → guess.end ≈ 15.578 (R7). Gold -63 (accepted-gold truncation), system -82.
- START i g 15.764 s 15.770: pre-voicing 15.744-15.752 (-60→-54, per .34→.70, glo 14.3-15.1), glottal attack trn 6.7 at
  15.758 (-41), -30 at 15.770. Onset ∈ [15.746, 15.756]. Gold +8..+18, system +14..+24 (late).
- i|guess g 15.908/15.910 s 15.855/15.857 (-53): AY -4/-6 to 15.878, decays -11→-20(15.890); G voice bar 15.890-15.912
  (per .43-.73, lo -0.1..-0.2, -22..-26); burst trn 11.6 at 15.914. Gold in closure 5 ms before burst (OK). System again
  inside the vowel (-5 dB), 22 ms after CTC I (15.824-15.836). Same "i" error.
- guess|i g 16.087/16.089 s 16.066/16.112 (+23): weak S (zcr .07-.09) decays -27→-48(16.058)→-52 (16.082 min); "i" has a
  breathy aperiodic onset 16.082-16.106 (per .13-.25, trn 2.3-2.8, -52→-33, lo -5.1 at 16.094), vowel trn 6.7 at 16.118.
  → boundary ≈ 16.082-16.088 (min + aperiodic onset, R1). Gold OK. System guess.end -21 (-48 dB cut), i.start +23 (vowel).
- i|would g 16.201/16.203 s 16.184: creaky AY (per .33-.47 16.158-16.194), loudness flat -15/-17 (min -17 at 16.176);
  hi -52.5(16.164)→-58.6(16.170)→-61.8(16.188) W constriction; per rises .53→.62 from 16.200. CTC SEP 16.176-16.206
  (peak .92 16.194), W 16.200-16.218. Candidates: hi-transition midpoint 16.170-16.176, constriction 16.188, per rise
  16.200. Gold 16.202, system 16.184 — both within the ambiguity. OK.
- would|add g 16.326/16.328 s 16.358 (+30): D closure 16.298-16.310 (-22, per .30-.42, lo -0.1); D burst trn 13.0 at 16.312;
  AE from 16.316 (-16→-13→-10). CTC L 16.294, D 16.324-16.336, SEP 16.342-16.366 (peak .93 16.354) — CTC lags the burst by
  12-40 ms. → boundary ∈ [16.312, 16.318] (burst; release→vowel-initial word ambiguous). Gold +10..+15, system +40..+46
  (SEP lag after a stop release, R4).
- add|that g 16.527/16.529 s 16.518: AE to 16.464; ONE shared voiced closure for D+DH 16.470-16.540 (-25..-30, lo -0.0,
  cent 5.1, per .69-.75, 70 ms); burst trn 7.6-8.7 at 16.540-16.546. Both in closure (R8 homorganic → release to "that").
  OK. (Placement inside a shared closure is unconstrained by acoustics; old gold 12 ms before burst.)
- that|use g 16.734/16.760 s 16.726/16.756: AE decays -20(16.718)→-29(16.724); glottalized T, no burst; closure min -45 at
  16.748 (per .53-.68 — creaky); Y rise -37(16.754)→-19(16.778), lo -2.1→-0.0. R5 → boundary ≈ 16.748. Both place "that"
  end at 16.726-16.734 and "use" start 16.756-16.760 (±10 of the min). OK.
- use|a g 16.960/16.962 s 16.972/16.973: UW→S: -18(16.930, lo 0)→-34(16.948); S only 16.950-16.962 (zcr .13-.17, cent 6.6,
  hi -25.5); AH rises from 16.964 (-26→-10 at 16.972). Boundary 16.963. Gold OK, system +10 (minor).
- a|broker g 17.041/17.043 s 17.036/17.037: B voice bar 17.022-17.040 (lo -0.0, per .75-.80, -18..-23); burst trn 14.4 at
  17.040. Both at/just before the burst — OK.
- broker|or g 17.455/17.457 s 17.450: ER's R constriction hi min -63.8 at 17.436; hi rises -59.4→-55.3 (17.442-17.448) into
  AO; lo -4.6→-3.7 (17.442-17.454). Boundary 17.444-17.450. Both OK.
- or|use g 17.511/17.513 s 17.534 (+21): "or" has NO CTC letters — it sits entirely under a SEP=1.00 plateau 17.454-17.510.
  R constriction hi -60.5 at 17.504; Y: hi rises to -53.5 (17.522), loudness -8→-12 (17.510-17.522), lo → -0.1 by 17.534.
  Boundary ≈ 17.512. Gold exact; system at the SEP trailing edge (+22). R4: SEP edge is not a boundary.
- use|a g 17.712/17.713 s 17.726 (+14): S of "use" unfricated (zcr .03-.05, lo -0.0..-0.5); loudness min -45 at 17.704
  (per .33); glottal attack 17.710-17.734 (trn 1.9-5.7, glo 14.3-16.0). R5 → 17.704. Gold +8, system +22 (SEP .94 at 17.722).
- a|good g 17.810/17.812 s 17.812: "a" vowel 17.716-17.765; G voice bar 17.770-17.812 (-25..-32, lo -0.0, per .63-.78);
  burst trn 6.8-7.4 at 17.814-17.820 (zcr .13-.18, cent 7.0). Both at the burst — OK.
- good|franchise g 18.009/18.011 s 17.964/18.032: D voicing 17.932-17.974 (-19..-32, lo -0.1..-0.5), lenis D release
  trn 7.9 at 17.962; decay -44(17.980)→-48→-52→-55(18.004) (weak voicing per .40-.54); silence 18.004-18.022; F onset with
  a labial click trn 25.8 at 18.028 (hi -29.9→-20.4, zcr .03→.14). good.end ∈ [17.975, 18.004]; system at the D release
  -45 (pause test at -25 dB) — slightly early; gold at the floor OK. franchise.start 18.024-18.028: gold -15 (in silence),
  system +6. Both acceptable.
- franchise|consultant g 18.515/18.517 s 18.480/18.526: AY→Z: -34(18.450)→-45(18.474); Z frication 18.480-18.500 (zcr
  .09-.17, cent 6.4-6.8, trn 3.0-3.3), decays -47(18.504)→-55(18.516) = K closure; K burst trn 15.4 at 18.522; aspiration
  18.528-18.552 (zcr .18-.26). → franchise.end ≈ 18.506, consultant.start ∈ [18.508, 18.522]. Gold OK. System
  franchise.end -26 (cut at SEP onset, excludes the Z — R7), consultant.start +4 after burst (OK).
- consultant.end g 19.165 s 19.150: T unreleased (no trn); decay -20(19.144)→-28→-34→-43(19.162)→-49(19.168); dip -50/-51 to
  19.192; then own onset (trn 2.3 at 19.202) and 200 ms of hiss 19.202-19.406 (-38..-47, zcr .12-.26, cent 6.4-7.5, lo
  -4..-16, per .27-.59) = exhale (same profile as the 10.47 breath), floor 19.44. → consultant.end ≈ 19.165. Both OK.
- START we g 19.495 s 19.492: onset 19.486-19.490 (glo 17.1, -66→-49→-28 trn 5.8). Both OK.
- we|all g 19.599/19.601 s 19.616 (+15): IY→AO V-V, loudness flat -3/-4; hi max -41.3 (19.586, IY); lo -2.5→-5.2 across
  19.598-19.610 (midpoint 19.604); cent 6.1→6.4. SEP peak .98 at 19.610. Gold at lo-change start/midpoint, system at its
  end. Both within 16 ms — OK.
- all|use g 19.812/19.814 s 19.824/19.825: AO (hi -52→-42) → dark L hi drop -51.7(19.812)→-58.9(19.818)→-62.1(19.830, min)
  → Y hi rise -54.3(19.836)→-50.1; lo -6.1→-4.2. SEP peak .99 at 19.812. L→Y boundary (hi turning point / midpoint) ≈
  19.830-19.836. Gold = L onset (-18), system mid-L (-8). Accepted gold places "all" end at the L onset (L given to "use"?)
  — low confidence (hi as F2 proxy).
- use|different g 20.036/20.038 s 19.992/20.048: Z of "use" unfricated (zcr .03-.09, lo -0.1..-5.0), decays -19→-39(19.986)
  →-49(20.010)→-54(20.016); D closure 20.016-20.040 (-54..-56); burst trn 11.3 at 20.046, 10.1 at 20.052; affricated
  release 20.052-20.066 (zcr .25-.28, cent 7.3); vowel 20.070. use.end ∈ [19.990 (-40), 20.016 (floor)]; different.start
  ∈ [20.016, 20.046]. Gold: end in closure, start 8 ms before burst OK. System: end at -42 dB OK, start at burst OK.
- different|names g 20.351/20.353 s 20.376/20.377 (+23): glottalized T (creak per .34-.37 at 20.320-20.332), loudness min
  -34 at 20.356; N of names from 20.362 (per .66, rise -27→-15). CTC T 20.320-20.356, SEP 20.362-20.398, N 20.404.
  R5 → 20.356. Gold -4 (right); system = SEP plateau (+20).
- names.end g 20.759 s 20.736: Z unfricated (zcr .04-.08, cent 5.5-6.0), voiced decay -22(20.714)→-39(20.738)→-44 (20.746-
  20.762, per .61-.79)→-47(20.770, per .43); click trn 7.9 at 20.778 with bump -39 at 20.786; floor -60 at 20.802.
  → names.end ≈ 20.772 (end of voicing; click ambiguous, up to 20.798). Gold -13, system -36 (cut at -33 dB, R6/R7).
- START coach (H) g 20.846 s 20.844: K burst trn 3.1 at 20.842, 5.9 at 20.850. Human = burst. Both OK.
- coach|consultant g 21.159/21.211 s 21.152/21.214: CH frication 21.122-21.164 (zcr .38-.42, cent 7.8-8.1, hi -22..-31),
  fades -46(21.164, zcr .31)→-55(21.170, zcr .25)→-61(21.176, zcr .21)→-59(21.182, zcr .00) floor. R7 → coach.end ≈ 21.178.
  Gold -19, system -26 (accepted gold truncates the affricate tail). consultant.start (H) 21.211: K transients 4.7 at
  21.206, 15.5 at 21.212 — human at the main burst. System +3 OK.
- consultant|broker (broker.s H) g 21.843/21.878 s 21.814/21.874: T = glottal stop (per dip .12 at 21.814); creaky tail
  21.820-21.850 (per .36-.64, -35..-48); B closure 21.856-21.870 (-53/-54); B burst trn 11.9 at 21.874 (6.4 at 21.880).
  consultant.end ≈ 21.845 (R5 falling creak to prior word): gold OK, system -30 (cut at the glottal dip). Human
  broker.start = burst +4. System exact.
- broker.end g 22.374 s 22.368: ER decays -21(22.362)→-29→-41(22.374); voiced tail -45..-49 to 22.404 (per .36-.56); then own
  onset trn 2.5 at 22.418 and exhale hiss 22.43-22.52 (zcr .19-.27, cent 7.0-7.3, -44..-54) (R3); floor 22.63.
  → broker.end ∈ [22.374, 22.406]. Both OK.
- START that's g 22.759 s 22.762: DH pre-voicing 22.730-22.752 (-61..-56, per .45-.62, lo -0.1, cent 4.9-5.6); main rise
  -43(22.758)→-27(22.764). Onset ∈ [22.732, 22.756]. Both at the main rise (minor, R1 would say 22.732).
- that's|the g 23.106/23.108 s 23.062/23.146: TS frication 23.032-23.092 (zcr .13-.24, cent 6.5-7.4, -39..-53), ends 23.096
  (zcr .19→.02, cent 7.0→5.1); silence 23.098-23.122 (-55..-61); DH voicing onset 23.124-23.128 (per .57), weak DH
  23.128-23.146 (-56..-39), vowel 23.150 (trn 4.3). → that's.end ≈ 23.096, the.start ∈ [23.098, 23.126]. Gold OK
  (end +10, start in the gap). System that's.end -34 (mid-S, cut at SEP onset — R7), the.start +20..+22 (at vowel, R1/R8).
- the|same g 23.230/23.232 s 23.220/23.306 (+74): AH decays -12(23.200)→-30(23.218); S onset 23.220-23.224 (hi -47.6→-36.0,
  zcr .05→.11, cent 5.3→5.9); S frication 23.224-23.326 (zcr .12-.26, cent 6.5-7.3, hi -19..-35, -38..-48). CTC SEP 23.236-
  23.278 (inside S), S 23.302-23.314. Gold +9 OK; system the.end exact, same.start at the CTC S letter 84 ms into the S
  (R1 — largest single case of "fricative-initial word starts at the CTC letter").
- same|animal (both H) g 23.559/23.560 s 23.606/23.607 (+47): M (lo -1.0..-1.3, hi -61..-63) → AE: hi jump -59.2(23.552)
  →-52.0(23.558)→-46.3(23.576), trn 5.6/6.6 at 23.558/23.564, glo 16.7 at 23.552, lo -1.6→-2.4. CTC E 23.528, SEP
  23.540-23.600 (peak 1.00 23.576). HUMAN = nasal release (hi jump + transient onset). System = SEP trailing edge.
- animal.end g 24.141 s 24.134: L decays -18(24.122)→-29(24.134)→-36→-43(24.146). -40 at ~24.143. Both OK.
- START um g 24.561 s 24.564: trn 23.0 at 24.560. OK.
- um.end g 24.931 s 24.922: M decays -20(24.916)→-26→-36(24.928)→-49(24.934). Gold at -40, system -9 (OK).
- START and g 25.148 s 25.150: trn 12.4/13.8 at 25.146/25.152. OK.
- and|if (and.e H, if.s H) g 25.232/25.233 s 25.230: "and" = [ən] with a D tap (CTC D 25.204-25.216), loudness flat -5/-6;
  release into IH: trn 3.7 (25.228), 6.3 (25.234), hi -60→-57.5→-49.4, lo -0.9→-1.8. HUMAN = release. System -2. OK.
- if|you (if.e H, you.s H) g 25.331/25.333 s 25.302/25.344: IH decays -7→-27(25.294); F frication 25.300-25.328 (zcr
  .08-.19, cent 6.0-6.9, hi -34.5→-21.2); at 25.330 a SPECTRAL STEP inside the frication: hi -24.0→-15.8, cent 6.7→7.0→7.6,
  zcr .16→.19→.31 = devoiced palatal onset of Y [ç] 25.330-25.340; voiced Y from 25.344 (zcr .03, per .58, lo -0.2).
  CTC F 25.282-25.294, SEP 25.300-25.336, Y 25.324-25.354. HUMAN = the F→[ç] spectral step (25.331). System if.end at
  the F ONSET (-29: dropped the whole F — R2) and you.start at voicing (+11: dropped the devoiced Y).
  NEW: a spectral step (hi/centroid jump) inside a continuous frication is a phone boundary; use it for C|C joins.
- you|don't (you.e H, don't.s H) g 25.417/25.418 s 25.438 (+20): D voice bar 25.398-25.416 (-18..-21, lo 0, per .60-.81);
  burst trn 7.0 at 25.416, 8.0 at 25.422; vowel -9(25.428). CTC SEP peak .92 at 25.434, D 25.440. HUMAN = burst onset.
  System 20 ms after the burst (SEP/CTC-D) — R8.
- don't.end g 25.661 s 25.640: T unreleased; decay -20(25.634)→-25→-28→-36(25.652)→-44(25.658)→-50(25.676); weak voiced tail
  -52/-53 to 25.69. -40 at ~25.655. Gold OK, system -21 (cut at -25 dB).
- START communicate (H) g 26.096 s 26.098: K burst trn 12.0 at 26.096, 10.7 at 26.102 (faint pre-burst 26.084-26.090).
  Human = burst. OK.
- communicate|well g 26.677/26.679 s 26.670/26.694: glottal T — per dip .28 and loudness min -35 at 26.682; W voicing from
  26.690 (per .69, lo -0.7→-0.1). R5 → 26.682. Gold -4. System -12/+12 (splits the closure with a 24 ms gap). OK.
- well|or g 27.097/27.099 s 27.100/27.101: L→AO: hi -60.8(27.096)→-55.1(27.102), loudness -7. Both OK.
- or|like g 27.302/27.304 s 27.264 (-38/-40): AO 27.10-27.17 (lo -5.9..-6.5); R 27.18-27.255 (CTC R 27.180-27.190, lo
  -3.6→-1.9, per .58-.71); at 27.260 a sharp class change: lo -1.9→-0.6→-0.3, per .62→.76, cent 5.85→5.72 = L onset;
  steady L 27.260-27.335 (lo -0.2..-0.8, hi -60..-65, -13 dB, 75 ms); L release into AY 27.340-27.360 (ssl peak .448,
  fvel 1.58, cent 5.8→6.3, CTC L 27.340). SEP 1.00 27.250-27.270. → boundary ≈ 27.260. SYSTEM RIGHT (+4).
  Accepted gold is 40 ms inside the steady L — no acoustic event at 27.30. Accepted-gold error.
- like|the (like.e H) g 27.588/27.655 s 27.562/27.630: K closure 27.532-27.550 (-45..-48); burst trn 10.2/9.5 at
  27.556/27.562; aspiration 27.562-27.604 (zcr .11-.21, cent 6.6-7.5, -30..-51), fades 27.610-27.616 (zcr .11→.09);
  floor 27.62-27.652. HUMAN like.end 27.588 = aspiration at -41 dB (the "-40 re p99" end convention, R6) — keeps the
  release, stops ~20 ms before the floor. System -26 (at the burst; R8). the.start: DH onset 27.654-27.658 (-57→-27,
  trn 3.4); gold exact (accepted); system -25 — started in floor silence at CTC T (27.622-27.634). CTC leads the
  acoustics after a pause (also through.start 5.510).
- the|one g 27.738/27.740 s 27.748: AH→W: loudness -10→-14 (27.730), lo -3.8→-1.1 (27.730-27.742), hi min -64.6 (27.754);
  constriction max ≈ 27.742; transition midpoint ≈ 27.720. Gold at constriction, system +6. OK.
- one|you're (both H) g 27.924/27.925 s 27.908/27.909: N (lo -1.0..-1.3, hi -62..-64) → Y: hi jump -61.0(27.918)→-52.6
  (27.924), trn 2.1/4.7 at 27.918/27.924, lo -1.2→-1.8→-2.5. CTC SEP 27.882-27.906 (peak .93 27.894), Y 27.900.
  HUMAN = nasal release (hi jump + transient), as in same|animal. System -16 (SEP falling edge / Y letter).
- you're|working (both H) g 28.081/28.082 s 28.078: R→W, loudness -12/-14, lo max -1.0 at 28.070, hi min -66.0 at 28.088;
  CTC E to 28.076, SEP 28.076-28.106 (peak .92 28.094). HUMAN = between lo max and hi min (constriction complex centre).
  System -3. OK.
- working|with g 28.398/28.400 s 28.400: NG → W with no acoustic change (lo -1.7..-3.3, flat -9/-10, hi -60..-66). CTC G
  28.366-28.378, SEP peak .92 at 28.390. Both at SEP end. OK (nothing better available).
- with|find g 28.592/28.594 s 28.542/28.606: TH onset 28.536 (trn 6.5, zcr .08→.14, -52); continuous frication to 28.610.
  Spectral step at 28.576-28.578: zcr .23→.36, cent 7.2→7.7, hi -30.2→-26.2, lo -5.3→-8.2 (after a dip at 28.566-28.572);
  lo keeps falling to -16.4 at 28.596. CTC H 28.512-28.536, SEP 28.542-28.578, F 28.602-28.614. Vowel 28.614.
  → TH|F ≈ 28.576 (spectral step, as in if|you); ambiguous up to 28.596. Gold +17. System with.end at the TH ONSET (-34
  vs step; dropped the TH — R2) and find.start at the CTC F (+30).
- find|another (find.e H, another.s H) g 28.814 s 28.820: D tap (loudness only -11, per dip .69); release trn 5.4 at 28.806;
  loudness recovers -8 at 28.812. HUMAN = release +8 ms (stop release into a vowel-initial word stays with the first
  word, cut just after the transient). System +6. OK.
- another|one g 29.164/29.166 s 29.160: creaky ER (per .47-.60, loudness jitter -14..-22) → W; hi drop -56.6→-62.2 at 29.164;
  SEP peak .98 at 29.152. Both OK.
- one.end g 29.320 s 29.336: N decays -24(29.314)→-29→-34→-41(29.332)→-50. -40 at 29.331. Gold -11, system +5. OK.

### 026-0 summary (85 tokens)
Human-moved (H) evidence in this clip (all consistent with R1-R11, plus refinements):
 - nasal onset (why|not), nasal RELEASE = hi jump + transient (same|animal, one|you're), flap release (and|if);
 - voiced-closure stop: closure minimum / first transient (they're|going, you|don't); burst for voiceless (coach, consultant,
   communicate, broker);
 - V→R: transition start/midpoint (a|red) — NOT the constriction max; R→W: constriction centre (you're|working);
 - frication-internal spectral step = boundary (if|you: F→devoiced Y);
 - released final K keeps aspiration down to -40 dB (like.end), not to the floor;
 - voiced island (hum) with CTC blank≈1 excluded (you.start -318).
 - humans leave small gaps (going|through 26 ms) — they do not force contiguity.
System failure classes seen (counts approximate):
 - CTC-letter start of fricative-initial words, mid-frication: so, support, first, flag, same (+84), find, frequently(?) — R1.
 - Final fricative/affricate/aspiration truncated by the -20 dB pause test or SEP onset: this, advice (-130), guess (-80),
   franchise, that's, if (whole F dropped), with (whole TH dropped), first, support (T release -143), like — R2/R7/R8.
 - "i" cut 25-30 ms after its CTC letter, inside the vowel: i|am -57, i|guess -60, i|guess -53 — lexical/duration prior bug.
 - SEP-edge placement at V-V / sonorant joins and after stop releases: have|all, is|a, or|use, use|a, would|add,
   different|names, same|animal, you|don't, they're|going — R4.
 - stop-initial words started after the burst: process, tell, you|don't (+20) — R8.
 - word start in floor silence following early CTC emissions: through (-44), the (-25) — new rule: never start below floor+6 dB.
 - untranscribed laugh (1.68-1.91) and hum (14.30-14.41) swallowed into adjacent words — R3.
Accepted-gold errors (old system, not human-checked) found: advice.end -148, support.end -132, guess.end -63, first.end -34,
 so.start +29, support.start +32, first.start +22, or|like +40, this.end -13..-51, coach.end -19, as.start -21,
 this|is -20, (and the "and"+voice-bar convention: ends at -27 dB before a D voice bar).

## 026-1 DEEP READ (71 tokens, 20.2 s)
Clip character: NOISY — dBfl only ~25 dB during speech, vowels have hi -25..-35 (vs -50..-60 in clean clips), cent 6.1-6.6;
local-floor stats are unreliable (dBfl goes negative at 0.36). Relative, not absolute, hi/zcr cues needed here.
- START uh g 0.000 s 0.080 (+80): clip starts mid-vowel (-3/-4 dB, per .45-.66 from sample 0; no onset exists). CTC blank
  until A 0.084. System started at the first CTC A. Rule: when the clip begins inside voicing, the first word starts at 0.
- uh|you g 0.359/0.377 s 0.338/0.382: uh decays -8→-13(0.320); breathy tail 0.326-0.356 (-20..-25, per .23-.28, zcr .07-.17,
  hi -11..-19); minimum -39 at 0.362; a very strong high-frequency burst 0.368-0.378 (zcr .41-.63, cent 8.3-8.6, hi -1.6..-2.8,
  trn 5.1) = devoiced palatal onset [ç] of "you" (cf. human if|you); voicing 0.380-0.392 (per .54-.60, lo -0.4).
  → uh.end ≈ 0.360 (min), you.start ≈ 0.365 (burst onset). Gold uh.end OK, you.start +12; system -22 / +17.
- you|know g 0.545/0.547 s 0.552: nasal onset lo -1.1→-0.5→-0.1 (0.538-0.550), cent 6.2→5.9→5.5, hi -24→-32. Boundary 0.546.
  Gold exact, system +6.
- know|before g 0.785/0.789 s 0.726 (-60): OW → B: lo → -0.0 and cent → 5.2 from 0.720 (voice bar), loudness decays -10→-23
  over 0.724-0.778 (per .42-.64) = 60 ms B voice bar; burst trn 3.6/7.6 at 0.784-0.790 (hi -14.5→-8.3); vowel 0.808.
  CTC SEP 0.700-0.754 (1.00 0.718-0.748), B 0.802. Gold = burst (accepted); system = closure onset/SEP peak. Human
  convention for voiced stops (you|don't, they're|going): voice bar stays with the previous word, boundary at burst.
  → system -60 is an error by that convention (R8 refinement: voiced stop = boundary at closure END / burst).
- before|that g 1.067/1.069 s 1.080/1.081: R (lo -10..-8) → DH: loudness dip -9 at 1.072, lo -6.0→-3.5→-1.9→-1.0 (1.060-1.078),
  zcr .07→.13→.19 (1.090); DH 1.066-1.096. Boundary 1.066 (constriction onset). Gold exact; system +12 (at lo max, inside DH).
- that|they g 1.227/1.229 s 1.256 (+27): glottal T: per dip .34/.28 at 1.220/1.226, loudness -3→-12; DH of "they" voiced
  1.232-1.270 (lo -0.2..-0.4, -14); CTC T 1.202-1.214, SEP 1.220-1.256, T(H) 1.262. R5 → 1.226. Gold exact; system = SEP end.
- they|were (both H) g 1.397/1.398 s 1.392/1.393: EY→W: hi -31.5(1.378)→-37.6(1.390)→-40.1(1.396)→-42.5(1.402, min);
  lo max -0.7 at 1.396-1.402; SEP peak .98 1.396-1.408. HUMAN = constriction max (lo max / hi min), NOT the transition
  midpoint (1.389). (Contrast a|red where the human cut at the R transition start.) System -5 OK.
- were|third (were.e H, third.s H) g 1.512/1.514 s 1.538 (+25): ER decays -6→-10(1.494); devoiced ER end 1.500-1.510 (-19,
  per .16-.23, zcr .11-.14, cent 6.1-6.4, hi -14..-16); STRONG frication onset 1.512-1.518 (trn 5.0/4.6, hi -14.4→-8.4→-3.6,
  zcr .19→.37, cent 7.1→8.1); TH 1.512-1.57 (zcr .36-.69, cent 8.1-8.6 — sibilant-like TH in this noisy clip).
  CTC R 1.482-1.494, E 1.500-1.518, SEP 1.518-1.554, T 1.560. HUMAN = strong frication onset (hi jump + trn), not the
  earlier devoicing/loudness drop at 1.500 — the devoiced vowel end stays with "were". System = SEP middle.
- third|and g 1.760/1.762 s 1.784 (+24): D voice bar 1.742-1.762 (lo 0, cent 5.2, per .58-.61, -11/-12); release trn 4.0/6.3
  at 1.766/1.772; AH 1.772+. CTC D 1.730-1.754, SEP 1.760-1.784 (peak .97 1.772), A 1.784. Release+8 convention (human
  find|another) → ~1.772. Gold -10 (closure end), system +12 (SEP end / A letter). Both ~OK.
- and|twelve g 1.866/1.868 s 1.882/1.883: N decays -8→-21(1.860); D/T closure 1.848-1.876 (voicing dies per .25→.04, -30..-38);
  T burst trn 15.4 at 1.878; aspiration 1.884-1.902 (zcr .25-.35). Gold in closure OK; system +4 after burst (marginal).
- twelve|they g 2.241/2.243 s 2.224/2.225 (-18): L (lo -7.2→-0.3 by 2.216) → V frication (hi -24→-16.1 at 2.222-2.240, zcr .09-.13,
  loudness min -16/-17 at 2.234-2.240) → DH (zcr .13→.04 and hi -18→-22 at 2.246-2.252, per .53-.55) → vowel 2.264.
  CTC E 2.192-2.216, SEP 2.222-2.240, T(H) 2.240-2.258. V|DH ≈ 2.246 (end of V frication peak). Gold -4, system -22 (SEP onset).
- they|were (both H) g 2.354/2.355 s 2.375/2.377 (+22): EY→W: hi -34.3(2.352)→-36.2→-40.4(2.370)→-42.2(2.376, min); lo local
  max -2.5 at 2.352, -1.9 at 2.382; loudness -5→-8. SEP 2.346-2.388 (peak .94 2.370), W 2.382. HUMAN = 2.354 = transition
  START here, whereas the same speaker/word pair at 1.397 was placed at the constriction MAX. Human glide placement
  scatters ±15 ms around the hi-transition MIDPOINT (1.389 vs human 1.397; 2.365 vs human 2.354; a|red 11.315 vs 11.306).
  → R4 refined: V→glide/liquid = midpoint of the hi (F2/F3 proxy) transition. System at constriction max (+11 vs midpoint).
- were|third (both H) g 2.462/2.463 s 2.494/2.495 (+32): ER devoicing 2.444-2.456 (per .44→.28, -11..-14); strong frication
  onset 2.456-2.462 (trn 5.4, zcr .15→.35, hi -14.9→-9.4, cent 6.8→7.7). HUMAN = strong frication onset (same as 1.512).
  System = SEP plateau (2.492-2.510).
- third|and g 2.725/2.727 s 2.761/2.763 (+36): D closure 2.712-2.742 (voice bar lo 0, -12..-14); release trn 3.5/6.0 at
  2.742/2.748; then "and" = nasal [ən] (lo -0.0, cent 5.1-5.3 continuing to 2.79). CTC D 2.700-2.718, SEP 2.742-2.754,
  A 2.760-2.790. Release+8 → ~2.750. Gold -24 (mid-closure), system +12. Both off; system closer.
- and|nine g 2.879/2.881 s 2.859/2.861 (-20): "and"'s N and "nine"'s N form ONE geminate nasal 2.79-2.886 (lo -0.0..-0.1, flat
  -5/-6, no internal cue); N releases into AY at 2.882-2.888 (trn 2.8/8.5, lo -0.1→-0.7→-1.8, cent 5.4→5.8→6.2). CTC D
  2.828-2.834, SEP 2.840-2.876 (peak .96 2.870), N 2.882. Gold = release (all the nasal to "and"); system = SEP rise.
  No acoustic evidence either way; CTC D/SEP suggest ~2.84-2.87. Ambiguous (geminate).
- nine|they (both H) g 3.142/3.143 s 3.099/3.101 (-42): AY (lo -5.6..-8.3, cent 6.6-7.1) to 3.098; AY→N transition 3.104-3.116
  (lo -3.0→-0.8); N 3.122-3.150 (lo -0.2..-0.0, cent 5.4-5.6, per .43-.66); DH closure min -17 at 3.152; DH release trn 4.2
  at 3.158. CTC E 3.068, SEP 3.098-3.122, T(H) 3.122-3.134 (on the N!), H 3.140-3.170. HUMAN = 3.142, inside the N, 8 ms
  before the N/DH change (3.150). System -42 = SEP onset, before the N even starts (would give the N to "they").
- they|were (both H, 3rd occurrence) g 3.237/3.238 s 3.249/3.251 (+13): hi -27.1(3.206)→-37.6(3.224); loudness -5→-8(3.236)→-11
  (3.254 min); lo max -0.8 at 3.254. HUMAN at the loudness-transition midpoint (3.236), between hi midpoint (3.215) and
  constriction max (3.254). Three "they|were" human placements: 1.397 / 2.354 / 3.237 relative to the transitions vary
  ±15 ms — glide joins have inherent ±15 ms human tolerance; any point inside the transition is acceptable.
- were|in (both H) g 3.368/3.369 s 3.371/3.373: ER→IH with no measurable change (loudness -3/-5, lo -1.4..-1.7, hi -30..-35,
  fvel ~0); CTC SEP 3.342-3.396 (peak .99 3.372-3.384). Human 3.368 ≈ SEP centre. System +4. OK.
- in|tough g 3.503/3.521 s 3.503/3.505: N decays to 3.502 (lo 0); T closure 3.506-3.518; burst trn 5.3/9.9 at 3.514/3.520;
  aspiration 3.526+ (zcr .47-.73). Both OK (gold at burst, system at closure start).
- tough.end g 3.881 s 3.874: F 3.844-3.876 (zcr .51-.62, cent 8.3-8.5) fades -34(3.884)→-40→-47(3.900)→-51(3.908) into a noisy
  background (-47..-57 with zcr .05-.44 of its own). F end ≈ 3.905. Gold -24, system -31 (R7 truncation).
- START tough g 3.996 s 3.998: T burst trn 14.7 at 3.996. OK.
- tough.end g 4.300 s 4.294: F -25(4.294)→-29→-35→-39(4.312, zcr .33)→-42(4.318, zcr .12); end ≈ 4.315. Gold -15, system -21 (R7).
- START situations g 4.731 s 4.738: background -49..-53 (zcr .14-.26); S rises -44(4.724)→-41(4.730, trn 4.5)→-34(4.736, zcr .37).
  Onset ≈ 4.722. Gold +9, system +16 (late).
- situations|and (both H) g 5.488/5.489 s 5.476 (-13): Z very loud (-6..-9 dB, zcr .71-.79, cent 8.7-8.8, hi 0) to 5.468;
  crossfade 5.474-5.498: zcr .63→.51→.34→.16→.12, hi -0.6→-2.5→-5.8→-12.3→-18.3, per .18→.26→.34→.64. HUMAN = crossfade
  midpoint (zcr/hi halfway, 5.484-5.490). System at crossfade start. RULE: fricative→vowel = midpoint of the crossfade.
- and|so g 5.589/5.591 s 5.606 (+16): N (lo -0.1, D elided) to 5.582; drop -11 at 5.588; S onset 5.594-5.600 (trn 5.8,
  zcr .09→.26, hi -15→-5). Boundary 5.594. Gold -4, system +12 (R1, late by 12).
- so|he's (so.e H, he's.s H) g 5.768/5.769 s 5.756 (-12): HH between vowels: per dip .68/.67 at 5.760-5.766, loudness dip -4/-5
  5.760-5.772, hi -33→-24 (5.754-5.766), lo -4.5→-1.0 rising. SEP peak .97 at 5.754, H letter 5.784. HUMAN at the per
  minimum / end of the hi rise (R4 /h/ = periodicity dip confirmed). System = SEP peak (-12).
- he's|really g 5.949/5.951 s 5.940/5.941 (-9): Z of he's very strong (zcr .53-.71, cent 8.5-8.7, hi -0.9..-2.0, lo -35..-37,
  -3..-6 dB) to 5.938; Z→R crossfade 5.944-5.962: zcr .57→.44→.19→.07, hi -1.6→-3.9→-12.4→-20.8, lo -16→-6→-0.7, per
  .21→.48→.65; loudness min -17 at 5.950. CTC SEP 5.920-5.940, R 5.940+. Crossfade midpoint ≈ 5.953 (fricative→sonorant
  rule, as situations|and). Gold -3 (at the loudness min) OK; system -12 (SEP end).
- really|good g 6.190/6.192 s 6.182/6.183: IY (lo 0, per .58-.62) → G: per .50→.22→.03 (6.180-6.192), loudness -20→-26→-28
  (min 6.192), glo 21.1 at 6.192; short voiceless closure 6.184-6.196; burst trn 8.6/7.3 at 6.198/6.204; release frication
  6.198-6.216 (zcr .24-.32, cent 7.8). CTC SEP 6.162-6.200, G 6.200. Both inside the closure (R8): gold at the deepest point,
  system at the closure onset (-8 vs gold, -16 vs burst). OK.
- good|a- (both H) g 6.591/6.592 s 6.464/6.536 (-127/-56): "good" vowel to 6.390 (CTC D 6.38-6.40); D voice bar 6.402-6.456
  (lo 0, cent 5.1-5.3, per .53-.66, -11..-18); voicing dies 6.462-6.492 (per .37→.00, -21..-30); FLOOR 6.498-6.528 (-37..-49,
  dBfl 5..-8, only the clip's HF background); burst trn 4.7/14.5 at 6.534/6.540; release frication 6.540-6.570 (zcr .36-.57,
  cent 8.0-8.3, hi -3..-8, -15..-25); voicing onset 6.576-6.582 (per .59→.66, lo -3.1→-1.1, zcr .18→.06); vowel -4 at 6.588.
  CTC blank .96-1.00 from 6.466 over the whole fragment (no letters for "a-"). HUMAN = vowel onset: the whole 140 ms D
  (voice bar + silent closure + burst + 30 ms frication release) stays with "good" (same as find|another: stop release
  into a vowel-initial word belongs to the first word). The 30 ms floor stretch is a CLOSURE, not a pause (R6/R8).
  System: good.end in the voice bar (dropped closure + release), a-.start AT the burst (gave the release to the fragment).
  RULE: final stop + vowel-initial next word → boundary at the voicing onset after the release (not at the burst).
- a-|across (a-.e H) g 6.726/6.727 s 6.694/6.736 (-32/+9): fragment vowel 6.578-6.688 (per .30-.69, -4..-9); drop -17→-25→-32
  (6.688-6.700); noise 6.700-6.730 (zcr .34-.47, cent 7.7-8.0, hi -4..-6, lo -7..-15, per .13-.42, -26..-33) = the fragment's
  aspirated/breathy offset ([k]-like, "ac-"); rise into across's AH: trn 2.0/2.6 at 6.724/6.730, -17 at 6.736, -7 at 6.742
  (trn 5.5). CTC blank .99 throughout. HUMAN = end of the noise / start of the rise (6.726): the noise belongs to the
  fragment (R2). System a-.end = noise onset (-32, dropped it, 42 ms false gap); across.start +9 (in the rise). OK start.
- across|the g 7.143/7.145 s 7.112/7.112 (-31/-32): S of across very strong (zcr .74-.87, cent 8.8, hi -0.1, lo -26..-35) to
  7.116; 7.118-7.134 frication continues (zcr .70→.59, hi -0.4..-1.3) while lo rises -27.1→-24.6→-21.7→-17.1→-13.3→-9.2 = voicing
  under frication = DH assimilated to the S ([sð] → voiced sibilant-like DH), loudness dip -14 at 7.132-7.136; frication
  collapses 7.136-7.144 (hi -3→-19, zcr .52→.13, per .30→.50) into the vowel. CTC SEP peak .98 at 7.112, T(H) 7.120-7.140,
  H 7.140-7.160. S|DH ≈ 7.118 (lo rise onset = CTC T onset). System -6 RIGHT; accepted gold +25 = vowel onset (gives the
  whole DH to "across"). Accepted-gold error suspected (R1: word-initial DH belongs to "the").
- the|board g 7.240/7.242 s 7.216 (-24/-26): "the" vowel 7.140-7.166 (-1..-3, per .53-.60, lo -1..-2.5); closure onset
  7.168-7.178 (-3→-14, lo → 0, hi -32→-43); B VOICE BAR 7.178-7.254 (lo 0, cent 4.9-5.2, per .63-.69, -12..-18, 76 ms);
  burst trn 6.6/5.8/13.3/9.8 at 7.254-7.266; vowel 7.270+. CTC E 7.180-7.200 (on the voice bar), SEP 7.200-7.240 (peak .97
  7.230), B 7.240-7.260. Voiced-closure convention (know|before, they're|going, you|don't: voice bar to the previous word,
  boundary at closure minimum/first transient) → 7.252. Gold -12 (late voice bar, OK by R8); system -36 = SEP centre.
- board|in g 7.532/7.534 s 7.540: vowel to 7.476 (CTC D 7.460-7.480 on the vowel end); D tap: -5→-13 (7.476-7.492), plateau
  -13/-14 7.492-7.512 (lo -0.1..-0.5, cent 5.3-5.6, per .38-.61); release trn 2.4/5.4/4.4/3.0 at 7.508-7.520, hi -35→-25;
  IH vowel -10 (7.520) → -7 (7.532). SEP 7.500-7.556 (peak 1.00 7.532). Release+8 convention (find|another) → 7.520.
  Gold +12 (loudness plateau start = SEP peak), system +20 (SEP falling edge). Minor.
- in|that g 7.709/7.711 s 7.706/7.707: loud N (-5, lo -0.1, cent 5.4, hi -35..-38, per .66-.71) → dental DH: glo 11→17→21
  (7.704-7.716), flat -7.4→-4.6 and hi -37.9→-26.4 (7.710-7.722), trn 4.0 at 7.722; CTC SEP to 7.720, T(H) 7.720. N|DH ≈
  7.712. Both OK.
- that.end g 7.935 s 7.926 (-9): T release aspiration 7.908-7.936 (zcr .23-.45, cent 7.7-8.3, hi -3..-10, -18..-33); ends
  7.936-7.944 (zcr .27→.06, hi -4.8→-15.3, -33/-34). Gold = aspiration end (R2 OK); system inside the aspiration (minor).
  Pause 7.944-8.136 = separate events, all CTC blank 1.00: dip -48 (dBfl 2) at 7.952; low hum 7.960-7.980 (per .59-.72,
  cent 3.9-4.4 = <100 Hz, -33..-36); second low event 8.008-8.064 (-32..-40, per .42-.66, trn 5.1 at 8.040); inhalation
  8.072-8.128 (zcr .45-.66, cent 7.9-8.5, hi -0.8..-3.3, -38..-45). All excluded by both (R3). OK.
- START and g 8.139 s 8.138: onset trn 2.1/2.8 at 8.136/8.144, -37→-17 dB. Both OK.
