/**
 * Chat Manager using singleton pattern
 */
class ChatManager {
    static instance = null;
    
    constructor() {
        if (ChatManager.instance) {
            return ChatManager.instance;
        }
        
        this.apiUrl = 'http://localhost:5000/api';
        this.messages = [];
        this.typewriterState = {
            queue: [],
            timer: null,
            target: null,
            running: false,
            speed: 100
        };
        
        ChatManager.instance = this;
    }
    
    static getInstance() {
        if (!ChatManager.instance) {
            ChatManager.instance = new ChatManager();
        }
        return ChatManager.instance;
    }
    
    init() {
        const sendBtn = document.getElementById('send-btn');
        const chatInput = document.getElementById('chat-input');
        
        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendMessage());
        }
        
        if (chatInput) {
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    const uiController = UIController.getInstance();
                    if (uiController.isRhasspyMode()) {
                        e.preventDefault();
                        console.log('⚠️ [CHAT] Manual input disabled while Rhasspy mode is active');
                        return;
                    }
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
    }
    
    async sendMessage(messageOverride = null, options = {}) {
        const { addUserMessage = true } = options;
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');
        const voiceBtn = document.getElementById('voice-btn');
        
        const rawMessage = typeof messageOverride === 'string'
            ? messageOverride
            : (chatInput?.value ?? '');
        const message = rawMessage.trim();
        
        const uiController = UIController.getInstance();
        if (uiController.isRhasspyMode()) {
            console.warn('⚠️ [CHAT] Ignoring manual message while Rhasspy mode is active');
            return;
        }
        
        if (!message) return;
        
        // Enter Manual mode when user sends a message
        if (uiController.isIdle()) {
            console.log('💬 [MANUAL] First message - entering Manual mode');
            uiController.enterManualMode();
        }
        
        // Disable send button and mic while processing
        console.log('🔒 [MANUAL] Disabling send controls during processing');
        if (sendBtn) sendBtn.disabled = true;
        if (voiceBtn) voiceBtn.disabled = true;
        if (chatInput) chatInput.disabled = true;
        
        if (uiController.isManualMode()) {
            const audioManager = AudioManager.getInstance();
            const manualController = audioManager?.manualController;
            manualController?.showProcessingUI();
        }
        
        if (!messageOverride && chatInput) {
            chatInput.value = '';
        }
        
        if (addUserMessage) {
            this.addMessage('user', message);
        }
        
        // Show typing indicator while waiting for response
        this.showTypingIndicator();
        
        // Update status - processing (only in manual mode)
        if (uiController.isManualMode()) {
            this.updateStatus('processing', 'Process');
        }
        
        try {
            const assistantManager = typeof AssistantManager !== 'undefined' ? AssistantManager.getInstance() : null;
            
            // Require Assistant API
            if (!assistantManager) {
                throw new Error('Assistant Manager not available');
            }
            
            let threadId = assistantManager.getCurrentThread() || '';
            let assistantId = assistantManager.getCurrentAssistant() || '';
            console.log('🧾 [CHAT] Sending context IDs:', { assistantId, threadId });
            
            const requestBody = { 
                message,
                language: window.currentLanguage || 'en-IN',
                stream: true  // Enable streaming
            };
            if (threadId) {
                requestBody.thread_id = threadId;
            }
            if (assistantId) {
                requestBody.assistant_id = assistantId;
            }
            
            // Get avatar manager
            const avatarManager = AvatarManager.getInstance();
            avatarManager.setEmotion('thinking', 0.6);
            
            // Send request to Assistant API with streaming
            const response = await fetch(`${this.apiUrl}/chats`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to get response');
            }
            
            // Handle streaming response
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let accumulatedText = '';
            let currentThreadId = threadId;
            let lastAssistantId = assistantId;
            let emotionData = null;
            const audioManager = AudioManager.getInstance();
            const audioState = {
                queue: [],
                isPlaying: false
            };
            
            const playNextAudioChunk = async () => {
                if (audioState.isPlaying || audioState.queue.length === 0) return;
                
                audioState.isPlaying = true;
                const audioChunk = audioState.queue.shift();
                
                try {
                    console.log('🔊 Playing audio chunk:', audioChunk.text.substring(0, 50));
                    await audioManager.playResponseAudio(audioChunk.audio);
                    console.log('✅ Audio chunk completed');
                } catch (error) {
                    console.error('❌ Error playing audio chunk:', error);
                } finally {
                    audioState.isPlaying = false;
                    if (audioState.queue.length > 0) {
                        playNextAudioChunk();
                    }
                }
            };
            
            // Start streaming message display
            this.addMessage('assistant', '', true);
            
            while (true) {
                const { done, value } = await reader.read();
                
                if (value) {
                    buffer += decoder.decode(value, { stream: true });
                }
                if (done) {
                    buffer += decoder.decode();
                }
                
                const lines = buffer.split('\n');
                if (!done) {
                    buffer = lines.pop() || '';
                } else {
                    buffer = '';
                }
                
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    
                    const jsonStr = line.substring(6);
                    if (!jsonStr.trim()) continue;
                    
                    try {
                        const data = JSON.parse(jsonStr);
                        
                        if (data.type === 'assistant_id') {
                            if (data.assistant_id) {
                                lastAssistantId = data.assistant_id;
                                assistantManager.setCurrentAssistant(data.assistant_id);
                            }
                        }
                        else if (data.type === 'thread_id') {
                            currentThreadId = data.thread_id;
                            if (assistantManager) {
                                assistantManager.setCurrentThread(currentThreadId);
                            }
                        }
                        else if (data.type === 'text') {
                            const delta = data.text ?? '';
                            if (!delta) continue;
                            
                            accumulatedText += delta;
                            this.appendStreamingText(delta);
                        }
                        else if (data.type === 'audio_chunk') {
                            console.log('📦 Received audio chunk');
                            audioState.queue.push({
                                audio: data.audio,
                                text: data.text
                            });
                            
                            if (!audioState.isPlaying) {
                                this.updateStatus('speaking', 'Speak');
                                playNextAudioChunk();
                            }
                        }
                        else if (data.type === 'done') {
                            if (data.thread_id) {
                                currentThreadId = data.thread_id;
                                assistantManager.setCurrentThread(currentThreadId);
                            }
                            if (data.assistant_id) {
                                lastAssistantId = data.assistant_id;
                                assistantManager.setCurrentAssistant(data.assistant_id);
                            }
                            emotionData = data.emotion;
                            accumulatedText = data.full_text || accumulatedText;
                            
                            this.finishStreaming(accumulatedText);
                            
                            let waitCount = 0;
                            const maxWait = 600;
                            const waitForAudio = setInterval(() => {
                                waitCount++;
                                if (audioState.queue.length === 0 && !audioState.isPlaying) {
                                    clearInterval(waitForAudio);
                                    this.updateStatus('idle', 'Ready');
                                    
                                    // Re-enable send controls after response is complete
                                    const uiController = UIController.getInstance();
                                    if (uiController.isManualMode()) {
                                        console.log('🔓 [MANUAL] Re-enabling send controls after response');
                                        const sendBtn = document.getElementById('send-btn');
                                        const voiceBtn = document.getElementById('voice-btn');
                                        const chatInput = document.getElementById('chat-input');
                                        if (sendBtn) sendBtn.disabled = false;
                                        if (voiceBtn) voiceBtn.disabled = false;
                                        if (chatInput) chatInput.disabled = false;
                                        
                                        const audioManager = AudioManager.getInstance();
                                        const manualController = audioManager?.manualController;
                                        manualController?.hideRecordingUI();
                                    }
                                    
                                    if (audioManager && audioManager.isActiveRecording && !audioManager.isListeningForWakeWord) {
                                        audioManager.continueFlow();
                                    }
                                } else if (waitCount > maxWait) {
                                    clearInterval(waitForAudio);
                                    console.warn('⚠️ Audio playback timeout');
                                    this.updateStatus('idle', 'Ready');
                                    
                                    // Re-enable even on timeout
                                    const uiController = UIController.getInstance();
                                    if (uiController.isManualMode()) {
                                        const sendBtn = document.getElementById('send-btn');
                                        const voiceBtn = document.getElementById('voice-btn');
                                        const chatInput = document.getElementById('chat-input');
                                        if (sendBtn) sendBtn.disabled = false;
                                        if (voiceBtn) voiceBtn.disabled = false;
                                        if (chatInput) chatInput.disabled = false;
                                        
                                        const audioManager = AudioManager.getInstance();
                                        const manualController = audioManager?.manualController;
                                        manualController?.hideRecordingUI();
                                    }
                                }
                            }, 100);
                        }
                        else if (data.type === 'error') {
                            console.error('Server error:', data.error);
                            throw new Error(data.error || 'Server error');
                        }
                    } catch (e) {
                        if (e.message && e.message.includes('Server error')) {
                            throw e; // Re-throw server errors to outer catch
                        }
                        console.error('Error parsing stream chunk:', e, 'JSON:', jsonStr);
                    }
                }
                
                if (done) {
                    break;
                }
            }
            
            const data = {
                response: accumulatedText,
                thread_id: currentThreadId,
                emotion: emotionData
            };
            
            if (data.thread_id) {
                assistantManager.setCurrentThread(data.thread_id);
            }
            if (lastAssistantId) {
                assistantManager.setCurrentAssistant(lastAssistantId);
            }
            
            if (data.emotion) {
                avatarManager.setEmotion(data.emotion.emotion, data.emotion.intensity);
            }
            
        } catch (error) {
            console.error('Error:', error);
            this.finishStreaming();
            this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
            
            // Reset state properly
            try {
                const audioManager = AudioManager.getInstance();
                const avatarManager = AvatarManager.getInstance();
                
                if (audioManager && audioManager.setState) {
                    audioManager.setState(AudioManager.STATES.IDLE);
                }
                if (avatarManager && avatarManager.stopLipSync) {
                    avatarManager.stopLipSync();
                }
            } catch (e) {
                console.warn('Could not reset managers:', e);
            }
            
            this.updateStatus('idle', 'Ready');
            
            // Re-enable send controls on error
            const uiController = UIController.getInstance();
            if (uiController.isManualMode()) {
                console.log('🔓 [MANUAL] Re-enabling send controls after error');
                const sendBtn = document.getElementById('send-btn');
                const voiceBtn = document.getElementById('voice-btn');
                const chatInput = document.getElementById('chat-input');
                if (sendBtn) sendBtn.disabled = false;
                if (voiceBtn) voiceBtn.disabled = false;
                if (chatInput) chatInput.disabled = false;
                
                const audioManager = AudioManager.getInstance();
                const manualController = audioManager?.manualController;
                manualController?.hideRecordingUI();
            }
        }
    }
    
    addMessage(role, content, isStreaming = false) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;
        
        // Remove typing indicator if present
        this.removeTypingIndicator();
        
        if (isStreaming && role === 'assistant') {
            let streamingMessage = messagesContainer.querySelector('.message.streaming');
            if (!streamingMessage) {
                streamingMessage = document.createElement('div');
                streamingMessage.className = 'message assistant streaming';
                
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                contentDiv.textContent = '';
                contentDiv.dataset.rawContent = '';
                
                const timeDiv = document.createElement('div');
                timeDiv.className = 'message-time';
                timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                
                streamingMessage.appendChild(contentDiv);
                streamingMessage.appendChild(timeDiv);
                messagesContainer.appendChild(streamingMessage);
                
                this.messages.push({ role, content: '', timestamp: new Date() });
            }
            
            if (content) {
                this.appendStreamingText(content);
            }
            
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            return;
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        if (role === 'assistant') {
            contentDiv.innerHTML = this.renderMarkdown(content);
        } else {
            contentDiv.textContent = content;
        }
    
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timeDiv);
    
        messagesContainer.appendChild(messageDiv);
        this.messages.push({ role, content, timestamp: new Date() });
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    appendStreamingText(delta) {
        if (!delta) return;
        
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;
        
        const streamingMessage = messagesContainer.querySelector('.message.streaming');
        if (!streamingMessage) return;
        
        const contentDiv = streamingMessage.querySelector('.message-content');
        if (!contentDiv) return;
        
        contentDiv.dataset.rawContent = (contentDiv.dataset.rawContent || '') + delta;
        if (!this.typewriterState.target) {
            this.typewriterState.target = contentDiv;
        }
        
        this.typewriterState.queue.push(...delta.split(''));
        if (!this.typewriterState.running) {
            this.startTypewriter();
        }
    }
    
    showTypingIndicator() {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;
        
        // Don't add if already present
        if (messagesContainer.querySelector('.typing-indicator')) return;
        
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
        
        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    removeTypingIndicator() {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;
        
        const typingIndicator = messagesContainer.querySelector('.typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }
    
    renderMarkdown(text) {
        // Render markdown to HTML
        if (typeof marked !== 'undefined') {
            return marked.parse(text);
        }
        // Fallback: simple markdown rendering
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // Bold **text**
            .replace(/\*(.*?)\*/g, '<em>$1</em>')              // Italic *text*
            .replace(/`(.*?)`/g, '<code>$1</code>')            // Code `text`
            .replace(/\n/g, '<br>');                            // Line breaks
    }
    
    finishStreaming(finalText) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;
        
        const streamingMessage = messagesContainer.querySelector('.message.streaming');
        if (!streamingMessage) return;
        
        const contentDiv = streamingMessage.querySelector('.message-content');
        const rawText = typeof finalText === 'string'
            ? finalText
            : (contentDiv?.dataset.rawContent || contentDiv?.textContent || '');
        
        this.stopTypewriter(rawText);
        
        if (contentDiv) {
            contentDiv.innerHTML = this.renderMarkdown(rawText);
            delete contentDiv.dataset.rawContent;
        }
        
        const timeDiv = streamingMessage.querySelector('.message-time');
        if (timeDiv) {
            timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        streamingMessage.classList.remove('streaming');
        
        const lastMessage = this.messages[this.messages.length - 1];
        if (lastMessage && lastMessage.role === 'assistant') {
            lastMessage.content = rawText;
        }
    }
    
    resetConversation() {
        this.messages = [];
        const messagesContainer = document.getElementById('chat-messages');
        if (messagesContainer) {
            messagesContainer.innerHTML = '';
        }
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            chatInput.value = '';
        }
        this.updateStatus('idle', 'Ready');
        this.stopTypewriter();
    }
    
    updateStatus(status, text) {
        const statusBtn = document.getElementById('status-btn');
        const statusBtnText = document.getElementById('status-btn-text');
        
        // Check if we're in Manual mode
        const uiController = UIController.getInstance();
        const isManualMode = uiController.isManualMode();
        
        // Update status button in bottom controls
        if (statusBtn && statusBtnText) {
            // Remove all status classes
            statusBtn.className = 'control-btn status-btn';
            // Add new status class
            statusBtn.classList.add(`status-${status}`);
            
            // Update text based on status (shortened for circular button)
            let displayText = '';
            
            // In Manual mode: only show "Speak" or "Ready", never "Listen"
            if (isManualMode) {
                switch(status) {
                    case 'processing':
                        displayText = 'Process';
                        break;
                    case 'speaking':
                        displayText = 'Speak';
                        break;
                    case 'listening':
                    case 'idle':
                    default:
                        displayText = 'Ready';
                        break;
                }
            } else {
                // Rhasspy mode: show all states
                switch(status) {
                    case 'listening':
                        displayText = 'Listen';
                        break;
                    case 'processing':
                        displayText = 'Process';
                        break;
                    case 'speaking':
                        displayText = 'Speak';
                        break;
                    case 'idle':
                    default:
                        displayText = 'Ready';
                        break;
                }
            }
            statusBtnText.textContent = displayText;
        }
    }

    startTypewriter() {
        if (this.typewriterState.running || !this.typewriterState.target) return;
        this.typewriterState.running = true;
        this.typewriterState.timer = setInterval(() => {
            if (!this.typewriterState.queue.length || !this.typewriterState.target) {
                this.stopTypewriter();
                return;
            }
            const nextChar = this.typewriterState.queue.shift();
            const target = this.typewriterState.target;
            target.textContent = (target.textContent || '') + nextChar;
        }, this.typewriterState.speed);
    }
    
    stopTypewriter(finalText) {
        if (this.typewriterState.timer) {
            clearInterval(this.typewriterState.timer);
            this.typewriterState.timer = null;
        }
        if (this.typewriterState.target) {
            const target = this.typewriterState.target;
            const raw = typeof finalText === 'string'
                ? finalText
                : (target.dataset.rawContent || target.textContent || '');
            if (typeof raw === 'string') {
                target.textContent = raw;
            }
        }
        this.typewriterState.queue = [];
        this.typewriterState.target = null;
        this.typewriterState.running = false;
    }
}

