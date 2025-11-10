/**
 * Audio Manager with proper state management and synchronization
 * Similar to OpenAI/Claude voice interaction flow
 */
class AudioManager {
    static instance = null;
    
    // State machine - Ready, Listen (user), Process (API), Speak (AI)
    static STATES = {
        IDLE: 'idle',           // Ready state
        LISTENING: 'listening', // User is speaking/listening (red)
        PROCESSING: 'processing', // API is processing (yellow/orange)
        SPEAKING: 'speaking'    // AI is speaking (green)
    };
    
    constructor() {
        if (AudioManager.instance) {
            return AudioManager.instance;
        }
        
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.currentState = AudioManager.STATES.IDLE;
        this.isListeningForWakeWord = true;
        this.isActiveRecording = false;
        this.assistantDisplayName = 'Rhasspy';
        this.wakeNameVariants = ['rhasspy', 'hasspy', 'raspy', 'haspy', 'rhaspy', 'raspi'];
        this.wakePrefixes = ['hey', 'hello', 'hi'];
        this.wakeWords = this.wakePrefixes.flatMap(prefix =>
            this.wakeNameVariants.map(variant => `${prefix} ${variant}`)
        );
        this.partialWakeWords = [...this.wakePrefixes]; // For better detection
        this.apiUrl = 'http://localhost:5000/api';
        this.recordingTimeout = null;
        this.recordingDuration = 0;
        // Dynamic recording duration - adapts based on voice activity
        this.minRecordingDuration = 250; // Minimum 0.25s to avoid cutting off speech while staying responsive
        this.maxRecordingDuration = 5000; // 5 seconds absolute max - reduces late processing
        this.silenceThreshold = 3000; // 3 seconds of silence before processing (allows pauses mid-sentence)
        this.adaptiveSilenceThreshold = 3000; // Starts at 3s, adapts based on context
        this.minAudioSize = 1500; // Minimum size to treat as meaningful audio (accept shorter utterances)
        this.silenceTimeout = null; // Track silence detection
        this.lastAudioTime = 0; // Track last audio activity
        this.firstAudioTime = 0; // Track when user first spoke
        this.autoPromptTimeout = null; // Dynamic auto-prompt based on voice activity
        this.recordingStartTime = 0; // Track when recording started
        this.recordingEndTime = 0; // Track when recording ended
        this.apiCallStartTime = 0; // Track when API call started
        this.apiCallEndTime = 0; // Track when API call ended
        this.audioLevelCheckInterval = null; // Check audio levels for VAD
        this.timeBasedVADInterval = null; // Time-based fallback VAD
        this.audioContext = null; // Web Audio API context
        this.analyser = null; // Audio analyser for VAD
        this.microphone = null; // Microphone source
        this.audioDataArray = null; // Audio data buffer
        this.silenceStartTime = 0; // When silence started
        this.audioLevelThreshold = -50; // dB threshold for voice detection (adjust as needed)
        this.audioStream = null; // Store audio stream for muting
        this.isMuted = false; // Mute state
        this.hasActiveConversation = false; // Track if a user session is active
        this.localConversationId = null; // Local session id when not using Assistants API
        
        // Voice detection gating
        this.voiceConsecutiveFrames = 0; // consecutive frames above threshold before we accept voice
        this.voiceFramesTotal = 0; // total number of voice frames in current recording
        this.hadSustainedVoice = false; // true once sustained voice detected in current recording
        this.minVoiceDurationMs = 150; // require at least ~0.15s of voiced speech before processing
        this.earlyPhaseWindowMs = 900; // treat the first 0.9s after first speech as early phase
        this.earlySilenceThresholdMs = 100; // need 3s silence to end early-phase utterance (allows pauses)
        this.normalSilenceThresholdMs = 120; // need >=120ms silence to end utterance after early phase
        
        // Queue and processing control
        this.processingQueue = [];
        this.isProcessing = false;
        this.currentAudio = null; // Track current playing audio to prevent overlap
        this.processingLock = false; // Prevent concurrent processing
        this.isAutoPrompting = false; // Track if we're in auto-prompt mode

        this.manualController = new ManualModeController(this);
        
        AudioManager.instance = this;
    }
    async parseErrorResponse(response, defaultMessage) {
        try {
            const cloned = response.clone();
            const json = await cloned.json();
            if (json && typeof json.error === 'string' && json.error.trim()) {
                return json.error;
            }
        } catch (jsonErr) {
            console.warn('⚠️ [AUDIO] Unable to parse error JSON:', jsonErr);
        }

        try {
            const text = await response.text();
            if (text && text.trim()) {
                return text;
            }
        } catch (textErr) {
            console.warn('⚠️ [AUDIO] Unable to parse error text:', textErr);
        }

        return defaultMessage;
    }
    
    static getInstance() {
        if (!AudioManager.instance) {
            AudioManager.instance = new AudioManager();
        }
        return AudioManager.instance;
    }
    
    async init() {
        await this.initMediaRecorder();
        this.initVoiceButton();
        // Start wake word detection after initialization
        // Small delay to ensure everything is ready
        setTimeout(() => {
            if (this.isListeningForWakeWord && !this.isActiveRecording) {
                console.log('👂 Starting wake word detection after initialization');
                    this.startWakeWordDetection();
                }
        }, 1000);
    }
    
    async initMediaRecorder() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            // Store stream reference for muting
            this.audioStream = stream;
            
            // Initialize Web Audio API for real-time voice activity detection
            this.initAudioAnalysis(stream);
            
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus',
                timeslice: 30 // Emit data every 30ms for ultra-responsive VAD
            });
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    // Collect chunks only; do NOT mark lastAudioTime here.
                    // lastAudioTime should reflect detected voice, not just audio stream activity.
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = async () => {
                console.log('🔔 [MEDIARECORDER] onstop fired', {
                    audioChunksLength: this.audioChunks.length,
                    ignoringOldRecording: this.ignoringOldRecording,
                    isManualRecording: this.isManualRecording,
                    isListeningForWakeWord: this.isListeningForWakeWord,
                    isAutoPrompting: this.isAutoPrompting
                });
                
                // Don't process if we're in auto-prompt mode
                if (this.isAutoPrompting) {
                    console.log('⏭️ [MEDIARECORDER] Skipping processing - in auto-prompt mode');
                    this.audioChunks = [];
                    return;
                }
                
                // CRITICAL: If we're ignoring old recordings (during manual mode transition), skip processing
                // BUT: Don't skip if this is the REAL manual recording (has isManualRecording AND audio chunks)
                if (this.ignoringOldRecording && !(this.isManualRecording && this.audioChunks.length > 0)) {
                    console.log('⏭️ [MEDIARECORDER] Skipping old recording - transitioning to Manual mode', {
                        audioChunksLength: this.audioChunks.length,
                        isManualRecording: this.isManualRecording,
                        isListeningForWakeWord: this.isListeningForWakeWord
                    });
                    this.audioChunks = [];
                    return;
                } else if (this.ignoringOldRecording && this.isManualRecording && this.audioChunks.length > 0) {
                    console.log('✅ [MEDIARECORDER] This is the REAL manual recording - processing it!', {
                        audioChunksLength: this.audioChunks.length
                    });
                    // Clear the flag now - this is the real recording
                    this.ignoringOldRecording = false;
                }
                
                if (this.audioChunks.length > 0) {
                    // In wake-word mode, always process the chunk to check for wake words,
                    // even if local VAD didn't detect sustained voice.
                    const inWakeWordMode = this.isListeningForWakeWord && !this.isActiveRecording;
                    if (!inWakeWordMode) {
                        // Active conversation mode: apply voice gating discards
                        // If no voice was detected during this recording, discard to avoid auto-processing
                        if (this.firstAudioTime === 0) {
                            console.log('🔇 [MEDIARECORDER] No voice detected during recording, discarding audio and continuing');
                            this.isProcessing = false;
                            this.processingLock = false;
                            // Continue correct mode
                            if (this.isListeningForWakeWord && !this.isActiveRecording) {
                                setTimeout(() => {
                                    this.recordForWakeWord();
                                }, 300);
                            } else if (this.isActiveRecording) {
                                setTimeout(() => {
                                    this.startRecording();
                                }, 300);
                            } else {
                                this.setState(AudioManager.STATES.IDLE);
                            }
                            this.audioChunks = [];
                            return;
                        }
                        // Additional guard: require minimum total voice duration
                        const totalVoiceMs = (this.voiceFramesTotal || 0) * 10;
                        const minRequiredMs = Math.max(120, Math.floor((this.minVoiceDurationMs || 150) * 0.6));
                        if (!this.hadSustainedVoice || totalVoiceMs < minRequiredMs) {
                            console.log('🔇 [MEDIARECORDER] Discard: insufficient voice. Stats:', {
                                firstAudioTime: this.firstAudioTime,
                                hadSustainedVoice: this.hadSustainedVoice,
                                voiceFramesTotal: this.voiceFramesTotal,
                                totalVoiceMs,
                                minRequired: minRequiredMs
                            });
                            this.isProcessing = false;
                            this.processingLock = false;
                            if (this.isListeningForWakeWord && !this.isActiveRecording) {
                                setTimeout(() => {
                                    this.recordForWakeWord();
                                }, 300);
                            } else if (this.isActiveRecording) {
                                setTimeout(() => {
                                    this.startRecording();
                                }, 300);
                            } else {
                                this.setState(AudioManager.STATES.IDLE);
                            }
                            this.audioChunks = [];
                            return;
                        }
                    }
                    // Only treat as user interrupt when in active conversation recording
                    if (this.isActiveRecording && this.currentAudio && !this.currentAudio.paused) {
                        console.log('🛑 [MEDIARECORDER] User interrupted - stopping current audio');
                        try {
                            this.currentAudio.pause();
                            this.currentAudio.currentTime = 0;
                            this.currentAudio.onended = null;
                            this.currentAudio.onerror = null;
                        } catch (error) {
                            console.log('⚠️ [MEDIARECORDER] Error stopping audio (expected):', error.message);
                        }
                        this.currentAudio = null;
                        const avatarManager = AvatarManager.getInstance();
                        avatarManager.stopLipSync();
                        // Ensure mic is unmuted if we stopped TTS early
                        this.unmuteMicrophone();
                        this.isProcessing = false;
                        this.processingLock = false;
                    }
                    
                    // Keep in LISTENING state while processing user audio
                    // State will change to SPEAKING when AI responds
                    
                    // Calculate recording duration
                    this.recordingEndTime = Date.now();
                    const recordingDuration = this.recordingStartTime > 0 
                        ? this.recordingEndTime - this.recordingStartTime 
                        : 0;
                    console.log(`⏱️ [TIMING] Recording Duration: ${recordingDuration}ms (${(recordingDuration / 1000).toFixed(2)}s)`);
                    
                    // Create blob and process immediately (no delays)
                    const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                    console.log('🎤 [MEDIARECORDER] Processing audio blob, size:', audioBlob.size, 'isListeningForWakeWord:', this.isListeningForWakeWord);
                    
                    // Check if we're in Manual mode using isManualRecording flag
                    const uiController = UIController.getInstance();
                    
                    // Debug: Log all conditions
                    console.log('🔍 [MEDIARECORDER] Mode check:', {
                        isManualRecording: this.isManualRecording,
                        isManualMode: uiController?.isManualMode(),
                        isActiveRecording: this.isActiveRecording,
                        willUseManualFlow: this.isManualRecording || (uiController && uiController.isManualMode() && !this.isActiveRecording)
                    });
                    
                    if (this.isManualRecording || (uiController && uiController.isManualMode() && !this.isActiveRecording)) {
                        console.log('💬 [MANUAL] Processing audio for manual message - MANUAL FLOW');
                        
                        // Clear the ignore flag now that we're processing the REAL manual recording
                        this.ignoringOldRecording = false;
                        
                        // Send to chat manager for manual mode - ONLY THIS PATH
                        this.processManualAudio(audioBlob).catch(error => {
                            console.error('❌ [MANUAL] Error processing audio:', error);
                            this.setState(AudioManager.STATES.IDLE);
                        });
                        // IMPORTANT: Return here to prevent Rhasspy flow from running
                        return;
                    } else {
                        // Process immediately - don't await, let it run (Rhasspy mode)
                        console.log('🎤 [RHASSPY] Processing audio - RHASSPY FLOW');
                    this.processAudio(audioBlob).catch(error => {
                        console.error('❌ [MEDIARECORDER] Error processing audio:', error);
                        this.setState(AudioManager.STATES.IDLE);
                            // If in wake word mode, continue recording
                            if (this.isListeningForWakeWord && !this.isActiveRecording) {
                                setTimeout(() => {
                                    this.recordForWakeWord();
                                }, 500);
                            }
                        });
                    }
            } else {
                    // No audio chunks - go back to listening or continue wake word detection
                    console.log('⏭️ [MEDIARECORDER] No audio chunks');
                    if (this.isListeningForWakeWord && !this.isActiveRecording) {
                        // Continue wake word detection
                        setTimeout(() => {
                            this.recordForWakeWord();
                        }, 300);
                    } else {
                    this.setState(AudioManager.STATES.IDLE);
                    }
                }
                this.audioChunks = [];
            };
            
            console.log('✅ MediaRecorder initialized');
        } catch (error) {
            console.error('❌ Error initializing MediaRecorder:', error);
            this.showError('Microphone permission denied. Please allow microphone access.');
        }
    }
    
    initAudioAnalysis(stream) {
        try {
            // Create audio context for real-time analysis
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.microphone = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.analyser.smoothingTimeConstant = 0.1; // Very low smoothing for instant response (was 0.8)
            this.microphone.connect(this.analyser);
            
            // Create data array for analysis
            const bufferLength = this.analyser.frequencyBinCount;
            this.audioDataArray = new Uint8Array(bufferLength);
            // Time-domain buffer for RMS-based VAD
            this.timeDomainArray = new Uint8Array(bufferLength);
            // Adaptive VAD calibration and hysteresis
            this.vadCalibrating = false;
            this.noiseBaselineRMS = 0;
            this.noiseBaselineFrames = 0;
            this.calibrationFramesTarget = 60; // ~600ms at 10ms check
            this.isVoiceActive = false;
            this.vadStartDelta = 0.02; // start talking if RMS is at least +0.02 above baseline
            this.vadStopDelta = 0.01;  // stop talking if RMS falls within +0.01 of baseline
            
            console.log('✅ Audio analysis initialized for VAD');
        } catch (error) {
            console.error('⚠️ Could not initialize audio analysis:', error);
            // Continue without VAD - will use time-based detection
        }
    }
    
    detectAudioLevel() {
        if (!this.analyser || !this.timeDomainArray || !this.isActiveRecording) {
            return false;
        }
        
        try {
            // Read time-domain waveform and compute RMS [-1, 1] normalized
            this.analyser.getByteTimeDomainData(this.timeDomainArray);
            let sumSquares = 0;
            for (let i = 0; i < this.timeDomainArray.length; i++) {
                const centered = (this.timeDomainArray[i] - 128) / 128; // normalize around 0
                sumSquares += centered * centered;
            }
            const rms = Math.sqrt(sumSquares / this.timeDomainArray.length);
            
            // Calibration phase: gather baseline RMS for ambient noise
            if (this.vadCalibrating) {
                // Initialize baseline quickly
                if (this.noiseBaselineFrames === 0) {
                    this.noiseBaselineRMS = rms;
                } else {
                    this.noiseBaselineRMS = ((this.noiseBaselineRMS * this.noiseBaselineFrames) + rms) / (this.noiseBaselineFrames + 1);
                }
                this.noiseBaselineFrames += 1;
                // If we detect likely speech during calibration, end calibration early
                if (rms > (this.noiseBaselineRMS + 0.02) && this.noiseBaselineFrames > 10) {
                    this.vadCalibrating = false;
                    console.log('🎚️ [VAD] Calibration ended early due to speech. Baseline RMS:', this.noiseBaselineRMS.toFixed(4));
                } else if (this.noiseBaselineFrames >= this.calibrationFramesTarget) {
                    this.vadCalibrating = false;
                    console.log('🎚️ [VAD] Calibration complete. Baseline RMS:', this.noiseBaselineRMS.toFixed(4));
                }
                // During calibration treat as silence
                return false;
            }
            
            // Hysteresis thresholds around baseline
            const startThreshold = this.noiseBaselineRMS + this.vadStartDelta;
            const stopThreshold = this.noiseBaselineRMS + this.vadStopDelta;
            
                const now = Date.now();
            let voiceNow = false;
            if (!this.isVoiceActive) {
                voiceNow = rms > startThreshold;
                if (voiceNow) {
                    this.isVoiceActive = true;
                }
            } else {
                voiceNow = rms > stopThreshold;
                if (!voiceNow) {
                    this.isVoiceActive = false;
                }
            }
            
            if (voiceNow) {
                // Increment consecutive frames counter
                this.voiceConsecutiveFrames = Math.min(this.voiceConsecutiveFrames + 1, 1000);
                // Accumulate total voice frames (~10ms per interval; actual interval is 10ms in startRealTimeVAD)
                this.voiceFramesTotal = Math.min(this.voiceFramesTotal + 1, 100000);
                this.lastAudioTime = now;
                
                // Mark sustained voice after small consecutive window
                if (this.firstAudioTime === 0 && this.voiceConsecutiveFrames >= 8) {
                    this.firstAudioTime = now;
                    this.hadSustainedVoice = true;
                    console.log('🎤 [VAD] Sustained voice detected, starting dynamic recording');
                }
                
                // Adapt silence threshold based on phase of utterance (early vs normal)
                if (this.firstAudioTime > 0) {
                    const sinceFirstSpeech = now - this.firstAudioTime;
                    if (sinceFirstSpeech < this.earlyPhaseWindowMs) {
                        this.adaptiveSilenceThreshold = this.earlySilenceThresholdMs;
                } else {
                        this.adaptiveSilenceThreshold = this.normalSilenceThresholdMs;
                    }
                } else {
                    this.adaptiveSilenceThreshold = this.normalSilenceThresholdMs;
                }
                
                if (this.silenceStartTime > 0) {
                    this.silenceStartTime = 0;
                }
                return true;
            } else {
                // Silence detected
                this.voiceConsecutiveFrames = Math.max(this.voiceConsecutiveFrames - 2, 0);
                return false;
            }
        } catch (error) {
            console.error('Error detecting audio level:', error);
            return false;
        }
    }
    
    // State management - Ready, Listen, Speak
    setState(newState) {
        const oldState = this.currentState;
        this.currentState = newState;
        
        const chatManager = ChatManager.getInstance();
        
        // Update Rhasspy button state (phone button in bottom controls)
        const rhasspyBtn = document.getElementById('rhasspy-start-btn');
        if (rhasspyBtn && rhasspyBtn.classList.contains('started')) {
            if (newState === AudioManager.STATES.LISTENING) {
                // Recording - red with blink
                rhasspyBtn.classList.add('recording');
            } else {
                // Speaking or Idle - remove blink
                rhasspyBtn.classList.remove('recording');
            }
        }
        
        switch (newState) {
            case AudioManager.STATES.IDLE:
                chatManager.updateStatus('idle', 'Ready');
                break;
            case AudioManager.STATES.LISTENING:
                // User is speaking/listening
                chatManager.updateStatus('listening', 'Listen');
                this.updateVoiceUI(true);
                break;
            case AudioManager.STATES.PROCESSING:
                // API is processing
                chatManager.updateStatus('processing', 'Process');
                this.updateVoiceUI(false);
                break;
            case AudioManager.STATES.SPEAKING:
                // AI is speaking
                chatManager.updateStatus('speaking', 'Speak');
                this.updateVoiceUI(false);
                break;
        }
        
        console.log(`🔄 State: ${oldState} → ${newState}`);
    }
    
    setConversationActive(isActive) {
        this.hasActiveConversation = isActive;
        
        if (isActive) {
            this.isListeningForWakeWord = false;
            if (!this.localConversationId) {
                this.localConversationId = this.generateLocalConversationId();
            }
            return;
        }
        
        this.resetConversationState();
    }
    
    resetConversationState() {
        const avatarManager = AvatarManager.getInstance();
        const chatManager = ChatManager.getInstance();
        
        if (this.recordingTimeout) {
            clearTimeout(this.recordingTimeout);
            this.recordingTimeout = null;
        }
        if (this.silenceTimeout) {
            clearTimeout(this.silenceTimeout);
            this.silenceTimeout = null;
        }
        if (this.autoPromptTimeout) {
            clearTimeout(this.autoPromptTimeout);
            this.autoPromptTimeout = null;
        }
        
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            try {
                this.mediaRecorder.stop();
            } catch (error) {
                console.warn('⚠️ [RESET] Unable to stop media recorder:', error);
            }
        }
        
        // Stop any currently playing audio
        if (this.currentAudio && !this.currentAudio.paused) {
            console.log('🛑 [RESET] Stopping audio playback');
            try {
                this.currentAudio.pause();
                this.currentAudio.currentTime = 0;
            } catch (error) {
                console.warn('⚠️ [RESET] Unable to stop audio playback:', error);
            }
        }
        if (this.currentAudio) {
            this.currentAudio.onended = null;
            this.currentAudio.onerror = null;
            this.currentAudio = null;
        }
        
        // Stop lip sync animation
        if (avatarManager) {
            avatarManager.stopLipSync();
            console.log('🛑 [RESET] Lip sync stopped');
        }
        
        this.processingQueue = [];
        this.isActiveRecording = false;
        this.processingLock = false;
        this.isProcessing = false;
        this.isListeningForWakeWord = true;
        this.hadSustainedVoice = false;
        this.voiceConsecutiveFrames = 0;
        this.voiceFramesTotal = 0;
        this.updateVoiceUI(false);
        this.unmuteMicrophone();
        this.localConversationId = null;
        
        this.setState(AudioManager.STATES.IDLE);
        chatManager?.updateStatus('idle', 'Ready');
        avatarManager?.setAwake(false);
        
        setTimeout(() => {
            if (!this.isActiveRecording) {
                this.startWakeWordDetection();
            }
        }, 600);
    }

    generateLocalConversationId() {
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return `conv-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    }

    getOrCreateConversationId() {
        if (!this.localConversationId) {
            this.localConversationId = this.generateLocalConversationId();
        }
        return this.localConversationId;
    }
    
    // Main audio processing flow with queue
    async processAudio(audioBlob) {
        // Check if audio is too small (likely silence) - increased threshold
        if (audioBlob.size < this.minAudioSize) {
            console.log(`⏭️ Audio too small (${(audioBlob.size / 1024).toFixed(2)} KB), likely silence/noise - skipping`);
            // Don't process - just continue listening
            if (this.isActiveRecording) {
                // Restart recording if we're in active mode
                setTimeout(() => {
                    if (!this.isProcessing && !this.processingLock) {
                        console.log('🔄 Restarting recording after silence detected');
                        this.startRecording();
                    }
                }, 500);
            } else {
                this.continueFlow();
            }
            return;
        }
        
        // Add to queue if already processing
        if (this.isProcessing || this.processingLock) {
            console.log('📦 Adding to queue (already processing)');
            this.processingQueue.push(audioBlob);
            return;
        }
        
        // Process immediately
        await this.processAudioInternal(audioBlob);
        
        // Process queue
        this.processQueue();
    }
    
    async processAudioInternal(audioBlob) {
        // Lock processing
        this.isProcessing = true;
        this.processingLock = true;
        
        // Get assistant manager once for the entire function
        const assistantManager = AssistantManager.getInstance();
        
        // Transition to PROCESSING state (recording complete, API call starting)
        // Avoid UI flicker during wake word detection - don't change status to Process
        if (!this.isListeningForWakeWord) {
        this.setState(AudioManager.STATES.PROCESSING);
        } else {
            console.log('🤫 [WAKE_WORD] Processing audio silently (no UI state change)');
        }
        
        const inWakeWordMode = this.isListeningForWakeWord && !this.isActiveRecording;
        
        // Set a timeout to prevent getting stuck
        let timeoutId = null;
        let timeoutId2 = null;
        let controller = null;
        
        try {
            // Log audio processing start
            console.log('🎤 Processing Audio:', {
                blob_size: audioBlob.size,
                blob_size_kb: (audioBlob.size / 1024).toFixed(2) + ' KB',
                timestamp: new Date().toISOString()
            });
            
            // Set overall timeout (must be longer than fetch timeout)
            timeoutId = setTimeout(() => {
                if (this.isProcessing || this.processingLock) {
                    console.error('⏱️ Processing timeout - resetting state');
                    // Abort the fetch if it's still running
                    if (controller) {
                        controller.abort();
                    }
                    this.isProcessing = false;
                    this.processingLock = false;
                    this.setState(AudioManager.STATES.IDLE);
                    if (!inWakeWordMode) {
                    const chatManager = ChatManager.getInstance();
                    chatManager.addMessage('assistant', 'Sorry, the request took too long. Please try again.');
                    this.continueFlow();
                    } else {
                        setTimeout(() => {
                            if (this.isListeningForWakeWord && !this.isActiveRecording && !this.isProcessing) {
                                this.startWakeWordDetection();
                }
                        }, 500);
                    }
                }
            }, 70000); // 70 second timeout for processing (longer than fetch timeout to allow completion)
            
            const currentLanguage = window.currentLanguage || 'en-IN';
                   const formData = new FormData();
                   formData.append('audio', audioBlob, 'recording.webm');
            if (!inWakeWordMode) {
                   formData.append('language', currentLanguage);
                if (assistantManager) {
                    const threadId = assistantManager.getCurrentThread();
                    const assistantId = assistantManager.getCurrentAssistant();
                    if (assistantId) {
                        formData.append('assistant_id', assistantId);
                        console.log('🤖 [AUDIO] Sending assistant_id:', assistantId);
                    }
                    if (threadId) {
                        formData.append('thread_id', threadId);
                        console.log('🧵 [AUDIO] Sending thread_id:', threadId);
                    }
                }
            } else {
                console.log('👂 [AUDIO] Wake-word mode active - using dedicated endpoint');
            }
            
            // Track API call timing
            this.apiCallStartTime = Date.now();
            
            if (inWakeWordMode) {
            controller = new AbortController();
            timeoutId2 = setTimeout(() => {
                    console.warn('⏱️ Fetch timeout - aborting wake-word request');
                controller.abort();
                }, 60000);
                
                const wakeResponse = await fetch(`${this.apiUrl}/audio/wake-word`, {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });
            
            this.apiCallEndTime = Date.now();
            const fetchDuration = this.apiCallEndTime - this.apiCallStartTime;
                console.log(`✅ [TIMING] Wake-word response in ${fetchDuration}ms (${(fetchDuration / 1000).toFixed(2)}s)`);
            
            if (timeoutId2) clearTimeout(timeoutId2);
            if (timeoutId) clearTimeout(timeoutId);
            
                if (!wakeResponse.ok) {
                    const errorMessage = await this.parseErrorResponse(
                        wakeResponse,
                        'Failed to process wake-word audio'
                    );
                    throw new Error(errorMessage);
                }
                
                const data = await wakeResponse.json();
                const wakeDetected = data.wake_word_detected === true;
                const wakeScore = typeof data.wake_word_score === 'number' ? data.wake_word_score : null;
                console.log('👂 [WAKE_WORD] Backend result:', { wakeDetected, wakeScore });

                if (wakeDetected) {
                this.stopRecording();
                    this.setState(AudioManager.STATES.LISTENING);
                    const chatManager = ChatManager.getInstance();
                    chatManager.updateStatus('listening', 'Listen');
                    await new Promise(resolve => setTimeout(resolve, 500));
                    
                    const rhasspyBtn = document.getElementById('rhasspy-start-btn');
                    if (rhasspyBtn && !rhasspyBtn.classList.contains('started')) {
                        console.log('🟢 [WAKE_WORD] Triggering Rhasspy start button click');
                        rhasspyBtn.click();
                    } else {
                        console.log('🟢 [WAKE_WORD] Button not available or already started, using wake-up flow');
                        await this.wakeUpRhasspy();
                    }
                } else {
                    console.log('⏭️ No wake word detected in wake-word mode, continuing to listen');
                    this.isProcessing = false;
                    this.processingLock = false;
                    setTimeout(() => {
                        if (this.isListeningForWakeWord && !this.isActiveRecording && !this.isProcessing) {
                            this.startWakeWordDetection();
                        }
                    }, 500);
                }
                    this.isProcessing = false;
                    this.processingLock = false;
                    return;
                }
                
            // Conversation mode: stream transcript + assistant response from single endpoint
            controller = new AbortController();
            timeoutId2 = setTimeout(() => {
                console.warn('⏱️ Audio fetch timeout - aborting request');
                controller.abort();
            }, 60000);
            
            console.log('📤 [TIMING] Sending audio to /api/audio...');
            const response = await fetch(`${this.apiUrl}/audio`, {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });
            
            this.apiCallEndTime = Date.now();
            const fetchDuration = this.apiCallEndTime - this.apiCallStartTime;
            console.log(`✅ [TIMING] Audio pipeline response in ${fetchDuration}ms (${(fetchDuration / 1000).toFixed(2)}s)`);
            
            if (timeoutId2) clearTimeout(timeoutId2);
            if (timeoutId) clearTimeout(timeoutId);
            
            if (!response.ok) {
                const errorMessage = await this.parseErrorResponse(
                    response,
                    'Failed to process audio'
                );
                throw new Error(errorMessage);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let accumulatedText = '';
            let assistantStreamStarted = false;
            const audioQueue = [];
            let isPlayingAudio = false;
            
            const chatManager = ChatManager.getInstance();
            const playNextAudio = async () => {
                if (isPlayingAudio || audioQueue.length === 0) return;
                isPlayingAudio = true;
                const audioChunk = audioQueue.shift();
                try {
                    await this.playResponseAudio(audioChunk.audio);
                } catch (error) {
                    console.error('❌ Error playing audio chunk:', error);
                } finally {
                    isPlayingAudio = false;
                    if (audioQueue.length > 0) {
                        playNextAudio();
                    }
                }
            };
            
            let buffer = '';
            const processEvents = () => {
                let boundary;
                while ((boundary = buffer.indexOf('\n\n')) !== -1) {
                    const rawEvent = buffer.slice(0, boundary);
                    buffer = buffer.slice(boundary + 2);
                    
                    const dataLines = [];
                    for (const line of rawEvent.split('\n')) {
                        if (line.startsWith('data:')) {
                            dataLines.push(line.substring(5).trim());
                        }
                    }
                    if (dataLines.length === 0) {
                        continue;
                    }
                    
                    const payload = dataLines.join('\n');
                    if (!payload) continue;
                    
                    try {
                        const data = JSON.parse(payload);
                        
                        if (data.type === 'input_text') {
                            const transcript = data.text || '';
                            if (transcript && chatManager) {
                                chatManager.addMessage('user', transcript);
                                chatManager.showTypingIndicator();
                            }
                        } else if (data.type === 'thread_id') {
                            if (assistantManager) {
                                assistantManager.setCurrentThread(data.thread_id);
                            }
                        } else if (data.type === 'text') {
                            const delta = data.text ?? '';
                            if (!delta || !chatManager) {
                                continue;
                            }
                            accumulatedText += delta;
                            if (!assistantStreamStarted) {
                                chatManager.addMessage('assistant', '', true);
                                assistantStreamStarted = true;
                            }
                            chatManager.appendStreamingText(delta);
                        } else if (data.type === 'audio_chunk') {
                            audioQueue.push({ audio: data.audio, text: data.text });
                            if (!isPlayingAudio) {
                                this.setState(AudioManager.STATES.SPEAKING);
                                playNextAudio();
                            }
                        } else if (data.type === 'done') {
                            if (chatManager) {
                                chatManager.finishStreaming(accumulatedText);
                            }
                            assistantStreamStarted = false;
                            
                            let waitCount = 0;
                            const maxWait = 600;
                            const waitForAudio = setInterval(() => {
                                waitCount++;
                                const audioFinished = audioQueue.length === 0 && !isPlayingAudio && !this.currentAudio;
                                
                                if (audioFinished) {
                                    clearInterval(waitForAudio);
                                    this.unmuteMicrophone();
                                    
                                    console.log('🎤 [AUDIO_DONE] Checking next state:', {
                isActiveRecording: this.isActiveRecording,
                isListeningForWakeWord: this.isListeningForWakeWord,
                currentState: this.currentState
            });
            
                                    if (this.isActiveRecording && !this.isListeningForWakeWord) {
                                        console.log('🎤 Conversation mode – resuming listening');
                                        this.setState(AudioManager.STATES.LISTENING);
                                        chatManager?.updateStatus('listening', 'Listen');
                        setTimeout(() => {
                            if (!this.isProcessing && !this.processingLock) {
                                this.startRecording();
                            }
                        }, 500);
                                    } else if (this.isListeningForWakeWord) {
                                        console.log('👂 Resuming wake-word detection');
                                        this.setState(AudioManager.STATES.IDLE);
                                        chatManager?.updateStatus('idle', 'Ready');
                                        this.startWakeWordDetection();
                    } else {
                                        console.log('⏸️ Returning to idle (no active mode)');
                                        this.setState(AudioManager.STATES.IDLE);
                                        chatManager?.updateStatus('idle', 'Ready');
                                    }
                                    
                                    this.continueFlow();
                                } else if (waitCount > maxWait) {
                                    clearInterval(waitForAudio);
                                    console.warn('⚠️ Audio playback timeout – forcing idle');
                                    this.unmuteMicrophone();
                                    this.setState(AudioManager.STATES.IDLE);
                                    chatManager?.updateStatus('idle', 'Ready');
                        this.continueFlow();
                    }
                            }, 100);
                        } else if (data.type === 'error') {
                            const errorMessage = data.error || 'Server error';
                            console.error('❌ Server error:', errorMessage);
                            
                            // Check if it's a "no speech detected" error
                            if (errorMessage.includes('No speech detected') || errorMessage.includes('text too short')) {
                                console.log('🔇 No speech detected - returning to listening state');
                                
                                // Reset processing state
                this.isProcessing = false;
                this.processingLock = false;
                                
                                // Return to listening state if in active conversation
                                if (this.isActiveRecording && !this.isListeningForWakeWord) {
                                    console.log('🎤 Continuing conversation - back to listening');
                                    this.setState(AudioManager.STATES.LISTENING);
                                    setTimeout(() => {
                                        this.startRecording();
                                    }, 300);
                                } else {
                                    // Return to idle state
                                    this.setState(AudioManager.STATES.IDLE);
                this.continueFlow();
                                }
                                return; // Exit early
                            }
                            
                            // For other errors, throw to be caught by outer catch
                            throw new Error(errorMessage);
                        }
                    } catch (error) {
                        console.error('❌ Error parsing SSE event:', error);
                        // Don't throw here - let the outer catch handle state reset
                    }
                }
            };
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    buffer += decoder.decode();
                    processEvents();
                    break;
                }
                
                buffer += decoder.decode(value, { stream: true });
                processEvents();
            }
        } catch (error) {
            // Clear timeouts
            if (timeoutId2) clearTimeout(timeoutId2);
            if (timeoutId) clearTimeout(timeoutId);
            
            console.error('❌ Error processing audio:', error);
            
            // Always reset processing state
            this.isProcessing = false;
            this.processingLock = false;
            if (this.currentAudio && !this.currentAudio.paused) {
                try {
                    this.currentAudio.pause();
                    this.currentAudio.currentTime = 0;
                } catch (pauseError) {
                    console.warn('⚠️ [AUDIO] Error stopping current audio after failure:', pauseError);
                }
            }
            this.currentAudio = null;

            if (inWakeWordMode) {
                console.warn('⚠️ Wake-word mode error suppressed:', error?.message || error);
                // Ensure UI returns to idle and resume listening for wake word
                this.setState(AudioManager.STATES.IDLE);
                setTimeout(() => {
                    if (this.isListeningForWakeWord && !this.isActiveRecording && !this.isProcessing) {
                        this.startWakeWordDetection();
                    }
                }, 500);
                return;
            }
            
            // Check if it's a timeout/abort error
            if (error.name === 'AbortError' || error.message.includes('timeout') || error.message.includes('aborted') || error.message.includes('signal is aborted')) {
                console.error('⏱️ Request timeout or aborted:', error.message);
                this.setState(AudioManager.STATES.IDLE);
                const chatManager = ChatManager.getInstance();
                chatManager.addMessage('assistant', 'Request timed out. The server may be processing your request. Please wait a moment and try again.');
                this.continueFlow();
                return;
            }
            
            // Handle network errors
            if (error.message.includes('Failed to fetch') || error.message.includes('network')) {
                console.error('🌐 Network error');
                this.setState(AudioManager.STATES.IDLE);
                const chatManager = ChatManager.getInstance();
                chatManager.addMessage('assistant', 'Network error. Please check your connection and try again.');
                this.continueFlow();
                return;
            }
            
            // Handle other errors - ensure we return to proper state
            console.error('❌ Unhandled error in processAudioInternal:', error);
            this.setState(AudioManager.STATES.IDLE);
            
            // If in active conversation, return to listening
            if (this.isActiveRecording && !this.isListeningForWakeWord) {
                console.log('🎤 Error occurred - returning to listening state');
                setTimeout(() => {
                    this.continueFlow();
                }, 500);
            } else {
                this.continueFlow();
            }
        }
    }
    
    async processQueue() {
        // Process next item in queue if available
        if (this.processingQueue.length > 0 && !this.isProcessing) {
            const nextAudio = this.processingQueue.shift();
            console.log(`📦 Processing queued audio (${this.processingQueue.length} remaining)`);
            await this.processAudioInternal(nextAudio);
            // Continue processing queue
            this.processQueue();
        }
    }
    
    async handleConversation(data) {
        console.log('💬 [HANDLE_CONVERSATION] Starting conversation handling');
        console.log('💬 [HANDLE_CONVERSATION] Input data:', {
            user_input: data.input_text,
            user_input_length: data.input_text?.length || 0,
            bot_response: data.response,
            bot_response_length: data.response?.length || 0,
            emotion: data.emotion?.emotion,
            emotion_intensity: data.emotion?.intensity,
            has_audio: !!data.audio,
            currentState: this.currentState,
            isProcessing: this.isProcessing,
            processingLock: this.processingLock
        });
        
        const chatManager = ChatManager.getInstance();
        const avatarManager = AvatarManager.getInstance();
        
        // Add user message with typing effect
        await chatManager.streamUserMessage(data.input_text);
        console.log('💬 [HANDLE_CONVERSATION] User message streaming to chat');
        
        // Audio processing is done, now AI will respond - stay in LISTENING until AI speaks
        this.isProcessing = false;  // Audio processing is done
        this.processingLock = false;
        console.log('💬 [HANDLE_CONVERSATION] Processing flags reset');
        // Keep LISTENING state - will change to SPEAKING when audio plays
        
        // Update avatar emotion
        avatarManager.setEmotion(data.emotion.emotion, data.emotion.intensity);
        console.log('💬 [HANDLE_CONVERSATION] Avatar emotion set:', data.emotion.emotion);
        
        // Check if response contains "namaste" and trigger gesture
        const responseLower = data.response.toLowerCase();
        if (responseLower.includes('namaste')) {
            console.log('🙏 [HANDLE_CONVERSATION] Detected "namaste" in response - triggering gesture');
            avatarManager.performNamaste(2500); // 2.5 second namaste gesture
        }
        
        // Play audio and stream text simultaneously
        chatManager.updateStatus('processing', 'Process');
        
        // Log response details
        console.log('🤖 [HANDLE_CONVERSATION] Bot Response Details:', {
            text: data.response,
            words: data.response.split(' ').length,
            characters: data.response.length,
            has_audio: !!data.audio,
            will_play_audio: !!data.audio
        });
        
        // Play audio if available (start immediately, don't wait)
        if (data.audio) {
            console.log('🔊 [HANDLE_CONVERSATION] Starting audio playback immediately');
            console.log('🔊 [HANDLE_CONVERSATION] State before playing audio:', {
                currentState: this.currentState,
                isProcessing: this.isProcessing
            });
            
            // Start audio playback (don't await - let it play in background)
            const audioPromise = this.playResponseAudio(data.audio);
            
            // Get audio duration for text streaming synchronization
            const estimatedDuration = this.estimateAudioDuration(data.audio);
            
            // Stream text synchronized with audio (also don't await - run in parallel)
            const streamPromise = chatManager.streamAssistantMessage(data.response, {
                totalDuration: estimatedDuration || undefined
            });
            
            // Wait for both to complete
            await Promise.all([audioPromise, streamPromise]);
            console.log('🔊 [HANDLE_CONVERSATION] Audio playback and text streaming completed');
        } else {
            console.log('⚠️ [HANDLE_CONVERSATION] No audio available, displaying text only');
            // No audio - just display text immediately
            chatManager.addMessage('assistant', data.response);
            console.log('💬 [HANDLE_CONVERSATION] Assistant message added to chat (no audio)');
            
            // Go back to ready
            this.isProcessing = false;
            this.processingLock = false;
            this.setState(AudioManager.STATES.IDLE);
            chatManager.updateStatus('idle', 'Ready');
            console.log('⚠️ [HANDLE_CONVERSATION] State set to IDLE');
            // Only continue flow if we're in active recording mode
            if (this.isActiveRecording && !this.isListeningForWakeWord) {
                console.log('⚠️ [HANDLE_CONVERSATION] Will restart recording in 500ms');
                setTimeout(() => {
                    console.log('⚠️ [HANDLE_CONVERSATION] Attempting to restart recording');
            this.startRecording();
            this.showManualRecordingUI();
                }, 500);
            } else {
                console.log('⚠️ [HANDLE_CONVERSATION] Not restarting recording:', {
                    isActiveRecording: this.isActiveRecording,
                    isListeningForWakeWord: this.isListeningForWakeWord
                });
            }
        }
    }
    
    async playResponseAudio(audioBase64) {
        const avatarManager = AvatarManager.getInstance();
        
        // MUTE MICROPHONE FIRST to prevent feedback/howling
        this.muteMicrophone();
        console.log('🔇 [PLAY_AUDIO] Microphone muted BEFORE audio playback to prevent feedback');
        
        // Stop any currently playing audio gracefully when new audio starts
        if (this.currentAudio && !this.currentAudio.paused) {
            console.log('🛑 [PLAY_AUDIO] Stopping previous audio to prevent overlap');
            try {
                // Pause instead of immediate stop to avoid AbortError
                this.currentAudio.pause();
                this.currentAudio.currentTime = 0;
                // Remove listeners to prevent errors
                this.currentAudio.onended = null;
                this.currentAudio.onerror = null;
            } catch (error) {
                console.log('⚠️ [PLAY_AUDIO] Error stopping previous audio (expected):', error.message);
            }
            this.currentAudio = null;
            avatarManager.stopLipSync();
            // Reset processing state immediately
            this.isProcessing = false;
            this.processingLock = false;
        }
        
        // AI is now speaking
        this.setState(AudioManager.STATES.SPEAKING);
        avatarManager.startLipSync(audioBase64);
        console.log('🔊 [PLAY_AUDIO] Starting playback', {
            base64Length: audioBase64?.length || 0
        });
        
        return new Promise((resolve, reject) => {
        const audio = new Audio(`data:audio/mpeg;base64,${audioBase64}`);
            this.currentAudio = audio; // Track current audio
        
        audio.onended = () => {
                console.log('🔊 [AUDIO_ENDED] Audio playback ended');
                console.log('🔊 [AUDIO_ENDED] Current state before cleanup:', {
                    currentState: this.currentState,
                    isProcessing: this.isProcessing,
                    processingLock: this.processingLock,
                    isActiveRecording: this.isActiveRecording,
                    isListeningForWakeWord: this.isListeningForWakeWord,
                    hasCurrentAudio: !!this.currentAudio
                });
                
            avatarManager.stopLipSync();
                this.currentAudio = null;
                this.isProcessing = false;
                this.processingLock = false;
                resolve();
        };
        
        audio.onerror = (error) => {
                console.error('❌ Audio playback error:', error);
            avatarManager.stopLipSync();
                this.currentAudio = null;
                this.isProcessing = false;
                this.processingLock = false;
                // Ensure mic unmuted on error
                this.unmuteMicrophone();
                
                // Reset state and continue
                this.setState(AudioManager.STATES.IDLE);
                setTimeout(() => {
                    this.continueFlow();
                }, 100);
                
                reject(error);
        };
        
        audio.play().catch(error => {
                // Ignore AbortError - it's expected when audio is interrupted
                if (error.name === 'AbortError' || error.message.includes('interrupted')) {
                    console.log('⚠️ [PLAY_AUDIO] Audio play interrupted (expected when new audio starts)');
                    resolve(); // Resolve instead of reject for AbortError
                    return;
                }
                
                console.error('❌ [PLAY_AUDIO] Error playing audio:', error);
            avatarManager.stopLipSync();
                this.currentAudio = null;
                this.isProcessing = false;
                this.processingLock = false;
                // Ensure mic unmuted on error
                this.unmuteMicrophone();
                
                // Reset state and continue
                this.setState(AudioManager.STATES.IDLE);
                setTimeout(() => {
                    this.continueFlow();
                }, 100);
                
                reject(error);
            });
        });
    }
    
    estimateAudioDuration(audioBase64) {
        if (!audioBase64) {
            return null;
        }
        const cleaned = audioBase64.replace(/[^A-Za-z0-9+/=]/g, '');
        if (!cleaned.length) {
            return null;
        }
        const byteLength = (cleaned.length * 3) / 4;
        const approximateBytesPerSecond = 6200; // rough estimate for compressed speech audio
        return Math.max(byteLength / approximateBytesPerSecond, 0);
    }
    
    // Wake word detection - improved matching
    checkWakeWord(transcript) {
        if (!transcript || transcript.trim().length === 0) {
            return false;
        }
        
        const lowerTranscript = transcript.toLowerCase().trim();
        const cleanTranscript = lowerTranscript
            .replace(/[^\w\s]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        
        console.log('🔍 Checking wake word in:', cleanTranscript);
        
        for (const wakeWord of this.wakeWords) {
            const cleanWakeWord = wakeWord.toLowerCase().trim();
            
            // Multiple matching strategies for better detection
            // 1. Exact contains match
            if (cleanTranscript.includes(cleanWakeWord)) {
                console.log('✅ Wake word detected (contains):', wakeWord);
                return true;
            }
            
            // 2. Starts with wake word
            if (cleanTranscript.startsWith(cleanWakeWord)) {
                console.log('✅ Wake word detected (starts with):', wakeWord);
                return true;
            }
            
            // 3. Ends with wake word
            if (cleanTranscript.endsWith(cleanWakeWord)) {
                console.log('✅ Wake word detected (ends with):', wakeWord);
                return true;
            }
            
            // 4. Check if words match (handles variations like "hey, rhasspy" vs "hey rhasspy")
            const transcriptWords = cleanTranscript.split(/\s+/);
            const wakeWords = cleanWakeWord.split(/\s+/);
            
            if (wakeWords.length === 2) {
                // For "hey rhasspy" - check if both words appear in sequence
                const word1Index = transcriptWords.indexOf(wakeWords[0]);
                const word2Index = transcriptWords.indexOf(wakeWords[1]);
                
                if (word1Index !== -1 && word2Index !== -1 && 
                    Math.abs(word2Index - word1Index) <= 2) {
                    console.log('✅ Wake word detected (words match):', wakeWord);
                    return true;
                }
            }
        }
        
        return false;
    }
    
    // Helper: detect wake name with common STT variations
    containsWakeName(text) {
        for (const variant of this.wakeNameVariants) {
            if (text.includes(variant)) {
                return true;
            }
        }
        return false;
    }
    
    // Check for partial wake words (like "hi rhasspy" or "hey rhasspy")
    // Note: "hey", "hi", "hello" must be followed by the wake name to be detected
    checkPartialWakeWord(transcript) {
        if (!transcript || transcript.trim().length === 0) {
            return false;
        }
        
        const lowerTranscript = transcript.toLowerCase().trim();
        const cleanTranscript = lowerTranscript
            .replace(/[^\w\s]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        
        // Check if transcript contains "wake word + wake name" (name must be present, allowing minor STT variations)
        for (const partialWord of this.partialWakeWords) {
            for (const variant of this.wakeNameVariants) {
                if (
                    cleanTranscript.includes(`${partialWord} ${variant}`) ||
                    cleanTranscript.includes(`${variant} ${partialWord}`) ||
                    (cleanTranscript.includes(partialWord) && this.containsWakeName(cleanTranscript))
                ) {
                    console.log('✅ Wake word with Rhasspy detected:', `${partialWord} ${variant}`);
                return true;
                }
            }
        }
        
        return false;
    }
    
    async wakeUpRhasspy() {
        console.log('🎬 [WAKE_UP] Wake word detected - starting conversation');
        const avatarManager = AvatarManager.getInstance();
        const chatManager = ChatManager.getInstance();
        
        // Check if Rhasspy button needs to be activated (first time)
        const rhasspyBtn = document.getElementById('rhasspy-start-btn');
        if (rhasspyBtn && !rhasspyBtn.classList.contains('started')) {
            console.log('🎬 [WAKE_UP] First time - activating Rhasspy button');
            rhasspyBtn.classList.add('started');
        }
        
        this.setConversationActive(true);

        const assistantManager = typeof AssistantManager !== 'undefined' ? AssistantManager.getInstance() : null;
        const assistantId = assistantManager?.getCurrentAssistant?.();
        if (!assistantId) {
            this.getOrCreateConversationId();
        }
        
        // Wake up avatar
        avatarManager.setAwake(true);
        
        // Switch to active recording mode
        this.isListeningForWakeWord = false;
        this.isActiveRecording = true;
        
        // Show listening state while generating welcome
        this.setState(AudioManager.STATES.LISTENING);
        chatManager.updateStatus('listening', 'Listen');
        
        // Full greeting message like button click - "Namaste! I am Rhasspy..."
        const welcomeMessage = `Namaste! I am ${this.assistantDisplayName}, your AI assistant. How can I help you today?`;
        chatManager.addMessage('assistant', welcomeMessage);
        
        // Trigger namaste gesture for greeting
        avatarManager.performNamaste(2500);
        
        // Generate welcome audio directly (don't send to LLM - it's a fixed greeting)
        try {
            const assistantManager = typeof AssistantManager !== 'undefined' ? AssistantManager.getInstance() : null;
            let threadId = null;
            let assistantId = null;
            
            // Always create a NEW thread when conversation starts via wake word
            // Each conversation session should have its own thread
            if (assistantManager) {
                assistantId = assistantManager.getCurrentAssistant();
                
                if (assistantId) {
                    console.log('🧵 [WAKE_UP] Creating new thread for new conversation:', assistantId);
                    try {
                        threadId = await assistantManager.createThread();
                        console.log('✅ [WAKE_UP] New thread created:', threadId);
                        // Store the new thread for this conversation
                        assistantManager.setCurrentThread(threadId);
                    } catch (error) {
                        console.error('❌ [WAKE_UP] Failed to create thread:', error);
                    }
                }
            }
            
            const requestBody = { 
                language: window.currentLanguage || 'en-IN'
            };
            
            // Include thread_id and assistant_id if using assistants
            if (assistantId) {
                requestBody.assistant_id = assistantId;
            }
            if (threadId) {
                requestBody.thread_id = threadId;
            }
            
            console.log('🎬 [WAKE_UP] Calling /api/chats/greeting endpoint (SSE streaming)');
            
            const response = await fetch('http://localhost:5000/api/chats/greeting', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // Handle SSE stream
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let audioQueue = [];
            let isPlaying = false;
            
            // Function to play next audio chunk
            const playNextAudio = async () => {
                if (isPlaying || audioQueue.length === 0) return;
                
                isPlaying = true;
                const audioData = audioQueue.shift();
                
                console.log('🔊 [WAKE_UP] Playing audio chunk');
                this.setState(AudioManager.STATES.SPEAKING);
                await this.playResponseAudio(audioData);
                
                isPlaying = false;
                
                // Play next chunk if available
                if (audioQueue.length > 0) {
                    playNextAudio();
                }
            };
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            if (data.type === 'thread_id' && data.thread_id) {
                                console.log('🧵 [WAKE_UP] Thread ID received:', data.thread_id);
                                if (assistantManager) {
                                    assistantManager.setCurrentThread(data.thread_id);
                                }
                            } else if (data.type === 'audio_chunk' && data.audio) {
                                console.log('🎵 [WAKE_UP] Audio chunk received');
                                audioQueue.push(data.audio);
                                
                                // Start playing if not already playing
                                if (!isPlaying) {
                                    playNextAudio();
                                }
                            } else if (data.type === 'done') {
                                console.log('✅ [WAKE_UP] Stream complete');
                                
                                // Wait for all audio to finish
                                while (isPlaying || audioQueue.length > 0) {
                                    await new Promise(resolve => setTimeout(resolve, 100));
                                }
                                
                                // Transition to listening state
                                console.log('🎤 [WAKE_UP] Transitioning to LISTENING state');
                                this.setState(AudioManager.STATES.LISTENING);
                                
                                // Start recording after a short delay
                                setTimeout(() => {
                                    console.log('🎤 [WAKE_UP] Starting recording');
                                    this.startRecording();
                                }, 500);
                                return; // Exit the function after stream is complete
                            }
                        } catch (e) {
                            console.error('❌ [WAKE_UP] Error parsing SSE data:', e);
                        }
                    }
                }
            }
        } catch (error) {
            console.log('⚠️ Could not generate welcome audio:', error);
        }
        
        // Start listening for conversation
        setTimeout(() => {
            this.startRecording();
        }, 500);
    }
    
    async handleWakeWordInterrupt() {
        console.log('🛑 [INTERRUPT] Wake word detected during conversation - stopping and asking how can I help');
        const avatarManager = AvatarManager.getInstance();
        const chatManager = ChatManager.getInstance();
        
        // Wake up avatar if not already
        avatarManager.setAwake(true);
        
        // Stop lip sync if active
        avatarManager.stopLipSync();
        
        // Ensure we're in active recording mode
        this.isListeningForWakeWord = false;
        this.isActiveRecording = true;
        
        // Set to listening state
        this.setState(AudioManager.STATES.LISTENING);
        chatManager.updateStatus('listening', 'Listen');
        
        // Response message - short and direct
        const responseMessage = 'I am listening, how can I help you?';
        chatManager.addMessage('assistant', responseMessage);
        
        // Generate and play response audio
        try {
            const assistantManager = typeof AssistantManager !== 'undefined' ? AssistantManager.getInstance() : null;
            const requestBody = { 
                message: responseMessage,
                isGreeting: true,  // Flag to indicate this is a greeting response
                language: window.currentLanguage || 'en-IN'
            };
            
            // Include thread_id and assistant_id if using assistants
            if (assistantManager) {
                const threadId = assistantManager.getCurrentThread();
                const assistantId = assistantManager.getCurrentAssistant();
                if (assistantId) {
                    requestBody.assistant_id = assistantId;
                }
                if (threadId) {
                    requestBody.thread_id = threadId;
                }
            }
            
            const response = await fetch(`${this.apiUrl}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.audio) {
                    // Set to speaking state
                    this.setState(AudioManager.STATES.SPEAKING);
                    await this.playResponseAudio(data.audio);
                    return; // Audio will handle continueFlow
                }
            }
        } catch (error) {
            console.log('⚠️ Could not generate interrupt response audio:', error);
        }
        
        // Start listening for conversation (fallback if no audio)
        setTimeout(() => {
            this.startRecording();
        }, 500);
    }
    
    // Recording management
    startRecording() {
        console.log('🎤 [START_RECORDING] Attempting to start recording');
        console.log('🎤 [START_RECORDING] Current state:', {
            hasMediaRecorder: !!this.mediaRecorder,
            mediaRecorderState: this.mediaRecorder?.state,
            currentState: this.currentState,
            isProcessing: this.isProcessing,
            processingLock: this.processingLock,
            isActiveRecording: this.isActiveRecording,
            isListeningForWakeWord: this.isListeningForWakeWord
        });
        // Auto-unmute if mic is muted to ensure we can record
        if (this.isMuted) {
            console.log('🔊 [START_RECORDING] Mic was muted - unmuting now for recording');
            this.unmuteMicrophone();
        }
        
        // Don't start if already processing or if media recorder is busy
        if (!this.mediaRecorder) {
            console.log('⏸️ [START_RECORDING] Cannot start - media recorder not available');
            return;
        }
        
        // Don't start if already processing or speaking
        if (this.isProcessing || 
            this.processingLock ||
            (this.currentState === AudioManager.STATES.LISTENING && this.mediaRecorder.state === 'recording') ||
            (this.currentState === AudioManager.STATES.PROCESSING) ||
            (this.currentState === AudioManager.STATES.SPEAKING)) {
            console.log('⏸️ [START_RECORDING] Cannot start - busy state:', {
                isProcessing: this.isProcessing,
                processingLock: this.processingLock,
                currentState: this.currentState,
                mediaRecorderState: this.mediaRecorder.state
            });
            return;
        }
        
        // If coming from speaking or processing state (audio just ended), reset to idle first
        if (this.currentState === AudioManager.STATES.SPEAKING || this.currentState === AudioManager.STATES.PROCESSING) {
            console.log('🔄 [START_RECORDING] Transitioning from SPEAKING/PROCESSING to IDLE before recording');
            this.setState(AudioManager.STATES.IDLE);
        }
        
        if (this.mediaRecorder.state === 'recording') {
            console.log('⏸️ [START_RECORDING] Already recording, state:', this.mediaRecorder.state);
            return;
        }
        
        console.log('🎤 [START_RECORDING] Starting recording now');
        this.isActiveRecording = true;
        this.audioChunks = [];
        this.recordingDuration = 0;
        // Reset timing trackers
        this.recordingStartTime = Date.now();
        this.recordingEndTime = 0;
        this.apiCallStartTime = 0;
        this.apiCallEndTime = 0;
        this.firstAudioTime = 0; // Reset - will be set when user first speaks
        this.adaptiveSilenceThreshold = 100; // Reset to initial threshold
        console.log(`⏱️ [TIMING] Recording Start Time: ${this.recordingStartTime}ms`);
        
        this.mediaRecorder.start();
        console.log('🎤 [START_RECORDING] MediaRecorder started, state:', this.mediaRecorder.state);
        
        // User is now speaking - set to LISTENING
        this.setState(AudioManager.STATES.LISTENING);
        console.log('🎤 [START_RECORDING] State set to LISTENING');
        
        this.lastAudioTime = 0; // will be set on actual detected voice
        this.silenceStartTime = 0;
        this.voiceConsecutiveFrames = 0;
        // VAD calibration for adaptive baseline
        this.vadCalibrating = true;
        this.noiseBaselineRMS = 0;
        this.noiseBaselineFrames = 0;
        this.isVoiceActive = false;
        this.voiceFramesTotal = 0;
        this.hadSustainedVoice = false;
        
        // Start real-time voice activity detection
        console.log('🎤 [START_RECORDING] Starting VAD');
        this.startRealTimeVAD();
        
        // Fallback: Time-based silence detection (if VAD doesn't work)
        // Skip VAD in manual recording mode - user controls when to send
        if (!this.isManualRecording) {
        // Check very frequently for instant response
        this.timeBasedVADInterval = setInterval(() => {
            if (!this.isActiveRecording) {
                if (this.timeBasedVADInterval) {
                    clearInterval(this.timeBasedVADInterval);
                    this.timeBasedVADInterval = null;
                }
                return;
            }
            
            // Only process if we have audio chunks (user actually spoke)
            if (this.audioChunks.length > 0) {
                const timeSinceLastAudio = Date.now() - this.lastAudioTime;
                const recordingDuration = Date.now() - this.recordingStartTime;
                
                    // Ensure minimum speech duration since first speech, not just total recording time
                    const sinceFirstSpeech = this.firstAudioTime > 0 ? (Date.now() - this.firstAudioTime) : 0;
                    const canProcess = this.firstAudioTime > 0 && sinceFirstSpeech >= this.minVoiceDurationMs;
                
                    // Use adaptive threshold (phase-aware)
                    const threshold = this.adaptiveSilenceThreshold || this.normalSilenceThresholdMs;
                
                // If no audio for adaptive threshold and minimum duration met, process immediately
                if (timeSinceLastAudio >= threshold && canProcess) {
                    // Silence threshold exceeded, process immediately
                    console.log(`⏱️ [VAD] Time-based VAD: Processing after ${timeSinceLastAudio}ms of silence (threshold: ${threshold}ms)`);
                    if (this.timeBasedVADInterval) {
                        clearInterval(this.timeBasedVADInterval);
                        this.timeBasedVADInterval = null;
                    }
                    // Clear VAD interval too
                    if (this.audioLevelCheckInterval) {
                        clearInterval(this.audioLevelCheckInterval);
                        this.audioLevelCheckInterval = null;
                    }
                    // Keep in LISTENING state - will process user audio
                    // State will change to SPEAKING when AI responds
                    console.log('⏱️ [VAD] Stopping recording to process immediately');
                    this.stopRecording();
                }
            }
        }, 30); // Check every 30ms for instant fallback detection
        } else {
            console.log('🎤 [MANUAL] VAD disabled - user controls when to send');
        }
        
        // Dynamic auto-prompt: only in wake word mode, not in active conversation
        // Disable auto-prompt in active conversation mode - VAD handles it
        if (this.isListeningForWakeWord) {
            // Only set up auto-prompt in wake word detection mode
            const setupDynamicPrompt = () => {
                if (this.autoPromptTimeout) {
                    clearTimeout(this.autoPromptTimeout);
                }
                
                const hasSpoken = this.firstAudioTime > 0;
                
                if (!hasSpoken) {
                    // User hasn't spoken yet - prompt after 10 seconds (only in wake word mode)
                    const promptDelay = 10000;
                    this.autoPromptTimeout = setTimeout(() => {
                        // Double check: still in wake word mode, user still hasn't spoken
                        if (this.isListeningForWakeWord && this.firstAudioTime === 0 && this.audioChunks.length === 0) {
                            console.log('💬 [START_RECORDING] 10 seconds passed with no audio in wake word mode - prompting user');
                            this.handleAutoPrompt();
                        } else {
                            console.log('💬 [START_RECORDING] Auto-prompt cancelled - user has spoken or not in wake word mode');
                        }
                    }, promptDelay);
                }
            };
            
            // Set up initial prompt check (only in wake word mode)
            setupDynamicPrompt();
            
            // Re-evaluate prompt timing when user speaks - cancel prompt if user speaks
            const checkInterval = setInterval(() => {
                if (!this.isListeningForWakeWord || !this.isActiveRecording) {
                    clearInterval(checkInterval);
                    return;
                }
                
                const hasSpoken = this.firstAudioTime > 0;
                
                // If user just started speaking, cancel any pending auto-prompt
                if (hasSpoken && this.autoPromptTimeout) {
                    console.log('💬 [START_RECORDING] User started speaking - cancelling auto-prompt');
                    clearTimeout(this.autoPromptTimeout);
                    this.autoPromptTimeout = null;
                    clearInterval(checkInterval);
                }
            }, 500); // Check every 500ms
        } else {
            // In active conversation mode - no auto-prompt, VAD handles everything
            console.log('💬 [START_RECORDING] Active conversation mode - auto-prompt disabled, VAD handles processing');
        }
        
        // Absolute safety net: stop after max duration (only if VAD completely fails)
        // This should rarely trigger since VAD handles most cases
        // Reduced to 10s to prevent long delays
        this.recordingTimeout = setTimeout(() => {
            console.log(`⏱️ [START_RECORDING] Absolute max duration reached (${this.maxRecordingDuration/1000}s) - VAD may not be working`);
            console.log(`⏱️ [START_RECORDING] Recording stats:`, {
                duration: Date.now() - this.recordingStartTime,
                hasSpoken: this.firstAudioTime > 0,
                audioChunks: this.audioChunks.length,
                lastAudioTime: this.lastAudioTime
            });
            // Keep in LISTENING state - processing user audio
            // Will change to SPEAKING when AI responds
            this.stopRecording();
        }, this.maxRecordingDuration);
        
        console.log('🎤 Recording started with real-time VAD');
    }
    
    stopRecording() {
        if (!this.mediaRecorder || this.mediaRecorder.state !== 'recording') {
            return;
        }
        
        // Clear all timeouts and intervals
        if (this.recordingTimeout) {
            clearTimeout(this.recordingTimeout);
            this.recordingTimeout = null;
        }
        if (this.silenceTimeout) {
            clearTimeout(this.silenceTimeout);
            this.silenceTimeout = null;
        }
        if (this.autoPromptTimeout) {
            clearTimeout(this.autoPromptTimeout);
            this.autoPromptTimeout = null;
        }
        if (this.audioLevelCheckInterval) {
            clearInterval(this.audioLevelCheckInterval);
            this.audioLevelCheckInterval = null;
        }
        if (this.timeBasedVADInterval) {
            clearInterval(this.timeBasedVADInterval);
            this.timeBasedVADInterval = null;
        }
        
        // Stop recording immediately (no delay)
        this.mediaRecorder.stop();
        
        // State transition to PROCESSING is handled in onstop handler
        // or in the VAD detection before calling stopRecording
        console.log('🛑 Recording stopped → Processing immediately');
    }
    
    startRealTimeVAD() {
        // Clear any existing interval
        if (this.audioLevelCheckInterval) {
            clearInterval(this.audioLevelCheckInterval);
        }
        
        // Reset silence tracking
        this.silenceStartTime = 0;
        this.lastAudioTime = Date.now();
        
        // Check audio levels in real-time (every 20ms for ultra-fast response)
        this.audioLevelCheckInterval = setInterval(() => {
            if (!this.isActiveRecording) {
                // Stop checking if not recording
                if (this.audioLevelCheckInterval) {
                    clearInterval(this.audioLevelCheckInterval);
                    this.audioLevelCheckInterval = null;
                }
                return;
            }
            
            // Detect current audio level
            const hasVoice = this.detectAudioLevel();
            
            if (hasVoice) {
                // Voice detected - reset silence timer immediately
                this.silenceStartTime = 0;
                this.lastAudioTime = Date.now();
            } else {
                // Silence detected - but only if we have audio chunks (user spoke)
                if (this.audioChunks.length > 0) {
                    if (this.silenceStartTime === 0) {
                        // Just started silence - mark the time immediately
                        this.silenceStartTime = Date.now();
                        console.log('🔇 Silence started, waiting for threshold...');
                    } else {
                        // Check if silence duration exceeds adaptive threshold
                        const silenceDuration = Date.now() - this.silenceStartTime;
                        const recordingDuration = Date.now() - this.recordingStartTime;
                        
                        // Ensure minimum speech duration since first speech to avoid cutting off utterance
                        const sinceFirstSpeech = this.firstAudioTime > 0 ? (Date.now() - this.firstAudioTime) : 0;
                        const canProcess = this.firstAudioTime > 0 && sinceFirstSpeech >= this.minVoiceDurationMs;
                        
                        // Use adaptive threshold based on utterance phase
                        const threshold = this.adaptiveSilenceThreshold || this.normalSilenceThresholdMs;
                        
                        if (silenceDuration >= threshold && canProcess) {
                            console.log(`🔇 [VAD] Silence detected (${silenceDuration}ms) with adaptive threshold (${threshold}ms) - stopping recording`);
                            console.log(`🔇 [VAD] Recording duration: ${recordingDuration}ms, Min required: ${this.minRecordingDuration}ms`);
                            
                            // Stop checking immediately
                            if (this.audioLevelCheckInterval) {
                                clearInterval(this.audioLevelCheckInterval);
                                this.audioLevelCheckInterval = null;
                            }
                            // Also stop time-based VAD
                            if (this.timeBasedVADInterval) {
                                clearInterval(this.timeBasedVADInterval);
                                this.timeBasedVADInterval = null;
                            }
                            // Keep in LISTENING state - processing user audio
                            // Will change to SPEAKING when AI responds
                            // Stop recording and process immediately
                            console.log('🔇 [VAD] Processing user audio immediately');
                            this.stopRecording();
                            return; // Exit immediately
                        }
                    }
                }
            }
        }, 10); // Check every 10ms for ultra-responsive detection (~100 times per second - faster response)
    }
    
    async handleAutoPrompt() {
        console.log('💬 [AUTO_PROMPT] Handling auto-prompt');
        
        // Stop current recording
        this.stopRecording();
        
        // Mark that we're in auto-prompt mode to prevent processing it as user input
        this.isAutoPrompting = true;
        
        // Send a prompt to the user (just display, don't process as input)
        const chatManager = ChatManager.getInstance();
        const promptMessage = 'I am here and ready to talk! How can I help you?';
        chatManager.addMessage('assistant', promptMessage);
        
        // Generate and play audio for the prompt (use isGreeting flag to prevent LLM processing)
        try {
            console.log('💬 [AUTO_PROMPT] Generating prompt audio');
            const response = await fetch(`${this.apiUrl}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: promptMessage,
                    isGreeting: true, // Flag to prevent LLM from processing this as user input
                    language: window.currentLanguage || 'en-IN'
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.audio) {
                    // AI will speak - set to SPEAKING
                    console.log('💬 [AUTO_PROMPT] Playing prompt audio');
                    this.setState(AudioManager.STATES.SPEAKING);
                    await this.playResponseAudio(data.audio);
                }
            }
        } catch (error) {
            console.error('❌ [AUTO_PROMPT] Could not generate auto-prompt audio:', error);
        } finally {
            // Reset auto-prompt flag
            this.isAutoPrompting = false;
            
            // After prompt, restart listening (but not immediately - wait for audio to finish)
            // This is handled in the audio.onended callback
        }
    }
    
    // Flow continuation
    continueFlow() {
        console.log('🔄 continueFlow called', {
            isProcessing: this.isProcessing,
            processingLock: this.processingLock,
            currentState: this.currentState,
            isActiveRecording: this.isActiveRecording,
            isListeningForWakeWord: this.isListeningForWakeWord,
            queueLength: this.processingQueue.length
        });
        
        // Always reset state if stuck
        if ((this.currentState === AudioManager.STATES.LISTENING || this.currentState === AudioManager.STATES.SPEAKING) && !this.isProcessing && !this.processingLock && !this.currentAudio) {
            console.log('🔄 Resetting stuck state to idle (recovery)');
            this.setState(AudioManager.STATES.IDLE);
        }
        
        // Process any queued items first
        if (this.processingQueue.length > 0 && !this.isProcessing && !this.processingLock) {
            console.log('📦 Processing queued items');
            this.processQueue();
            return;
        }
        
        // Ensure we're not in a processing state
        if (this.isProcessing || this.processingLock) {
            console.log('⏸️ Still processing, will retry');
            setTimeout(() => {
                this.continueFlow();
            }, 500);
            return;
        }
        
        // After processing, we should be in Ready state
        // User can then click voice button or say wake word to continue
        console.log('✅ Processing complete, system is Ready');
        this.setState(AudioManager.STATES.IDLE);
        const chatManager = ChatManager.getInstance();
            chatManager.updateStatus('idle', 'Ready');
        
        // If we were in active conversation mode, keep the flag - don't reset it
        // The SSE stream handler will manage the transition back to listening
        if (this.isActiveRecording && !this.isListeningForWakeWord) {
            console.log('🎤 Conversation mode active - waiting for audio response to complete');
        } else if (this.isListeningForWakeWord) {
            // Restart wake word detection
            console.log('👂 Restarting wake word detection');
            setTimeout(() => {
                if (this.isListeningForWakeWord && !this.isActiveRecording && !this.isProcessing) {
                this.startWakeWordDetection();
                }
            }, 500);
        }
    }
    
    // Wake word detection mode
    startWakeWordDetection() {
        this.isListeningForWakeWord = true;
        this.isActiveRecording = false;
        this.setState(AudioManager.STATES.IDLE);
        
        // Record in chunks and check for wake word
        this.recordForWakeWord();
        
        const voiceStatus = document.getElementById('voice-status');
        if (voiceStatus) {
            voiceStatus.textContent = 'Say "Hey Rhasspy" to wake me up';
        }
        
        console.log('👂 Wake word detection started');
    }
    
    stopWakeWordDetection() {
        console.log('🛑 [WAKE_WORD] Stopping wake word detection');
        
        // Stop listening for wake words
        this.isListeningForWakeWord = false;
        
        // Stop any ongoing recording
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            console.log('🛑 [WAKE_WORD] Stopping active recording');
            try {
                this.mediaRecorder.stop();
            } catch (error) {
                console.warn('⚠️ [WAKE_WORD] Error stopping recorder:', error);
            }
        }
        
        console.log('✅ [WAKE_WORD] Wake word detection stopped');
    }
    
    recordForWakeWord() {
        if (!this.mediaRecorder) {
            console.log('⏸️ MediaRecorder not available for wake word');
            return;
        }
        
        // Don't start if already processing or in active recording
        if (this.isActiveRecording || this.isProcessing || this.processingLock) {
            console.log('⏸️ Cannot record for wake word - busy state:', {
                isActiveRecording: this.isActiveRecording,
                isProcessing: this.isProcessing,
                processingLock: this.processingLock
            });
            // Retry after a delay if processing
            if (this.isProcessing || this.processingLock) {
                setTimeout(() => {
                    if (this.isListeningForWakeWord && !this.isActiveRecording && 
                        !this.isProcessing && !this.processingLock) {
                        this.recordForWakeWord();
                    }
                }, 1000);
            }
            return;
        }
        
        if (this.mediaRecorder.state === 'recording') {
            console.log('⏸️ Already recording for wake word');
            return;
        }
        
        console.log('🎤 Starting wake word recording');
        this.audioChunks = [];
        // Set recording start time for proper processing
        this.recordingStartTime = Date.now();
        
        try {
            this.mediaRecorder.start();
            console.log('🎤 [WAKE_WORD] Recording started, will check after 3 seconds');
            
            // Record for 3 seconds, then check (faster processing)
            setTimeout(() => {
                if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
                    console.log('🛑 [WAKE_WORD] Stopping recording to check for wake word');
                    this.mediaRecorder.stop();
                    // The onstop handler will process the audio and check for wake words
                }
            }, 3000); // 3 seconds for faster wake word detection
        } catch (error) {
            console.error('❌ Error starting wake word recording:', error);
        }
    }
    
    // Voice button handler
    initVoiceButton() {
        const voiceBtn = document.getElementById('voice-btn');
        
        if (!voiceBtn) {
            console.error('❌ Voice button not found');
            return;
        }
        
        voiceBtn.addEventListener('click', async () => {
            const uiController = UIController.getInstance();
            await this.manualController.handleVoiceButtonClick(uiController);
        });
    }
    
    async beginManualRecording(isSwitchingFromWakeWord) {
        return this.manualController.beginRecording(isSwitchingFromWakeWord);
    }
    
    /**
     * Process audio for Manual mode
     * Uses shared MessageProcessor - NO duplicate code
     */
    async processManualAudio(audioBlob) {
        return this.manualController.processRecording(audioBlob);
    }
    
    // Manual recording UI helpers
    showManualRecordingUI() {
        this.manualController.showRecordingUI();
    }
    
    hideManualRecordingUI() {
        this.manualController.hideRecordingUI();
    }
    
    // UI updates
    updateVoiceUI(isRecording) {
        const voiceBtn = document.getElementById('voice-btn');
        const voiceStatus = document.getElementById('voice-status');
        
        if (voiceBtn) {
            if (isRecording) {
                voiceBtn.classList.add('recording');
            } else {
            voiceBtn.classList.remove('recording');
            }
        }
        
        if (voiceStatus) {
            if (isRecording) {
                voiceStatus.textContent = 'Listening...';
            } else if (this.isListeningForWakeWord) {
                voiceStatus.textContent = 'Say "Hey Rhasspy" to wake me up';
            } else {
            voiceStatus.textContent = 'Click to speak';
            }
        }
    }
    
    // Error handling
    handleError(error) {
        const chatManager = ChatManager.getInstance();
        const errorMsg = error.message || 'Unknown error';
        
        console.error('❌ Error:', errorMsg);
        
        if (errorMsg.includes('OPENAI_API_KEY')) {
            chatManager.addMessage('assistant', 'OpenAI API key is required for voice features. Please add OPENAI_API_KEY to your .env file.');
        } else if (errorMsg.includes('Rate limit') || errorMsg.includes('rate limit')) {
            chatManager.addMessage('assistant', 'Rate limit reached. Please wait a moment before speaking again.');
            setTimeout(() => {
                this.continueFlow();
            }, 5000); // Reduced delay for paid accounts
            return;
        } else if (errorMsg.includes('quota') || errorMsg.includes('Quota')) {
            chatManager.addMessage('assistant', 'OpenAI quota exceeded. Please check your billing at https://platform.openai.com/account/billing');
        } else {
            chatManager.addMessage('assistant', `Error: ${errorMsg}`);
            }
            
            chatManager.updateStatus('idle', 'Ready');
        this.setState(AudioManager.STATES.IDLE);
        this.continueFlow();
    }
    
    showError(message) {
        const chatManager = ChatManager.getInstance();
        chatManager.addMessage('assistant', message);
    }
    
    // Mute/unmute microphone
    muteMicrophone() {
        if (this.audioStream) {
            this.audioStream.getAudioTracks().forEach(track => {
                track.enabled = false;
            });
            this.isMuted = true;
            console.log('🔇 Microphone muted');
        }
    }
    
    unmuteMicrophone() {
        if (this.audioStream) {
            this.audioStream.getAudioTracks().forEach(track => {
                track.enabled = true;
            });
            this.isMuted = false;
            console.log('🔊 Microphone unmuted');
        }
    }
    
    // Get audio stream reference
    getAudioStream() {
        return this.audioStream;
    }
    
    // Get audio status
    getAudioStatus() {
        return {
            microphone: this.audioStream !== null,
            muted: this.isMuted,
            state: this.currentState,
            isActiveRecording: this.isActiveRecording,
            isListeningForWakeWord: this.isListeningForWakeWord
        };
    }
}