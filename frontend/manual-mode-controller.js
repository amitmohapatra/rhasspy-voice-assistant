class ManualModeController {
    constructor(audioManager) {
        this.audio = audioManager;
    }

    async handleVoiceButtonClick(uiController) {
        const audio = this.audio;
        console.log('🎤 [MANUAL] Voice button clicked', {
            currentMode: uiController.getCurrentMode(),
            isProcessing: audio.isProcessing,
            currentState: audio.currentState,
            mediaRecorderState: audio.mediaRecorder?.state
        });

        if (uiController.isRhasspyMode()) {
            console.log('⚠️ [MANUAL] Voice button disabled in Rhasspy mode');
            return;
        }

        if (uiController.isIdle()) {
            console.log('💬 [MANUAL] Entering Manual mode');
            uiController.enterManualMode();
        }

        if (audio.mediaRecorder && audio.mediaRecorder.state === 'recording') {
            if (audio.isManualRecording) {
                console.log('🛑 [MANUAL] Stopping recording to send message');
                this.hideRecordingUI();
                audio.stopRecording();
                return;
            }

            console.log('🔄 [MANUAL] Converting wake-word recording to manual workflow');
            await this.beginRecording(true);
            return;
        }

        await this.beginRecording(false);
    }

    async beginRecording(isSwitchingFromWakeWord) {
        const audio = this.audio;
        console.log('🎤 [MANUAL] Starting recording for manual message');
        console.log('🔄 [MANUAL] Resetting all flags and stopping wake word detection');

        audio.ignoringOldRecording = true;
        audio.isListeningForWakeWord = false;

        if (audio.mediaRecorder && audio.mediaRecorder.state === 'recording') {
            try {
                console.log('🛑 [MANUAL] Stopping existing recording before manual start');
                audio.mediaRecorder.stop();
                await new Promise(resolve => setTimeout(resolve, 200));
            } catch (e) {
                console.warn('⚠️ Error stopping recorder:', e);
            }
        }

        audio.isProcessing = false;
        audio.processingLock = false;
        audio.isActiveRecording = false;
        audio.processingQueue = [];
        audio.setState(AudioManager.STATES.IDLE);

        const avatarManager = AvatarManager.getInstance();
        avatarManager.setAwake(true);

        setTimeout(() => {
            console.log('🎤 [MANUAL] Now starting recording after reset');
            audio.isManualRecording = true;
            audio.startRecording();
            this.showRecordingUI();
            audio.ignoringOldRecording = false;
        }, isSwitchingFromWakeWord ? 600 : 500);
    }

    async processRecording(audioBlob) {
        const audio = this.audio;
        console.log('💬 [MANUAL] Processing audio message');

        const chatManager = ChatManager.getInstance();
        const messageProcessor = MessageProcessor.getInstance();

        try {
            await messageProcessor.processAudioMessage(audioBlob, {
                mode: 'manual',
                onStart: () => {
                    console.log('💬 [MANUAL] Starting message processing');
                    if (chatManager) {
                        chatManager.updateStatus('processing', 'Process');
                    }
                    this.showProcessingUI();
                },
                onComplete: () => {
                    console.log('✅ [MANUAL] Message processing complete');
                    audio.isManualRecording = false;
                    audio.isActiveRecording = false;
                    this.hideRecordingUI();
                    audio.setState(AudioManager.STATES.IDLE);
                    if (chatManager) {
                        chatManager.updateStatus('idle', 'Ready');
                    }
                },
                onError: (error) => {
                    console.error('❌ [MANUAL] Error:', error);
                    audio.isManualRecording = false;
                    audio.isActiveRecording = false;
                    this.hideRecordingUI();
                    if (chatManager) {
                        chatManager.updateStatus('idle', 'Ready');
                    }
                }
            });
        } catch (error) {
            console.error('❌ [MANUAL] Failed to process audio:', error);
            audio.isManualRecording = false;
            audio.isActiveRecording = false;
            this.hideRecordingUI();
            if (chatManager) {
                chatManager.updateStatus('idle', 'Ready');
            }
            throw error;
        }
    }

    showRecordingUI() {
        console.log('🎨 [MANUAL] Showing recording UI');

        const recordingIndicator = document.getElementById('recording-indicator');
        if (recordingIndicator) {
            this.setIndicatorState({
                text: 'Speak now...',
                mode: 'recording',
                showDot: true
            });
        }

        const micIcon = document.getElementById('mic-icon');
        const sendArrowIcon = document.getElementById('send-arrow-icon');
        if (micIcon) micIcon.style.display = 'none';
        if (sendArrowIcon) sendArrowIcon.style.display = 'block';

        const voiceBtn = document.getElementById('voice-btn');
        if (voiceBtn) {
            voiceBtn.classList.add('recording');
            voiceBtn.title = 'Click to send';
        }

        const chatInput = document.getElementById('chat-input');
        if (chatInput) chatInput.placeholder = '';
    }

    hideRecordingUI() {
        console.log('🎨 [MANUAL] Hiding recording UI');

        const recordingIndicator = document.getElementById('recording-indicator');
        if (recordingIndicator) {
            recordingIndicator.style.display = 'none';
            recordingIndicator.classList.remove('processing');
            recordingIndicator.classList.remove('recording');
            const dot = recordingIndicator.querySelector('.recording-dot');
            if (dot) dot.style.display = 'inline-block';
        }

        const micIcon = document.getElementById('mic-icon');
        const sendArrowIcon = document.getElementById('send-arrow-icon');
        if (micIcon) micIcon.style.display = 'block';
        if (sendArrowIcon) sendArrowIcon.style.display = 'none';

        const voiceBtn = document.getElementById('voice-btn');
        if (voiceBtn) {
            voiceBtn.classList.remove('recording');
            voiceBtn.title = 'Click to speak';
        }

        const chatInput = document.getElementById('chat-input');
        if (chatInput) chatInput.placeholder = 'Send me message...';
    }

    showProcessingUI() {
        console.log('⚙️ [MANUAL] Showing processing indicator');
        this.setIndicatorState({
            text: 'Processing...',
            mode: 'processing',
            showDot: false
        });

        const micIcon = document.getElementById('mic-icon');
        const sendArrowIcon = document.getElementById('send-arrow-icon');
        if (micIcon) micIcon.style.display = 'none';
        if (sendArrowIcon) sendArrowIcon.style.display = 'none';

        const chatInput = document.getElementById('chat-input');
        if (chatInput) chatInput.placeholder = '';
    }

    setIndicatorState({ text, mode, showDot }) {
        const recordingIndicator = document.getElementById('recording-indicator');
        if (!recordingIndicator) return;

        recordingIndicator.style.display = 'flex';
        recordingIndicator.classList.toggle('processing', mode === 'processing');
        recordingIndicator.classList.toggle('recording', mode === 'recording');

        const dot = recordingIndicator.querySelector('.recording-dot');
        if (dot) {
            dot.style.display = showDot ? 'inline-block' : 'none';
        }

        const textSpan = recordingIndicator.querySelector('.recording-text');
        if (textSpan && typeof text === 'string') {
            textSpan.textContent = text;
        }
    }
}

if (typeof window !== 'undefined') {
    window.ManualModeController = ManualModeController;
}

