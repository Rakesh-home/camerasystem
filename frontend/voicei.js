// AI-POWERED VOICE CONTROL
// Now uses: Whisper + GPT-4 + Vision + Rachel Voice!

let voiceRecognition = null;
let voiceActive = false;
let listeningForCommand = false;
let voiceCheckbox = null;
let mediaRecorder = null;
let audioChunks = [];
let isProcessing = false;
let currentLanguage = 'en';

function initVoiceControl() {
    voiceCheckbox = document.getElementById('voiceControl');
    
    if (!voiceCheckbox) {
        console.error('❌ Voice control checkbox not found');
        return;
    }
    
    voiceCheckbox.addEventListener('change', (e) => {
        if (e.target.checked) {
            startVoiceControl();
        } else {
            stopVoiceControl();
        }
    });
    
    console.log('✅ AI Voice control initialized');
}

function startVoiceControl() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        alert('❌ Voice recognition not supported in this browser.\n\nTry Chrome, Edge, or Safari.');
        voiceCheckbox.checked = false;
        return;
    }
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    voiceRecognition = new SpeechRecognition();
    
    voiceRecognition.continuous = true;
    voiceRecognition.interimResults = false;
    voiceRecognition.lang = 'en-US';
    voiceRecognition.maxAlternatives = 1;
    
    voiceRecognition.onstart = handleVoiceStart;
    voiceRecognition.onend = handleVoiceEnd;
    voiceRecognition.onresult = handleVoiceResult;
    voiceRecognition.onerror = handleVoiceError;
    
    try {
        voiceRecognition.start();
        voiceActive = true;
        listeningForCommand = false;
        
        if (window.robotAssistant) {
            robotAssistant.show();
            robotAssistant.onVoiceActivated();
        }
        
        console.log('🎤 AI Voice control started');
    } catch (err) {
        console.error('❌ Failed to start:', err);
        voiceCheckbox.checked = false;
    }
}

function stopVoiceControl() {
    if (voiceRecognition) {
        voiceRecognition.stop();
        voiceRecognition = null;
    }
    
    voiceActive = false;
    listeningForCommand = false;
    
    if (window.robotAssistant) {
        robotAssistant.hide();
    }
    
    console.log('🎤 AI Voice stopped');
}

function handleVoiceStart() {
    console.log('🎤 Listening...');
}

function handleVoiceEnd() {
    if (voiceActive && voiceCheckbox.checked) {
        setTimeout(() => {
            try {
                voiceRecognition.start();
            } catch (err) {
                console.error('❌ Restart error:', err);
            }
        }, 100);
    }
}

async function handleVoiceResult(event) {
    const last = event.results.length - 1;
    const transcript = event.results[last][0].transcript.toLowerCase().trim();
    
    console.log(`🎤 Heard: "${transcript}"`);
    
    if (isWakeWord(transcript)) {
        activateListening();
        return;
    }
    
    if (listeningForCommand && isDeactivateWord(transcript)) {
        deactivateListening();
        return;
    }
    
    if (listeningForCommand) {
        // NEW: Send to AI backend!
        await executeAICommand(transcript);
    } else {
        console.log('⚠️ Say "STACY" first');
    }
}

function handleVoiceError(event) {
    console.error('🎤 Error:', event.error);
    
    if (event.error === 'no-speech') {
        return;
    }
    
    if (event.error === 'not-allowed') {
        alert('❌ Microphone access denied');
        stopVoiceControl();
        voiceCheckbox.checked = false;
        return;
    }
}

function isWakeWord(text) {
    const wakeWords = [
        'stacy', 'stacey', 'tracy', 'spacey',
        'hey stacy', 'hey stacey',
        'ok stacy', 'okay stacy','htc','h-t-c','h t c'
    ];
    
    return wakeWords.some(word => text.includes(word));
}

function isDeactivateWord(text) {
    const deactivateWords = ['exit', 'deactivate', 'stop listening', 'voice off'];
    return deactivateWords.some(word => text.includes(word));
}

function activateListening() {
    listeningForCommand = true;
    
    if (window.robotAssistant) {
        robotAssistant.onWakeWordDetected();
    }
    
    console.log('✅ LISTENING - AI Mode Active');
}

function deactivateListening() {
    listeningForCommand = false;
    
    if (window.robotAssistant) {
        robotAssistant.onVoiceDeactivated();
    }
    
    console.log('🔇 Deactivated');
}

// ============================================================================
// NEW: AI-POWERED COMMAND EXECUTION
// ============================================================================

async function executeAICommand(transcript) {
    if (isProcessing) {
        console.log('⚠️ Already processing...');
        return;
    }
    
    isProcessing = true;
    
    console.log(`⚡ AI Processing: "${transcript}"`);
    
    if (window.robotAssistant) {
        robotAssistant.setRobotState('processing');
        robotAssistant.addMessage(`You: ${transcript}`, 'info');
    }
    
    // Check if it's a vision command
    if (isVisionCommand(transcript)) {
        await handleVisionCommand(transcript);
    } else {
        await handleRegularCommand(transcript);
    }
    
    isProcessing = false;
}

function isVisionCommand(text) {
    const visionWords = ['see', 'look', 'view', 'identify', 'what is', 'describe', 'show me', '보여', '보이'];
    return visionWords.some(word => text.includes(word));
}

async function handleVisionCommand(transcript) {
    console.log('👁️ Vision command detected!');
    
    if (window.robotAssistant) {
        robotAssistant.addMessage('Analyzing camera...', 'info');
    }
    
    try {
        // Detect language
        const isKorean = /[ㄱ-ㅎ|ㅏ-ㅣ|가-힣]/.test(transcript);
        const language = isKorean ? 'ko' : 'en';
        
        const response = await fetch(`${API_BASE}/robot/vision?language=${language}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.error) {
            console.error('❌ Vision error:', result.error);
            if (window.robotAssistant) {
                robotAssistant.addMessage(`Error: ${result.error}`, 'error');
            }
        } else {
            console.log('👁️ Vision result:', result.response);
            
            if (window.robotAssistant) {
                robotAssistant.addMessage(`Robot: ${result.response}`, 'success');
            }
            
            // Play Rachel voice response
            if (result.audio) {
                await playRobotVoice(result.audio);
            }
        }
        
    } catch (err) {
        console.error('❌ Vision request failed:', err);
        if (window.robotAssistant) {
            robotAssistant.addMessage('Vision analysis failed', 'error');
        }
    }
    
    if (window.robotAssistant) {
        robotAssistant.setRobotState('listening');
    }
}

async function handleRegularCommand(transcript) {
    console.log('🎮 Regular command detected');
    
    try {
        // Create audio blob from transcript (we'll use text-to-command for now)
        // In future, could record actual audio
        const formData = new FormData();
        
        // For now, just send text command directly
        // We can optimize this later to send actual audio
        const response = await fetch(`${API_BASE}/robot/text_command`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: transcript })
        });
        
        // If text_command endpoint doesn't exist, fallback to local processing
        if (response.status === 404) {
            console.log('⚠️ Using fallback local command processing');
            await executeLocalCommand(transcript);
            return;
        }
        
        const result = await response.json();
        
        if (result.error) {
            console.error('❌ Command error:', result.error);
            await executeLocalCommand(transcript);  // Fallback
        } else {
            console.log('✅ AI Response:', result.response);
            
            if (window.robotAssistant) {
                robotAssistant.addMessage(`Robot: ${result.response}`, 'success');
            }
            
            // Play Rachel voice
            if (result.audio) {
                await playRobotVoice(result.audio);
            }
            
            // Execute action
            if (result.action) {
                await executeAction(result.action, result.parameters);
            }
        }
        
    } catch (err) {
        console.error('❌ Command processing failed:', err);
        // Fallback to local command processing
        await executeLocalCommand(transcript);
    }
    
    if (window.robotAssistant) {
        robotAssistant.setRobotState('listening');
    }
}

async function executeAction(action, parameters) {
    console.log(`🎬 Executing action: ${action}`);
    
    try {
        const response = await fetch(`${API_BASE}/robot/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, parameters })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log('✅ Action executed successfully');
        } else {
            console.error('❌ Action failed:', result.message);
        }
        
    } catch (err) {
        console.error('❌ Execute error:', err);
    }
}

async function playRobotVoice(base64Audio) {
    return new Promise((resolve) => {
        try {
            // Pause microphone while playing (avoid echo!)
            if (voiceRecognition) {
                voiceRecognition.stop();
            }
            
            // Convert base64 to audio
            const audioBlob = base64ToBlob(base64Audio, 'audio/mpeg');
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            
            if (window.robotAssistant) {
                robotAssistant.setRobotState('processing');
            }
            
            audio.play();
            
            audio.onended = () => {
                URL.revokeObjectURL(audioUrl);
                
                // Resume microphone after voice finishes
                setTimeout(() => {
                    if (voiceActive && voiceCheckbox.checked) {
                        try {
                            voiceRecognition.start();
                        } catch (err) {
                            console.error('❌ Resume error:', err);
                        }
                    }
                }, 500);
                
                if (window.robotAssistant) {
                    robotAssistant.setRobotState('listening');
                }
                
                resolve();
            };
            
            audio.onerror = () => {
                console.error('❌ Audio playback error');
                URL.revokeObjectURL(audioUrl);
                
                // Resume microphone even on error
                setTimeout(() => {
                    if (voiceActive && voiceCheckbox.checked) {
                        try {
                            voiceRecognition.start();
                        } catch (err) {
                            console.error('❌ Resume error:', err);
                        }
                    }
                }, 500);
                
                resolve();
            };
            
        } catch (err) {
            console.error('❌ Voice playback error:', err);
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
// FALLBACK: LOCAL COMMAND PROCESSING (if AI fails)
// ============================================================================

async function executeLocalCommand(command) {
    console.log(`🔄 Fallback local processing: "${command}"`);
    
    let executed = false;
    let actionName = '';
    
    if (command.includes('stop')) {
        fetch(`${API_BASE}/ptz/stop`, { method: 'POST' });
        actionName = 'Stop';
        executed = true;
    }
    else if (command.includes('zoom')) {
        const result = handleZoomCommand(command);
        if (result.success) {
            executed = true;
            actionName = result.action;
        }
    }
    else if (command.includes('focus')) {
        const result = handleFocusCommand(command);
        if (result.success) {
            executed = true;
            actionName = result.action;
        }
    }
    else if (command.includes('pan') || command.includes('left') || command.includes('right')) {
        const result = handlePanCommand(command);
        if (result.success) {
            executed = true;
            actionName = result.action;
        }
    }
    else if (command.includes('brightness') || command.includes('brighter') || command.includes('darker')) {
        const result = handleBrightnessCommand(command);
        if (result.success) {
            executed = true;
            actionName = result.action;
        }
    }
    
    if (window.robotAssistant) {
        if (executed) {
            robotAssistant.onCommandExecuted(actionName, true);
        } else {
            robotAssistant.onCommandUnknown(command);
        }
    }
}

// Keep old command handlers as fallback
function handleZoomCommand(command) {
    const isLittle = command.includes('little') || command.includes('bit');
    
    if (command.includes('in') || command.includes('plus') || command.includes('closer')) {
        if (isLittle) {
            fetch(`${API_BASE}/zoom/in`, { method: 'POST' });
            return { success: true, action: 'Zoom in (step)' };
        } else {
            fetch(`${API_BASE}/ptz/zoom/start/in`, { method: 'POST' });
            setTimeout(() => fetch(`${API_BASE}/ptz/zoom/stop`, { method: 'POST' }), 2500);
            return { success: true, action: 'Zoom in' };
        }
    }
    else if (command.includes('out') || command.includes('minus') || command.includes('back')) {
        if (isLittle) {
            fetch(`${API_BASE}/zoom/out`, { method: 'POST' });
            return { success: true, action: 'Zoom out (step)' };
        } else {
            fetch(`${API_BASE}/ptz/zoom/start/out`, { method: 'POST' });
            setTimeout(() => fetch(`${API_BASE}/ptz/zoom/stop`, { method: 'POST' }), 2500);
            return { success: true, action: 'Zoom out' };
        }
    }
    
    return { success: false, action: '' };
}

function handleFocusCommand(command) {
    const isLittle = command.includes('little') || command.includes('bit') || command.includes('detail');
    
    if (command.includes('in') || command.includes('near') || command.includes('closer')) {
        if (isLittle) {
            fetch(`${API_BASE}/ptz/focus/step/in`, { method: 'POST' });
            return { success: true, action: 'Focus in (step)' };
        } else {
            fetch(`${API_BASE}/ptz/focus/start/in`, { method: 'POST' });
            setTimeout(() => fetch(`${API_BASE}/ptz/focus/stop`, { method: 'POST' }), 2500);
            return { success: true, action: 'Focus in' };
        }
    }
    else if (command.includes('out') || command.includes('far') || command.includes('away')) {
        if (isLittle) {
            fetch(`${API_BASE}/ptz/focus/step/out`, { method: 'POST' });
            return { success: true, action: 'Focus out (step)' };
        } else {
            fetch(`${API_BASE}/ptz/focus/start/out`, { method: 'POST' });
            setTimeout(() => fetch(`${API_BASE}/ptz/focus/stop`, { method: 'POST' }), 2500);
            return { success: true, action: 'Focus out' };
        }
    }
    
    return { success: false, action: '' };
}

function handlePanCommand(command) {
    const isLittle = command.includes('little') || command.includes('bit');
    
    if (command.includes('left')) {
        if (isLittle) {
            fetch(`${API_BASE}/ptz/left`, { method: 'POST' });
            return { success: true, action: 'Pan left (step)' };
        } else {
            fetch(`${API_BASE}/ptz/pan/start/left`, { method: 'POST' });
            setTimeout(() => fetch(`${API_BASE}/ptz/pan/stop`, { method: 'POST' }), 2500);
            return { success: true, action: 'Pan left' };
        }
    }
    else if (command.includes('right') ||command.includes('ban rate') ||command.includes('bandrate') || command.includes('pan write')) {
        if (isLittle) {
            fetch(`${API_BASE}/ptz/right`, { method: 'POST' });
            return { success: true, action: 'Pan right (step)' };
        } else {
            fetch(`${API_BASE}/ptz/pan/start/right`, { method: 'POST' });
            setTimeout(() => fetch(`${API_BASE}/ptz/pan/stop`, { method: 'POST' }), 2500);
            return { success: true, action: 'Pan right' };
        }
    }
    
    return { success: false, action: '' };
}

function handleBrightnessCommand(command) {
    const slider = document.getElementById('brightnessSlider');
    const display = document.getElementById('brightnessValue');
    let current = parseInt(slider.value);
    let newValue;
    
    if (command.includes('up') || command.includes('brighter') || command.includes('increase')) {
        newValue = Math.min(60, current + 5);
    } else if (command.includes('down') || command.includes('darker') || command.includes('decrease')) {
        newValue = Math.max(7, current - 5);
    } else {
        return { success: false, action: '' };
    }
    
    slider.value = newValue;
    display.textContent = newValue;
    fetch(`${API_BASE}/brightness/${newValue}`, { method: 'POST' });
    
    return { success: true, action: `Brightness: ${newValue}` };
}

// Initialize
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVoiceControl);
} else {
    initVoiceControl();
}

console.log('AI Voice Control loaded - Whisper + GPT-4 + Vision + Rachel!');