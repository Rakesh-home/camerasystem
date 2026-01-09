class RobotAssistant {
    constructor() {
        this.container = null;
        this.robot = null;
        this.messageBox = null;
        this.messages = [];
        this.maxMessages = 5;
        this.isActive = false;
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.currentX = 0;
        this.currentY = 0;
        this.offsetX = 0;
        this.offsetY = 0;
        this.init();
    }
    
    init() {
        this.createRobotHTML();
        this.setupDraggable();
        this.loadPosition();
        this.hide();
        console.log('🤖 Robot assistant initialized');
    }
    
    createRobotHTML() {
        const container = document.createElement('div');
        container.className = 'robot-assistant';
        container.id = 'robotAssistant';
        
        container.innerHTML = `
            <div class="message-box">
                <div class="message-box-header" id="robotDragHandle">
                    <span class="message-box-title">🎤 VOICE LOG</span>
                    <span class="message-box-close" id="robotMinimizeBtn">−</span>
                </div>
                <div class="message-box-content" id="messageBoxContent"></div>
            </div>
            
            <div class="robot sleeping" id="robotChar">
                <div class="robot-antenna"></div>
                <div class="robot-head">
                    <div class="robot-eyes">
                        <div class="robot-eye"></div>
                        <div class="robot-eye"></div>
                    </div>
                    <div class="robot-mouth"></div>
                </div>
                <div class="robot-body"></div>
                <div class="robot-arm left"></div>
                <div class="robot-arm right"></div>
                <div class="robot-leg left"></div>
                <div class="robot-leg right"></div>
            </div>
        `;
        
        document.body.appendChild(container);
        
        this.container = container;
        this.robot = document.getElementById('robotChar');
        this.messageContent = document.getElementById('messageBoxContent');
        
        const minimizeBtn = document.getElementById('robotMinimizeBtn');
        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleMinimize();
            });
        }
    }
    
    setupDraggable() {
        const dragHandle = document.getElementById('robotChar');
        
        if (!dragHandle) return;
        
        dragHandle.addEventListener('mousedown', (e) => this.startDrag(e));
        document.addEventListener('mousemove', (e) => this.drag(e));
        document.addEventListener('mouseup', () => this.stopDrag());
        
        dragHandle.addEventListener('touchstart', (e) => this.startDrag(e));
        document.addEventListener('touchmove', (e) => this.drag(e));
        document.addEventListener('touchend', () => this.stopDrag());
    }
    
    startDrag(e) {
        this.isDragging = true;
        
        const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
        const clientY = e.type.includes('touch') ? e.touches[0].clientY : e.clientY;
        
        const rect = this.container.getBoundingClientRect();
        this.offsetX = clientX - rect.left;
        this.offsetY = clientY - rect.top;
        
        this.container.classList.add('dragging');
        
        console.log('🖱️ Started dragging');
    }
    
    drag(e) {
        if (!this.isDragging) return;
        
        e.preventDefault();
        
        const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
        const clientY = e.type.includes('touch') ? e.touches[0].clientY : e.clientY;
        
        this.currentX = clientX - this.offsetX;
        this.currentY = clientY - this.offsetY;
        
        const maxX = window.innerWidth - this.container.offsetWidth;
        const maxY = window.innerHeight - this.container.offsetHeight;
        
        this.currentX = Math.max(0, Math.min(this.currentX, maxX));
        this.currentY = Math.max(0, Math.min(this.currentY, maxY));
        
        this.container.style.left = `${this.currentX}px`;
        this.container.style.top = `${this.currentY}px`;
        this.container.style.right = 'auto';
        this.container.style.bottom = 'auto';
    }
    
    stopDrag() {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        this.container.classList.remove('dragging');
        this.savePosition();
        
        console.log(`🖱️ Stopped - Position: (${this.currentX}, ${this.currentY})`);
    }
    
    savePosition() {
        try {
            localStorage.setItem('robotPosition', JSON.stringify({
                x: this.currentX,
                y: this.currentY
            }));
        } catch (err) {
            console.error('Save failed:', err);
        }
    }
    
    loadPosition() {
        try {
            const saved = localStorage.getItem('robotPosition');
            if (saved) {
                const pos = JSON.parse(saved);
                this.currentX = pos.x;
                this.currentY = pos.y;
                
                this.container.style.left = `${this.currentX}px`;
                this.container.style.top = `${this.currentY}px`;
                this.container.style.right = 'auto';
                this.container.style.bottom = 'auto';
                
                console.log(`📍 Loaded: (${this.currentX}, ${this.currentY})`);
            }
        } catch (err) {
            console.error('Load failed:', err);
        }
    }
    
    resetPosition() {
        this.container.style.left = 'auto';
        this.container.style.top = 'auto';
        this.container.style.right = '35%';
        this.container.style.bottom = '20px';
        
        localStorage.removeItem('robotPosition');
        console.log('🔄 Reset');
    }
    
    show() {
        if (this.isActive) return;
        
        this.isActive = true;
        this.container.classList.add('active');
        this.setRobotState('idle');
        this.addMessage('Say "STACY" to activate', 'info');
        
        console.log('🤖 Shown');
    }
    
    hide() {
        if (!this.isActive) return;
        
        this.isActive = false;
        this.container.classList.remove('active');
        this.setRobotState('sleeping');
        this.clearMessages();
        
        console.log('🤖 Hidden');
    }
    
    setRobotState(state) {
        if (!this.robot) return;
        
        this.robot.classList.remove('sleeping', 'idle', 'listening', 'processing');
        this.robot.classList.add(state);
        
        console.log(`🤖 State: ${state}`);
    }
    
    addMessage(text, type = 'info') {
        const time = new Date().toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit'
        });
        
        const message = { time, text, type };
        this.messages.push(message);
        
        if (this.messages.length > this.maxMessages) {
            this.messages.shift();
        }
        
        this.renderMessages();
    }
    
    renderMessages() {
        if (!this.messageContent) return;
        
        this.messageContent.innerHTML = '';
        
        this.messages.forEach(msg => {
            const div = document.createElement('div');
            div.className = `message-item ${msg.type}`;
            div.innerHTML = `<span class="message-time">${msg.time}</span>${msg.text}`;
            this.messageContent.appendChild(div);
        });
        
        this.messageContent.scrollTop = this.messageContent.scrollHeight;
    }
    
    clearMessages() {
        this.messages = [];
        this.renderMessages();
    }
    
    onVoiceActivated() {
        this.setRobotState('idle');
        this.addMessage('Voice control activated', 'success');
        this.addMessage('Say "STACY" to start listening', 'info');
    }
    
    onWakeWordDetected() {
        this.setRobotState('listening');
        this.addMessage('✅ Wake word detected!', 'success');
        this.addMessage('I\'m listening for commands...', 'info');
    }
    
    onCommandHeard(command) {
        this.setRobotState('processing');
        this.addMessage(`🎤 Heard: "${command}"`, 'info');
    }
    
    onCommandExecuted(command, success = true) {
        this.setRobotState('listening');
        if (success) {
            this.addMessage(`✅ ${command}`, 'success');
        } else {
            this.addMessage(`❌ ${command} failed`, 'error');
        }
    }
    
    onCommandUnknown(command) {
        this.setRobotState('listening');
        this.addMessage(`❓ Unknown: "${command}"`, 'warning');
    }
    
    onVoiceDeactivated() {
        this.setRobotState('sleeping');
        this.addMessage('Voice control deactivated', 'warning');
    }
    
    onVoiceError(error) {
        this.setRobotState('idle');
        this.addMessage(`⚠️ Error: ${error}`, 'error');
    }
    
    toggleMinimize() {
        const content = this.container.querySelector('.message-box-content');
        const closeBtn = this.container.querySelector('.message-box-close');
        
        if (content.style.display === 'none') {
            content.style.display = 'block';
            closeBtn.textContent = '−';
        } else {
            content.style.display = 'none';
            closeBtn.textContent = '+';
        }
    }
}

let robotAssistant = null;

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        robotAssistant = new RobotAssistant();
    });
} else {
    robotAssistant = new RobotAssistant();
}

console.log('✅ Robot loaded - Touch robot to drag!');