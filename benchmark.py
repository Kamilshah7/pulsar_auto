import json
import difflib
import numpy as np

def compute_wer_and_alignment(ref_tokens, hyp_tokens):
    ref_texts = [t["text"].lower() for t in ref_tokens]
    hyp_texts = [t["text"].lower() for t in hyp_tokens]
    
    sm = difflib.SequenceMatcher(None, ref_texts, hyp_texts)
    
    errors = 0
    aligned_pairs = []
    speaker_matches = 0
    
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                ref_t = ref_tokens[i1 + k]
                hyp_t = hyp_tokens[j1 + k]
                aligned_pairs.append((ref_t, hyp_t))
                if ref_t.get("speaker") == hyp_t.get("speaker"):
                    speaker_matches += 1
        elif tag == 'replace':
            errors += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            errors += (i2 - i1)
        elif tag == 'insert':
            errors += (j2 - j1)
            
    wer = errors / max(len(ref_texts), 1)
    
    return wer, aligned_pairs, speaker_matches

def evaluate_run(ref_tokens, hyp_tokens):
    if not ref_tokens:
        return {"error": "Empty reference tokens"}
        
    wer, aligned_pairs, speaker_matches = compute_wer_and_alignment(ref_tokens, hyp_tokens)
    
    token_count_diff = abs(len(ref_tokens) - len(hyp_tokens))
    token_count_acc = max(0, 1.0 - (token_count_diff / max(len(ref_tokens), 1)))
    
    timing_errors = []
    boundary_hits = 0
    
    for ref_t, hyp_t in aligned_pairs:
        start_diff = abs(ref_t["start"] - hyp_t["start"])
        end_diff = abs(ref_t["end"] - hyp_t["end"])
        timing_errors.extend([start_diff, end_diff])
        
        if start_diff <= 0.020:
            boundary_hits += 1
        if end_diff <= 0.020:
            boundary_hits += 1
            
    timing_mae = np.mean(timing_errors) if timing_errors else 1.0
    boundary_precision = boundary_hits / (len(aligned_pairs) * 2) if aligned_pairs else 0.0
    speaker_acc = speaker_matches / len(aligned_pairs) if aligned_pairs else 0.0
    
    # Calculate score (0-100)
    # Weights: WER (35%), Timing MAE (25%), Token Count (15%), Boundary Prec (15%), Speaker (10%)
    
    # Normalize WER (0 = perfect, >0.5 = 0 score)
    wer_score = max(0, 1.0 - (wer * 2))
    
    # Normalize Timing MAE (0s = perfect, >0.2s = 0 score)
    timing_score = max(0, 1.0 - (timing_mae * 5))
    
    final_score = (
        (token_count_acc * 15) + 
        (wer_score * 35) + 
        (timing_score * 25) + 
        (boundary_precision * 15) + 
        (speaker_acc * 10)
    )
    
    return {
        "score": round(final_score, 2),
        "wer": round(wer, 4),
        "timing_mae_ms": round(timing_mae * 1000, 2),
        "boundary_prec": round(boundary_precision, 4),
        "token_count_acc": round(token_count_acc, 4),
        "speaker_acc": round(speaker_acc, 4),
        "ref_count": len(ref_tokens),
        "hyp_count": len(hyp_tokens)
    }

if __name__ == "__main__":
    # Simple self-test
    print("Testing scoring engine...")
    test_ref = [{"text": "hello", "start": 0.1, "end": 0.5, "speaker": "S1"}, 
                {"text": "world", "start": 0.6, "end": 1.0, "speaker": "S1"}]
    test_hyp = [{"text": "hello", "start": 0.1, "end": 0.52, "speaker": "S1"}, 
                {"text": "world", "start": 0.58, "end": 1.0, "speaker": "S1"}]
    
    res = evaluate_run(test_ref, test_hyp)
    print("Self-test result:", json.dumps(res, indent=2))
