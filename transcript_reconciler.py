"""
Word-sequence reconciliation: merge TWO independently-derived draft transcripts of the
same audio into a single corrected, Pulsar-guideline-compliant word sequence per clip:
  1. Whisper (Groq) -- accurate spelling, but drops disfluencies (autoregressive LM bias).
  2. Our own wav2vec2 CTC acoustic stream -- no language model, can't fabricate content,
     but garbles spelling. Now annotated with per-word acoustic CONFIDENCE (see below).

History: a 3-way version adding CrisperWhisper 2.0 verbatim mode as a third source was
tried and measured WORSE (10.26% WER vs 8.28% for the 2-way version) -- CrisperWhisper
makes its own independent judgment calls about fillers/cutoffs that sometimes conflicted
with, rather than reinforced, what sources 1+2 agreed on, adding noise in exactly the
hardest category rather than signal. Reverted to 2-way for that reason.

NEW in this version -- confidence annotation: neither Whisper nor a plain CTC decode ever
expose a per-word confidence signal, which is exactly why "((word))"/"(())" (Pulsar's
guessed/unclear-speech markers) are hard to reconcile toward -- every source always emits
its single best guess, confident or not, so the reconciler has no way to tell a solid
guess from a shaky one. Confirmed concretely on our golden set: at one gold "((ever))"
position, the CTC pass genuinely did output "ev" (a plausible cutoff of "ever") with
0.54 confidence vs its neighbours' 0.9+, but that low-confidence signal was previously
discarded after greedy decoding and the reconciler never saw it. CTC words below 0.75
confidence are now prefixed with "¿" in the text handed to the reconciler, with guidance
to treat them as unclear/guessed-word candidates rather than solid text.

Deliberately PRE-LABEL-INDEPENDENT: this pipeline must work on raw audio alone, without
requiring an externally-provided draft transcript. Both sources used here (Whisper via
Groq, and the wav2vec2 CTC stream) are computed by us directly from the clip audio.

This step exists because ForcedAligner.align() force-aligns EXACTLY the word sequence
it is given across the ENTIRE clip duration: if that sequence is missing words (e.g.
Whisper's dropped disfluencies) or has extra/wrong words, the acoustic aligner has no
way to know and will silently distribute time across the wrong word count, corrupting
boundaries for the whole clip -- not just locally around the error. Getting the word
SEQUENCE right is a precondition for boundary precision, not a separate concern.

No per-clip or per-word hardcoding: this module only encodes the general, empirically
observed failure modes of the two sources (see docstring above) and the general Pulsar
tokenization rules, then asks an LLM to apply that judgment per clip.

NEW in this version -- large-model CTC + contested-gap scanning: switched the CTC pass
from WAV2VEC2_ASR_BASE_960H to WAV2VEC2_ASR_LARGE_LV60K_960H (60k-hour pretraining vs
960h) for text extraction specifically (the live boundary-alignment pipeline stays on the
base model -- swapping it there was tested separately and made boundary precision worse,
since the hand-tuned snapping heuristics are calibrated to base's specific quirks; this is
a one-off signal-extraction pass, not a pipeline swap). Verified directly that the base
model shows ~100% blank confidence in most truncation-fragment gaps (nothing to recover),
while the large model shows meaningfully more raw signal in the same gaps. We now scan
every blank-argmax gap for a "runner-up" letter probability above a threshold (0.3) and
surface it as a bracketed hint "⟪<letters>⟫" at that position in the CTC text (distinct
from the "¿" low-confidence-WORD marker, since a gap has no word at all, just a letter
hint). Caveat, confirmed empirically: only about 1 in 3 manually-checked truncation
gaps produced a clean, correctly-isolated hint (clip 4's "r-"); the other two produced no
signal at all, and some hints across the dataset are likely noise from ordinary
co-articulation at word boundaries rather than genuine truncations. Treat these as
speculative candidates only, not confirmed content -- the prompt says so explicitly.
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

PULSAR_TOKENIZATION_RULES = """
PULSAR TOKENIZATION RULES (verbatim word-level transcription):
- Lowercase, no punctuation except: apostrophes in real contractions (don't, it's), and
  a hyphen at the exact point of truncation in a cut-off word (elev-, see-).
- Hyphenated words/numbers/backchannels are split into separate tokens with hyphens
  stripped: "eighty-seven" -> "eighty" "seven"; "coca-cola" -> "coca" "cola";
  "part-time" -> "part" "time"; "uh-huh" -> "uh" "huh"; "mm-mm" -> "mm" "mm".
- Backchannels/filled pauses use ONLY these standard spellings (never substitute a
  similar-sounding one): "mm hm" (agree, mouth closed), "uh huh" (agree, mouth open),
  "hmm" (thinking -- even if it sounds like "mmm"), "uh" (open hesitation), "um"
  (closed/nasal hesitation), "mm mm" (disagree, mouth closed), "nuh huh" (disagree,
  mouth open), "oh" (realization), "ooh" (impressed). Each component is its own token.
- STUTTERS AND REPETITIONS ARE TRANSCRIBED VERBATIM, EVERY TIME -- never collapsed to
  one occurrence. A cut-off restart keeps a hyphen on every truncated attempt except the
  final complete word: "el-" "el-" "elevator". A repeated whole word gets no hyphen and
  every repetition is its own token: "the" "the" "the" (three tokens, not one).
- Letter sequences (each letter its own token: "a" "b" "c") vs acronyms pronounced as a
  word (one token: "opec", "nasa") -- do not confuse the two.
- Informal contractions transcribed as written when that's how they're said: gonna,
  wanna, gotta, gimme, lemme, whatcha, dunno, gotcha, kinda, y'all, 'til, 'er, 'em,
  c'mon, 'cause. Anything else not a standard contraction: spell out the full words
  ("there're" -> "there" "are").
- Mispronunciations: transcribe the speaker's clearly INTENDED word, not a phonetic
  spelling of the slip (intended "visit", said "vitis" -> write "visit").
- Guessable-but-unclear word -> "((word))" (its own token). Fully unintelligible
  stretch -> "(())" (its own token). Never invent words that aren't audible.
- Proper names (people, places, brands, teams) are not dictionary words -- an ASR system
  will frequently mishear/misspell them; use context to recover the intended spelling.
"""

TRANSCRIPT_QUIRKS_NOTE = """
WHY YOU ARE GIVEN TWO DIFFERENT DRAFT TRANSCRIPTS OF THE SAME AUDIO, AND HOW THEY
TYPICALLY FAIL:

1. WHISPER TRANSCRIPT: a general-purpose autoregressive ASR model trained to produce
   clean, readable text. It is usually far more accurate on WORD CHOICE AND SPELLING,
   but it is trained to smooth speech and will systematically DROP disfluencies it
   treats as noise: stutters, restarts, repeated words, filler words (um/uh), and
   truncated fragments often vanish entirely rather than being transcribed. It also
   silently normalizes informal speech into its written-standard form (e.g. expanding a
   contraction, or "cleaning up" a stutter), which Pulsar's tokenization rules do not
   want -- Pulsar wants the verbatim spoken form. Because it's a language model, it can
   also occasionally invent plausible-sounding words that were not actually said,
   especially near the very start or end of a clip.

2. WAV2VEC2 CTC ACOUSTIC STREAM: a plain discriminative frame-by-frame classifier run
   directly on the audio, with NO language model and NO smoothing. It records essentially
   every acoustic event including stutters, restarts, repeated words, and filler words
   that Whisper drops -- if a sound was made, it tends to show up here. Its weakness is
   spelling/word-choice: it has no notion of real words, dictionaries, or grammar, so it
   frequently renders a real word as a garbled or nonsense-looking sequence of letters,
   especially for proper nouns and short function words, and it has no punctuation or
   capitalization at all. Unlike Whisper it cannot fabricate content that wasn't said --
   if it's missing entirely, that's evidence the sound genuinely wasn't there.

IMPORTANT -- source 2 confidence markers: a word in the CTC stream prefixed with "¿"
(e.g. "¿ev") is one CTC itself was not confident about (its own acoustic model gave it a
low probability, well below its typical ~0.9+ for a clear word). This is NOT a Pulsar
notation -- it's telling you where the acoustic evidence itself is weak. Neither source
can ever output "I'm not sure" on its own; each always emits its single best guess,
confident-sounding or not, which is exactly why the tokenization rules' "((word))"/"(())"
markers are so easy to under-use in reconciliation -- there is no direct signal for
genuine unclear speech unless you use this one. Treat a "¿"-marked word as a real
candidate for "((word))" (if it's a recognizable partial word / plausible guess, per
context) or "(())" (if Whisper also has nothing coherent there and no plausible word can
be reconstructed) rather than either dropping it silently or accepting it as solid,
confident text.

IMPORTANT -- source 2 gap hints: a bracketed tag like "⟪r⟫" appearing BETWEEN two CTC
words marks a spot where CTC's default (blank/silence) decoding won, but a real letter
had non-trivial competing probability there -- a candidate for a brief truncated-word
fragment that the main decode missed entirely (e.g. a genuine "r-" cutoff sitting between
two instances of "read"). This is speculative, not a confirmed word: roughly 2 out of 3
such hints checked by hand turned out to be nothing (ordinary word-boundary noise), so do
NOT treat a "⟪⟫" hint as solid evidence on its own. Only act on it (typically by adding a
hyphenated truncation token matching those letters, e.g. "⟪r⟫" -> "r-") when the
surrounding context makes a cut-off restart plausible there (e.g. the same or a similar
word repeats immediately after) -- otherwise ignore it.

YOUR JOB: reconstruct the single, correct, verbatim, Pulsar-compliant token sequence for
each clip. As a general rule: trust the CTC stream for WHETHER a disfluency, cut-off
restart, repeated word, or filler token exists at all (don't silently drop something the
CTC stream shows just because Whisper dropped it); trust Whisper for the correct SPELLING
of a word when the two sources clearly refer to the same word in the same position. When
the CTC stream shows a garbled sequence with no correspondence in Whisper at all, use it
to recover an attested word/name via context and phonetic resemblance rather than
inventing one from nothing; if no plausible word can be reconstructed from the garbled
CTC text, treat that stretch as unclear speech per the tokenization rules rather than
guessing freely.
"""

OUTPUT_INSTRUCTIONS = """
OUTPUT: For each clip, output ONLY the corrected sequence of word tokens, in speaking
order, as a JSON list of lowercase strings (no timestamps -- those are re-computed by a
separate forced-alignment step from the audio, so do not spend effort estimating them).
Format your entire response as a single JSON object mapping clip index (as a string) to
that list, and nothing else -- no prose, no markdown fences.
Example: {"0": ["i", "um", "think", "uh", "yes"], "1": ["the", "the", "cat", "ran"]}
"""


def build_clip_prompt(clip_index, whisper_text, ctc_text):
    return (
        f"--- Clip {clip_index} ---\n"
        f"Whisper transcript: {whisper_text}\n"
        f"CTC acoustic stream: {ctc_text}\n"
    )


def build_full_prompt(clips_payload):
    """clips_payload: list of (clip_index, whisper_text, ctc_text)."""
    parts = [PULSAR_TOKENIZATION_RULES, TRANSCRIPT_QUIRKS_NOTE]
    parts.append("\nCLIPS TO RECONCILE:\n")
    for ci, wh, ctc in clips_payload:
        parts.append(build_clip_prompt(ci, wh, ctc))
    parts.append(OUTPUT_INSTRUCTIONS)
    return "\n".join(parts)


CONF_THRESHOLD = 0.75      # CTC words below this get flagged with the "¿" low-confidence marker
GAP_HINT_THRESHOLD = 0.3   # contested-gap hints below this are dropped as too noisy to surface


def _ctc_text_with_confidence_and_gaps(acoustic_words, contested_gaps):
    """Interleave words and gap hints in time order. Words below CONF_THRESHOLD get a
    "¿" prefix; gaps at/above GAP_HINT_THRESHOLD are inserted as "⟪letters⟫" tokens at
    their position."""
    items = []
    for w in acoustic_words:
        word = w["word"].upper()
        if w.get("confidence", 1.0) < CONF_THRESHOLD:
            word = "¿" + word
        items.append((w["start"], word))
    for g in contested_gaps:
        if g.get("peak_confidence", 0.0) >= GAP_HINT_THRESHOLD:
            items.append((g["start"], f"⟪{g['letters'].upper()}⟫"))
    items.sort(key=lambda x: x[0])
    return " ".join(text for _, text in items)


def load_clip_texts():
    """Returns list of (clip_index:int, whisper_text:str, ctc_text:str) for all clips
    currently in audio/, using output/ordered_clips.json, output/groq_transcriptions.json,
    and the CTC stream. Prefers the large-model extraction with confidence + contested-gap
    hints (output/wav2vec2_large_with_gaps.json), falling back to the base-model
    confidence-only extraction, then the plain base-model text, in that order. No
    pre-label file is read."""
    ordered = json.load(open(os.path.join(ROOT, "output", "ordered_clips.json"), encoding="utf-8"))
    groq = {g["clip_index"]: g for g in json.load(open(os.path.join(ROOT, "output", "groq_transcriptions.json"), encoding="utf-8"))}

    large_gaps_path = os.path.join(ROOT, "output", "wav2vec2_large_with_gaps.json")
    conf_path = os.path.join(ROOT, "output", "wav2vec2_acoustic_with_confidence.json")
    plain_path = os.path.join(ROOT, "output", "wav2vec2_acoustic_transcriptions.json")

    if os.path.exists(large_gaps_path):
        mode = "large_gaps"
        src_path = large_gaps_path
    elif os.path.exists(conf_path):
        mode = "confidence"
        src_path = conf_path
    else:
        mode = "plain"
        src_path = plain_path
    w2v = {d["clip_index"]: d for d in json.load(open(src_path, encoding="utf-8"))} if os.path.exists(src_path) else {}

    out = []
    for c in ordered:
        ci = c["index"]
        wh_words = [w["word"] for w in groq.get(ci, {}).get("words", [])]
        wh_text = " ".join(w for w in wh_words if w)
        entry = w2v.get(ci, {})
        if mode == "large_gaps":
            ctc_text = _ctc_text_with_confidence_and_gaps(
                entry.get("acoustic_words", []), entry.get("contested_gaps", []))
        elif mode == "confidence":
            ctc_text = _ctc_text_with_confidence_and_gaps(entry.get("acoustic_words", []), [])
        else:
            ctc_text = entry.get("raw_acoustic_text", "")
        out.append((ci, wh_text, ctc_text))
    return out


if __name__ == "__main__":
    clips = load_clip_texts()
    prompt = build_full_prompt(clips)
    out_path = os.path.join(ROOT, "output", "reconcile_prompt_v5.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"Wrote {out_path} ({len(prompt)} chars, {len(clips)} clips)")
