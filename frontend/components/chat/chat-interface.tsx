'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, User, Bot, Mic, MicOff, Square, X, Wrench } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { api, type ChatDisplayMessage, type ResponseSchema } from '@/lib/api';
import { useVoiceRecorder, formatDuration, blobToBase64 } from '@/hooks/use-voice-recorder';

interface ChatInterfaceProps {
  assistantId: string;
  conversationId?: string;
  onConversationChange?: (conversationId: string) => void;
}

export function ChatInterface({
  assistantId,
  conversationId: initialConversationId,
  onConversationChange,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatDisplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState(initialConversationId);
  const [previousResponseId, setPreviousResponseId] = useState<string | undefined>();
  const [isTranscribing, setIsTranscribing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Voice recorder hook
  const {
    state: recorderState,
    isRecording,
    startRecording,
    stopRecording,
    cancelRecording,
    audioLevel,
    duration,
    error: recorderError,
  } = useVoiceRecorder({
    sampleRate: 16000,
    channelCount: 1,
  });

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (initialConversationId && initialConversationId !== conversationId) {
      setConversationId(initialConversationId);
      setPreviousResponseId(undefined);
      loadConversation(initialConversationId);
    }
  }, [initialConversationId]);

  /** Load conversation history by fetching responses and flattening items. */
  const loadConversation = async (convId: string) => {
    try {
      const responses = await api.getConversationResponses(convId);
      const flatMessages = flattenResponses(responses);
      setMessages(flatMessages);

      // Set previousResponseId to the last response
      if (responses.length > 0) {
        setPreviousResponseId(responses[responses.length - 1].id);
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  /** Flatten responses into display messages. */
  function flattenResponses(responses: ResponseSchema[]): ChatDisplayMessage[] {
    const msgs: ChatDisplayMessage[] = [];
    for (const resp of responses) {
      for (const item of resp.output) {
        if (item.item_type === 'message' && item.content) {
          msgs.push({
            id: item.id,
            role: (item.role || 'assistant') as ChatDisplayMessage['role'],
            content: item.content,
            created_at: item.created_at,
          });
        }
        // Tool calls can be shown inline if desired
      }
    }
    return msgs;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const text = input.trim();
    setInput('');
    await sendMessage(text);
  };

  const sendMessage = async (text: string) => {
    const userMessage: ChatDisplayMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await api.createResponseStream({
        assistant_id: assistantId,
        input: [{ type: 'message', role: 'user', content: text }],
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
        // Keep the last incomplete line in the buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6));

              switch (event.type) {
                case 'response.created': {
                  const newConversationId = event.response?.conversation_id;
                  if (newConversationId) {
                    setConversationId(newConversationId);
                    onConversationChange?.(newConversationId);
                  }
                  break;
                }

                case 'response.content.delta': {
                  assistantMessage = {
                    ...assistantMessage,
                    content: assistantMessage.content + (event.delta || ''),
                  };
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantMessage.id ? assistantMessage : m
                    )
                  );
                  break;
                }

                case 'response.content.done': {
                  // Final content - update to ensure consistency
                  if (event.text) {
                    assistantMessage = {
                      ...assistantMessage,
                      content: event.text,
                    };
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMessage.id ? assistantMessage : m
                      )
                    );
                  }
                  break;
                }

                case 'response.output_item.added': {
                  // Could display tool execution status inline
                  if (event.item?.type === 'function_call') {
                    // Show tool call indicator
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
                      m.id === assistantMessage.id ? assistantMessage : m
                    )
                  );
                  // Chain for next turn
                  if (event.response?.id) {
                    setPreviousResponseId(event.response.id);
                  }
                  break;
                }

                case 'response.failed': {
                  throw new Error(event.error?.message || 'Response failed');
                }
              }
            } catch (parseError) {
              if (parseError instanceof Error && parseError.message !== 'Response failed') {
                // Skip invalid JSON
              } else {
                throw parseError;
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage: ChatDisplayMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Failed to get response'}`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  // Handle voice recording
  const handleRecordingToggle = async () => {
    if (isRecording) {
      const audioBlob = await stopRecording();
      if (audioBlob) {
        await handleVoiceSubmit(audioBlob);
      }
    } else {
      await startRecording();
    }
  };

  const handleVoiceSubmit = async (audioBlob: Blob) => {
    setIsTranscribing(true);
    try {
      const base64Audio = await blobToBase64(audioBlob);
      const format = audioBlob.type.includes('webm') ? 'webm' : 'wav';

      const data = await api.transcribeAudio(base64Audio, { format });
      const transcribedText = data.text;

      if (transcribedText && transcribedText.trim()) {
        setInput('');
        await sendMessage(transcribedText.trim());
      }
    } catch (error) {
      console.error('Voice transcription error:', error);
      const errorMessage: ChatDisplayMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: 'Failed to transcribe voice message. Please try again or type your message.',
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsTranscribing(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Start a conversation...</p>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                'flex gap-3 message-appear',
                message.role === 'user' ? 'justify-end' : 'justify-start'
              )}
            >
              {message.role !== 'user' && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-primary" />
                </div>
              )}
              <div
                className={cn(
                  'max-w-[80%] rounded-lg px-4 py-2',
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                )}
              >
                {message.role === 'user' ? (
                  <p className="whitespace-pre-wrap">{message.content}</p>
                ) : (
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {message.content}
                    </ReactMarkdown>
                    {message.isStreaming && (
                      <span className="inline-block w-2 h-4 bg-current animate-pulse ml-1" />
                    )}
                  </div>
                )}
              </div>
              {message.role === 'user' && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                  <User className="w-4 h-4 text-primary-foreground" />
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t p-4">
        {/* Recording indicator */}
        {isRecording && (
          <div className="mb-3 flex items-center gap-3 p-3 bg-red-50 dark:bg-red-950/30 rounded-lg border border-red-200 dark:border-red-900">
            <div className="relative">
              <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
              <div
                className="absolute inset-0 w-3 h-3 bg-red-500 rounded-full animate-ping"
                style={{ animationDuration: '1.5s' }}
              />
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-red-700 dark:text-red-400">
                  Recording...
                </span>
                <span className="text-sm text-red-600 dark:text-red-400 font-mono">
                  {formatDuration(duration)}
                </span>
              </div>
              {/* Audio level visualizer */}
              <div className="mt-2 h-1 bg-red-200 dark:bg-red-900 rounded-full overflow-hidden">
                <div
                  className="h-full bg-red-500 transition-all duration-75"
                  style={{ width: `${audioLevel * 100}%` }}
                />
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={cancelRecording}
              className="text-red-600 hover:text-red-700 hover:bg-red-100 dark:hover:bg-red-900/50"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        )}

        {/* Transcribing indicator */}
        {isTranscribing && (
          <div className="mb-3 flex items-center gap-3 p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-900">
            <Loader2 className="w-4 h-4 animate-spin text-blue-600 dark:text-blue-400" />
            <span className="text-sm text-blue-700 dark:text-blue-400">
              Transcribing your voice message...
            </span>
          </div>
        )}

        {/* Error message */}
        {recorderError && (
          <div className="mb-3 p-3 bg-red-50 dark:bg-red-950/30 rounded-lg border border-red-200 dark:border-red-900">
            <p className="text-sm text-red-700 dark:text-red-400">{recorderError}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isRecording ? "Recording..." : "Type your message or record audio..."}
            disabled={isLoading || isRecording || isTranscribing}
            className="flex-1"
          />

          {/* Voice record button */}
          <Button
            type="button"
            variant={isRecording ? "destructive" : "outline"}
            size="icon"
            onClick={handleRecordingToggle}
            disabled={isLoading || isTranscribing}
            title={isRecording ? "Stop recording" : "Record voice message"}
          >
            {isRecording ? (
              <Square className="w-4 h-4" />
            ) : (
              <Mic className="w-4 h-4" />
            )}
          </Button>

          {/* Send button */}
          <Button
            type="submit"
            disabled={isLoading || isRecording || isTranscribing || !input.trim()}
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </form>

        {/* Keyboard shortcut hints */}
        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
          <span>Press Enter to send</span>
          <span>Hold Space to record (coming soon)</span>
        </div>
      </div>
    </div>
  );
}
