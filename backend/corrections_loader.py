"""
Corrections Loader - Smart loader for fast corrections
Y-Channel NLM implementation matching C# approach
"""
import numpy as np
import struct
import cv2
from pathlib import Path
import threading
import time
cv2.setNumThreads(0)
try:
    from corrections_fast import (
        apply_blc_slc_fast,
        apply_glc_fast,
        apply_dark_glc_fast
    )
    FAST_MODE = True
    print("✓ Using FAST corrections (Cython + OpenMP)")
except ImportError:
    FAST_MODE = False
    print("⚠ Using SLOW corrections (Pure Python) - Run: python setup.py build_ext --inplace")
    
    def apply_blc_slc_fast(frame, blc_r, blc_g, blc_b, slc_diff_r, slc_diff_g, slc_diff_b):
        """Pure Python fallback for BLC/SLC"""
        b, g, r = cv2.split(frame)
        b = b.astype(np.int32)
        g = g.astype(np.int32)
        r = r.astype(np.int32)
        
        r = ((r - blc_r) * 255) // slc_diff_r
        g = ((g - blc_g) * 255) // slc_diff_g
        b = ((b - blc_b) * 255) // slc_diff_b
        
        r = np.clip(r, 0, 255).astype(np.uint8)
        g = np.clip(g, 0, 255).astype(np.uint8)
        b = np.clip(b, 0, 255).astype(np.uint8)
        
        return cv2.merge([b, g, r])
    
    def apply_glc_fast(frame, glc_r, glc_g, glc_b):
        """Pure Python fallback for GLC"""
        return frame
    
    def apply_dark_glc_fast(frame, dark_glc_r, dark_glc_g, dark_glc_b):
        """Pure Python fallback for Dark GLC"""
        return frame


class CorrectionEngine:
    """
    High-performance correction engine with Y-channel NLM
    Matches C# implementation for maximum performance
    """
    
    def __init__(self):
        self.calibration = None
        self.is_loaded = False
        
        # NLM threading (C# style - simple latest frame approach)
        self.nlm_lock = threading.Lock()
        self.nlm_thread = None
        self.nlm_running = False
        self.nlm_enabled = False
        
        # Latest frame buffers (C# style)
        self.latest_nlm_input = None
        self.latest_nlm_output = None
        
        # NLM parameters (matching C# defaults)
        self.nlm_h_luma = 3
        self.nlm_template = 7
        self.nlm_search = 7
        
    def start_nlm_thread(self):
        """Start the NLM processing thread (C# style)"""
        if self.nlm_thread is not None and self.nlm_thread.is_alive():
            return
        
        self.nlm_running = True
        self.nlm_thread = threading.Thread(target=self._nlm_worker_loop, daemon=True)
        self.nlm_thread.start()
        print("✓ NLM thread started (Y-channel processing)")
    
    def stop_nlm_thread(self):
        """Stop the NLM processing thread"""
        self.nlm_running = False
        if self.nlm_thread is not None:
            self.nlm_thread.join(timeout=1.0)
        
        with self.nlm_lock:
            self.latest_nlm_input = None
            self.latest_nlm_output = None
        
        print("✓ NLM thread stopped")
    
    def _nlm_worker_loop(self):
        """
        Worker thread that processes NLM denoising
        Matches C# NlmWorkerLoop() implementation
        """
        print("NLM worker thread started (Y-channel mode)")
        
        while self.nlm_running:
            input_copy = None
            
            # Get latest input (C# style)
            with self.nlm_lock:
                if self.latest_nlm_input is not None:
                    input_copy = self.latest_nlm_input.copy()
            
            if input_copy is not None:
                try:
                    # Convert BGR to YCrCb
                    ycrcb = cv2.cvtColor(input_copy, cv2.COLOR_BGR2YCrCb)
                    
                    # Split channels
                    y_channel, cr_channel, cb_channel = cv2.split(ycrcb)
                    
                    # Denoise ONLY Y (luminance) channel
                    y_denoised = cv2.fastNlMeansDenoising(
                        y_channel,
                        None,
                        h=self.nlm_h_luma,
                        templateWindowSize=self.nlm_template,
                        searchWindowSize=self.nlm_search
                    )
                    
                    # Merge back with original Cr, Cb
                    ycrcb_denoised = cv2.merge([y_denoised, cr_channel, cb_channel])
                    
                    # Convert back to BGR
                    denoised_bgr = cv2.cvtColor(ycrcb_denoised, cv2.COLOR_YCrCb2BGR)
                    
                    # Store output (C# style)
                    with self.nlm_lock:
                        self.latest_nlm_output = denoised_bgr
                
                except Exception as e:
                    print(f"⚠️ NLM worker error: {e}")
            
            else:
                # No input, sleep briefly
                time.sleep(0.001)
        
        print("NLM worker thread stopped")
    
    def load_calibration(self, filepath):
        """Load calibration file (fixed 18-byte header)"""
        print(f"Loading calibration: {filepath}")
        
        with open(filepath, 'rb') as f:
            w = struct.unpack('<I', f.read(4))[0]
            h = struct.unpack('<I', f.read(4))[0]
            blc_flag = struct.unpack('?', f.read(1))[0]
            slc_flag = struct.unpack('?', f.read(1))[0]
            date = struct.unpack('<q', f.read(8))[0]
            
            size = w * h
            
            blc_bytes = f.read(size * 12)
            blc_data = np.frombuffer(blc_bytes, dtype=np.int32).reshape(h, w, 3)
            blc_r = blc_data[:, :, 0].copy()
            blc_g = blc_data[:, :, 1].copy()
            blc_b = blc_data[:, :, 2].copy()
            
            slc_bytes = f.read(size * 12)
            slc_data = np.frombuffer(slc_bytes, dtype=np.int32).reshape(h, w, 3)
            slc_r = slc_data[:, :, 0].copy()
            slc_g = slc_data[:, :, 1].copy()
            slc_b = slc_data[:, :, 2].copy()
            
            slc_diff_r = np.maximum(1, slc_r - blc_r).astype(np.int32)
            slc_diff_g = np.maximum(1, slc_g - blc_g).astype(np.int32)
            slc_diff_b = np.maximum(1, slc_b - blc_b).astype(np.int32)
            
            glc_flag = struct.unpack('?', f.read(1))[0]
            
            glc_r = glc_g = glc_b = None
            if glc_flag:
                glc_bytes = f.read(size * 12)
                glc_data = np.frombuffer(glc_bytes, dtype=np.int32).reshape(h, w, 3)
                glc_r = np.clip(glc_data[:, :, 0], 0, 255).astype(np.int32).copy()
                glc_g = np.clip(glc_data[:, :, 1], 0, 255).astype(np.int32).copy()
                glc_b = np.clip(glc_data[:, :, 2], 0, 255).astype(np.int32).copy()
            
            dark_glc_flag = struct.unpack('?', f.read(1))[0]
            
            dark_glc_r = dark_glc_g = dark_glc_b = None
            if dark_glc_flag:
                dark_glc_bytes = f.read(size * 12)
                dark_glc_data = np.frombuffer(dark_glc_bytes, dtype=np.int32).reshape(h, w, 3)
                dark_glc_r = dark_glc_data[:, :, 0].astype(np.int32).copy()
                dark_glc_g = dark_glc_data[:, :, 1].astype(np.int32).copy()
                dark_glc_b = dark_glc_data[:, :, 2].astype(np.int32).copy()
            
            self.calibration = {
                'width': w,
                'height': h,
                'blc_r': blc_r,
                'blc_g': blc_g,
                'blc_b': blc_b,
                'slc_diff_r': slc_diff_r,
                'slc_diff_g': slc_diff_g,
                'slc_diff_b': slc_diff_b,
                'glc_r': glc_r,
                'glc_g': glc_g,
                'glc_b': glc_b,
                'dark_glc_r': dark_glc_r,
                'dark_glc_g': dark_glc_g,
                'dark_glc_b': dark_glc_b,
                'has_glc': glc_flag,
                'has_dark_glc': dark_glc_flag
            }
            
            self.is_loaded = True
            
            print(f"  ✓ Dimensions: {w} × {h}")
            print(f"  ✓ BLC/SLC: Loaded")
            print(f"  ✓ GLC: {'Loaded' if glc_flag else 'Not available'}")
            print(f"  ✓ Dark GLC: {'Loaded' if dark_glc_flag else 'Not available'}")
            
            return True
    
    def apply_corrections(self, frame, enable_blc_slc=True, enable_glc=True, enable_dark_glc=True, enable_nlm=False):
        """
        Apply corrections to frame (in-place modification for speed)
        
        Args:
            frame: BGR numpy array (will be modified in-place)
            enable_blc_slc: Enable BLC/SLC correction
            enable_glc: Enable GLC correction
            enable_dark_glc: Enable Dark GLC correction
            enable_nlm: Enable NLM denoising (Y-channel, threaded)
            
        Returns:
            frame: Corrected frame
        """
        if not self.is_loaded:
            return frame
        
        calib = self.calibration
        
        if not frame.flags['C_CONTIGUOUS']:
            frame = np.ascontiguousarray(frame)
        
        # Stage 1: BLC/SLC
        if enable_blc_slc:
            if FAST_MODE:
                apply_blc_slc_fast(
                    frame,
                    calib['blc_r'],
                    calib['blc_g'],
                    calib['blc_b'],
                    calib['slc_diff_r'],
                    calib['slc_diff_g'],
                    calib['slc_diff_b']
                )
            else:
                frame = apply_blc_slc_fast(
                    frame,
                    calib['blc_r'],
                    calib['blc_g'],
                    calib['blc_b'],
                    calib['slc_diff_r'],
                    calib['slc_diff_g'],
                    calib['slc_diff_b']
                )
        
        # Stage 2: GLC
        if enable_glc and calib['has_glc'] and FAST_MODE:
            apply_glc_fast(
                frame,
                calib['glc_r'],
                calib['glc_g'],
                calib['glc_b']
            )
        
        # Stage 3: Dark GLC
        if enable_dark_glc and calib['has_dark_glc'] and FAST_MODE:
            apply_dark_glc_fast(
                frame,
                calib['dark_glc_r'],
                calib['dark_glc_g'],
                calib['dark_glc_b']
            )
        
        # Stage 4: NLM Denoising (Y-channel, C# style threading)
        if enable_nlm:
            # Start thread if not running
            if not self.nlm_running:
                self.start_nlm_thread()
            
            # Send frame to NLM thread (C# style - just update latest)
            with self.nlm_lock:
                self.latest_nlm_input = frame.copy()
            
            # Get latest denoised output (C# style - if available)
            with self.nlm_lock:
                if self.latest_nlm_output is not None:
                    frame = self.latest_nlm_output.copy()
        
        else:
            # Stop thread if NLM disabled
            if self.nlm_running:
                self.stop_nlm_thread()
        
        return frame


correction_engine = CorrectionEngine()

def load_calibration(filepath):
    """Load calibration file"""
    return correction_engine.load_calibration(filepath)

def apply_corrections(frame, enable_blc_slc=True, enable_glc=True, enable_dark_glc=True, enable_nlm=False):
    """Apply corrections to frame"""
    return correction_engine.apply_corrections(frame, enable_blc_slc, enable_glc, enable_dark_glc, enable_nlm)

def is_fast_mode():
    """Check if fast mode is available"""
    return FAST_MODE