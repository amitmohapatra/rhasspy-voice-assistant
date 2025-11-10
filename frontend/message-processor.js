/**
 * Message Processor - Shared logic for both Rhasspy and Manual modes
 * Enterprise-grade, maintainable, no duplicate code
 */

class MessageProcessor {
    static instance = null;
    
    constructor() {
        if (MessageProcessor.instance) {
            return MessageProcessor.instance;
        }
        MessageProcessor.instance = this;
        
        this.apiUrl = 'http://localhost:5000/api';
        console.log('📨 MessageProcessor initialized');
    }
    
    static getInstance() {
        if (!MessageProcessor.instance) {
            MessageProcessor.instance = new MessageProcessor();
        }
        return MessageProcessor.instance;
    }
    
    /**
     * Process audio and send as message using /api/audio endpoint
     * Used by Manual mode - sends audio directly to backend
     * @param {Blob} audioBlob - Audio to process
     * @param {Object} options - Additional options
     * @returns {Promise<void>}
     */
    async processAudioMessage(audioBlob, options = {}) {
        console.log('🎤 [PROCESSOR] Processing audio message via /api/audio');
        
        const {
            onStart = null,
            onComplete = null,
            onError = null
        } = options;
        
        try {
            // Call onStart callback
            if (onStart) onStart();
            
            // Include any existing assistant/thread IDs (backend will ensure or create as needed)
            const assistantManager = AssistantManager.getInstance();
            const assistantId = assistantManager.getCurrentAssistant() || '';
            const threadId = assistantManager.getCurrentThread() || '';
            console.log('🧾 [PROCESSOR] Sending context IDs:', { assistantId, threadId });
            
            // Create FormData with audio file
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            if (threadId) {
                formData.append('thread_id', threadId);
            }
            if (assistantId) {
                formData.append('assistant_id', assistantId);
            }
            
            console.log('📤 [PROCESSOR] Sending audio to /api/audio', {
                audioSize: audioBlob.size,
                threadId,
                assistantId,
                url: `${this.apiUrl}/audio`
            });
            
            // Send to /api/audio endpoint (SSE stream)
            const response = await fetch(`${this.apiUrl}/audio`, {
                method: 'POST',
                body: formData
            });
            
            console.log('📥 [PROCESSOR] Response received', {
                status: response.status,
                statusText: response.statusText,
                ok: response.ok,
                headers: Object.fromEntries(response.headers.entries())
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ [PROCESSOR] Error response:', errorText);
                throw new Error(`Audio processing failed: ${response.status} - ${errorText}`);
            }
            
            // Get chat manager to handle the SSE stream
            const chatManager = ChatManager.getInstance();
            if (!chatManager) {
                throw new Error('ChatManager not available');
            }
            
            // Process SSE stream (similar to chat.js sendMessage)
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let fullText = '';
            
            const audioManager = AudioManager.getInstance();
            let currentThreadId = threadId || '';
            let lastAssistantId = assistantId || '';
            const audioState = {
                queue: [],
                isPlaying: false
            };
            
            const playNextAudioChunk = async () => {
                if (audioState.isPlaying || audioState.queue.length === 0) return;
                
                audioState.isPlaying = true;
                const audioData = audioState.queue.shift();
                
                try {
                    await audioManager.playResponseAudio(audioData);
                } catch (error) {
                    console.error('❌ Error playing audio:', error);
                }
                
                audioState.isPlaying = false;
                if (audioState.queue.length > 0) {
                    playNextAudioChunk();
                }
            };
            
            console.log('🔄 [PROCESSOR] Starting SSE stream processing...');
            let eventCount = 0;
            let assistantStreamStarted = false;
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    console.log('🏁 [PROCESSOR] Stream ended', { eventCount });
                    break;
                }
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            eventCount++;
                            console.log(`📦 [PROCESSOR] SSE Event #${eventCount}:`, data.type, data);
                            
                            if (data.type === 'assistant_id') {
                                if (data.assistant_id) {
                                    lastAssistantId = data.assistant_id;
                                    if (assistantManager) {
                                        assistantManager.setCurrentAssistant(data.assistant_id);
                                    }
                                }
                            } else if (data.type === 'thread_id') {
                                if (data.thread_id) {
                                    currentThreadId = data.thread_id;
                                    if (assistantManager) {
                                        assistantManager.setCurrentThread(data.thread_id);
                                    }
                                }
                            } else if (data.type === 'input_text') {
                                // Transcribed text from STT
                                console.log('📝 [PROCESSOR] Transcribed:', data.text);
                                chatManager.addMessage('user', data.text);
                            } else if (data.type === 'text') {
                                // Assistant response text
                                const delta = data.text ?? '';
                                if (!delta) continue;
                                
                                fullText += delta;
                                if (!assistantStreamStarted) {
                                    chatManager.addMessage('assistant', '', true);
                                    assistantStreamStarted = true;
                                }
                                chatManager.appendStreamingText(delta);
                            } else if (data.type === 'audio_chunk') {
                                // Audio chunk for playback
                                console.log('🔊 [PROCESSOR] Audio chunk received, queue length:', audioState.queue.length);
                                audioState.queue.push(data.audio);
                                if (!audioState.isPlaying) {
                                    chatManager.updateStatus('speaking', 'Speak');
                                    playNextAudioChunk();
                                }
                            } else if (data.type === 'done') {
                                // Stream complete
                                console.log('✅ [PROCESSOR] Audio processing complete, total events:', eventCount);
                                
                                // Finalize streaming message
                                if (assistantStreamStarted) {
                                    chatManager.finishStreaming(fullText);
                                } else if (fullText) {
                                    chatManager.addMessage('assistant', fullText);
                                }
                                if (data.thread_id) {
                                    currentThreadId = data.thread_id;
                                    if (assistantManager) {
                                        assistantManager.setCurrentThread(data.thread_id);
                                    }
                                }
                                if (data.assistant_id) {
                                    lastAssistantId = data.assistant_id;
                                    if (assistantManager) {
                                        assistantManager.setCurrentAssistant(data.assistant_id);
                                    }
                                }
                                
                                // Wait for audio to finish
                                const waitForAudio = setInterval(() => {
                                    if (audioState.queue.length === 0 && !audioState.isPlaying) {
                                        clearInterval(waitForAudio);
                                        chatManager.updateStatus('idle', 'Ready');
                                        if (onComplete) onComplete();
                                    }
                                }, 100);
                                
                                setTimeout(() => {
                                    clearInterval(waitForAudio);
                                    chatManager.updateStatus('idle', 'Ready');
                                    if (onComplete) onComplete();
                                }, 30000);
                            } else if (data.type === 'error') {
                                const errorMessage = data.error || 'Audio processing error';
                                if (errorMessage.toLowerCase().includes('no speech detected')) {
                                    console.warn('⚠️ [PROCESSOR] No speech detected, skipping payload');
                                    if (onError) onError(new Error(errorMessage));
                                    continue;
                                }
                                throw new Error(errorMessage);
                            }
                        } catch (parseError) {
                            console.error('❌ [PROCESSOR] Error parsing SSE:', parseError);
                        }
                    }
                }
            }
            if (assistantStreamStarted) {
                chatManager.finishStreaming(fullText);
            }
            
            if (assistantManager) {
                if (lastAssistantId) {
                    assistantManager.setCurrentAssistant(lastAssistantId);
                }
                if (currentThreadId) {
                    assistantManager.setCurrentThread(currentThreadId);
                }
            }
            
        } catch (error) {
            console.error('❌ [PROCESSOR] Error processing audio:', error);
            if (onError) onError(error);
            throw error;
        }
    }
}

// Export for use in other files
if (typeof window !== 'undefined') {
    window.MessageProcessor = MessageProcessor;
}

