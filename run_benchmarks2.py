import os
import json
import time
import sys
import copy
from benchmark import evaluate_run

# Import pipeline components
sys.path.insert(0, os.path.dirname(__file__))
from pipeline import PulsarPipeline
import vad_trimmer
import reconciler

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
GT_PATH = os.path.join(OUTPUT_DIR, "baseline_ground_truth.json")

def load_ground_truth():
    with open(GT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

class ExperimentOrchestrator:
    def __init__(self):
        self.gt_tokens = load_ground_truth()
        self.results = {}
        self.pipeline = PulsarPipeline()
        
        # Save original classes/methods to restore later
        self.OrigVadTrimmer = vad_trimmer.VadTrimmer
        self.orig_compute_energy = vad_trimmer.VadTrimmer._compute_energy_curve
        self.orig_trim = vad_trimmer.VadTrimmer.trim_segment_bounded
        
        self.OrigAcousticReconciler = reconciler.AcousticReconciler
        self.orig_reconcile = reconciler.AcousticReconciler.reconcile_clip
        self.orig_trim_and_fix = reconciler.AcousticReconciler._trim_and_fix_overlaps

    def restore_defaults(self):
        vad_trimmer.VadTrimmer._compute_energy_curve = self.orig_compute_energy
        vad_trimmer.VadTrimmer.trim_segment_bounded = self.orig_trim
        reconciler.AcousticReconciler.reconcile_clip = self.orig_reconcile
        reconciler.AcousticReconciler._trim_and_fix_overlaps = self.orig_trim_and_fix

    def run_experiment(self, name, setup_func):
        print(f"\n--- Running Experiment: {name} ---")
        self.restore_defaults()
        setup_func()
        
        # Run baseline generation
        try:
            # Clear previous baseline tokens
            out_file = os.path.join(OUTPUT_DIR, "injected_tokens.json")
            if os.path.exists(out_file):
                os.remove(out_file)
                
            self.pipeline.generate_acoustic_baseline()
            
            # Read output
            if not os.path.exists(out_file):
                print(f"FAILED: {out_file} not generated.")
                return
                
            with open(out_file, "r", encoding="utf-8") as f:
                hyp_tokens = json.load(f)
                
            # Score
            score_data = evaluate_run(self.gt_tokens, hyp_tokens)
            self.results[name] = score_data
            print(f"Score: {score_data['score']}/100 (WER: {score_data['wer']:.4f})")
            
        except Exception as e:
            print(f"Experiment {name} failed: {e}")
            import traceback
            traceback.print_exc()

    def print_results(self):
        print("\n" + "="*80)
        print("BENCHMARK RESULTS")
        print("="*80)
        print(f"{'Experiment':<35} | {'Score':<6} | {'WER':<6} | {'Timing MAE':<10} | {'BndryPrec':<9} | {'Toks Acc'}")
        print("-" * 80)
        
        sorted_res = sorted(self.results.items(), key=lambda x: x[1]['score'], reverse=True)
        for name, res in sorted_res:
            print(f"{name:<35} | {res['score']:<6} | {res['wer']:<6.4f} | {res['timing_mae_ms']:<7.2f} ms | {res['boundary_prec']:<9.4f} | {res['token_count_acc']:<8.4f}")

# --- Setup Functions for Experiments ---

def exp_a_default():
    pass # Uses restored defaults

# B: VAD Tuning
def exp_b2_sensitive_vad():
    orig_compute = vad_trimmer.VadTrimmer._compute_energy_curve
    orig_trim = vad_trimmer.VadTrimmer.trim_segment_bounded
    
    def modified_compute(self):
        orig_compute(self)
        self.noise_floor = float(np.percentile(self.rms, 10))
        self.speech_thresh = max(self.noise_floor * 1.5, self.peak_energy * 0.02, 0.003)
        
    def modified_trim(self, start_sec, end_sec, prev_end_sec=0.0, next_start_sec=None, min_dur=0.045):
        import numpy as np
        if next_start_sec is None:
            next_start_sec = self.duration
        orig_start = max(0.001, min(start_sec, self.duration - 0.002))
        orig_end = max(orig_start + min_dur, min(end_sec, self.duration - 0.001))
        orig_dur = orig_end - orig_start
        search_start_left = max(prev_end_sec, orig_start - 0.100)
        search_start_right = min(orig_end - min_dur, orig_start + 0.080)
        refined_start = orig_start
        i_left = int(search_start_left * self.sr)
        i_right = int(search_start_right * self.sr)
        if i_left < i_right:
            sub = self.rms[i_left:i_right]
            above = np.where(sub >= self.speech_thresh)[0]
            if len(above) > 0:
                raw_onset = (i_left + above[0]) / self.sr - 0.008 # 8ms attack
                refined_start = max(search_start_left, round(raw_onset, 4))
        search_end_left = max(refined_start + min_dur, orig_end - 0.080)
        search_end_right = min(next_start_sec, orig_end + 0.100)
        refined_end = orig_end
        i_end_left = int(search_end_left * self.sr)
        i_end_right = int(search_end_right * self.sr)
        if i_end_left < i_end_right:
            sub_end = self.rms[i_end_left:i_end_right]
            above_end = np.where(sub_end >= self.speech_thresh)[0]
            if len(above_end) > 0:
                raw_offset = (i_end_left + above_end[-1]) / self.sr + 0.010 # 10ms decay
                refined_end = min(search_end_right, round(raw_offset, 4))
        idx_s = self._nearest_zero_crossing(int(refined_start * self.sr))
        idx_e = self._nearest_zero_crossing(int(refined_end * self.sr))
        self.stats["zero_crossings_snapped"] += 2
        new_start = max(0.001, min(round(idx_s / float(self.sr), 4), self.duration - 0.002))
        new_end = max(new_start + min_dur, min(round(idx_e / float(self.sr), 4), self.duration - 0.001))
        self.stats["total_silence_shaved_ms"] += max(0.0, (orig_dur - (new_end - new_start)) * 1000.0)
        self.stats["tokens_trimmed"] += 1
        return new_start, new_end

    import numpy as np
    vad_trimmer.VadTrimmer._compute_energy_curve = modified_compute
    vad_trimmer.VadTrimmer.trim_segment_bounded = modified_trim

def exp_b3_less_sensitive_vad():
    orig_compute = vad_trimmer.VadTrimmer._compute_energy_curve
    orig_trim = vad_trimmer.VadTrimmer.trim_segment_bounded
    
    def modified_compute(self):
        orig_compute(self)
        self.noise_floor = float(np.percentile(self.rms, 20))
        self.speech_thresh = max(self.noise_floor * 3.0, self.peak_energy * 0.05, 0.008)
        
    def modified_trim(self, start_sec, end_sec, prev_end_sec=0.0, next_start_sec=None, min_dur=0.045):
        import numpy as np
        if next_start_sec is None:
            next_start_sec = self.duration
        orig_start = max(0.001, min(start_sec, self.duration - 0.002))
        orig_end = max(orig_start + min_dur, min(end_sec, self.duration - 0.001))
        orig_dur = orig_end - orig_start
        search_start_left = max(prev_end_sec, orig_start - 0.100)
        search_start_right = min(orig_end - min_dur, orig_start + 0.080)
        refined_start = orig_start
        i_left = int(search_start_left * self.sr)
        i_right = int(search_start_right * self.sr)
        if i_left < i_right:
            sub = self.rms[i_left:i_right]
            above = np.where(sub >= self.speech_thresh)[0]
            if len(above) > 0:
                raw_onset = (i_left + above[0]) / self.sr - 0.020 # 20ms attack
                refined_start = max(search_start_left, round(raw_onset, 4))
        search_end_left = max(refined_start + min_dur, orig_end - 0.080)
        search_end_right = min(next_start_sec, orig_end + 0.100)
        refined_end = orig_end
        i_end_left = int(search_end_left * self.sr)
        i_end_right = int(search_end_right * self.sr)
        if i_end_left < i_end_right:
            sub_end = self.rms[i_end_left:i_end_right]
            above_end = np.where(sub_end >= self.speech_thresh)[0]
            if len(above_end) > 0:
                raw_offset = (i_end_left + above_end[-1]) / self.sr + 0.020 # 20ms decay
                refined_end = min(search_end_right, round(raw_offset, 4))
        idx_s = self._nearest_zero_crossing(int(refined_start * self.sr))
        idx_e = self._nearest_zero_crossing(int(refined_end * self.sr))
        self.stats["zero_crossings_snapped"] += 2
        new_start = max(0.001, min(round(idx_s / float(self.sr), 4), self.duration - 0.002))
        new_end = max(new_start + min_dur, min(round(idx_e / float(self.sr), 4), self.duration - 0.001))
        self.stats["total_silence_shaved_ms"] += max(0.0, (orig_dur - (new_end - new_start)) * 1000.0)
        self.stats["tokens_trimmed"] += 1
        return new_start, new_end

    import numpy as np
    vad_trimmer.VadTrimmer._compute_energy_curve = modified_compute
    vad_trimmer.VadTrimmer.trim_segment_bounded = modified_trim

# C: Reconciliation Strategy
def exp_c2_prelabels_only():
    def modified_reconcile(self, pre_segments, target_tokens, clip_duration=None):
        return self._trim_and_fix_overlaps(pre_segments, clip_duration), {}
    reconciler.AcousticReconciler.reconcile_clip = modified_reconcile

def exp_e3_proportional_split():
    orig_trim_fix = reconciler.AcousticReconciler._trim_and_fix_overlaps
    def modified_trim_fix(self, aligned_tokens, clip_dur=None):
        if clip_dur is None:
            clip_dur = 9999.0
            
        min_gap = 0.005
        min_dur = 0.045
        for i in range(len(aligned_tokens)):
            cur = aligned_tokens[i]
            # VAD Trim first
            ps = 0.0 if i == 0 else aligned_tokens[i-1]["end"]
            ns = clip_dur if i == len(aligned_tokens)-1 else aligned_tokens[i+1]["start"]
            if self.trimmer:
                ns_ms, ne_ms = self.trimmer.trim_segment_bounded(cur["start"], cur["end"], ps, ns, min_dur)
            else:
                ns_ms, ne_ms = cur["start"], cur["end"]
            cur["start"] = ns_ms
            cur["end"] = ne_ms
        
        # Proportional split
        for i in range(len(aligned_tokens) - 1):
            cur = aligned_tokens[i]
            nxt = aligned_tokens[i+1]
            if cur["end"] > nxt["start"]:
                overlap = cur["end"] - nxt["start"]
                cur_len = max(0.01, cur["end"] - cur["start"])
                nxt_len = max(0.01, nxt["end"] - nxt["start"])
                tot_len = cur_len + nxt_len
                # shift according to length ratio
                cur_shift = overlap * (cur_len / tot_len)
                
                mid = cur["end"] - cur_shift
                cur["end"] = round(mid - (min_gap/2), 4)
                nxt["start"] = round(mid + (min_gap/2), 4)
                
        for t in aligned_tokens:
            if t["end"] < t["start"] + min_dur:
                t["end"] = round(t["start"] + min_dur, 4)
            if t["end"] >= clip_dur:
                t["end"] = clip_dur - 0.001
                if t["end"] < t["start"] + min_dur:
                    t["start"] = round(t["end"] - min_dur, 4)
        return aligned_tokens
        
    reconciler.AcousticReconciler._trim_and_fix_overlaps = modified_trim_fix

def exp_c3_whisper_with_fallback():
    orig_reconcile = reconciler.AcousticReconciler.reconcile_clip
    def modified_reconcile(self, pre_segments, target_tokens, clip_duration=None):
        if len(pre_segments) > 0 and len(target_tokens) < len(pre_segments) * 0.5:
            return self._trim_and_fix_overlaps(pre_segments, clip_duration), {}
        return orig_reconcile(self, pre_segments, target_tokens, clip_duration)
    reconciler.AcousticReconciler.reconcile_clip = modified_reconcile

def exp_g_prelabels_prefer():
    def modified_reconcile(self, pre_segments, target_tokens, clip_duration=None):
        if not pre_segments and not target_tokens:
            return [], {}
        if pre_segments:
            return self._trim_and_fix_overlaps(pre_segments, clip_duration), {}
        else:
            return self._trim_and_fix_overlaps(target_tokens, clip_duration), {}
    reconciler.AcousticReconciler.reconcile_clip = modified_reconcile


def exp_i_llm_text():
    raise NotImplementedError(
        "pipeline.USE_LLM_TEXT / USE_HYBRID_SNAP do not exist in pipeline.py (inject_pipeline.py, "
        "which was meant to add them, never ran). Setting them is a no-op, so exp_i and exp_j ran "
        "byte-identical code and any comparison between them was meaningless. Use "
        "bench/run_gold_bench.py for alignment comparisons.")
    import pipeline
    pipeline.USE_LLM_TEXT = True
    pipeline.USE_HYBRID_SNAP = False
    pipeline.PulsarPipeline().generate_acoustic_baseline()

def exp_j_hybrid():
    raise NotImplementedError(
        "pipeline.USE_LLM_TEXT / USE_HYBRID_SNAP do not exist in pipeline.py (inject_pipeline.py, "
        "which was meant to add them, never ran). Setting them is a no-op, so exp_i and exp_j ran "
        "byte-identical code and any comparison between them was meaningless. Use "
        "bench/run_gold_bench.py for alignment comparisons.")
    import pipeline
    pipeline.USE_LLM_TEXT = True
    pipeline.USE_HYBRID_SNAP = True
    pipeline.PulsarPipeline().generate_acoustic_baseline()

if __name__ == '__main__':
    orch = ExperimentOrchestrator()
    orch.run_experiment('Wav2Vec2 Forced Alignment (LLM Text)', exp_i_llm_text)
    orch.run_experiment('Hybrid Wav2Vec2 + Waveform Snapping (LLM Text)', exp_j_hybrid)
    orch.print_results()
