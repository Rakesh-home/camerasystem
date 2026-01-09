import cv2
import numpy as np
import threading
import time

class HistogramProcessor:
    def __init__(self):
        self.min_value = 0
        self.max_value = 255
        self.nlm_enabled = False
        
        # Threading for histogram normalization (similar to NLM approach)
        self.hist_lock = threading.Lock()
        self.hist_thread = None
        self.hist_running = False
        self.hist_normalization_enabled = False
        
        # Latest frame buffers
        self.latest_hist_input = None
        self.latest_hist_output = None
        
    def start_hist_thread(self):
        """Start the histogram normalization thread"""
        if self.hist_thread is not None and self.hist_thread.is_alive():
            return
        
        self.hist_running = True
        self.hist_thread = threading.Thread(target=self._hist_worker_loop, daemon=True)
        self.hist_thread.start()
        print("✓ Histogram normalization thread started")
    
    def stop_hist_thread(self):
        """Stop the histogram normalization thread"""
        self.hist_running = False
        if self.hist_thread is not None:
            self.hist_thread.join(timeout=1.0)
        
        with self.hist_lock:
            self.latest_hist_input = None
            self.latest_hist_output = None
        
        print("✓ Histogram normalization thread stopped")
    
    def _hist_worker_loop(self):
        """Worker thread for histogram normalization (async processing)"""
        print("Histogram normalization worker thread started")
        
        while self.hist_running:
            input_copy = None
            
            # Get latest input
            with self.hist_lock:
                if self.latest_hist_input is not None:
                    input_copy = self.latest_hist_input.copy()
            
            if input_copy is not None:
                try:
                    # Apply normalization
                    normalized = self._apply_normalization_internal(input_copy)
                    
                    # Store output
                    with self.hist_lock:
                        self.latest_hist_output = normalized
                
                except Exception as e:
                    print(f"⚠️ Histogram worker error: {e}")
            
            else:
                # No input, sleep briefly
                time.sleep(0.001)
        
        print("Histogram normalization worker thread stopped")
    
    def _apply_normalization_internal(self, frame):
        """Internal normalization function (called by worker thread)"""
        if self.min_value == 0 and self.max_value == 255:
            return frame
        
        frame = frame.astype(np.float32)
        frame = (frame - self.min_value) * 255.0 / (self.max_value - self.min_value)
        frame = np.clip(frame, 0, 255).astype(np.uint8)
        return frame
    
    def set_min_max(self, min_val, max_val):
        self.min_value = max(0, min(255, min_val))
        self.max_value = max(0, min(255, max_val))
        if self.min_value >= self.max_value:
            self.max_value = self.min_value + 1
        
        # Enable threading if non-default range
        self.hist_normalization_enabled = (self.min_value != 0 or self.max_value != 255)
    
    def set_nlm(self, enabled):
        self.nlm_enabled = enabled
    
    def apply_nlm(self, frame):
        if not self.nlm_enabled:
            return frame
        return cv2.fastNlMeansDenoisingColored(frame, None, 10, 10, 7, 21)
    
    def apply_normalization(self, frame):
        """Apply normalization (threaded if enabled, otherwise instant)"""
        
        # Check if normalization is needed
        if not self.hist_normalization_enabled:
            return frame
        
        # Start thread if not running
        if not self.hist_running:
            self.start_hist_thread()
        
        # Send frame to worker thread
        with self.hist_lock:
            self.latest_hist_input = frame.copy()
        
        # Get latest normalized output (if available)
        with self.hist_lock:
            if self.latest_hist_output is not None:
                return self.latest_hist_output.copy()
        
        # No output yet, return original frame
        return frame
    
    def apply_normalization_sync(self, frame):
        """Synchronous normalization (for when you need guaranteed processing)"""
        return self._apply_normalization_internal(frame)
    
    def calculate_histogram(self, frame):
        hist_r = cv2.calcHist([frame], [2], None, [256], [0, 256])
        hist_g = cv2.calcHist([frame], [1], None, [256], [0, 256])
        hist_b = cv2.calcHist([frame], [0], None, [256], [0, 256])
        
        hist_r = hist_r.flatten().tolist()
        hist_g = hist_g.flatten().tolist()
        hist_b = hist_b.flatten().tolist()
        
        return {
            'r': hist_r,
            'g': hist_g,
            'b': hist_b
        }
    
    def process_frame(self, frame):
        if self.nlm_enabled:
            frame = self.apply_nlm(frame)
        
        if self.hist_normalization_enabled:
            frame = self.apply_normalization(frame)
        
        return frame