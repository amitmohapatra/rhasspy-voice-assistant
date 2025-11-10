/**
 * UI Controller - Manages button states and mode switching
 * Ensures clean separation between Rhasspy mode and Manual mode
 */

class UIController {
    static instance = null;
    
    constructor() {
        if (UIController.instance) {
            return UIController.instance;
        }
        UIController.instance = this;
        
        this.currentMode = 'idle'; // 'idle', 'rhasspy', 'manual'
        this.initializeElements();
        
        console.log('🎮 UIController initialized');
    }
    
    static getInstance() {
        if (!UIController.instance) {
            UIController.instance = new UIController();
        }
        return UIController.instance;
    }
    
    initializeElements() {
        // Rhasspy mode elements
        this.rhasspyBtn = document.getElementById('rhasspy-start-btn');
        this.statusBtn = document.querySelector('.status-btn');
        
        // Manual mode elements
        this.chatInput = document.getElementById('chat-input');
        this.chatMicrophone = document.getElementById('voice-btn');
        this.chatSendBtn = document.getElementById('send-btn');
        
        console.log('🎮 UI Elements:', {
            rhasspyBtn: !!this.rhasspyBtn,
            statusBtn: !!this.statusBtn,
            chatInput: !!this.chatInput,
            chatMicrophone: !!this.chatMicrophone,
            chatSendBtn: !!this.chatSendBtn
        });
    }
    
    /**
     * Enter Rhasspy Mode - Automatic voice conversation
     * Disables all chat controls
     */
    enterRhasspyMode() {
        console.log('🎤 [UI] Entering Rhasspy Mode - disabling chat controls');
        this.currentMode = 'rhasspy';
        
        // Enable Rhasspy controls
        this.enableElement(this.rhasspyBtn);
        this.enableElement(this.statusBtn);
        
        // Disable Manual controls
        this.disableElement(this.chatInput);
        this.disableElement(this.chatMicrophone);
        this.disableElement(this.chatSendBtn);
        
        console.log('✅ [UI] Rhasspy Mode active - chat disabled');
    }
    
    /**
     * Enter Manual Mode - User manually sends messages
     * Disables Rhasspy controls
     */
    enterManualMode() {
        console.log('💬 [UI] Entering Manual Mode - disabling Rhasspy controls');
        this.currentMode = 'manual';
        
        // Stop wake word detection in background
        const audioManager = window.AudioManager?.getInstance();
        if (audioManager) {
            audioManager.stopWakeWordDetection();
        }
        
        // Disable Rhasspy controls
        this.disableElement(this.rhasspyBtn);
        this.disableElement(this.statusBtn);
        
        // Enable Manual controls
        this.enableElement(this.chatInput);
        this.enableElement(this.chatMicrophone);
        this.enableElement(this.chatSendBtn);
        
        console.log('✅ [UI] Manual Mode active - Rhasspy disabled, wake word stopped');
    }
    
    /**
     * Return to Idle Mode - All controls enabled
     */
    enterIdleMode() {
        console.log('🏠 [UI] Entering Idle Mode - enabling all controls');
        this.currentMode = 'idle';
        
        // Restart wake word detection
        const audioManager = window.AudioManager?.getInstance();
        if (audioManager) {
            setTimeout(() => {
                audioManager.startWakeWordDetection();
            }, 500);
        }
        
        // Enable all controls
        this.enableElement(this.rhasspyBtn);
        this.enableElement(this.statusBtn);
        this.enableElement(this.chatInput);
        this.enableElement(this.chatMicrophone);
        this.enableElement(this.chatSendBtn);
        
        console.log('✅ [UI] Idle Mode - all controls enabled, wake word restarted');
    }
    
    /**
     * Disable an element
     */
    disableElement(element) {
        if (!element) return;
        
        element.disabled = true;
        element.classList.add('ui-disabled');
        element.style.pointerEvents = 'none';
        element.style.opacity = '0.5';
        element.style.cursor = 'not-allowed';
    }
    
    /**
     * Enable an element
     */
    enableElement(element) {
        if (!element) return;
        
        element.disabled = false;
        element.classList.remove('ui-disabled');
        element.style.pointerEvents = 'auto';
        element.style.opacity = '1';
        element.style.cursor = (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') ? 'text' : 'pointer';
    }
    
    /**
     * Get current mode
     */
    getCurrentMode() {
        return this.currentMode;
    }
    
    /**
     * Check if in Rhasspy mode
     */
    isRhasspyMode() {
        return this.currentMode === 'rhasspy';
    }
    
    /**
     * Check if in Manual mode
     */
    isManualMode() {
        return this.currentMode === 'manual';
    }
    
    /**
     * Check if idle
     */
    isIdle() {
        return this.currentMode === 'idle';
    }
}

// Export for use in other files
if (typeof window !== 'undefined') {
    window.UIController = UIController;
}

