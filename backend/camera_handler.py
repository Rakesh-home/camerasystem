import cv2
import numpy as np
import threading
import time
from pathlib import Path
import struct
import ctypes
from queue import Queue, Full, Empty
from config import *
import platform
from corrections_loader import correction_engine, is_fast_mode
from histogram_processor import HistogramProcessor

# Create global histogram processor instance
histogram_proc = HistogramProcessor()

class CameraHandler:
    def __init__(self):
        self.cap = None
        self.running = False
        
        # OPTIMIZED: Multi-stage queues for parallel processing
        self.raw_queue = Queue(maxsize=1)
        self.corrected_queue = Queue(maxsize=1)  # NEW: After corrections, before hist norm
        self.output_queue = Queue(maxsize=1)
        
        self.brightness = BRIGHTNESS_DEFAULT
        self.zoom = 5
        self.pan = 0
        self.focus = 150
        
        self.auto_corrections = False
        self.calibration_loaded = False
        self.current_profile = None
        
        self.enable_blc_slc = True
        self.enable_glc = True
        self.enable_dark_glc = True
        self.enable_nlm = False
        
        # Histogram processor reference
        self.histogram_proc = histogram_proc
        
    def start(self):
        try:
            if platform.system() == "Windows":
                backend = cv2.CAP_DSHOW
                backend_name = "DirectShow"
            elif platform.system() == "Linux":
                backend = cv2.CAP_V4L2
                backend_name = "V4L2"
            else:
                backend = cv2.CAP_ANY
                backend_name = "Auto"
            
            print(f"Opening camera with {backend_name} backend...")
            self.cap = cv2.VideoCapture(CAMERA_INDEX, backend)
            
            if not self.cap.isOpened():
                print(f"❌ Failed to open camera at index {CAMERA_INDEX}")
                return False
            
            print(f"✅ Camera opened with {backend_name}")
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, VIDEO_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, VIDEO_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, FPS)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            print("✅ Autofocus disabled for manual control")
            
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            
            print(f"Camera resolution: {actual_width}x{actual_height} @ {actual_fps}fps")
            
            self.set_brightness(self.brightness)
            
            print("Testing frame capture...")
            ret, test_frame = self.cap.read()
            if not ret:
                print("❌ ERROR: Camera opened but cannot read frames!")
                self.cap.release()
                self.cap = None
                return False
            
            print(f"✅ Frame capture test successful: {test_frame.shape}")
            
            for i in range(5):
                self.cap.grab()
            
            while not self.raw_queue.empty():
                try:
                    self.raw_queue.get_nowait()
                except Empty:
                    break
            
            # OPTIMIZED: Clear new queue
            while not self.corrected_queue.empty():
                try:
                    self.corrected_queue.get_nowait()
                except Empty:
                    break
            
            while not self.output_queue.empty():
                try:
                    self.output_queue.get_nowait()
                except Empty:
                    break
            
            self.running = True
            
            # OPTIMIZED: 3 threads for parallel processing
            threading.Thread(target=self._camera_thread, daemon=True).start()
            threading.Thread(target=self._processing_thread, daemon=True).start()
            threading.Thread(target=self._histogram_thread, daemon=True).start()  # NEW
            
            print(f"✅ Camera system started successfully (OPTIMIZED PIPELINE)")
            
            zoom_val = self.cap.get(cv2.CAP_PROP_ZOOM)
            focus_val = self.cap.get(cv2.CAP_PROP_FOCUS)
            pan_val = self.cap.get(cv2.CAP_PROP_PAN)
            autofocus_val = self.cap.get(cv2.CAP_PROP_AUTOFOCUS)
            print(f"PTZ Status - Zoom: {zoom_val:.1f}, Focus: {focus_val:.1f}, Pan: {pan_val:.1f}, Autofocus: {autofocus_val}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error starting camera: {e}")
            if self.cap:
                self.cap.release()
                self.cap = None
            return False
    
    def stop(self):
        print("Stopping camera...")
        self.running = False
        time.sleep(0.3)
        if self.cap:
            self.cap.release()
            self.cap = None
        
        while not self.raw_queue.empty():
            try:
                self.raw_queue.get_nowait()
            except Empty:
                break
        
        # OPTIMIZED: Clear new queue
        while not self.corrected_queue.empty():
            try:
                self.corrected_queue.get_nowait()
            except Empty:
                break
        
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except Empty:
                break
        
        print("Camera stopped")
    
    def _camera_thread(self):
        print("Camera thread started")
        while self.running:
            if self.cap is None:
                time.sleep(0.1)
                continue
            
            success, frame = self.cap.read()
            if success:
                try:
                    self.raw_queue.put(frame, block=False)
                except Full:
                    try:
                        self.raw_queue.get_nowait()
                        self.raw_queue.put(frame, block=False)
                    except:
                        pass
            else:
                time.sleep(0.01)
            
            time.sleep(0.001)
        print("Camera thread stopped")
    
    def _processing_thread(self):
        """
        OPTIMIZED: Apply corrections (BLC/SLC/GLC/DarkGLC/NLM)
        NLM runs in PARALLEL in corrections_loader thread
        """
        print("Processing thread started (corrections only)")
        while self.running:
            frame = None
            while True:
                try:
                    frame = self.raw_queue.get_nowait()
                except Empty:
                    break
            
            if frame is None:
                time.sleep(0.01)
                continue
            
            processed_frame = frame.copy()
            
            # Apply corrections (BLC/SLC/GLC/DarkGLC/NLM)
            # NLM is THREADED inside correction_engine, so this won't block!
            if self.auto_corrections and self.calibration_loaded:
                try:
                    processed_frame = correction_engine.apply_corrections(
                        processed_frame,
                        enable_blc_slc=self.enable_blc_slc,
                        enable_glc=self.enable_glc,
                        enable_dark_glc=self.enable_dark_glc,
                        enable_nlm=self.enable_nlm
                    )
                except Exception as e:
                    print(f"⚠️ Correction error: {e}")
            
            # OPTIMIZED: Send to histogram thread (parallel processing)
            try:
                self.corrected_queue.put(processed_frame, block=False)
            except Full:
                try:
                    self.corrected_queue.get_nowait()
                    self.corrected_queue.put(processed_frame, block=False)
                except:
                    pass
            
            time.sleep(0.001)
        print("Processing thread stopped")
    
    def _histogram_thread(self):
        """
        OPTIMIZED: NEW thread for histogram normalization
        Runs in PARALLEL with NLM thread
        """
        print("Histogram thread started (parallel processing)")
        while self.running:
            frame = None
            while True:
                try:
                    frame = self.corrected_queue.get_nowait()
                except Empty:
                    break
            
            if frame is None:
                time.sleep(0.01)
                continue
            
            # Apply histogram normalization (FAST, runs in parallel with NLM)
            try:
                final_frame = self.histogram_proc.apply_normalization(frame)
            except Exception as e:
                print(f"⚠️ Histogram normalization error: {e}")
                final_frame = frame
            
            # Send to output
            try:
                self.output_queue.put(final_frame, block=False)
            except Full:
                try:
                    self.output_queue.get_nowait()
                    self.output_queue.put(final_frame, block=False)
                except:
                    pass
            
            time.sleep(0.001)
        print("Histogram thread stopped")
    
    def get_frame(self):
        try:
            frame = self.output_queue.get(timeout=0.1)
            return frame
        except Empty:
            return None
    
    def set_brightness(self, value):
        self.brightness = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, value))
        if self.cap:
            result = self.cap.set(cv2.CAP_PROP_BRIGHTNESS, self.brightness)
            if result:
                print(f"Brightness set to {self.brightness}")
            else:
                print(f"Warning: Could not set brightness to {self.brightness}")
        self.load_calibration_for_brightness(self.brightness)
    
    def set_zoom(self, value):
        self.zoom = max(1, min(10, value))
        if self.cap:
            result = self.cap.set(cv2.CAP_PROP_ZOOM, self.zoom)
            if result:
                print(f"✅ Zoom set to {self.zoom}")
            else:
                print(f"⚠️ Warning: Could not set zoom to {self.zoom}")
            return result
        return False
    
    def set_pan(self, value):
        self.pan = max(-10, min(10, value))
        if self.cap:
            result = self.cap.set(cv2.CAP_PROP_PAN, self.pan)
            if result:
                print(f"✅ Pan set to {self.pan}")
            else:
                print(f"⚠️ Warning: Could not set pan to {self.pan}")
            return result
        return False
    
    def set_focus(self, value):
        self.focus = max(0, min(800, value))
        if self.cap:
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            
            result = self.cap.set(cv2.CAP_PROP_FOCUS, self.focus)
            if result:
                print(f"✅ Focus set to {self.focus} (autofocus OFF)")
            else:
                print(f"⚠️ Warning: Could not set focus to {self.focus}")
            
            af_status = self.cap.get(cv2.CAP_PROP_AUTOFOCUS)
            if af_status != 0:
                print(f"⚠️ WARNING: Autofocus re-enabled itself! Status: {af_status}")
                self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            
            return result
        return False
    
    def set_auto_corrections(self, enabled):
        self.auto_corrections = enabled
        status = "enabled" if enabled else "disabled"
        mode = "FAST" if is_fast_mode() else "SLOW"
        print(f"Auto corrections: {status} (Mode: {mode})")
        
        if enabled and not self.calibration_loaded:
            print(f"Loading calibration for current brightness: {self.brightness}")
            self.load_calibration_for_brightness(self.brightness)
    
    def load_calibration_for_brightness(self, brightness):
        genfile_path = Path(GENFILES_PATH) / f"VG{brightness:02d}.genrgb"
        
        if not genfile_path.exists():
            print(f"⚠️ Calibration file not found: {genfile_path}")
            self.calibration_loaded = False
            self.current_profile = None
            return False
        
        try:
            if correction_engine.load_calibration(str(genfile_path)):
                self.calibration_loaded = True
                self.current_profile = f"VG{brightness:02d}"
                mode = "FAST" if is_fast_mode() else "SLOW"
                print(f"✓ Calibration loaded: {self.current_profile} (Mode: {mode})")
                return True
            else:
                self.calibration_loaded = False
                self.current_profile = None
                return False
            
        except Exception as e:
            print(f"Error loading calibration: {e}")
            self.calibration_loaded = False
            self.current_profile = None
            return False
    
    def toggle_blc_slc(self):
        self.enable_blc_slc = not self.enable_blc_slc
        print(f"BLC/SLC: {'ON' if self.enable_blc_slc else 'OFF'}")
        return self.enable_blc_slc
    
    def toggle_glc(self):
        self.enable_glc = not self.enable_glc
        print(f"GLC: {'ON' if self.enable_glc else 'OFF'}")
        return self.enable_glc
    
    def toggle_dark_glc(self):
        self.enable_dark_glc = not self.enable_dark_glc
        print(f"Dark GLC: {'ON' if self.enable_dark_glc else 'OFF'}")
        return self.enable_dark_glc
    
    def toggle_nlm(self):
        self.enable_nlm = not self.enable_nlm
        status = 'ON' if self.enable_nlm else 'OFF'
        fps_impact = '(~60 FPS)' if self.enable_nlm else '(~60 FPS)'
        print(f"NLM Denoise: {status} {fps_impact}")
        return self.enable_nlm
    
    def get_status(self):
        return {
            'brightness': self.brightness,
            'zoom': self.zoom,
            'pan': self.pan,
            'focus': self.focus,
            'auto_corrections': self.auto_corrections,
            'profile': self.current_profile if self.calibration_loaded else None,
            'connected': self.cap is not None and self.cap.isOpened(),
            'fast_mode': is_fast_mode(),
            'enable_blc_slc': self.enable_blc_slc,
            'enable_glc': self.enable_glc,
            'enable_dark_glc': self.enable_dark_glc,
            'enable_nlm': self.enable_nlm
        }
    
    def diagnose_camera(self):
        if not self.cap or not self.cap.isOpened():
            print("❌ Camera not opened")
            return
        
        properties = {
            'WIDTH': cv2.CAP_PROP_FRAME_WIDTH,
            'HEIGHT': cv2.CAP_PROP_FRAME_HEIGHT,
            'FPS': cv2.CAP_PROP_FPS,
            'BRIGHTNESS': cv2.CAP_PROP_BRIGHTNESS,
            'ZOOM': cv2.CAP_PROP_ZOOM,
            'FOCUS': cv2.CAP_PROP_FOCUS,
            'PAN': cv2.CAP_PROP_PAN,
            'TILT': cv2.CAP_PROP_TILT,
            'AUTOFOCUS': cv2.CAP_PROP_AUTOFOCUS,
            'FORMAT': cv2.CAP_PROP_FORMAT,
        }
        
        print("\n" + "=" * 60)
        print("📹 CAMERA DIAGNOSTICS")
        print("=" * 60)
        for name, prop in properties.items():
            value = self.cap.get(prop)
            print(f"{name:15} : {value}")
        
        ret, frame = self.cap.read()
        if ret:
            print(f"\n✅ Frame read successful: {frame.shape}")
        else:
            print("\n❌ Failed to read frame!")
        print("=" * 60 + "\n")