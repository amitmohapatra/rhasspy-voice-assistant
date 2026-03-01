'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '@/lib/api';
import type {
  EnrichedDocument, LLMKeyInfo, DocumentChatMessage, SourceCitation,
} from './types';
import { SourceCitationChip } from './source-citation';

interface DocumentChatProps {
  documentId: string;
  parsedDoc: EnrichedDocument;
  onNavigateToElement: (elementId: string) => void;
}

/**
 * Document-scoped chat tab.
 *
 * States:
 * - No keys saved → "No API key configured. [Go to Settings]"
 * - Keys exist, no message → Vendor/model dropdowns + suggested prompts
 * - First message sent → Lock dropdowns, hide prompts, start chat
 * - Ongoing → Locked badge + streaming messages + source citations
 */
export function DocumentChat({ documentId, parsedDoc, onNavigateToElement }: DocumentChatProps) {
  // LLM key state
  const [llmKeys, setLlmKeys] = useState<LLMKeyInfo[]>([]);
  const [keysLoading, setKeysLoading] = useState(true);

  // Vendor/model selection
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [models, setModels] = useState<Array<{ id: string; name: string; display_name: string }>>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [locked, setLocked] = useState(false);

  // Chat state
  const [messages, setMessages] = useState<DocumentChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  // Suggested prompts
  const suggestedPrompts = (parsedDoc.metadata?.suggested_prompts as string[]) || [];

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load LLM keys
  useEffect(() => {
    (async () => {
      try {
        const res = await api.listLLMKeys();
        setLlmKeys(res.keys);
        if (res.keys.length > 0 && !selectedProvider) {
          setSelectedProvider(res.keys[0].provider);
        }
      } catch {
        setLlmKeys([]);
      } finally {
        setKeysLoading(false);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load models when provider changes
  useEffect(() => {
    if (!selectedProvider) {
      setModels([]);
      return;
    }

    (async () => {
      setModelsLoading(true);
      try {
        const res = await api.listModels({ provider_id: selectedProvider, status: 'active', limit: 50 });
        const modelList = (res.models || []).map((m: any) => ({
          id: m.model_id || m.id,
          name: m.name,
          display_name: m.display_name || m.name,
        }));
        setModels(modelList);
        if (modelList.length > 0 && !selectedModel) {
          setSelectedModel(modelList[0].id);
        }
      } catch {
        setModels([]);
      } finally {
        setModelsLoading(false);
      }
    })();
  }, [selectedProvider]); // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming || !selectedProvider) return;

    // Lock vendor/model after first message
    if (!locked) setLocked(true);

    const userMsg: DocumentChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text.trim(),
    };

    const assistantMsgId = `assistant-${Date.now()}`;
    const assistantMsg: DocumentChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      sources: [],
    };

    // Build conversation history from existing messages (before adding new ones)
    const history = messages
      .filter(m => !m.isStreaming && (m.role === 'user' || m.role === 'assistant'))
      .map(m => ({ role: m.role, content: m.content }));

    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setInputText('');
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await api.documentChat(documentId, {
        message: text.trim(),
        provider: selectedProvider,
        model: selectedModel || undefined,
        conversation_history: history.length > 0 ? history : undefined,
      }, controller.signal);

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Chat failed' }));
        throw new Error(err.detail || 'Chat failed');
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let currentContent = '';
      let currentSources: SourceCitation[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          try {
            const event = JSON.parse(line.slice(6));

            switch (event.type) {
              case 'response.created': {
                // Response initialized
                break;
              }

              case 'response.output_item.added': {
                // RAG context with source citations
                if (event.item?.type === 'rag_context' && event.item?.rag_sources) {
                  const sources: SourceCitation[] = (event.item.rag_sources as any[])
                    .filter((s: any) => s.element_id)
                    .map((s: any) => ({
                      element_id: s.element_id,
                      page_number: s.page_number || 0,
                      type: s.element_type || 'text',
                      preview: (s.content || '').substring(0, 60),
                    }));
                  currentSources = sources;
                  setMessages(prev =>
                    prev.map(m => m.id === assistantMsgId
                      ? { ...m, sources: sources }
                      : m
                    )
                  );
                }
                break;
              }

              case 'response.content.delta': {
                currentContent += event.delta || '';
                setMessages(prev =>
                  prev.map(m => m.id === assistantMsgId
                    ? { ...m, content: currentContent }
                    : m
                  )
                );
                break;
              }

              case 'response.content.done': {
                if (event.text) {
                  currentContent = event.text;
                  setMessages(prev =>
                    prev.map(m => m.id === assistantMsgId
                      ? { ...m, content: event.text }
                      : m
                    )
                  );
                }
                break;
              }

              case 'response.completed': {
                setMessages(prev =>
                  prev.map(m => m.id === assistantMsgId
                    ? { ...m, isStreaming: false, sources: currentSources }
                    : m
                  )
                );
                break;
              }

              case 'response.failed': {
                throw new Error(event.error?.message || 'Response failed');
              }
            }
          } catch (parseErr) {
            if (parseErr instanceof Error && parseErr.message !== 'Response failed') {
              // Skip invalid JSON lines
            } else {
              throw parseErr;
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      setMessages(prev =>
        prev.map(m => m.id === assistantMsgId
          ? { ...m, content: `Error: ${err.message}`, isStreaming: false }
          : m
        )
      );
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [isStreaming, selectedProvider, selectedModel, documentId, locked, messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(inputText);
  };

  const handlePromptClick = (prompt: string) => {
    sendMessage(prompt);
  };

  const handleCitationClick = (citation: SourceCitation) => {
    onNavigateToElement(citation.element_id);
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  // ==================== Loading ====================
  if (keysLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-zinc-500 text-sm">Loading...</div>
      </div>
    );
  }

  // ==================== No keys ====================
  if (llmKeys.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 px-6 text-center">
        <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center">
          <svg className="w-6 h-6 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
        </div>
        <p className="text-sm text-zinc-400">No API key configured for document chat.</p>
        <a
          href="/settings/providers"
          className="text-sm text-emerald-400 hover:text-emerald-300 underline"
        >
          Go to Settings
        </a>
      </div>
    );
  }

  // ==================== Chat UI ====================
  return (
    <div className="flex flex-col h-full">
      {/* Vendor/Model selector */}
      <div className="flex-shrink-0 border-b border-zinc-800 px-4 py-2 flex items-center gap-2">
        {locked ? (
          <div className="flex items-center gap-2">
            <svg className="w-3.5 h-3.5 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            <span className="text-xs text-zinc-400">
              {selectedProvider} / {selectedModel || 'default'}
            </span>
          </div>
        ) : (
          <>
            <select
              value={selectedProvider}
              onChange={(e) => {
                setSelectedProvider(e.target.value);
                setSelectedModel('');
              }}
              className="h-7 bg-zinc-800 border border-zinc-700 rounded px-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
            >
              {llmKeys.map((k) => (
                <option key={k.provider} value={k.provider}>{k.provider}</option>
              ))}
            </select>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={modelsLoading}
              className="h-7 bg-zinc-800 border border-zinc-700 rounded px-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-emerald-500 max-w-[200px]"
            >
              {modelsLoading ? (
                <option>Loading...</option>
              ) : models.length === 0 ? (
                <option value="">No models</option>
              ) : (
                models.map((m) => (
                  <option key={m.id} value={m.id}>{m.display_name}</option>
                ))
              )}
            </select>
          </>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto px-4 py-3 space-y-4">
        {messages.length === 0 && (
          <div className="space-y-4">
            {/* Document summary */}
            <div className="text-xs text-zinc-500">
              {parsedDoc.filename && (
                <p className="mb-1">Document: <span className="text-zinc-300">{parsedDoc.filename}</span></p>
              )}
              <p>{Object.keys(parsedDoc.elements).length} elements, {parsedDoc.page_count || 1} pages</p>
            </div>

            {/* Suggested prompts */}
            {suggestedPrompts.length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] text-zinc-600 uppercase tracking-wider font-medium">Suggested</p>
                <div className="flex flex-wrap gap-2">
                  {suggestedPrompts.map((prompt, i) => (
                    <button
                      key={i}
                      onClick={() => handlePromptClick(prompt)}
                      className="px-3 py-1.5 text-xs text-zinc-300 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 hover:border-zinc-600 rounded-lg transition-colors text-left"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                msg.role === 'user'
                  ? 'bg-emerald-600/20 text-emerald-100'
                  : 'bg-zinc-800 text-zinc-200'
              }`}
            >
              <p className="whitespace-pre-wrap break-words">{msg.content}</p>
              {msg.isStreaming && (
                <span className="inline-block w-1.5 h-4 bg-zinc-400 animate-pulse ml-0.5" />
              )}
              {/* Source citations */}
              {msg.sources && msg.sources.length > 0 && !msg.isStreaming && (
                <div className="mt-2 pt-2 border-t border-zinc-700 flex flex-wrap gap-1.5">
                  {msg.sources.map((src, i) => (
                    <SourceCitationChip
                      key={i}
                      citation={src}
                      onClick={handleCitationClick}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="flex-shrink-0 border-t border-zinc-800 p-3">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Ask about this document..."
            disabled={isStreaming}
            className="flex-1 h-9 bg-zinc-800 border border-zinc-700 rounded-lg px-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={handleStop}
              className="h-9 px-3 bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded-lg text-sm font-medium transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!inputText.trim() || !selectedProvider}
              className="h-9 px-4 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white transition-colors"
            >
              Send
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
