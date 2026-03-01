'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import {
  Bot,
  Plus,
  MessageSquare,
  Settings,
  LogOut,
  User2,
  Video,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ChatInterface } from '@/components/chat/chat-interface';
import { api, type Assistant, type Conversation } from '@/lib/api';
import { cn } from '@/lib/utils';

// Dynamically import AvatarChat to avoid SSR issues with Three.js
const AvatarChat = dynamic(
  () => import('@/components/avatar/avatar-chat').then((mod) => mod.AvatarChat),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    ),
  }
);

type ChatMode = 'text' | 'avatar';

function ChatPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const assistantIdParam = searchParams.get('assistant');
  const modeParam = searchParams.get('mode') as ChatMode | null;

  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [selectedAssistant, setSelectedAssistant] = useState<Assistant | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState(true);
  const [chatMode, setChatMode] = useState<ChatMode>(modeParam || 'text');

  useEffect(() => {
    loadAssistants();
  }, []);

  useEffect(() => {
    if (assistantIdParam && assistants.length > 0) {
      const assistant = assistants.find((a) => a.id === assistantIdParam);
      if (assistant) {
        setSelectedAssistant(assistant);
      }
    }
  }, [assistantIdParam, assistants]);

  useEffect(() => {
    if (selectedAssistant) {
      loadConversations(selectedAssistant.id);
    }
  }, [selectedAssistant]);

  const loadAssistants = async () => {
    const token = api.getToken();
    if (!token) {
      setAssistants([]);
      setIsLoading(false);
      return;
    }

    try {
      const data = await api.listAssistants();
      const items = data.items || [];
      setAssistants(items);
      if (items.length > 0 && !assistantIdParam) {
        setSelectedAssistant(items[0]);
      }
    } catch (error) {
      console.error('Failed to load assistants:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadConversations = async (assistantId: string) => {
    try {
      const data = await api.listConversations(assistantId);
      setConversations(data);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const handleNewConversation = () => {
    setSelectedConversation(undefined);
  };

  const handleConversationChange = (conversationId: string) => {
    setSelectedConversation(conversationId);
    if (selectedAssistant) {
      loadConversations(selectedAssistant.id);
    }
  };

  const handleLogout = () => {
    api.logout();
    router.push('/auth/login');
  };

  const toggleChatMode = () => {
    setChatMode((prev) => (prev === 'text' ? 'avatar' : 'text'));
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-screen flex">
      {/* Sidebar - Hidden in avatar mode on mobile */}
      <div
        className={cn(
          'w-64 border-r bg-muted/30 flex flex-col shrink-0',
          chatMode === 'avatar' && 'hidden md:flex'
        )}
      >
        {/* Header */}
        <div className="p-4 border-b">
          <Link href="/dashboard" className="flex items-center gap-2 hover:opacity-80">
            <Bot className="h-6 w-6 text-primary" />
            <span className="font-semibold">Rhasspy</span>
          </Link>
        </div>

        {/* Chat Mode Toggle */}
        <div className="p-4 border-b">
          <div className="flex rounded-lg border bg-background p-1">
            <button
              onClick={() => setChatMode('text')}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                chatMode === 'text'
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-muted'
              )}
            >
              <MessageSquare className="w-4 h-4" />
              Text
            </button>
            <button
              onClick={() => setChatMode('avatar')}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                chatMode === 'avatar'
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-muted'
              )}
            >
              <User2 className="w-4 h-4" />
              Avatar
            </button>
          </div>
        </div>

        {/* Assistant Selector */}
        <div className="p-4 border-b">
          <label className="text-xs text-muted-foreground mb-2 block">Assistant</label>
          <select
            value={selectedAssistant?.id || ''}
            onChange={(e) => {
              const assistant = assistants.find((a) => a.id === e.target.value);
              setSelectedAssistant(assistant || null);
              setSelectedConversation(undefined);
            }}
            className="w-full px-3 py-2 rounded-md border bg-background text-sm"
          >
            {assistants.length === 0 && (
              <option value="">No assistants</option>
            )}
            {assistants.map((assistant) => (
              <option key={assistant.id} value={assistant.id}>
                {assistant.name}
              </option>
            ))}
          </select>
        </div>

        {/* New Conversation Button - Only for text mode */}
        {chatMode === 'text' && (
          <div className="p-4">
            <Button onClick={handleNewConversation} className="w-full" variant="outline">
              <Plus className="w-4 h-4 mr-2" />
              New Conversation
            </Button>
          </div>
        )}

        {/* Conversations List - Only for text mode */}
        {chatMode === 'text' && (
          <div className="flex-1 overflow-y-auto p-2">
            {conversations.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No conversations yet
              </p>
            ) : (
              conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  onClick={() => setSelectedConversation(conversation.id)}
                  className={cn(
                    'w-full text-left px-3 py-2 rounded-md text-sm flex items-center gap-2 hover:bg-muted transition-colors',
                    selectedConversation === conversation.id && 'bg-muted'
                  )}
                >
                  <MessageSquare className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">
                    {conversation.title || 'New Conversation'}
                  </span>
                </button>
              ))
            )}
          </div>
        )}

        {/* Avatar mode info */}
        {chatMode === 'avatar' && (
          <div className="flex-1 p-4">
            <div className="bg-primary/5 rounded-lg p-4 text-sm text-muted-foreground">
              <Video className="w-6 h-6 mb-2 text-primary" />
              <p className="font-medium text-foreground mb-1">Avatar Mode</p>
              <p>
                Talk to your AI assistant with a 3D animated avatar. The avatar will
                speak responses aloud.
              </p>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="p-4 border-t space-y-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start"
            onClick={() => router.push('/dashboard')}
          >
            <Settings className="w-4 h-4 mr-2" />
            Dashboard
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start text-destructive hover:text-destructive"
            onClick={handleLogout}
          >
            <LogOut className="w-4 h-4 mr-2" />
            Logout
          </Button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {selectedAssistant ? (
          <>
            {/* Chat Header */}
            <div className="h-14 border-b flex items-center justify-between px-4 shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                  {chatMode === 'avatar' ? (
                    <User2 className="w-5 h-5 text-primary" />
                  ) : (
                    <Bot className="w-5 h-5 text-primary" />
                  )}
                </div>
                <div>
                  <h2 className="font-medium">{selectedAssistant.name}</h2>
                  <p className="text-xs text-muted-foreground">
                    {selectedAssistant.model} ({selectedAssistant.provider})
                  </p>
                </div>
              </div>

              {/* Mode toggle for mobile */}
              <Button
                variant="outline"
                size="sm"
                onClick={toggleChatMode}
                className="md:hidden"
              >
                {chatMode === 'text' ? (
                  <>
                    <User2 className="w-4 h-4 mr-2" />
                    Avatar
                  </>
                ) : (
                  <>
                    <MessageSquare className="w-4 h-4 mr-2" />
                    Text
                  </>
                )}
              </Button>
            </div>

            {/* Chat Interface */}
            <div className="flex-1 min-h-0">
              {chatMode === 'text' ? (
                <ChatInterface
                  assistantId={selectedAssistant.id}
                  conversationId={selectedConversation}
                  onConversationChange={handleConversationChange}
                />
              ) : (
                <AvatarChat
                  assistantId={selectedAssistant.id}
                  assistantName={selectedAssistant.name}
                />
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <Bot className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No assistants available</p>
              <Button
                variant="link"
                className="mt-2"
                onClick={() => router.push('/assistants')}
              >
                Create an assistant
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin" /></div>}>
      <ChatPageInner />
    </Suspense>
  );
}
