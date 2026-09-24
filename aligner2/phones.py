"""
Transcript tokens -> phone label ids of the pretrained phoneme model (facebook/wav2vec2-xlsr-53-espeak-cv-ft),
using espeak through phonemizer -- the same tool that produced the model's training labels. Runs in the
Modal engine (espeak is installed there).

Phrases are phonemized whole, so function words get their running-speech (reduced) forms; a phrase whose
output word count does not match its tokens falls back to word-by-word. Wildcards (WILD): '(())', tokens
without letters, one-letter cut-offs (espeak would read them as letter names).
"""
import re

WILD = -1
MODEL = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"
_VOCAB = None


def vocab():
    global _VOCAB
    if _VOCAB is None:
        import json
        from huggingface_hub import hf_hub_download
        _VOCAB = json.load(open(hf_hub_download(MODEL, "vocab.json"), encoding="utf-8"))
    return _VOCAB


def _clean(tok):
    w = re.sub(r"^\(\((.*)\)\)$", r"\1", tok.strip())
    cutoff = w.endswith("-")
    w = w.rstrip("-")
    if not re.search(r"[A-Za-z0-9]", w) or (cutoff and len(re.sub(r"[^A-Za-z]", "", w)) <= 1):
        return None
    return w


def _ids(phone_str):
    V = vocab(); out = []
    for p in phone_str.split():
        if p in V:
            out.append(V[p])
        else:                                   # unknown symbol: its characters if they exist, else wildcard
            parts = [V[c] for c in p if c in V]
            out.extend(parts if parts else [WILD])
    return out or [WILD]


def token_units(tokens):
    """list (per token) of phone id lists; also the phone strings for inspection"""
    from phonemizer import phonemize
    from phonemizer.separator import Separator
    sep = Separator(phone=" ", word="|", syllable="")
    words = [_clean(t) for t in tokens]
    units, strs = [None] * len(tokens), [""] * len(tokens)
    i = 0
    while i < len(words):
        if words[i] is None:
            units[i], strs[i] = [WILD], "*"; i += 1; continue
        j = i
        while j < len(words) and words[j] is not None:
            j += 1
        chunk = words[i:j]
        out = phonemize(" ".join(chunk), language="en-us", backend="espeak", separator=sep, strip=True,
                        preserve_punctuation=False, njobs=1)
        parts = [p.strip() for p in out.split("|") if p.strip()]
        if len(parts) != len(chunk):
            parts = [p.replace("|", " ").strip() for p in phonemize(chunk, language="en-us", backend="espeak",
                     separator=sep, strip=True, preserve_punctuation=False, njobs=1)]
        for k, p in enumerate(parts):
            units[i + k], strs[i + k] = _ids(p), p
        i = j
    return units, strs


VOWELS = set("aeiouæɐɑɒɔəɚɛɜɝɞɤɨɪɯɵʉʊʌʏøœɶy")
MANNER = [("stop", set("pbtdkgʔ")), ("fric", set("fvθðszʃʒhçx")), ("nasal", set("mnŋ")), ("liquid", set("lɹɾɫr")),
          ("glide", set("wj"))]
CLASSES = ["vowel", "stop", "affric", "fric", "nasal", "liquid", "glide"]


def manner(ph):
    """broad manner class of an espeak phone symbol (general phonetics)"""
    if not ph or ph == "*":
        return None
    base = ph.replace("ː", "").replace("ˈ", "").replace("ˌ", "")
    if base in ("tʃ", "dʒ"):
        return "affric"
    if base[0] in VOWELS:
        return "vowel"
    for name, S in MANNER:
        if base[0] in S:
            return name
    return None


def class_matrix():
    """(n_classes, vocab) 0/1 membership of every real phone label (ids >= 4) in each manner class"""
    import numpy as np
    V = vocab(); M = np.zeros((len(CLASSES), max(V.values()) + 1))
    for sym, i in V.items():
        c = manner(sym) if i >= 4 else None
        if c:
            M[CLASSES.index(c), i] = 1
    return M
