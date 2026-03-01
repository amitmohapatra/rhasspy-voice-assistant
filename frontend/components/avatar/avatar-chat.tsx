'use client';

import { useState, useRef, useEffect, useCallback, Suspense } from 'react';
import dynamic from 'next/dynamic';
import { Send, Loader2, Mic, MicOff, Volume2, VolumeX, Settings2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { api, type ChatDisplayMessage, type VoicePreset } from '@/lib/api';
import { useVoiceRecorder, blobToBase64 } from '@/hooks/use-voice-recorder';

// Dynamically import Avatar3D to avoid SSR issues with Three.js
const Avatar3D = dynamic(
  () => import('./avatar-3d').then((mod) => mod.Avatar3D),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex items-center justify-center bg-muted">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    ),
  }
);

interface AvatarChatProps {
  assistantId: string;
  assistantName?: string;
}

export function AvatarChat({ assistantId, assistantName }: AvatarChatProps) {
  const [messages, setMessages] = useState<ChatDisplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [previousResponseId, setPreviousResponseId] = useState<string | undefined>();
  const [emotion, setEmotion] = useState<'neutral' | 'happy' | 'thinking'>('neutral');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recognitionRef = useRef<any>(null);

  // Voice preset state
  const [ttsPresets, setTtsPresets] = useState<VoicePreset[]>([]);
  const [sttPresets, setSttPresets] = useState<VoicePreset[]>([]);
  const [selectedTtsId, setSelectedTtsId] = useState<string>('');
  const [selectedSttId, setSelectedSttId] = useState<string>('');
  const [showPresetBar, setShowPresetBar] = useState(false);

  const voiceRecorder = useVoiceRecorder();

  // Load presets
  useEffect(() => {
    const loadPresets = async () => {
      try {
        const [ttsData, sttData] = await Promise.all([
          api.listVoicePresets('tts'),
          api.listVoicePresets('stt'),
        ]);
        setTtsPresets(ttsData.items);
        setSttPresets(sttData.items);

        // Select default presets
        const defaultTts = ttsData.items.find((p) => p.is_default);
        if (defaultTts) setSelectedTtsId(defaultTts.id);
        else if (ttsData.items.length > 0) setSelectedTtsId(ttsData.items[0].id);

        const defaultStt = sttData.items.find((p) => p.is_default);
        if (defaultStt) setSelectedSttId(defaultStt.id);
        else if (sttData.items.length > 0) setSelectedSttId(sttData.items[0].id);
      } catch {
        // Presets are optional, continue without them
      }
    };
    loadPresets();
  }, []);

  // Get selected presets
  const selectedTts = ttsPresets.find((p) => p.id === selectedTtsId);
  const selectedStt = sttPresets.find((p) => p.id === selectedSttId);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // TTS: speak text using selected preset
  const speak = useCallback(
    async (text: string) => {
      if (isMuted) return;

      const config = selectedTts?.config || {};
      const source = (config.source as string) || 'browser';

      if (source === 'browser') {
        if (!window.speechSynthesis) return;
        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = (config.speed as number) || 1.0;
        utterance.pitch = (config.pitch as number) || 1.0;

        // Set voice if specified
        const voiceUri = config.voice_uri as string;
        if (voiceUri) {
          const voices = window.speechSynthesis.getVoices();
          const voice = voices.find((v) => v.voiceURI === voiceUri);
          if (voice) utterance.voice = voice;
        }

        utterance.onstart = () => {
          setIsSpeaking(true);
          setEmotion('happy');
        };
        utterance.onend = () => {
          setIsSpeaking(false);
          setEmotion('neutral');
        };
        utterance.onerror = () => {
          setIsSpeaking(false);
          setEmotion('neutral');
        };

        window.speechSynthesis.speak(utterance);
      } else {
        // Vendor TTS — call backend
        try {
          setIsSpeaking(true);
          setEmotion('happy');

          const result = await api.synthesizeSpeech(text, {
            voice_id: config.voice_id as string,
            provider: source,
            speaking_rate: (config.speed as number) || 1.0,
          });

          const audioBytes = Uint8Array.from(atob(result.audio), (c) =>
            c.charCodeAt(0)
          );
          const blob = new Blob([audioBytes], {
            type: `audio/${result.format}`,
          });
          const url = URL.createObjectURL(blob);

          // Stop any previous audio
          if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current = null;
          }

          const audio = new Audio(url);
          audioRef.current = audio;

          audio.onended = () => {
            setIsSpeaking(false);
            setEmotion('neutral');
            URL.revokeObjectURL(url);
            audioRef.current = null;
          };
          audio.onerror = () => {
            setIsSpeaking(false);
            setEmotion('neutral');
            URL.revokeObjectURL(url);
            audioRef.current = null;
          };

          await audio.play();
        } catch (err) {
          console.error('TTS error:', err);
          setIsSpeaking(false);
          setEmotion('neutral');
        }
      }
    },
    [isMuted, selectedTts]
  );

  // Submit a message (extracted for reuse by STT)
  const submitMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      const userMessage: ChatDisplayMessage = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: text.trim(),
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setInput('');
      setIsLoading(true);
      setEmotion('thinking');

      try {
        const response = await api.createResponseStream({
          assistant_id: assistantId,
          input: [
            { type: 'message', role: 'user', content: userMessage.content },
          ],
          previous_response_id: previousResponseId,
          conversation_id: conversationId,
          stream: true,
        });

        if (!response.ok) {
          throw new Error('Failed to send message');
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let assistantMessage: ChatDisplayMessage = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: '',
          created_at: new Date().toISOString(),
          isStreaming: true,
        };

        setMessages((prev) => [...prev, assistantMessage]);

        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event = JSON.parse(line.slice(6));

                switch (event.type) {
                  case 'response.created': {
                    if (event.response?.conversation_id) {
                      setConversationId(event.response.conversation_id);
                    }
                    break;
                  }

                  case 'response.content.delta': {
                    assistantMessage = {
                      ...assistantMessage,
                      content:
                        assistantMessage.content + (event.delta || ''),
                    };
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMessage.id
                          ? assistantMessage
                          : m
                      )
                    );
                    break;
                  }

                  case 'response.content.done': {
                    if (event.text) {
                      assistantMessage = {
                        ...assistantMessage,
                        content: event.text,
                      };
                      setMessages((prev) =>
                        prev.map((m) =>
                          m.id === assistantMessage.id
                            ? assistantMessage
                            : m
                        )
                      );
                    }
                    break;
                  }

                  case 'response.completed': {
                    assistantMessage = {
                      ...assistantMessage,
                      isStreaming: false,
                    };
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMessage.id
                          ? assistantMessage
                          : m
                      )
                    );
                    if (event.response?.id) {
                      setPreviousResponseId(event.response.id);
                    }
                    const responseEmotion = event.response?.emotion;
                    if (
                      responseEmotion === 'happy' ||
                      responseEmotion === 'excited'
                    ) {
                      setEmotion('happy');
                    }
                    // Speak the response
                    speak(assistantMessage.content);
                    break;
                  }

                  case 'response.failed': {
                    throw new Error(
                      event.error?.message || 'Response failed'
                    );
                  }
                }
              } catch {
                // Skip invalid JSON
              }
            }
          }
        }
      } catch (error) {
        console.error('Chat error:', error);
        setEmotion('neutral');
      } finally {
        setIsLoading(false);
        if (!isSpeaking) {
          setEmotion('neutral');
        }
        inputRef.current?.focus();
      }
    },
    [
      assistantId,
      conversationId,
      previousResponseId,
      isLoading,
      isSpeaking,
      speak,
    ]
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitMessage(input);
  };

  const toggleMute = () => {
    if (!isMuted) {
      window.speechSynthesis?.cancel();
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      setIsSpeaking(false);
    }
    setIsMuted(!isMuted);
  };

  // STT: toggle listening using selected preset
  const toggleListening = useCallback(async () => {
    if (isListening) {
      // Stop
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        recognitionRef.current = null;
      }
      if (voiceRecorder.isRecording) {
        const blob = await voiceRecorder.stopRecording();
        if (blob) {
          const config = selectedStt?.config || {};
          const base64 = await blobToBase64(blob);
          try {
            const result = await api.transcribeAudio(base64, {
              format: 'webm',
              language: (config.language as string) || 'en-US',
            });
            if (result.text.trim()) {
              submitMessage(result.text);
            }
          } catch (err) {
            console.error('Transcription failed:', err);
          }
        }
      }
      setIsListening(false);
      return;
    }

    // Start listening
    const config = selectedStt?.config || {};
    const source = (config.source as string) || 'browser';

    setIsListening(true);

    if (source === 'browser') {
      const SpeechRecognitionAPI =
        (window as unknown as Record<string, unknown>).SpeechRecognition ||
        (window as unknown as Record<string, unknown>).webkitSpeechRecognition;

      if (!SpeechRecognitionAPI) {
        console.error('Browser speech recognition not supported');
        setIsListening(false);
        return;
      }

      const recognition = new (SpeechRecognitionAPI as any)();
      recognition.lang = (config.language as string) || 'en-US';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognitionRef.current = recognition;

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        if (transcript.trim()) {
          submitMessage(transcript);
        }
        setIsListening(false);
        recognitionRef.current = null;
      };

      recognition.onerror = () => {
        setIsListening(false);
        recognitionRef.current = null;
      };

      recognition.onend = () => {
        setIsListening(false);
        recognitionRef.current = null;
      };

      recognition.start();
    } else {
      // Vendor STT — record audio then send to backend
      try {
        await voiceRecorder.startRecording();
      } catch (err) {
        console.error('Failed to start recording:', err);
        setIsListening(false);
      }
    }
  }, [isListening, selectedStt, voiceRecorder, submitMessage]);

  const hasPresets = ttsPresets.length > 0 || sttPresets.length > 0;

  return (
    <div className="h-full flex flex-col">
      {/* Avatar Section */}
      <div className="h-1/2 min-h-[300px] bg-gradient-to-b from-primary/5 to-background relative">
        <Suspense
          fallback={
            <div className="w-full h-full flex items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin" />
            </div>
          }
        >
          <Avatar3D isSpeaking={isSpeaking} emotion={emotion} />
        </Suspense>

        {/* Avatar Controls */}
        <div className="absolute bottom-4 right-4 flex gap-2">
          {hasPresets && (
            <Button
              size="icon"
              variant="secondary"
              onClick={() => setShowPresetBar(!showPresetBar)}
              className="rounded-full"
              title="Voice presets"
            >
              <Settings2 className="h-4 w-4" />
            </Button>
          )}
          <Button
            size="icon"
            variant="secondary"
            onClick={toggleMute}
            className="rounded-full"
          >
            {isMuted ? (
              <VolumeX className="h-4 w-4" />
            ) : (
              <Volume2 className="h-4 w-4" />
            )}
          </Button>
          <Button
            size="icon"
            variant={isListening ? 'default' : 'secondary'}
            onClick={toggleListening}
            className={cn('rounded-full', isListening && 'animate-pulse')}
          >
            {isListening ? (
              <Mic className="h-4 w-4" />
            ) : (
              <MicOff className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* Assistant Name */}
        <div className="absolute top-4 left-4">
          <h2 className="text-lg font-semibold">
            {assistantName || 'AI Assistant'}
          </h2>
          <p className="text-sm text-muted-foreground">
            {isSpeaking
              ? 'Speaking...'
              : isListening
                ? 'Listening...'
                : isLoading
                  ? 'Thinking...'
                  : 'Ready'}
          </p>
        </div>

        {/* Preset Selection Bar */}
        {showPresetBar && hasPresets && (
          <div className="absolute bottom-16 right-4 bg-popover border rounded-lg shadow-lg p-3 space-y-2 min-w-[220px]">
            {ttsPresets.length > 0 && (
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  TTS Preset
                </label>
                <Select
                  value={selectedTtsId}
                  onValueChange={setSelectedTtsId}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue placeholder="Select TTS" />
                  </SelectTrigger>
                  <SelectContent>
                    {ttsPresets.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {sttPresets.length > 0 && (
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  STT Preset
                </label>
                <Select
                  value={selectedSttId}
                  onValueChange={setSelectedSttId}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue placeholder="Select STT" />
                  </SelectTrigger>
                  <SelectContent>
                    {sttPresets.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chat Section */}
      <div className="flex-1 flex flex-col border-t">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Say hello to start a conversation...
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  'max-w-[85%] rounded-lg px-4 py-2 message-appear',
                  message.role === 'user'
                    ? 'ml-auto bg-primary text-primary-foreground'
                    : 'bg-muted'
                )}
              >
                {message.role === 'user' ? (
                  <p className="whitespace-pre-wrap text-sm">
                    {message.content}
                  </p>
                ) : (
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                    {message.isStreaming && (
                      <span className="inline-block w-2 h-4 bg-current animate-pulse ml-1" />
                    )}
                  </div>
                )}
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t p-4">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type or speak your message..."
              disabled={isLoading}
              className="flex-1"
            />
            <Button type="submit" disabled={isLoading || !input.trim()}>
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
