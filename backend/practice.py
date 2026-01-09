import cv2
import time
import numpy as np
from corrections_loader import correction_engine, is_fast_mode

print("=" * 70)
print("CAMERA + CORRECTIONS TEST - SIDE BY SIDE")
print("=" * 70)

calibration_file = "genfiles/VG43.genrgb"

print(f"\nLoading calibration: {calibration_file}")
if not correction_engine.load_calibration(calibration_file):
    print("✗ Failed to load calibration")
    print("\nTrying alternative files...")
    alternatives = ["genfiles/VG40.genrgb", "genfiles/VG42.genrgb", "genfiles/VG43.genrgb"]
    success = False
    for alt in alternatives:
        print(f"  Trying: {alt}")
        if correction_engine.load_calibration(alt):
            print(f"  ✓ Loaded: {alt}")
            calibration_file = alt
            success = True
            break
    if not success:
        print("✗ No calibration file found!")
        exit(1)

print(f"\n✓ Calibration loaded: {calibration_file}")
print(f"✓ Fast mode: {is_fast_mode()}")

print("\nOpening camera...")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 483)
cap.set(cv2.CAP_PROP_BRIGHTNESS, 43)
cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)

if not cap.isOpened():
    print("✗ Failed to open camera")
    exit(1)

actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"✓ Camera opened: {actual_w}×{actual_h}")

for i in range(5):
    cap.grab()

print("\n" + "=" * 70)
print("CONTROLS:")
print("  SPACE     = Toggle ALL corrections ON/OFF")
print("  '1'       = Toggle BLC/SLC only")
print("  '2'       = Toggle GLC only")
print("  '3'       = Toggle Dark GLC only")
print("  UP/DOWN   = Adjust brightness")
print("  'q'       = Quit")
print("=" * 70)

corrections_enabled = True
enable_blc_slc = True
enable_glc = True
enable_dark_glc = True

fps_time = time.time()
fps_counter = 0
fps = 0

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to read frame")
        time.sleep(0.1)
        continue
    
    fps_counter += 1
    if time.time() - fps_time > 1.0:
        fps = fps_counter
        fps_counter = 0
        fps_time = time.time()
    
    raw_frame = frame.copy()
    
    if corrections_enabled:
        corrected_frame = frame.copy()
        corrected_frame = correction_engine.apply_corrections(
            corrected_frame,
            enable_blc_slc=enable_blc_slc,
            enable_glc=enable_glc,
            enable_dark_glc=enable_dark_glc
        )
    else:
        corrected_frame = frame.copy()
    
    h, w = frame.shape[:2]
    display = np.zeros((h, w*2, 3), dtype=np.uint8)
    display[:, :w] = raw_frame
    display[:, w:] = corrected_frame
    
    cv2.putText(display, "RAW", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    cv2.putText(display, "CORRECTED", (w+10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    
    y = 60
    status_color = (0, 255, 0) if corrections_enabled else (0, 0, 255)
    cv2.putText(display, f"Corrections: {'ON' if corrections_enabled else 'OFF'}", 
               (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 1)
    y += 25
    
    if corrections_enabled:
        stages = [
            (enable_blc_slc, "1.BLC/SLC"),
            (enable_glc, "2.GLC"),
            (enable_dark_glc, "3.DarkGLC")
        ]
        
        for enabled, name in stages:
            color = (0, 255, 0) if enabled else (100, 100, 100)
            cv2.putText(display, f"{name}: {'ON' if enabled else 'OFF'}", 
                       (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            y += 20
    
    cv2.putText(display, f"FPS: {fps}", (10, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
    y += 25
    
    mode_text = "FAST" if is_fast_mode() else "SLOW"
    mode_color = (0, 255, 0) if is_fast_mode() else (0, 165, 255)
    cv2.putText(display, f"Mode: {mode_text}", (10, y),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, mode_color, 1)
    
    cv2.line(display, (w, 0), (w, h), (255, 255, 255), 2)
    
    cv2.imshow('Camera + Corrections Test', display)
    
    key = cv2.waitKey(1) & 0xFF
    
    if key == ord('q'):
        break
    elif key == ord(' '):
        corrections_enabled = not corrections_enabled
        print(f"\nCorrections: {'ON' if corrections_enabled else 'OFF'}")
    elif key == ord('1'):
        enable_blc_slc = not enable_blc_slc
        print(f"BLC/SLC: {'ON' if enable_blc_slc else 'OFF'}")
    elif key == ord('2'):
        enable_glc = not enable_glc
        print(f"GLC: {'ON' if enable_glc else 'OFF'}")
    elif key == ord('3'):
        enable_dark_glc = not enable_dark_glc
        print(f"Dark GLC: {'ON' if enable_dark_glc else 'OFF'}")
    elif key == 82:
        b = int(cap.get(cv2.CAP_PROP_BRIGHTNESS)) + 1
        cap.set(cv2.CAP_PROP_BRIGHTNESS, min(60, b))
        print(f"Brightness: {b}")
    elif key == 84:
        b = int(cap.get(cv2.CAP_PROP_BRIGHTNESS)) - 1
        cap.set(cv2.CAP_PROP_BRIGHTNESS, max(7, b))
        print(f"Brightness: {b}")

cap.release()
cv2.destroyAllWindows()
print("\n✓ Test completed")