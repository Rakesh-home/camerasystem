const API_BASE = 'http://192.168.2.8:8000';

// ============== STATUS UPDATES ==============

function updateStatus() {
    fetch(`${API_BASE}/status`)
        .then(res => res.json())
        .then(data => {
            document.getElementById('connectionStatus').style.background = 
                data.connected ? '#00ff00' : '#ff0000';
            document.getElementById('statusText').textContent = 
                data.connected ? 'Connected' : 'Disconnected';
            
            document.getElementById('brightnessValue').textContent = data.brightness;
            document.getElementById('brightnessSlider').value = data.brightness;
            
            const profileText = data.profile ? `Profile: ${data.profile} ✓` : 'Profile: RAW MODE';
            document.getElementById('profileStatus').textContent = profileText;
            
            document.getElementById('autoCorrections').checked = data.auto_corrections;
            
            // Update horizontal flip checkbox state
            if (data.horizontal_flip !== undefined) {
                document.getElementById('horizontalFlip').checked = data.horizontal_flip;
            }
        })
        .catch(err => {
            console.error('Status update failed:', err);
            document.getElementById('connectionStatus').style.background = '#ff0000';
            document.getElementById('statusText').textContent = 'Error';
        });
}

// ============== PROFESSIONAL PTZ CONTROL SYSTEM ==============
// Handles both single-click steps and hold-to-move continuous control

class PTZController {
    constructor() {
        this.holdTimers = {};
        this.isHolding = {};
        this.activeMovement = null;
    }

    /**
     * Setup a PTZ button with smart click/hold behavior
     * @param {string} buttonId - DOM element ID
     * @param {string} startEndpoint - Continuous movement start endpoint
     * @param {string} stopEndpoint - Stop movement endpoint
     * @param {string} stepEndpoint - Single step endpoint
     * @param {number} holdDelay - Milliseconds before hold activates (default 250ms)
     */
    setupButton(buttonId, startEndpoint, stopEndpoint, stepEndpoint, holdDelay = 250) {
        const button = document.getElementById(buttonId);
        if (!button) {
            console.error(`Button ${buttonId} not found`);
            return;
        }

        const buttonState = {
            isPressed: false,
            isHolding: false,
            timer: null
        };

        const startAction = async () => {
            if (buttonState.isPressed) return;
            
            buttonState.isPressed = true;
            buttonState.isHolding = false;
            
            // Visual feedback
            button.style.transform = 'scale(0.92)';
            button.style.opacity = '0.8';
            
            // CRITICAL: Stop all other movements first to prevent conflicts
            await this.stopAllMovements();
            
            // Start hold timer
            buttonState.timer = setTimeout(async () => {
                if (!buttonState.isPressed) return;
                
                buttonState.isHolding = true;
                this.activeMovement = buttonId;
                
                // Enhanced visual feedback for hold
                button.style.transform = 'scale(0.95)';
                button.style.opacity = '1';
                button.style.boxShadow = '0 0 15px rgba(0, 255, 255, 0.6)';
                
                // Start continuous movement
                try {
                    const response = await fetch(`${API_BASE}${startEndpoint}`, { method: 'POST' });
                    const data = await response.json();
                    console.log(`[PTZ] Started continuous: ${buttonId}`, data);
                } catch (err) {
                    console.error(`[PTZ] Start error: ${buttonId}`, err);
                }
            }, holdDelay);
        };

        const stopAction = async () => {
            if (!buttonState.isPressed) return;
            
            // Clear hold timer
            if (buttonState.timer) {
                clearTimeout(buttonState.timer);
                buttonState.timer = null;
            }

            const wasHolding = buttonState.isHolding;
            buttonState.isPressed = false;
            buttonState.isHolding = false;
            
            // Reset visual state
            button.style.transform = '';
            button.style.opacity = '';
            button.style.boxShadow = '';

            if (wasHolding) {
                // Stop continuous movement
                if (this.activeMovement === buttonId) {
                    this.activeMovement = null;
                }
                
                try {
                    const response = await fetch(`${API_BASE}${stopEndpoint}`, { method: 'POST' });
                    const data = await response.json();
                    console.log(`[PTZ] Stopped continuous: ${buttonId}`, data);
                } catch (err) {
                    console.error(`[PTZ] Stop error: ${buttonId}`, err);
                }
            } else {
                // Was a quick click - execute single step
                if (stepEndpoint) {
                    try {
                        // Small delay to ensure stop is processed
                        await new Promise(resolve => setTimeout(resolve, 50));
                        
                        const response = await fetch(`${API_BASE}${stepEndpoint}`, { method: 'POST' });
                        const data = await response.json();
                        console.log(`[PTZ] Single step: ${buttonId}`, data);
                    } catch (err) {
                        console.error(`[PTZ] Step error: ${buttonId}`, err);
                    }
                }
            }
        };

        const cancelAction = async () => {
            if (buttonState.timer) {
                clearTimeout(buttonState.timer);
                buttonState.timer = null;
            }

            if (buttonState.isHolding && this.activeMovement === buttonId) {
                this.activeMovement = null;
                try {
                    await fetch(`${API_BASE}${stopEndpoint}`, { method: 'POST' });
                    console.log(`[PTZ] Cancelled: ${buttonId}`);
                } catch (err) {
                    console.error(`[PTZ] Cancel error: ${buttonId}`, err);
                }
            }

            buttonState.isPressed = false;
            buttonState.isHolding = false;
            button.style.transform = '';
            button.style.opacity = '';
            button.style.boxShadow = '';
        };

        // Mouse events
        button.addEventListener('mousedown', (e) => {
            e.preventDefault();
            startAction();
        });

        button.addEventListener('mouseup', (e) => {
            e.preventDefault();
            stopAction();
        });

        button.addEventListener('mouseleave', () => {
            cancelAction();
        });

        // Touch events for mobile
        button.addEventListener('touchstart', (e) => {
            e.preventDefault();
            startAction();
        });

        button.addEventListener('touchend', (e) => {
            e.preventDefault();
            stopAction();
        });

        button.addEventListener('touchcancel', (e) => {
            e.preventDefault();
            cancelAction();
        });

        console.log(`✅ PTZ button configured: ${buttonId}`);
    }

    async stopAllMovements() {
        try {
            await fetch(`${API_BASE}/ptz/stop`, { method: 'POST' });
            this.activeMovement = null;
        } catch (err) {
            console.error('[PTZ] Stop all error:', err);
        }
    }
}

// ============== INITIALIZE PTZ CONTROLS ==============

const ptzController = new PTZController();

// PAN controls (UP/DOWN/LEFT/RIGHT)
ptzController.setupButton(
    'ptzUp',
    '/ptz/focus/start/in',
    '/ptz/focus/stop',
    '/ptz/focus/step/in',
    250
);

ptzController.setupButton(
    'ptzDown',
    '/ptz/focus/start/out',
    '/ptz/focus/stop',
    '/ptz/focus/step/out',
    250
);

ptzController.setupButton(
    'ptzLeft',
    '/ptz/pan/start/left',
    '/ptz/pan/stop',
    '/ptz/left',
    250
);

ptzController.setupButton(
    'ptzRight',
    '/ptz/pan/start/right',
    '/ptz/pan/stop',
    '/ptz/right',
    250
);

// ZOOM controls
ptzController.setupButton(
    'zoomIn',
    '/ptz/zoom/start/in',
    '/ptz/zoom/stop',
    '/zoom/in',
    250
);

ptzController.setupButton(
    'zoomOut',
    '/ptz/zoom/start/out',
    '/ptz/zoom/stop',
    '/zoom/out',
    250
);

// ============== OTHER CONTROLS ==============

document.getElementById('brightnessSlider').addEventListener('input', (e) => {
    const value = e.target.value;
    document.getElementById('brightnessValue').textContent = value;
    fetch(`${API_BASE}/brightness/${value}`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            const profileText = data.profile ? `Profile: ${data.profile} ✓` : 'Profile: RAW MODE';
            document.getElementById('profileStatus').textContent = profileText;
        })
        .catch(err => console.error('Brightness error:', err));
});

document.getElementById('autoCorrections').addEventListener('change', (e) => {
    const enabled = e.target.checked;
    fetch(`${API_BASE}/auto_corrections/${enabled}`, { method: 'POST' })
        .catch(err => console.error('Auto corrections error:', err));
});

document.getElementById('nlmDenoise').addEventListener('change', (e) => {
    const enabled = e.target.checked;
    fetch(`${API_BASE}/corrections/toggle/nlm`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            console.log('NLM Denoise:', data.nlm ? 'ON (~25 FPS)' : 'OFF (~60 FPS)');
        })
        .catch(err => console.error('NLM toggle error:', err));
});

// Horizontal flip control
document.getElementById('horizontalFlip').addEventListener('change', (e) => {
    const enabled = e.target.checked;
    fetch(`${API_BASE}/horizontal_flip/${enabled}`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            console.log('Horizontal Flip:', data.horizontal_flip ? 'ENABLED' : 'DISABLED');
        })
        .catch(err => console.error('Horizontal flip error:', err));
});

// Histogram controls
document.getElementById('histogramBtn').addEventListener('click', () => {
    document.getElementById('mainControls').classList.add('hidden');
    document.getElementById('histogramControls').classList.remove('hidden');
    if (typeof startHistogramUpdates === 'function') {
        startHistogramUpdates();
    }
});

document.getElementById('backBtn').addEventListener('click', () => {
    document.getElementById('histogramControls').classList.add('hidden');
    document.getElementById('mainControls').classList.remove('hidden');
    if (typeof stopHistogramUpdates === 'function') {
        stopHistogramUpdates();
    }
});

// ============== INITIALIZATION ==============


setInterval(updateStatus, 1000);
updateStatus();

// Log initialization
console.log('Professional PTZ Control System Loaded');
console.log('USAGE:');
console.log('   • CLICK = Single step movement');
console.log('   • HOLD (250ms+) = Continuous movement');
console.log('   • All conflicts are automatically prevented');
console.log('   • Voice control available via checkbox');