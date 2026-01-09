from fastapi import FastAPI, WebSocket, Response, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import cv2
import json
import threading
import time
from pathlib import Path
from camera_handler import CameraHandler
from histogram_processor import HistogramProcessor
from config import *
from fastapi import UploadFile, File
import base64
#from jarvis_voice import RobotAI
import asyncio



app = FastAPI()
#robot_ai = RobotAI()
frontend_path = Path(__file__).parent.parent / "frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

camera = CameraHandler()
histogram_proc = HistogramProcessor()
camera.histogram_proc = histogram_proc
# PTZ continuous control state
zoom_moving = False
focus_moving = False
pan_moving = False
zoom_speed = 0
focus_speed = 0
pan_speed = 0
ptz_thread_running = False
# Image flip state
horizontal_flip_enabled = False

def apply_zoom_step(speed):
    """Apply zoom control with speed"""
    if camera.cap is None or not camera.cap.isOpened():
        return False
    
    try:
        current = camera.cap.get(cv2.CAP_PROP_ZOOM)
        if current is None:
            return False
        
        if speed == 0:
            return True
        
        step_size = 0.5
        new_value = current + (speed * step_size)
        new_value = max(1, min(10, round(new_value, 1)))
        
        if (current >= 10 and speed > 0) or (current <= 1 and speed < 0):
            return False
        
        result = camera.cap.set(cv2.CAP_PROP_ZOOM, new_value)
        if result:
            camera.zoom = new_value
            print(f"[ZOOM] {current:.1f} → {new_value:.1f}")
        return result
    except Exception as e:
        print(f"[ZOOM] Error: {e}")
        return False

def apply_focus_step(speed):
    """Apply focus control with speed - RANGE: 0-300"""
    if camera.cap is None or not camera.cap.isOpened():
        return False
    
    try:
        # CRITICAL: Disable autofocus for manual control
        camera.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        
        current = camera.cap.get(cv2.CAP_PROP_FOCUS)
        if current is None:
            current = 150  # Default fallback
        
        if speed == 0:
            # Stop - just hold current position
            camera.cap.set(cv2.CAP_PROP_FOCUS, current)
            return True
        
        step_size = 3.0  # Increased for better visibility
        new_value = current + (speed * step_size)
        new_value = max(0, min(1000, round(new_value)))  # CORRECT RANGE: 0-300
        
        if (current >= 500 and speed > 0) or (current <= 0 and speed < 0):
            print(f"[FOCUS] At limit {current:.1f}")
            return False
        
        result = camera.cap.set(cv2.CAP_PROP_FOCUS, new_value)
        if result:
            camera.focus = new_value
            print(f"[FOCUS] {current:.1f} → {new_value:.1f}")
        else:
            print(f"[FOCUS] ⚠️ Failed to set focus to {new_value}")
        return result
    except Exception as e:
        print(f"[FOCUS] Error: {e}")
        return False

def apply_pan_step(speed):
    """Apply pan control with speed"""
    if camera.cap is None or not camera.cap.isOpened():
        return False
    
    try:
        current = camera.cap.get(cv2.CAP_PROP_PAN)
        if current is None:
            current = 0
        
        if speed == 0:
            # Stop: just maintain current position
            safe_current = max(-10, min(10, current))
            camera.cap.set(cv2.CAP_PROP_PAN, safe_current)
            return True
        
        step_size = 0.5
        new_value = current + (speed * step_size)
        
        if (current >= 9.5 and speed > 0) or (current <= -9.5 and speed < 0):
            print(f"[PAN] At limit {current:.1f}")
            return False
        
        new_value = max(-10, min(10, round(new_value, 1)))
        
        result = camera.cap.set(cv2.CAP_PROP_PAN, new_value)
        if result:
            camera.pan = new_value
            print(f"[PAN] {current:.1f} → {new_value:.1f}")
        return result
    except Exception as e:
        print(f"[PAN] Error: {e}")
        return False

def ptz_controller_thread():
    """Continuous PTZ control loop"""
    global zoom_speed, focus_speed, pan_speed
    global zoom_moving, focus_moving, pan_moving
    global ptz_thread_running
    
    print("[PTZ] Controller thread started")
    ptz_thread_running = True
    
    while ptz_thread_running:
        try:
            
            if zoom_moving and abs(zoom_speed) > 0:
                apply_zoom_step(zoom_speed)
            
            
            if focus_moving and abs(focus_speed) > 0:
                apply_focus_step(focus_speed)
            
            
            if pan_moving and abs(pan_speed) > 0:
                apply_pan_step(pan_speed)
            
            time.sleep(0.15) 
        
        except Exception as e:
            print(f"[PTZ] Error: {e}")
            time.sleep(0.15)
    
    print("[PTZ] Controller thread stopped")
def process(self, frame):
    """Return histogram data (for /histogram endpoint)"""
    hist_data = self.calculate_histogram(frame)
    return {
        'histogram': hist_data,
        'min': self.min_value,
        'max': self.max_value,
        'nlm_enabled': self.nlm_enabled
    }
@app.on_event("startup")
async def startup():
    global ptz_thread_running
    if camera.start():
        # Disable autofocus on startup
        if camera.cap and camera.cap.isOpened():
            camera.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            print("✅ Autofocus disabled for manual control")
        
        # Start PTZ controller thread
        threading.Thread(target=ptz_controller_thread, daemon=True).start()
        print("Application started successfully")
    else:
        print(" Failed to start camera")

# ============================================================================
# STATIC FILE SERVING
# ============================================================================

@app.get("/style.css")
async def serve_css():
    """Serve CSS file"""
    css_file = frontend_path / "style.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS file not found")

@app.get("/app.js")
async def serve_app_js():
    """Serve app.js file"""
    js_file = frontend_path / "app.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")

@app.get("/histogram.js")
async def serve_histogram_js():
    """Serve histogram.js file"""
    js_file = frontend_path / "histogram.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="histogram.js not found")
@app.get("/robot-assistant.css")
async def serve_robot_css():
    """Serve robot-assistant.css file"""
    css_file = frontend_path / "robot-assistant.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="robot-assistant.css not found")

@app.get("/robot-assistant.js")
async def serve_robot_js():
    """Serve robot-assistant.js file"""
    js_file = frontend_path / "robot-assistant.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="robot-assistant.js not found")
@app.get("/voicei.js")
async def serve_voice_js():
    """Serve voice.js file"""
    js_file = frontend_path / "voicei.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="voicei.js not found")

@app.get("/favicon.ico")
async def serve_favicon():
    """Serve favicon"""
    favicon_file = frontend_path / "favicon.ico"
    if favicon_file.exists():
        return FileResponse(favicon_file, media_type="image/x-icon")
    # Return 204 No Content if favicon doesn't exist
    return Response(status_code=204)

@app.on_event("shutdown")
async def shutdown():
    global ptz_thread_running, zoom_moving, focus_moving, pan_moving
    
    # Stop PTZ movements
    ptz_thread_running = False
    zoom_moving = False
    focus_moving = False
    pan_moving = False
    
    camera.stop()
    print("Application stopped")

@app.get("/")
async def root():
    frontend_file = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_file.exists():
        with open(frontend_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    return {"app": "SeeDevice", "status": "running", "message": "Frontend not found. Open frontend/index.html manually"}

@app.get("/video_feed")
async def video_feed():
    def generate():
        while True:
            frame = camera.get_frame()
            if frame is None:
                continue
            
            # Apply horizontal flip if enabled
            if horizontal_flip_enabled:
                frame = cv2.flip(frame, 1)  # 1 = horizontal flip
            
            # Process histogram
            ##frame = histogram_proc.process_frame(frame)
            
            # Encode to JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/status")
async def get_status():
    status = camera.get_status()
    status['histogram_min'] = histogram_proc.min_value
    status['histogram_max'] = histogram_proc.max_value
    status['nlm_enabled'] = histogram_proc.nlm_enabled
    status['zoom_moving'] = zoom_moving
    status['focus_moving'] = focus_moving
    status['pan_moving'] = pan_moving
    status['horizontal_flip'] = horizontal_flip_enabled
    return status

@app.get("/histogram")
async def get_histogram():
    """Get histogram of RAW frame (before normalization)"""
    frame = camera.get_frame()
    if frame is None:
        return {"error": "No frame available"}
    
   
    hist_data = histogram_proc.calculate_histogram(frame)
    
    return {
        'histogram': hist_data,
        'min': histogram_proc.min_value,
        'max': histogram_proc.max_value
    }
@app.post("/brightness/{value}")
async def set_brightness(value: int):
    camera.set_brightness(value)
    return {"brightness": camera.brightness, "profile": camera.current_profile}

@app.post("/auto_corrections/{enabled}")
async def set_auto_corrections(enabled: bool):
    camera.set_auto_corrections(enabled)
    return {"auto_corrections": camera.auto_corrections}
@app.post("/corrections/toggle/nlm")
async def toggle_nlm():
    state = camera.toggle_nlm()
    return {"nlm": state}
@app.post("/histogram/min/{value}")
async def set_histogram_min(value: int):
    histogram_proc.set_min_max(value, histogram_proc.max_value)
    return {"min": histogram_proc.min_value}

@app.post("/histogram/max/{value}")
async def set_histogram_max(value: int):
    histogram_proc.set_min_max(histogram_proc.min_value, value)
    return {"max": histogram_proc.max_value}

@app.post("/nlm/{enabled}")
async def set_nlm(enabled: bool):
    histogram_proc.set_nlm(enabled)
    return {"nlm_enabled": histogram_proc.nlm_enabled}

@app.post("/horizontal_flip/{enabled}")
async def set_horizontal_flip(enabled: bool):
    """Toggle horizontal flip of video feed"""
    global horizontal_flip_enabled
    horizontal_flip_enabled = enabled
    print(f"[FLIP] Horizontal flip: {'ENABLED' if enabled else 'DISABLED'}")
    return {"horizontal_flip": horizontal_flip_enabled, "success": True}

# ============================================================================
# PTZ CONTINUOUS MOVEMENT CONTROLS (Hold-to-Move)
# ============================================================================

@app.post("/ptz/zoom/start/{direction}")
async def zoom_start(direction: str):
    """Start continuous zoom movement"""
    global zoom_moving, zoom_speed
    
    if direction == "in":
        zoom_speed = 2
        zoom_moving = True
        print(f"[ZOOM] Started continuous IN (speed={zoom_speed})")
        return {"action": "zoom_in_start", "speed": zoom_speed}
    elif direction == "out":
        zoom_speed = -2
        zoom_moving = True
        print(f"[ZOOM] Started continuous OUT (speed={zoom_speed})")
        return {"action": "zoom_out_start", "speed": zoom_speed}
    else:
        return {"error": "Invalid direction. Use 'in' or 'out'"}

@app.post("/ptz/zoom/stop")
async def zoom_stop():
    """Stop zoom movement - INSTANT"""
    global zoom_moving, zoom_speed
    zoom_moving = False
    zoom_speed = 0
    
    # Force immediate position hold
    if camera.cap and camera.cap.isOpened():
        current = camera.cap.get(cv2.CAP_PROP_ZOOM)
        if current is not None:
            camera.cap.set(cv2.CAP_PROP_ZOOM, current)
            print(f"[ZOOM] STOPPED at {current:.1f}")
    
    return {"action": "zoom_stop", "instant": True}

@app.post("/ptz/focus/start/{direction}")
async def focus_start(direction: str):
    """Start continuous focus movement - RANGE: 0-300"""
    global focus_moving, focus_speed
    
    # CRITICAL: Ensure autofocus is OFF
    if camera.cap and camera.cap.isOpened():
        camera.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        # Verify
        af = camera.cap.get(cv2.CAP_PROP_AUTOFOCUS)
        print(f"[FOCUS] Autofocus status: {af} (should be 0)")
    
    if direction == "in" or direction == "near":
        focus_speed = 8  # Increased speed for better visibility
        focus_moving = True
        print(f"[FOCUS] Started continuous IN (speed={focus_speed}, range=0-300)")
        return {"action": "focus_in_start", "speed": focus_speed, "autofocus": "disabled"}
    elif direction == "out" or direction == "far":
        focus_speed = -8
        focus_moving = True
        print(f"[FOCUS] Started continuous OUT (speed={focus_speed}, range=0-300)")
        return {"action": "focus_out_start", "speed": focus_speed, "autofocus": "disabled"}
    else:
        return {"error": "Invalid direction. Use 'in'/'near' or 'out'/'far'"}

@app.post("/ptz/focus/stop")
async def focus_stop():
    """Stop focus movement - INSTANT"""
    global focus_moving, focus_speed
    focus_moving = False
    focus_speed = 0
    
    # Force immediate position hold
    if camera.cap and camera.cap.isOpened():
        current = camera.cap.get(cv2.CAP_PROP_FOCUS)
        if current is not None:
            camera.cap.set(cv2.CAP_PROP_FOCUS, current)
            print(f"[FOCUS] STOPPED at {current:.1f}")
    
    return {"action": "focus_stop", "instant": True}

@app.post("/ptz/pan/start/{direction}")
async def pan_start(direction: str):
    """Start continuous pan movement"""
    global pan_moving, pan_speed
    
    if direction == "left":
        pan_speed = -2
        pan_moving = True
        print(f"[PAN] Started continuous LEFT (speed={pan_speed})")
        return {"action": "pan_left_start", "speed": pan_speed}
    elif direction == "right":
        pan_speed = 2
        pan_moving = True
        print(f"[PAN] Started continuous RIGHT (speed={pan_speed})")
        return {"action": "pan_right_start", "speed": pan_speed}
    else:
        return {"error": "Invalid direction. Use 'left' or 'right'"}

@app.post("/ptz/pan/stop")
async def pan_stop():
    """Stop pan movement - INSTANT"""
    global pan_moving, pan_speed
    pan_moving = False
    pan_speed = 0
    
    # Force immediate position hold
    if camera.cap and camera.cap.isOpened():
        current = camera.cap.get(cv2.CAP_PROP_PAN)
        if current is not None:
            camera.cap.set(cv2.CAP_PROP_PAN, current)
            print(f"[PAN] STOPPED at {current:.1f}")
    
    return {"action": "pan_stop", "instant": True}

@app.post("/ptz/stop")
async def ptz_stop_all():
    """Emergency stop - stops ALL PTZ movements immediately"""
    global zoom_moving, focus_moving, pan_moving
    global zoom_speed, focus_speed, pan_speed
    
    zoom_moving = False
    focus_moving = False
    pan_moving = False
    zoom_speed = 0
    focus_speed = 0
    pan_speed = 0
    
    # Force immediate position holds
    if camera.cap and camera.cap.isOpened():
        zoom_val = camera.cap.get(cv2.CAP_PROP_ZOOM)
        focus_val = camera.cap.get(cv2.CAP_PROP_FOCUS)
        pan_val = camera.cap.get(cv2.CAP_PROP_PAN)
        
        if zoom_val is not None:
            camera.cap.set(cv2.CAP_PROP_ZOOM, zoom_val)
        if focus_val is not None:
            camera.cap.set(cv2.CAP_PROP_FOCUS, focus_val)
        if pan_val is not None:
            camera.cap.set(cv2.CAP_PROP_PAN, pan_val)
    
    print("[PTZ] ALL STOPPED (emergency)")
    return {"action": "all_stopped"}

# ============================================================================
# PTZ SINGLE STEP CONTROLS (Click-to-Step)
# ============================================================================

@app.post("/zoom/in")
async def zoom_in_step():
    """Single step zoom in"""
    if not camera.cap or not camera.cap.isOpened():
        return {"error": "Camera not available"}
    
    current = camera.cap.get(cv2.CAP_PROP_ZOOM)
    if current is None:
        current = 5
    
    new_val = min(15, current + 1)
    result = camera.cap.set(cv2.CAP_PROP_ZOOM, new_val)
    
    if result:
        camera.zoom = new_val
        print(f"[ZOOM STEP] IN: {current:.1f} → {new_val:.1f}")
        return {"action": "zoom_in", "zoom": new_val, "success": True}
    return {"error": "Failed to set zoom", "success": False}

@app.post("/zoom/out")
async def zoom_out_step():
    """Single step zoom out"""
    if not camera.cap or not camera.cap.isOpened():
        return {"error": "Camera not available"}
    
    current = camera.cap.get(cv2.CAP_PROP_ZOOM)
    if current is None:
        current = 5
    
    new_val = max(1, current - 1)
    result = camera.cap.set(cv2.CAP_PROP_ZOOM, new_val)
    
    if result:
        camera.zoom = new_val
        print(f"[ZOOM STEP] OUT: {current:.1f} → {new_val:.1f}")
        return {"action": "zoom_out", "zoom": new_val, "success": True}
    return {"error": "Failed to set zoom", "success": False}

@app.post("/ptz/focus/step/in")
async def focus_step_in():
    """Single step focus in (near) - RANGE: 0-300"""
    if not camera.cap or not camera.cap.isOpened():
        return {"error": "Camera not available"}
    
    # CRITICAL: Disable autofocus
    camera.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    
    current = camera.cap.get(cv2.CAP_PROP_FOCUS)
    if current is None:
        current = 150
    
    new_value = min(1000, round(current + 15))  # Larger step for visibility, 0-300 range
    result = camera.cap.set(cv2.CAP_PROP_FOCUS, new_value)
    
    if result:
        camera.focus = new_value
        print(f"[FOCUS STEP] IN: {current:.1f} → {new_value:.1f}")
        return {"action": "focus_step_in", "focus": new_value, "success": True}
    
    print(f"[FOCUS STEP] ⚠️ Failed to set focus to {new_value}")
    return {"error": "Failed to set focus", "success": False}

@app.post("/ptz/focus/step/out")
async def focus_step_out():
    """Single step focus out (far) - RANGE: 0-300"""
    if not camera.cap or not camera.cap.isOpened():
        return {"error": "Camera not available"}
    
    # CRITICAL: Disable autofocus
    camera.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    
    current = camera.cap.get(cv2.CAP_PROP_FOCUS)
    if current is None:
        current = 150
    
    new_value = max(0, round(current - 15))  # Larger step for visibility, 0-300 range
    result = camera.cap.set(cv2.CAP_PROP_FOCUS, new_value)
    
    if result:
        camera.focus = new_value
        print(f"[FOCUS STEP] OUT: {current:.1f} → {new_value:.1f}")
        return {"action": "focus_step_out", "focus": new_value, "success": True}
    
    print(f"[FOCUS STEP] ⚠️ Failed to set focus to {new_value}")
    return {"error": "Failed to set focus", "success": False}

@app.post("/ptz/left")
async def ptz_left_step():
    """Single step pan left"""
    if not camera.cap or not camera.cap.isOpened():
        return {"error": "Camera not available"}
    
    current = camera.cap.get(cv2.CAP_PROP_PAN)
    if current is None:
        current = 0
    
    new_val = max(-10, current - 1)
    result = camera.cap.set(cv2.CAP_PROP_PAN, new_val)
    
    if result:
        camera.pan = new_val
        print(f"[PAN STEP] LEFT: {current:.1f} → {new_val:.1f}")
        return {"action": "left", "pan": new_val, "success": True}
    return {"error": "Failed to set pan", "success": False}

@app.post("/ptz/right")
async def ptz_right_step():
    """Single step pan right"""
    if not camera.cap or not camera.cap.isOpened():
        return {"error": "Camera not available"}
    
    current = camera.cap.get(cv2.CAP_PROP_PAN)
    if current is None:
        current = 0
    
    new_val = min(10, current + 1)
    result = camera.cap.set(cv2.CAP_PROP_PAN, new_val)
    
    if result:
        camera.pan = new_val
        print(f"[PAN STEP] RIGHT: {current:.1f} → {new_val:.1f}")
        return {"action": "right", "pan": new_val, "success": True}
    return {"error": "Failed to set pan", "success": False}

# ============================================================================
# DIAGNOSTICS
# ============================================================================

@app.get("/diagnose")
async def diagnose():
    """Run camera diagnostics"""
    camera.diagnose_camera()
    return {"message": "Check console for diagnostics"}

@app.post("/robot/voice")
async def robot_process_voice(audio: UploadFile = File(...)):
    """
    Process voice command with AI
    Returns: transcript, response, action, and Rachel voice audio
    """
    try:
        audio_data = await audio.read()
        result = await robot_ai.process_voice_command(audio_data)
        return result
    except Exception as e:
        print(f"[ROBOT/VOICE] Error: {e}")
        return {"error": str(e)}

@app.post("/robot/vision")
async def robot_analyze_vision(language: str = "en"):
    """
    Analyze camera frame with GPT-4 Vision
    READ-ONLY: Just looks and describes, doesn't change anything!
    """
    try:
        # Get current frame (WITH your corrections applied!)
        frame = camera.get_frame()
        if frame is None:
            return {"error": "No camera frame available"}
        
        # Apply horizontal flip if enabled
        if horizontal_flip_enabled:
            frame = cv2.flip(frame, 1)
        
        # Encode frame to base64
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ret:
            return {"error": "Failed to encode frame"}
        
        frame_base64 = base64.b64encode(buffer).decode()
        
        # Analyze with AI (READ-ONLY!)
        if language == "ko":
            prompt = "무엇이 보이나요?"
        else:
            prompt = "What do you see?"
        
        result = await robot_ai.analyze_vision(frame_base64, prompt, language)
        return result
        
    except Exception as e:
        print(f"[ROBOT/VISION] Error: {e}")
        return {"error": str(e)}

@app.post("/robot/execute")
async def robot_execute_action(command: dict):
    """
    Execute PTZ action from robot command
    """
    action = command.get("action")
    parameters = command.get("parameters", {})
    
    if not action:
        return {"success": False, "message": "No action"}
    
    try:
        if action == "zoom_in":
            duration = parameters.get("duration", 2)
            await zoom_start("in")
            await asyncio.sleep(duration)
            await zoom_stop()
            return {"success": True}
        
        elif action == "zoom_out":
            duration = parameters.get("duration", 2)
            await zoom_start("out")
            await asyncio.sleep(duration)
            await zoom_stop()
            return {"success": True}
        
        elif action == "focus_in":
            duration = parameters.get("duration", 2)
            await focus_start("in")
            await asyncio.sleep(duration)
            await focus_stop()
            return {"success": True}
        
        elif action == "focus_out":
            duration = parameters.get("duration", 2)
            await focus_start("out")
            await asyncio.sleep(duration)
            await focus_stop()
            return {"success": True}
        
        elif action == "pan_left":
            duration = parameters.get("duration", 2)
            await pan_start("left")
            await asyncio.sleep(duration)
            await pan_stop()
            return {"success": True}
        
        elif action == "pan_right":
            duration = parameters.get("duration", 2)
            await pan_start("right")
            await asyncio.sleep(duration)
            await pan_stop()
            return {"success": True}
        
        elif action == "brightness_up":
            amount = parameters.get("amount", 5)
            new_val = min(60, camera.brightness + amount)
            await set_brightness(new_val)
            return {"success": True}
        
        elif action == "brightness_down":
            amount = parameters.get("amount", 5)
            new_val = max(7, camera.brightness - amount)
            await set_brightness(new_val)
            return {"success": True}
        
        elif action == "stop":
            await ptz_stop_all()
            return {"success": True}
        
        elif action == "vision_request":
            return {"success": True, "message": "Vision requested"}
        
        else:
            return {"success": False, "message": f"Unknown action: {action}"}
            
    except Exception as e:
        print(f"[ROBOT/EXECUTE] Error: {e}")
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
