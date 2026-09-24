"""
Generate the LLM prompt and input payload for all 11 clips.
Combines Pulsar rules, pre-label references, and Groq Whisper word timestamps.
"""
import os
import json

OUTPUT_DIR = "f:/BB/ETN-SC/pulsar_auto/output"
comparisons_path = os.path.join(OUTPUT_DIR, "clip_comparisons.json")
comparisons = json.load(open(comparisons_path, encoding="utf-8"))

n_clips = len(comparisons)

SYSTEM_PROMPT = f"""# PULSAR AUDIO ANNOTATION & TOKENIZATION AGENT

You are an expert audio transcription annotator for the Pulsar alignment project.
Your task is to review {n_clips} audio clips and output the perfected word-level tokens and timestamps for each clip, strictly adhering to the Pulsar guidelines.

## SOURCE DATA PROVIDED FOR EACH CLIP:
For each clip, you are given:
1. Pre-label Draft: An earlier ASR output that captured stutters, truncations (e.g., "de-", "see-"), repetitions, and filler words.
2. Groq Whisper v3 Transcript: High-accuracy phonetic transcript from Whisper-large-v3.
3. Groq Word Timestamps: Millisecond-accurate word start and end times (in seconds).

## TOKENIZATION & FORMATTING RULES:
1. Spoken Form & Lowercase:
   - Transcribe strictly what is spoken, in lowercase. Example: "billy eichner", "zuckerberg", "mickey mouse clubhouse".
2. Punctuation:
   - Strip all punctuation (periods, commas, exclamation marks, question marks, colons, quotes).
   - EXCEPTIONS:
     - Apostrophes in valid contractions: "that's", "i'd", "don't", "he's", "it's", "that'll".
     - Hyphens at the exact point of truncation / cut-off words: "de-", "see-", "elev-", "li-".
3. Hyphenated Words:
   - Treat as separate lexical items. Split hyphens:
     - "eighty-seven" -> "eighty", "seven"
     - "part-time" -> "part", "time"
     - "coca-cola" -> "coca", "cola"
4. Backchannels & Filled Pauses:
   - Standard spellings only:
     - Agreeing (mouth closed): "mm hm" -> split into 2 tokens: "mm", "hm"
     - Agreeing (mouth open): "uh huh" -> split into 2 tokens: "uh", "huh"
     - Thinking / considering: "hmm" (even if audio sounds like "mmm", write "hmm")
     - Hesitations: "uh", "um"
     - Disagreeing (mouth closed): "mm mm" -> split: "mm", "mm"
     - Disagreeing (mouth open): "nuh huh" -> split: "nuh", "huh"
     - Realization / surprise: "oh"
     - Impressed: "ooh"
   - Hyphens are NOT allowed in backchannels ("uh-huh" must be split into "uh" and "huh").
5. Letter Sequences & Acronyms:
   - Individually pronounced letters get separate segments: "a", "b", "c" (no periods).
   - Acronyms pronounced as a word stay single: "opec".
   - "ok" or "okay" is a single token.
6. Numbers:
   - Transcribe as spoken words: "three zero six" or "three hundred and six"; "fifth".
7. Contractions:
   - Allowed informal contractions: "gonna", "wanna", "gotta", "gimme", "lemme", "whatcha", "dunno", "gotcha", "kinda", "y'all", "'til", "'er", "'em", "c'mon", "'cause".
   - Non-standard/nested contractions must be expanded: "there're" -> "there are", "i'd've" -> "i'd have", "whaddya" -> "what do you".
8. Stutters, Restarts, & Truncations:
   - Transcribe every audible repetition.
   - Cut-off words take a hyphen: "el-", "el-", "elevator".
   - Whole-word repetitions do NOT take a hyphen: "the", "the".
   - If pre-label shows stutters/cutoffs (e.g., "his his um his uh his shooty wheelchair", "he see- see- seem- seems"), keep and segment each repetition!
9. Proper Names:
   - Check against context and transcribe in lowercase: "billy eichner", "zuckerberg", "paul manafort", "delano", "graham", "io9", "gizmodo".
10. Unclear Speech:
    - If reasonably guessable: "((word))"
    - If completely unintelligible: "(())"

## TIMESTAMP ALIGNMENT RULES:
1. Every token must have "start" and "end" in seconds (relative to the clip start, 0.0s).
2. Use Groq Whisper's timestamps as the primary source of truth for boundaries.
3. When Groq combines multiple tokens (or when splitting a word like "eighty-seven" into "eighty" and "seven", or adding stutter tokens), subdivide the time interval proportionally:
   - Example: if "eighty-seven" spans [1.00, 1.80], assign "eighty" [1.00, 1.40] and "seven" [1.40, 1.80].
4. Segments must NEVER overlap (token[i].end <= token[i+1].start). If needed, leave at least 0.005s gap.
5. Duration of any segment must be at least 0.050s (50 ms).

## OUTPUT FORMAT:
Output ONLY a valid JSON object mapping clip index ("0" to "{n_clips - 1}") to a list of token objects:
```json
{{
  "0": [
    {{"text": "i'd", "start": 0.020, "end": 0.220}},
    {{"text": "i", "start": 0.250, "end": 0.380}},
    {{"text": "find", "start": 0.380, "end": 0.720}}
  ],
  "1": [ ... ],
  ...
  "{n_clips - 1}": [ ... ]
}}
```
"""

prompt_file = os.path.join(OUTPUT_DIR, "pulsar_llm_prompt.txt")
with open(prompt_file, "w", encoding="utf-8") as pf:
    pf.write(SYSTEM_PROMPT.strip())

input_file = os.path.join(OUTPUT_DIR, "pulsar_llm_input.txt")
with open(input_file, "w", encoding="utf-8") as inf:
    inf.write("=== CLIPS TO PROCESS ===\n\n")
    for c in comparisons:
        inf.write(f"--- CLIP {c['clip_index']} ({c['filename']}) ---\n")
        inf.write(f"Pre-label Draft:\n{c['pre_label_text']}\n\n")
        inf.write(f"Groq Whisper Transcript:\n{c['groq_text']}\n\n")
        inf.write("Groq Word Timestamps (seconds):\n")
        words_str = ", ".join(f"{w['word']} [{w['start']:.2f}-{w['end']:.2f}]" for w in c["groq_words_with_timing"])
        inf.write(f"{words_str}\n\n")
        inf.write("=" * 60 + "\n\n")

print(f"Generated:")
print(f"  Prompt: {prompt_file}")
print(f"  Input:  {input_file}")
