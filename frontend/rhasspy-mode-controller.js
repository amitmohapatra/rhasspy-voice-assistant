class RhasspyModeController {
    static instance = null;

    constructor() {
        if (RhasspyModeController.instance) {
            return RhasspyModeController.instance;
        }

        this.uiController = UIController.getInstance();
        this.audioManager = AudioManager.getInstance();
        this.chatManager = ChatManager.getInstance();
        this.avatarManager = AvatarManager.getInstance();
        this.assistantManager = AssistantManager.getInstance();

        this.isStarted = false;
        this.rhasspyBtn = document.getElementById('rhasspy-start-btn');

        RhasspyModeController.instance = this;
    }

    static getInstance() {
        if (!RhasspyModeController.instance) {
            RhasspyModeController.instance = new RhasspyModeController();
        }
        return RhasspyModeController.instance;
    }

    bind() {
        if (!this.rhasspyBtn) {
            console.error('❌ Rhasspy start button not found');
            return;
        }

        this.rhasspyBtn.addEventListener('click', async () => {
            if (this.isStarted) {
                await this.endConversation();
            } else {
                await this.startConversation();
            }
        });
    }

    async startConversation() {
        console.log('🎬 [RHASSPY] Starting Rhasspy conversation');
        this.isStarted = true;
        this.rhasspyBtn.classList.add('started');

        this.uiController.enterRhasspyMode();
        this.chatManager.updateStatus('speaking', 'Speak');

        if (this.audioManager?.setConversationActive) {
            this.audioManager.setConversationActive(true);
        }

        this.avatarManager.setAwake(true);
        this.avatarManager.performNamaste(2500);

        try {
            await this.streamGreeting();
        } catch (error) {
            console.error('❌ [RHASSPY] Failed to stream greeting:', error);
            await this.endConversation(true);
        }
    }

    async endConversation(isError = false) {
        console.log('🛑 [RHASSPY] Ending Rhasspy conversation');
        this.isStarted = false;
        this.rhasspyBtn.classList.remove('started', 'recording');

        this.assistantManager?.clearSession();

        if (this.audioManager?.setConversationActive) {
            this.audioManager.setConversationActive(false);
        }
        this.audioManager.isActiveRecording = false;
        this.audioManager.isListeningForWakeWord = false;

        this.chatManager?.resetConversation();
        this.avatarManager?.setAwake(false);

        this.uiController.enterIdleMode(isError);
    }

    async streamGreeting() {
        const existingAssistantId = this.assistantManager?.getCurrentAssistant();
        let lastAssistantId = existingAssistantId || '';

        const greetingMessage = 'Namaste! I am Rhasspy, your AI assistant. How can I help you today?';
        const requestBody = {
            message: greetingMessage,
            language: window.currentLanguage || 'en-IN'
        };

        if (existingAssistantId) {
            requestBody.assistant_id = existingAssistantId;
            console.log('🤖 [RHASSPY] Using existing assistant_id from storage:', existingAssistantId);
        } else {
            console.log('🤖 [RHASSPY] No existing assistant_id - backend will select one');
        }

        this.audioManager.isActiveRecording = true;
        this.audioManager.isListeningForWakeWord = false;

        const response = await fetch('http://localhost:5000/api/chats/greeting', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`Greeting API returned ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        const audioQueue = [];
        let accumulatedText = '';
        let isPlayingAudio = false;
        let buffer = '';
        let currentThreadId = this.assistantManager?.getCurrentThread() || '';
        let assistantStreamStarted = false;

        const playNextAudio = async () => {
            if (isPlayingAudio || audioQueue.length === 0) return;
            isPlayingAudio = true;
            const audioChunk = audioQueue.shift();
            try {
                this.audioManager.setState(AudioManager.STATES.SPEAKING);
                await this.audioManager.playResponseAudio(audioChunk.audio);
            } catch (error) {
                console.error('❌ [RHASSPY] Error playing greeting audio:', error);
            } finally {
                isPlayingAudio = false;
                if (audioQueue.length > 0) {
                    playNextAudio();
                }
            }
        };

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
                if (dataLines.length === 0) continue;

                const payload = dataLines.join('\n');
                if (!payload) continue;

                try {
                    const data = JSON.parse(payload);

                    if (data.type === 'assistant_id') {
                        if (data.assistant_id) {
                            lastAssistantId = data.assistant_id;
                            this.assistantManager.setCurrentAssistant(data.assistant_id);
                        }
                    } else if (data.type === 'thread_id') {
                        this.assistantManager.setCurrentThread(data.thread_id);
                        currentThreadId = data.thread_id;
                        console.log('🧵 [RHASSPY] Thread ID stored:', data.thread_id);
                    } else if (data.type === 'text') {
                        const delta = data.text ?? '';
                        if (!delta) {
                            continue;
                        }
                        accumulatedText += delta;
                        if (!assistantStreamStarted) {
                            this.chatManager.addMessage('assistant', '', true);
                            assistantStreamStarted = true;
                        }
                        this.chatManager.appendStreamingText(delta);
                    } else if (data.type === 'audio_chunk') {
                        audioQueue.push({ audio: data.audio, text: data.text });
                        playNextAudio();
                    } else if (data.type === 'done') {
                        this.chatManager.finishStreaming(accumulatedText);
                        console.log('✅ [RHASSPY] Greeting stream complete');
                        if (data.thread_id) {
                            currentThreadId = data.thread_id;
                            this.assistantManager.setCurrentThread(data.thread_id);
                        }
                        if (data.assistant_id) {
                            lastAssistantId = data.assistant_id;
                            this.assistantManager.setCurrentAssistant(data.assistant_id);
                        }

                        this.waitForGreetingAudio(audioQueue, () => {
                            this.audioManager.unmuteMicrophone();
                            this.audioManager.setState(AudioManager.STATES.LISTENING);
                            this.chatManager.updateStatus('listening', 'Listen');

                            setTimeout(() => {
                                if (!this.audioManager.isProcessing && !this.audioManager.processingLock) {
                                    console.log('🎤 [RHASSPY] Starting recording for user input');
                                    this.audioManager.startRecording();
                                }
                            }, 500);
                        });
                    } else if (data.type === 'error') {
                        throw new Error(data.error || 'Greeting stream error');
                    }
                } catch (error) {
                    console.error('❌ [RHASSPY] Error parsing greeting SSE event:', error);
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

        if (assistantStreamStarted) {
            this.chatManager.finishStreaming(accumulatedText);
        }

        if (lastAssistantId) {
            this.assistantManager.setCurrentAssistant(lastAssistantId);
        }
        if (currentThreadId) {
            this.assistantManager.setCurrentThread(currentThreadId);
        }
    }

    waitForGreetingAudio(audioQueue, onComplete) {
        let waitCount = 0;
        const maxWait = 600;
        const interval = setInterval(() => {
            waitCount++;
            const audioFinished = audioQueue.length === 0 && !this.audioManager.currentAudio;

            if (audioFinished) {
                clearInterval(interval);
                onComplete();
            } else if (waitCount > maxWait) {
                clearInterval(interval);
                console.warn('⚠️ [RHASSPY] Greeting audio timeout - forcing transition');
                onComplete();
            }
        }, 100);
    }
}

if (typeof window !== 'undefined') {
    window.RhasspyModeController = RhasspyModeController;
}

