import os
import numpy as np
import soundfile as sf

def snap_boundary(wpath, time_sec, window_ms=30):
    try:
        data, sr = sf.read(wpath)
        if len(data.shape) > 1:
            data = data.mean(axis=1) # Mono
        
        center_idx = int(time_sec * sr)
        half_win = int((window_ms / 1000.0) * sr)
        start_idx = max(0, center_idx - half_win)
        end_idx = min(len(data), center_idx + half_win)
        
        if start_idx >= end_idx:
            return time_sec
            
        window_data = data[start_idx:end_idx]
        
        frame_len = int(0.005 * sr) # 5ms frame
        if frame_len < 1: frame_len = 1
        
        energies = []
        for i in range(len(window_data) - frame_len):
            frame = window_data[i:i+frame_len]
            energies.append(np.sum(frame**2))
        
        if not energies:
            return time_sec
            
        min_energy_idx = np.argmin(energies)
        snapped_idx = start_idx + min_energy_idx + (frame_len//2)
        return snapped_idx / sr
    except Exception as e:
        return time_sec
