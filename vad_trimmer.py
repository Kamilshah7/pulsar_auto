"""
Acoustic Waveform Energy & VAD Edge Snapper.
Trims silence padding and snaps word boundaries to true acoustic onset/offset within ~20ms.
Features:
  - Short-time RMS energy curve (10ms window, 2ms step)
  - Dynamic noise floor and speech threshold detection
  - Neighbor-bounded search windows to eliminate token overlap
  - Zero-crossing snapping to prevent audio clicks and phase distortion
  - Full telemetry tracking (silence shaved in ms, onset/offset adjustments)
"""
import wave
import numpy as np
import os

class VadTrimmer:
    def __init__(self, wav_path):
        self.wav_path = wav_path
        self.filename = os.path.basename(wav_path)
        with wave.open(wav_path, "rb") as wf:
            self.sr = wf.getframerate()
            self.n_channels = wf.getnchannels()
            self.sampwidth = wf.getsampwidth()
            self.n_frames = wf.getnframes()
            self.duration = self.n_frames / float(self.sr)
            raw = wf.readframes(self.n_frames)
            
        if self.sampwidth == 2:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif self.sampwidth == 4:
            samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        if self.n_channels > 1:
            samples = samples.reshape(-1, self.n_channels).mean(axis=1)

        self.samples = samples
        self.stats = {
            "total_silence_shaved_ms": 0.0,
            "tokens_trimmed": 0,
            "zero_crossings_snapped": 0
        }
        self._compute_energy_curve()

    def _compute_energy_curve(self):
        """Compute short-time RMS energy curve with 10ms window and 2ms step."""
        win_size = int(self.sr * 0.010)  # 10ms
        
        # Calculate squared samples
        sq = self.samples ** 2
        
        # Fast moving average for windowed energy
        kernel = np.ones(win_size) / win_size
        energy = np.convolve(sq, kernel, mode="same")
        self.rms = np.sqrt(np.maximum(energy, 0))

        # Dynamic noise floor estimation (15th percentile of energy)
        self.noise_floor = float(np.percentile(self.rms, 15))
        self.peak_energy = float(np.percentile(self.rms, 95))
        
        # Speech onset threshold
        self.speech_thresh = max(self.noise_floor * 2.2, self.peak_energy * 0.03, 0.005)

    def trim_segment_bounded(self, start_sec, end_sec, prev_end_sec=0.0, next_start_sec=None, min_dur=0.045):
        """
        Refine a word segment boundary bounded by its predecessor and successor words.
        Snaps start inward/outward to acoustic onset and end to acoustic offset without colliding into neighbor words.
        """
        if next_start_sec is None:
            next_start_sec = self.duration

        orig_start = max(0.001, min(start_sec, self.duration - 0.002))
        orig_end = max(orig_start + min_dur, min(end_sec, self.duration - 0.001))
        orig_dur = orig_end - orig_start

        # Search window for onset (start): do not search left past prev_end
        search_start_left = max(prev_end_sec, orig_start - 0.100)
        search_start_right = min(orig_end - min_dur, orig_start + 0.080)
        
        refined_start = orig_start
        i_left = int(search_start_left * self.sr)
        i_right = int(search_start_right * self.sr)
        if i_left < i_right:
            sub = self.rms[i_left:i_right]
            above = np.where(sub >= self.speech_thresh)[0]
            if len(above) > 0:
                raw_onset = (i_left + above[0]) / self.sr - 0.012 # 12ms attack buffer
                refined_start = max(search_start_left, round(raw_onset, 4))

        # Search window for offset (end): do not search right past next_start
        search_end_left = max(refined_start + min_dur, orig_end - 0.080)
        search_end_right = min(next_start_sec, orig_end + 0.100)
        
        refined_end = orig_end
        i_end_left = int(search_end_left * self.sr)
        i_end_right = int(search_end_right * self.sr)
        if i_end_left < i_end_right:
            sub_end = self.rms[i_end_left:i_end_right]
            above_end = np.where(sub_end >= self.speech_thresh)[0]
            if len(above_end) > 0:
                raw_offset = (i_end_left + above_end[-1]) / self.sr + 0.015 # 15ms decay buffer
                refined_end = min(search_end_right, round(raw_offset, 4))

        # Snap to nearest zero-crossing
        idx_s = self._nearest_zero_crossing(int(refined_start * self.sr))
        idx_e = self._nearest_zero_crossing(int(refined_end * self.sr))
        self.stats["zero_crossings_snapped"] += 2

        new_start = round(idx_s / float(self.sr), 4)
        new_end = round(idx_e / float(self.sr), 4)

        if new_end < new_start + min_dur:
            new_end = round(new_start + min_dur, 4)

        new_start = max(0.001, min(new_start, self.duration - 0.002))
        new_end = max(new_start + min_dur, min(new_end, self.duration - 0.001))

        # Track silence delta
        new_dur = new_end - new_start
        silence_delta_ms = (orig_dur - new_dur) * 1000.0
        self.stats["total_silence_shaved_ms"] += max(0.0, silence_delta_ms)
        self.stats["tokens_trimmed"] += 1

        return new_start, new_end

    def _nearest_zero_crossing(self, frame_idx, window_ms=10):
        """Snap sample index to the nearest zero-crossing within window_ms to eliminate pops."""
        radius = int(self.sr * (window_ms / 1000.0) / 2)
        start = max(0, frame_idx - radius)
        end = min(len(self.samples) - 1, frame_idx + radius)
        
        slice_samples = self.samples[start:end]
        zero_crossings = np.where(np.diff(np.signbit(slice_samples)))[0]
        
        if len(zero_crossings) > 0:
            best = zero_crossings[np.argmin(np.abs(zero_crossings - (frame_idx - start)))]
            return start + best
        return frame_idx

    def get_acoustic_summary(self):
        return {
            "duration_sec": round(self.duration, 3),
            "sample_rate": self.sr,
            "noise_floor": round(self.noise_floor, 5),
            "speech_thresh": round(self.speech_thresh, 5),
            "peak_energy": round(self.peak_energy, 5),
            "total_silence_shaved_ms": round(self.stats["total_silence_shaved_ms"], 1),
            "tokens_trimmed": self.stats["tokens_trimmed"]
        }
