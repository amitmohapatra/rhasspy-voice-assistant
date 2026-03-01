'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { Send, Plus, Bot, User, Loader2, Paperclip, Mic, StopCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { api } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface APIModel {
  id: string;
  model_id: string;
  name: string;
  display_name: string;
  provider?: { name: string; display_name: string };
  provider_name?: string;
  category: string;
  status: string;
  short_description?: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState('');
  const [availableModels, setAvailableModels] = useState<APIModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [conversations, setConversations] = useState<{ id: string; title: string }[]>([
    { id: '1', title: 'New conversation' },
  ]);
  const [activeConversation, setActiveConversation] = useState('1');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Fetch models from API on mount
  useEffect(() => {
    async function loadModels() {
      setModelsLoading(true);
      try {
        const modelsRes = await api.listModels({ status: 'active', limit: 500 });
        // Filter to chat-capable models (not embeddings, STT, TTS)
        const chatModels = (modelsRes.models || [] as APIModel[]).filter(
          m => !['embedding', 'audio_stt', 'audio_tts', 'reranking'].includes(m.category)
        );
        setAvailableModels(chatModels);
        // Default to first model or a well-known default
        if (chatModels.length > 0) {
          const defaultModel = chatModels.find(m => m.model_id === 'gpt-4o') || chatModels[0];
          setSelectedModel(defaultModel.model_id);
        }
      } catch (err) {
        console.error('Failed to load models:', err);
      } finally {
        setModelsLoading(false);
      }
    }
    loadModels();
  }, []);

  // Group models by provider for the dropdown
  const groupedModels = useMemo(() => {
    const groups: Record<string, APIModel[]> = {};
    for (const model of availableModels) {
      const provider = model.provider?.display_name || model.provider_name || 'Other';
      if (!groups[provider]) groups[provider] = [];
      groups[provider].push(model);
    }
    return groups;
  }, [availableModels]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // Simulate API response
    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `This is a simulated response from ${selectedModel}. In a real implementation, this would call the backend API to generate a response using the selected model.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
    }, 1500);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const startNewConversation = () => {
    const newId = Date.now().toString();
    setConversations((prev) => [{ id: newId, title: 'New conversation' }, ...prev]);
    setActiveConversation(newId);
    setMessages([]);
  };

  return (
    <div className="flex h-screen">
      {/* Conversation History Sidebar */}
      <div className="w-64 border-r bg-muted/30 flex flex-col hidden lg:flex">
        <div className="p-3 border-b">
          <Button onClick={startNewConversation} className="w-full" size="sm">
            <Plus className="w-4 h-4 mr-2" />
            New Chat
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.map((conv) => (
            <button
              key={conv.id}
              onClick={() => setActiveConversation(conv.id)}
              className={cn(
                'w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors',
                activeConversation === conv.id
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-muted text-muted-foreground hover:text-foreground'
              )}
            >
              {conv.title}
            </button>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="h-14 border-b flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-3">
            <Select value={selectedModel} onValueChange={setSelectedModel}>
              <SelectTrigger className="w-[240px]">
                <SelectValue placeholder={modelsLoading ? "Loading models..." : "Select model"} />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(groupedModels).map(([provider, models]) => (
                  <div key={provider}>
                    <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">{provider}</div>
                    {models.map((model) => (
                      <SelectItem key={model.model_id} value={model.model_id}>
                        <div className="flex flex-col">
                          <span>{model.display_name}</span>
                          <span className="text-xs text-muted-foreground">{model.short_description || model.category}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </div>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" size="sm" className="lg:hidden" onClick={startNewConversation}>
            <Plus className="w-4 h-4" />
          </Button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
                <Bot className="w-8 h-8 text-primary" />
              </div>
              <h2 className="text-2xl font-semibold mb-2">How can I help you today?</h2>
              <p className="text-muted-foreground max-w-md">
                Start a conversation by typing a message below. I can help with coding, analysis, writing, and more.
              </p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto py-4 px-4 space-y-6">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    'flex gap-4',
                    message.role === 'user' && 'flex-row-reverse'
                  )}
                >
                  <div
                    className={cn(
                      'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
                      message.role === 'user' ? 'bg-primary' : 'bg-muted'
                    )}
                  >
                    {message.role === 'user' ? (
                      <User className="w-4 h-4 text-primary-foreground" />
                    ) : (
                      <Bot className="w-4 h-4" />
                    )}
                  </div>
                  <div
                    className={cn(
                      'flex-1 space-y-2 min-w-0',
                      message.role === 'user' && 'text-right'
                    )}
                  >
                    <div
                      className={cn(
                        'inline-block px-4 py-2 rounded-2xl max-w-full',
                        message.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      )}
                    >
                      <p className="text-sm whitespace-pre-wrap break-words">
                        {message.content}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">Thinking...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t p-4 shrink-0">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="relative flex items-end gap-2">
              <div className="flex-1 relative">
                <Textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Message AI assistant..."
                  className="resize-none pr-24 min-h-[52px] max-h-[200px]"
                  rows={1}
                />
                <div className="absolute right-2 bottom-2 flex items-center gap-1">
                  <Button type="button" variant="ghost" size="icon" className="h-8 w-8">
                    <Paperclip className="w-4 h-4" />
                  </Button>
                  <Button type="button" variant="ghost" size="icon" className="h-8 w-8">
                    <Mic className="w-4 h-4" />
                  </Button>
                </div>
              </div>
              <Button
                type="submit"
                size="icon"
                disabled={!input.trim() || isLoading}
                className="h-[52px] w-[52px] shrink-0"
              >
                <Send className="w-5 h-5" />
              </Button>
            </div>
            <p className="text-xs text-center text-muted-foreground mt-2">
              AI can make mistakes. Consider checking important information.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
