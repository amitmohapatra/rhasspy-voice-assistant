'use client';

/**
 * Conversation History Page
 *
 * Browse and search through past conversations.
 */

import { useState, useEffect } from 'react';
import {
  MessageSquare,
  Search,
  Calendar,
  Trash2,
  Download,
  Loader2,
  MoreHorizontal,
  Bot,
  User,
  ChevronRight,
  X,
  Filter,
  Clock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { api, type Conversation, type ChatDisplayMessage, type ResponseSchema, type Assistant } from '@/lib/api';

interface ExtendedConversation extends Conversation {
  assistant_name?: string;
  last_message?: string;
}

export default function ChatHistoryPage() {
  const [conversations, setConversations] = useState<ExtendedConversation[]>([]);
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [assistantFilter, setAssistantFilter] = useState('all');
  const [dateFilter, setDateFilter] = useState('all');
  const [selectedConversation, setSelectedConversation] = useState<ExtendedConversation | null>(null);
  const [messages, setMessages] = useState<ChatDisplayMessage[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [conversationToDelete, setConversationToDelete] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [convos, assists] = await Promise.all([
        api.listConversations(),
        api.listAssistants(),
      ]);
      setConversations(convos);
      setAssistants(assists.items || []);
    } catch (err) {
      console.error('Failed to load chat history:', err);
      setAssistants([]);
      setConversations([]);
    } finally {
      setIsLoading(false);
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
      }
    }
    return msgs;
  }

  const loadMessages = async (conversationId: string) => {
    setIsLoadingMessages(true);
    try {
      const responses = await api.getConversationResponses(conversationId);
      setMessages(flattenResponses(responses));
    } catch {
      setMessages([]);
    } finally {
      setIsLoadingMessages(false);
    }
  };

  const handleSelectConversation = async (conversation: ExtendedConversation) => {
    setSelectedConversation(conversation);
    await loadMessages(conversation.id);
  };

  const handleDeleteConversation = async () => {
    if (!conversationToDelete) return;
    try {
      await api.deleteConversation(conversationToDelete);
    } catch {
      // Mock delete
    }
    setConversations(prev => prev.filter(c => c.id !== conversationToDelete));
    if (selectedConversation?.id === conversationToDelete) {
      setSelectedConversation(null);
      setMessages([]);
    }
    setShowDeleteDialog(false);
    setConversationToDelete(null);
  };

  const handleExport = async (conversationId: string) => {
    const conversation = conversations.find(c => c.id === conversationId);
    if (!conversation) return;

    try {
      const responses = await api.getConversationResponses(conversationId);
      const exportData = {
        conversation,
        responses,
        exported_at: new Date().toISOString(),
      };
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `conversation-${conversationId}.json`;
      a.click();
    } catch {
      alert('Export functionality would download the conversation');
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  };

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const filteredConversations = conversations.filter(conv => {
    const matchesSearch = !searchQuery ||
      conv.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      conv.last_message?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesAssistant = assistantFilter === 'all' || conv.assistant_id === assistantFilter;

    let matchesDate = true;
    if (dateFilter !== 'all') {
      const convDate = new Date(conv.created_at);
      const now = new Date();
      const diff = now.getTime() - convDate.getTime();
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));

      if (dateFilter === 'today' && days > 0) matchesDate = false;
      if (dateFilter === 'week' && days > 7) matchesDate = false;
      if (dateFilter === 'month' && days > 30) matchesDate = false;
    }

    return matchesSearch && matchesAssistant && matchesDate;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-screen">
      {/* Header */}
      <div className="p-6 border-b">
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <MessageSquare className="w-6 h-6" />
          Conversation History
        </h1>
        <p className="text-muted-foreground mt-1">
          Browse and search through {conversations.length} conversations
        </p>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Conversation List */}
        <div className="w-96 border-r flex flex-col">
          {/* Filters */}
          <div className="p-4 border-b space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search conversations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex gap-2">
              <Select value={assistantFilter} onValueChange={setAssistantFilter}>
                <SelectTrigger className="flex-1">
                  <Bot className="w-4 h-4 mr-2" />
                  <SelectValue placeholder="Assistant" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Assistants</SelectItem>
                  {assistants.map(a => (
                    <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={dateFilter} onValueChange={setDateFilter}>
                <SelectTrigger className="w-32">
                  <Calendar className="w-4 h-4 mr-2" />
                  <SelectValue placeholder="Date" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Time</SelectItem>
                  <SelectItem value="today">Today</SelectItem>
                  <SelectItem value="week">This Week</SelectItem>
                  <SelectItem value="month">This Month</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Conversation List */}
          <ScrollArea className="flex-1">
            {filteredConversations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64">
                <MessageSquare className="w-12 h-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No conversations found</p>
              </div>
            ) : (
              <div className="divide-y">
                {filteredConversations.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => handleSelectConversation(conv)}
                    className={cn(
                      'p-4 cursor-pointer hover:bg-muted/50 transition-colors',
                      selectedConversation?.id === conv.id && 'bg-muted'
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium truncate">{conv.title || 'Untitled'}</h4>
                        <p className="text-sm text-muted-foreground truncate mt-1">
                          {conv.last_message}
                        </p>
                        <div className="flex items-center gap-2 mt-2">
                          <Badge variant="outline" className="text-xs">
                            {conv.assistant_name}
                          </Badge>
                          <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatDate(conv.created_at)}
                          </span>
                        </div>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleExport(conv.id)}>
                            <Download className="w-4 h-4 mr-2" />
                            Export
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => { setConversationToDelete(conv.id); setShowDeleteDialog(true); }}
                            className="text-destructive"
                          >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>

        {/* Message View */}
        <div className="flex-1 flex flex-col">
          {selectedConversation ? (
            <>
              {/* Conversation Header */}
              <div className="p-4 border-b flex items-center justify-between">
                <div>
                  <h2 className="font-medium">{selectedConversation.title || 'Untitled'}</h2>
                  <p className="text-sm text-muted-foreground">
                    {selectedConversation.response_count ?? 0} responses with {selectedConversation.assistant_name}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => handleExport(selectedConversation.id)}>
                    <Download className="w-4 h-4 mr-2" />
                    Export
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => { setSelectedConversation(null); setMessages([]); }}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {/* Messages */}
              <ScrollArea className="flex-1 p-4">
                {isLoadingMessages ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                  <div className="space-y-4 max-w-3xl mx-auto">
                    {messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={cn(
                          'flex gap-3',
                          msg.role === 'user' && 'flex-row-reverse'
                        )}
                      >
                        <div className={cn(
                          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                          msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'
                        )}>
                          {msg.role === 'user' ? (
                            <User className="w-4 h-4" />
                          ) : (
                            <Bot className="w-4 h-4" />
                          )}
                        </div>
                        <div className={cn(
                          'flex-1 max-w-[80%]',
                          msg.role === 'user' && 'flex flex-col items-end'
                        )}>
                          <div className={cn(
                            'rounded-lg p-3',
                            msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'
                          )}>
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                          </div>
                          <span className="text-xs text-muted-foreground mt-1">
                            {formatTime(msg.created_at)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <MessageSquare className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
                <h3 className="font-medium mb-2">Select a conversation</h3>
                <p className="text-sm text-muted-foreground">
                  Choose a conversation from the list to view its messages
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Delete Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Conversation</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this conversation? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteConversation}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
