// JARVIS Frontend Controller
const API_BASE = 'http://192.168.1.171:8000';

// State
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let currentLanguage = 'en';
let isProcessing = false;

// Elements
const voiceButton = document.getElementById('voiceButton');
const visionBtn = document.getElementById('visionBtn');
const stopBtn = document.getElementById('stopBtn');
const jarvisAvatar = document.getElementById('jarvisAvatar');
const avatarStatus = document.getElementById('avatarStatus');
const logContent = document.getElementById('logContent');
const jarvisAudio = document.getElementById('jarvisAudio');
const loadingOverlay = document.getElementById('loadingOverlay');
const visionOverlay = document.getElementById('visionOverlay');
const visionText = document.getElementById('visionText');
const brightnessSlider = document.getElementById('brightnessSlider');
const brightnessValue = document.getElementById('brightnessValue');

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initializeVoiceControl();
    initializeLanguageToggle();
    initializePTZButtons();
    initializeBrightnessControl();
    initializeActionButtons();
    updateStatus();
    setInterval(updateStatus, 2000);
    
    addLog('JARVIS system initialized', 'success');
});

// ============================================================================
// STATUS UPDATES
// ============================================================================

async function updateStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();
        
        document.getElementById('cameraStatus').textContent = data.connected ? 'CONNECTED' : 'OFFLINE';
        document.getElementById('cameraStatus').style.color = data.connected ? 'var(--success)' : 'var(--error)';
    } catch (err) {
        console.error('Status update failed:', err);
    }
}

// ============================================================================
// VOICE CONTROL
// ============================================================================

function initializeVoiceControl() {
    // Hold to speak
    voiceButton.addEventListener('mousedown', startRecording);
    voiceButton.addEventListener('mouseup', stopRecording);
    voiceButton.addEventListener('mouseleave', stopRecording);
    
    // Touch support
    voiceButton.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startRecording();
    });
    voiceButton.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopRecording();
    });
    
    console.log('✅ Voice control initialized');
}

async function startRecording() {
    if (isRecording || isProcessing) return;
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        audioChunks = [];
        
        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };
        
        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            processVoiceCommand(audioBlob);
            stream.getTracks().forEach(track => track.stop());
        };
        
        mediaRecorder.start();
        isRecording = true;
        
        voiceButton.classList.add('active');
        setAvatarState('listening');
        addLog('Listening...', 'info');
        
        console.log('🎤 Recording started');
        
    } catch (err) {
        console.error('❌ Microphone error:', err);
        addLog('Microphone access denied', 'error');
        alert('Please allow microphone access');
    }
}

function stopRecording() {
    if (!isRecording) return;
    
    mediaRecorder.stop();
    isRecording = false;
    
    voiceButton.classList.remove('active');
    setAvatarState('processing');
    
    console.log('🎤 Recording stopped');
}

async function processVoiceCommand(audioBlob) {
    if (isProcessing) return;
    isProcessing = true;
    
    showLoading('Processing voice...');
    
    try {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'voice.webm');
        formData.append('language', currentLanguage);
        
        const response = await fetch(`${API_BASE}/jarvis/audio`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.error) {
            addLog(`Error: ${result.error}`, 'error');
            hideLoading();
            setAvatarState('idle');
            isProcessing = false;
            return;
        }
        
        // Log transcript
        addLog(`You: ${result.transcript}`, 'info');
        
        // Log response
        addLog(`JARVIS: ${result.response}`, 'success');
        
        // Play voice response
        if (result.audio) {
            await playJarvisVoice(result.audio);
        }
        
        // Execute action
        if (result.action) {
            await executeAction(result.action, result.parameters);
        }
        
        hideLoading();
        setAvatarState('idle');
        
    } catch (err) {
        console.error('❌ Voice processing error:', err);
        addLog('Voice processing failed', 'error');
        hideLoading();
        setAvatarState('idle');
    }
    
    isProcessing = false;
}

// ============================================================================
// VISION ANALYSIS
// ============================================================================

async function analyzeVision() {
    if (isProcessing) return;
    isProcessing = true;
    
    setAvatarState('processing');
    visionOverlay.classList.remove('hidden');
    visionText.textContent = 'Analyzing camera feed...';
    
    try {
        const prompt = currentLanguage === 'ko' 
            ? '무엇이 보이나요?' 
            : 'What do you see?';
        
        const response = await fetch(`${API_BASE}/jarvis/vision?prompt=${encodeURIComponent(prompt)}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.error) {
            visionText.textContent = `Error: ${result.error}`;
            addLog(`Vision error: ${result.error}`, 'error');
        } else {
            visionText.textContent = result.response;
            addLog(`JARVIS Vision: ${result.response}`, 'success');
            
            // Play voice response
            if (result.audio) {
                await playJarvisVoice(result.audio);
            }
        }
        
        // Hide vision overlay after 5 seconds
        setTimeout(() => {
            visionOverlay.classList.add('hidden');
        }, 5000);
        
    } catch (err) {
        console.error('❌ Vision error:', err);
        visionText.textContent = 'Vision analysis failed';
        addLog('Vision analysis failed', 'error');
        
        setTimeout(() => {
            visionOverlay.classList.add('hidden');
        }, 3000);
    }
    
    setAvatarState('idle');
    isProcessing = false;
}

// ============================================================================
// AUDIO PLAYBACK
// ============================================================================

async function playJarvisVoice(base64Audio) {
    return new Promise((resolve) => {
        try {
            const audioBlob = base64ToBlob(base64Audio, 'audio/mpeg');
            const audioUrl = URL.createObjectURL(audioBlob);
            
            jarvisAudio.src = audioUrl;
            jarvisAudio.play();
            
            setAvatarState('speaking');
            
            jarvisAudio.onended = () => {
                setAvatarState('idle');
                URL.revokeObjectURL(audioUrl);
                resolve();
            };
            
        } catch (err) {
            console.error('❌ Audio playback error:', err);
            resolve();
        }
    });
}

function base64ToBlob(base64, mimeType) {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type: mimeType });
}

// ============================================================================
// PTZ COMMAND EXECUTION
// ============================================================================

async function executeAction(action, parameters) {
    if (!action) return;
    
    addLog(`Executing: ${action}`, 'info');
    
    try {
        const response = await fetch(`${API_BASE}/jarvis/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, parameters })
        });
        
        const result = await response.json();
        
        if (result.success) {
            addLog(`✓ ${result.message}`, 'success');
        } else {
            addLog(`✗ ${result.message}`, 'error');
        }
        
    } catch (err) {
        console.error('❌ Action execution error:', err);
        addLog(`Action failed: ${action}`, 'error');
    }
}

// ============================================================================
// UI STATE MANAGEMENT
// ============================================================================

function setAvatarState(state) {
    avatarStatus.textContent = state.toUpperCase();
    jarvisAvatar.className = 'jarvis-avatar ' + state;
    
    const colors = {
        'idle': 'var(--arc-blue)',
        'listening': 'var(--success)',
        'processing': 'var(--warning)',
        'speaking': 'var(--arc-blue)'
    };
    
    avatarStatus.style.color = colors[state] || 'var(--arc-blue)';
    avatarStatus.style.textShadow = `0 0 10px ${colors[state] || 'var(--arc-blue)'}`;
}

function showLoading(message = 'Processing...') {
    loadingOverlay.querySelector('.loading-text').textContent = message;
    loadingOverlay.classList.remove('hidden');
}

function hideLoading() {
    loadingOverlay.classList.add('hidden');
}

function addLog(text, type = 'info') {
    const time = new Date().toLocaleTimeString('en-US', { 
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-text">${text}</span>
    `;
    
    logContent.appendChild(entry);
    logContent.scrollTop = logContent.scrollHeight;
    
    // Keep only last 50 entries
    while (logContent.children.length > 50) {
        logContent.removeChild(logContent.firstChild);
    }
}

// ============================================================================
// LANGUAGE TOGGLE
// ============================================================================

function initializeLanguageToggle() {
    const langButtons = document.querySelectorAll('.lang-btn');
    
    langButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            langButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentLanguage = btn.dataset.lang;
            
            const langName = currentLanguage === 'ko' ? 'Korean' : 'English';
            addLog(`Language: ${langName}`, 'info');
        });
    });
}

// ============================================================================
// PTZ BUTTON CONTROLS
// ============================================================================

function initializePTZButtons() {
    const ptzButtons = document.querySelectorAll('.ptz-btn');
    
    ptzButtons.forEach(btn => {
        btn.addEventListener('click', async () => {
            const action = btn.dataset.action;
            await executeAction(action, { duration: 2 });
        });
    });
}

// ============================================================================
// ACTION BUTTONS
// ============================================================================

function initializeActionButtons() {
    visionBtn.addEventListener('click', analyzeVision);
    
    stopBtn.addEventListener('click', async () => {
        try {
            await fetch(`${API_BASE}/ptz/stop`, { method: 'POST' });
            addLog('All movements stopped', 'success');
        } catch (err) {
            console.error('Stop error:', err);
        }
    });
}

// ============================================================================
// BRIGHTNESS CONTROL
// ============================================================================

function initializeBrightnessControl() {
    brightnessSlider.addEventListener('input', async (e) => {
        const value = e.target.value;
        brightnessValue.textContent = value;
        
        try {
            await fetch(`${API_BASE}/brightness/${value}`, { method: 'POST' });
        } catch (err) {
            console.error('Brightness error:', err);
        }
    });
}

// ============================================================================
// UTILITY
// ============================================================================

console.log('🤖 JARVIS interface loaded');
console.log('🎯 Ready for voice commands');
