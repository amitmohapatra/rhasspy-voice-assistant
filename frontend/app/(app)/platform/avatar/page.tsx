'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import {
  Bot,
  ChevronDown,
  Maximize2,
  Minimize2,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api, type Assistant } from '@/lib/api';
import { cn } from '@/lib/utils';

const AvatarChat = dynamic(
  () => import('@/components/avatar/avatar-chat').then((mod) => mod.AvatarChat),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    ),
  }
);

function AvatarPageInner() {
  const searchParams = useSearchParams();
  const assistantIdParam = searchParams.get('assistant');

  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [selectedAssistant, setSelectedAssistant] = useState<Assistant | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showAssistantMenu, setShowAssistantMenu] = useState(false);

  useEffect(() => {
    loadAssistants();
  }, []);

  useEffect(() => {
    if (assistantIdParam && assistants.length > 0) {
      const assistant = assistants.find((a) => a.id === assistantIdParam);
      if (assistant) setSelectedAssistant(assistant);
    }
  }, [assistantIdParam, assistants]);

  const loadAssistants = async () => {
    const token = api.getToken();
    if (!token) {
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

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col h-full', isFullscreen && 'fixed inset-0 z-50 bg-background')}>
      {/* Toolbar */}
      <div className="h-12 border-b flex items-center justify-between px-4 shrink-0">
        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAssistantMenu(!showAssistantMenu)}
            className="flex items-center gap-2"
          >
            <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center">
              <Bot className="w-3 h-3 text-primary" />
            </div>
            <span className="max-w-[200px] truncate">
              {selectedAssistant?.name || 'Select Assistant'}
            </span>
            <ChevronDown className="w-3.5 h-3.5" />
          </Button>

          {showAssistantMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowAssistantMenu(false)} />
              <div className="absolute top-full left-0 mt-1 w-64 bg-popover border rounded-lg shadow-lg z-50">
                <div className="p-2">
                  <p className="text-xs text-muted-foreground px-2 py-1">Select an assistant</p>
                  {assistants.map((assistant) => (
                    <button
                      key={assistant.id}
                      onClick={() => {
                        setSelectedAssistant(assistant);
                        setShowAssistantMenu(false);
                      }}
                      className={cn(
                        'w-full text-left px-3 py-2 rounded-md text-sm flex items-center gap-3 hover:bg-muted transition-colors',
                        selectedAssistant?.id === assistant.id && 'bg-muted'
                      )}
                    >
                      <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <Bot className="w-4 h-4 text-primary" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium truncate">{assistant.name}</p>
                        <p className="text-xs text-muted-foreground truncate">{assistant.model}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        <Button variant="ghost" size="icon" onClick={toggleFullscreen}>
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </Button>
      </div>

      {/* Avatar Chat Area */}
      <div className="flex-1 min-h-0">
        {selectedAssistant ? (
          <AvatarChat
            assistantId={selectedAssistant.id}
            assistantName={selectedAssistant.name}
          />
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <Bot className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <h3 className="text-lg font-medium mb-2">No Assistant Selected</h3>
              <p className="text-sm mb-4">Select an assistant to start avatar chat</p>
              <Link href="/assistants/builder">
                <Button>Create an Assistant</Button>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AvatarPage() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <AvatarPageInner />
    </Suspense>
  );
}
