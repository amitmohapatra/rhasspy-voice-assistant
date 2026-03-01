'use client';

/**
 * Assistant Builder - DB-Driven
 *
 * Features:
 * - DB-driven provider and model lists (fetched from API)
 * - Knowledge base attachment for RAG
 * - Live preview panel
 * - Collapsible sections with progressive disclosure
 */

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Bot,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  Check,
  Loader2,
  Brain,
  Wrench,
  Database,
  Settings,
  Eye,
  Upload,
  Plus,
  X,
  MessageSquare,
  Send,
  Wand2,
  RotateCcw,
} from 'lucide-react';
import { api, type KnowledgeBase, type AIModel, type AIProvider, type BuiltinToolDB, type Tool } from '@/lib/api';

// Tool icon mapping for builtin tools
const TOOL_ICONS: Record<string, string> = {
  'file-search': '📂', search: '🔍', globe: '🌐', code: '💻', image: '🖼️',
  monitor: '🖥️', box: '📦', plug: '🔌', function: '⚡', braces: '{ }',
  brain: '🧠', calculator: '🔢', file: '📄', database: '🗄️',
  slack: '💬', github: '🐙', jira: '📋', notion: '📝',
  linear: '📊', calendar: '📅', mail: '📧', cloud: '☁️',
};

// ==================== Types ====================

interface AssistantConfig {
  name: string;
  description: string;
  avatar_url: string | null;
  provider_id: string;
  model_id: string;
  instructions: string;
  knowledge_base_id: string | null;
  tools: string[];
  temperature: number;
  max_tokens: number;
  top_p: number;
  welcome_message: string;
}

// ==================== Constants ====================

const INSTRUCTION_TEMPLATES = [
  { id: 'customer_support', name: 'Customer Support', prompt: 'You are a helpful customer support assistant. You help users with their questions about products, orders, returns, and general inquiries. Be friendly, professional, and always try to resolve issues efficiently.' },
  { id: 'code_assistant', name: 'Code Assistant', prompt: 'You are an expert programming assistant. Help users write, debug, and understand code. Explain concepts clearly, provide working examples, and follow best practices for the relevant programming language.' },
  { id: 'knowledge_expert', name: 'Knowledge Expert', prompt: 'You are a knowledgeable assistant with access to a specialized knowledge base. Answer questions accurately based on the available information. If you don\'t know something, say so rather than making up information.' },
  { id: 'creative_writer', name: 'Creative Writer', prompt: 'You are a creative writing assistant. Help users with storytelling, content creation, and writing tasks. Be imaginative, engaging, and adapt your style to the user\'s needs.' },
];

const SETTING_PRESETS = [
  { id: 'balanced', name: 'Balanced', temperature: 0.7, top_p: 1.0 },
  { id: 'creative', name: 'Creative', temperature: 1.0, top_p: 0.95 },
  { id: 'precise', name: 'Precise', temperature: 0.3, top_p: 0.9 },
];

// ==================== Main Component ====================

export default function AssistantBuilderPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [previewMessages, setPreviewMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([]);
  const [previewInput, setPreviewInput] = useState('');

  // DB-driven providers and models
  const [dbProviders, setDbProviders] = useState<AIProvider[]>([]);
  const [dbModels, setDbModels] = useState<AIModel[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(true);

  // DB-driven tools
  const [builtinTools, setBuiltinTools] = useState<BuiltinToolDB[]>([]);
  const [customTools, setCustomTools] = useState<(Tool & { is_available: boolean; unavailable_reason?: string })[]>([]);
  const [isLoadingTools, setIsLoadingTools] = useState(false);

  // Collapsible sections
  const [expandedSections, setExpandedSections] = useState({
    knowledge: false,
    tools: false,
    advanced: false,
  });

  const [config, setConfig] = useState<AssistantConfig>({
    name: '',
    description: '',
    avatar_url: null,
    provider_id: '',
    model_id: '',
    instructions: '',
    knowledge_base_id: null,
    tools: ['file_search'],
    temperature: 0.7,
    max_tokens: 4096,
    top_p: 1.0,
    welcome_message: 'Hello! How can I help you today?',
  });

  useEffect(() => {
    loadData();
  }, []);

  // Fetch available tools when model changes
  useEffect(() => {
    const selectedProvider = dbProviders.find(p => p.name === config.provider_id);
    const selectedModel = dbModels.find(m => m.model_id === config.model_id && m.provider_id === selectedProvider?.id);
    if (!selectedModel) {
      setBuiltinTools([]);
      setCustomTools([]);
      return;
    }

    let cancelled = false;
    setIsLoadingTools(true);
    api.getAvailableToolsForModel(selectedModel.id)
      .then(result => {
        if (cancelled) return;
        setBuiltinTools(result.builtin_tools || []);
        setCustomTools(result.custom_tools || []);
      })
      .catch(() => {
        if (cancelled) return;
        setBuiltinTools([]);
        setCustomTools([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingTools(false);
      });

    return () => { cancelled = true; };
  }, [config.model_id, config.provider_id, dbProviders, dbModels]);

  useEffect(() => {
    if (config.welcome_message && previewMessages.length === 0) {
      setPreviewMessages([{ role: 'assistant', content: config.welcome_message }]);
    }
  }, [config.welcome_message]);

  const loadData = async () => {
    setIsLoadingModels(true);
    try {
      const [providersRes, modelsRes, kbsRes] = await Promise.all([
        api.listProviders({ status: 'active' }),
        api.listModels({ status: 'active', limit: 500 }),
        api.listKnowledgeBases(),
      ]);
      setDbProviders(providersRes);
      setDbModels(modelsRes.models || []);
      setKnowledgeBases(kbsRes.items || []);

      // Set initial provider/model
      if (providersRes.length > 0) {
        const firstProvider = providersRes[0];
        const providerModels = (modelsRes.models || []).filter(
          (m: AIModel) => m.provider_id === firstProvider.id && m.status === 'active'
        );
        const defaultModel = providerModels.find((m: AIModel) => m.is_default) || providerModels[0];
        setConfig(prev => ({
          ...prev,
          provider_id: firstProvider.name,
          model_id: defaultModel?.model_id || '',
        }));
      }
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoadingModels(false);
    }
  };

  const getFilteredProviders = (): AIProvider[] => {
    return dbProviders.filter(p => p.status === 'active');
  };

  const getFilteredModels = (providerId: string): AIModel[] => {
    const provider = dbProviders.find(p => p.name === providerId);
    if (!provider) return [];
    return dbModels.filter(m => m.provider_id === provider.id && m.status === 'active');
  };

  const selectedProviderObj = dbProviders.find(p => p.name === config.provider_id);
  const selectedModelObj = dbModels.find(m => m.model_id === config.model_id && m.provider_id === selectedProviderObj?.id);
  const selectedKB = knowledgeBases.find(kb => kb.id === config.knowledge_base_id);

  const filteredKnowledgeBases = useMemo(() => {
    return knowledgeBases.filter(kb => kb.kb_type === 'platform_managed');
  }, [knowledgeBases]);

  const updateConfig = <K extends keyof AssistantConfig>(key: K, value: AssistantConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const toggleTool = (toolId: string) => {
    if (config.tools.includes(toolId)) {
      updateConfig('tools', config.tools.filter(t => t !== toolId));
    } else {
      updateConfig('tools', [...config.tools, toolId]);
    }
  };

  const applyTemplate = (templateId: string) => {
    const template = INSTRUCTION_TEMPLATES.find(t => t.id === templateId);
    if (template) updateConfig('instructions', template.prompt);
  };

  const applyPreset = (presetId: string) => {
    const preset = SETTING_PRESETS.find(p => p.id === presetId);
    if (preset) {
      updateConfig('temperature', preset.temperature);
      updateConfig('top_p', preset.top_p);
    }
  };

  const handlePreviewSend = () => {
    if (!previewInput.trim()) return;
    setPreviewMessages(prev => [
      ...prev,
      { role: 'user', content: previewInput },
      { role: 'assistant', content: `I understand you're asking about "${previewInput}". ${selectedKB ? `I'll search the ${selectedKB.name} knowledge base to find the best answer for you.` : 'How can I help you with that?'}` },
    ]);
    setPreviewInput('');
  };

  const handleSubmit = async () => {
    if (!config.name.trim() || !config.instructions.trim()) {
      alert('Please fill in the required fields: Name and Instructions');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.createAssistant({
        name: config.name,
        description: config.description,
        system_prompt: config.instructions,
        model: config.model_id || 'gpt-4o',
        provider: config.provider_id,
        temperature: config.temperature,
        welcome_message: config.welcome_message,
        knowledge_base_ids: config.knowledge_base_id ? [config.knowledge_base_id] : [],
        tools: config.tools,
      });
      router.push('/assistants');
    } catch (error) {
      console.error('Failed to create assistant:', error);
      alert('Failed to create assistant. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const canCreate = config.name.trim().length > 0 && config.instructions.trim().length > 0;

  return (
    <div className="min-h-screen bg-[#0a0a0a]">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-[#0a0a0a] border-b border-zinc-800">
        <div className="max-w-screen-2xl mx-auto px-6">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-4">
              <Link
                href="/assistants"
                className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
                <span className="text-[13px]">Assistants</span>
              </Link>
              <div className="h-4 w-px bg-zinc-800" />
              <h1 className="text-[15px] font-semibold text-white">Create Assistant</h1>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => router.push('/assistants')}
                className="px-3 py-1.5 text-[13px] text-zinc-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!canCreate || isSubmitting}
                className="flex items-center gap-2 px-4 py-1.5 bg-white text-black hover:bg-zinc-200 disabled:bg-zinc-700 disabled:text-zinc-500 rounded-md text-[13px] font-medium transition-colors"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    Create Assistant
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content - Two Column Layout */}
      <div className="max-w-screen-2xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Configuration */}
          <div className="space-y-4">
            {/* Essentials Card */}
            <div className="bg-[#18181b] border border-zinc-800 rounded-lg">
              <div className="p-5 border-b border-zinc-800">
                <h2 className="text-[14px] font-semibold text-white">Essentials</h2>
                <p className="text-[12px] text-zinc-500 mt-1">Required information for your assistant</p>
              </div>

              <div className="p-5 space-y-5">
                {/* Avatar & Name Row */}
                <div className="flex gap-4">
                  <div className="flex-shrink-0">
                    <div className="relative">
                      <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-emerald-500 to-blue-600 flex items-center justify-center">
                        <Bot className="w-8 h-8 text-white" />
                      </div>
                      <button className="absolute -bottom-1 -right-1 p-1 bg-zinc-800 border border-zinc-700 rounded-md hover:bg-zinc-700 transition-colors">
                        <Upload className="w-3 h-3 text-zinc-400" />
                      </button>
                    </div>
                  </div>

                  <div className="flex-1 space-y-3">
                    <div>
                      <label className="block text-[12px] font-medium text-zinc-400 mb-1.5">
                        Name <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        value={config.name}
                        onChange={(e) => updateConfig('name', e.target.value)}
                        placeholder="e.g., Customer Support Bot"
                        className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-[13px] text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none transition-colors"
                      />
                    </div>
                    <div>
                      <label className="block text-[12px] font-medium text-zinc-400 mb-1.5">Description</label>
                      <input
                        type="text"
                        value={config.description}
                        onChange={(e) => updateConfig('description', e.target.value)}
                        placeholder="Brief description of what this assistant does"
                        className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-[13px] text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none transition-colors"
                      />
                    </div>
                  </div>
                </div>

                {/* Model Selector */}
                <div>
                  <label className="block text-[12px] font-medium text-zinc-400 mb-1.5">Model</label>
                  <button
                    onClick={() => setShowModelSelector(true)}
                    className="w-full flex items-center justify-between px-3 py-2.5 bg-zinc-900 border border-zinc-800 rounded-md hover:border-zinc-700 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                        <Brain className="w-4 h-4 text-zinc-400" />
                      </div>
                      <div className="text-left">
                        {isLoadingModels ? (
                          <p className="text-[13px] text-zinc-500">Loading models...</p>
                        ) : selectedModelObj ? (
                          <>
                            <p className="text-[13px] font-medium text-white">{selectedModelObj.display_name}</p>
                            <p className="text-[11px] text-zinc-500">
                              {selectedProviderObj?.display_name} · {selectedModelObj.context_window.toLocaleString()} context
                            </p>
                          </>
                        ) : (
                          <p className="text-[13px] text-zinc-500">Select a model</p>
                        )}
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-zinc-500" />
                  </button>
                </div>

                {/* Instructions */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-[12px] font-medium text-zinc-400">
                      Instructions <span className="text-red-400">*</span>
                    </label>
                    <div className="flex items-center gap-2">
                      <select
                        onChange={(e) => e.target.value && applyTemplate(e.target.value)}
                        className="px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-[11px] text-zinc-300 focus:outline-none"
                        defaultValue=""
                      >
                        <option value="" disabled>Use Template</option>
                        {INSTRUCTION_TEMPLATES.map(t => (
                          <option key={t.id} value={t.id}>{t.name}</option>
                        ))}
                      </select>
                      <button className="flex items-center gap-1 px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-[11px] text-zinc-300 hover:bg-zinc-700 transition-colors">
                        <Wand2 className="w-3 h-3" />
                        Generate
                      </button>
                    </div>
                  </div>
                  <textarea
                    value={config.instructions}
                    onChange={(e) => updateConfig('instructions', e.target.value)}
                    placeholder="You are a helpful assistant that..."
                    rows={5}
                    className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-[13px] text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none transition-colors resize-none font-mono"
                  />
                </div>

                {/* Welcome Message */}
                <div>
                  <label className="block text-[12px] font-medium text-zinc-400 mb-1.5">Welcome Message</label>
                  <input
                    type="text"
                    value={config.welcome_message}
                    onChange={(e) => updateConfig('welcome_message', e.target.value)}
                    placeholder="Hello! How can I help you today?"
                    className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-[13px] text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none transition-colors"
                  />
                </div>
              </div>
            </div>

            {/* Knowledge Base Section - Collapsible */}
            <div className="bg-[#18181b] border border-zinc-800 rounded-lg overflow-hidden">
              <button
                onClick={() => toggleSection('knowledge')}
                className="w-full flex items-center justify-between p-4 hover:bg-zinc-800/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Database className="w-4 h-4 text-zinc-500" />
                  <span className="text-[13px] font-medium text-white">Knowledge Base</span>
                  {selectedKB && (
                    <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-[11px] rounded">
                      1 attached
                    </span>
                  )}
                </div>
                <ChevronDown className={`w-4 h-4 text-zinc-500 transition-transform ${expandedSections.knowledge ? 'rotate-180' : ''}`} />
              </button>

              {expandedSections.knowledge && (
                <div className="px-4 pb-4 border-t border-zinc-800">
                  <p className="text-[12px] text-zinc-500 mt-3 mb-3">
                    Attach a knowledge base for RAG-powered responses
                  </p>

                  {selectedKB ? (
                    <div className="flex items-center justify-between p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                      <div className="flex items-center gap-3">
                        <Database className="w-4 h-4 text-emerald-400" />
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="text-[13px] font-medium text-white">{selectedKB.name}</p>
                            <span className={`px-1.5 py-0.5 text-[9px] font-medium rounded ${
                              selectedKB.kb_type === 'provider_managed'
                                ? 'bg-blue-500/20 text-blue-400'
                                : 'bg-emerald-500/20 text-emerald-400'
                            }`}>
                              {selectedKB.kb_type === 'provider_managed' ? 'Provider' : 'Platform'}
                            </span>
                          </div>
                          <p className="text-[11px] text-zinc-500">{selectedKB.document_count} docs · {selectedKB.total_chunks} chunks</p>
                        </div>
                      </div>
                      <button onClick={() => updateConfig('knowledge_base_id', null)} className="p-1 hover:bg-zinc-800 rounded transition-colors">
                        <X className="w-4 h-4 text-zinc-400" />
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {filteredKnowledgeBases.length === 0 ? (
                        <div className="text-center py-6 border border-dashed border-zinc-700 rounded-lg">
                          <Database className="w-6 h-6 text-zinc-600 mx-auto mb-2" />
                          <p className="text-[12px] text-zinc-500 mb-2">
                            No knowledge bases available
                          </p>
                          <Link href="/knowledge-bases" className="text-[12px] text-emerald-400 hover:underline">
                            Create Knowledge Base
                          </Link>
                        </div>
                      ) : (
                        filteredKnowledgeBases.map(kb => (
                          <button
                            key={kb.id}
                            onClick={() => updateConfig('knowledge_base_id', kb.id)}
                            className="w-full flex items-center justify-between p-3 bg-zinc-900 border border-zinc-800 rounded-lg hover:border-zinc-700 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              <Database className="w-4 h-4 text-zinc-500" />
                              <div className="text-left">
                                <div className="flex items-center gap-2">
                                  <p className="text-[13px] font-medium text-white">{kb.name}</p>
                                  <span className={`px-1.5 py-0.5 text-[9px] font-medium rounded ${
                                    kb.kb_type === 'provider_managed'
                                      ? 'bg-blue-500/20 text-blue-400'
                                      : 'bg-emerald-500/20 text-emerald-400'
                                  }`}>
                                    {kb.kb_type === 'provider_managed' ? 'Provider' : 'Platform'}
                                  </span>
                                </div>
                                <p className="text-[11px] text-zinc-500">{kb.document_count} docs · {kb.total_chunks} chunks</p>
                              </div>
                            </div>
                            <Plus className="w-4 h-4 text-zinc-500" />
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Tools Section - Collapsible */}
            <div className="bg-[#18181b] border border-zinc-800 rounded-lg overflow-hidden">
              <button
                onClick={() => toggleSection('tools')}
                className="w-full flex items-center justify-between p-4 hover:bg-zinc-800/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Wrench className="w-4 h-4 text-zinc-500" />
                  <span className="text-[13px] font-medium text-white">Tools</span>
                  {config.tools.length > 0 && (
                    <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-[11px] rounded">
                      {config.tools.length} enabled
                    </span>
                  )}
                </div>
                <ChevronDown className={`w-4 h-4 text-zinc-500 transition-transform ${expandedSections.tools ? 'rotate-180' : ''}`} />
              </button>

              {expandedSections.tools && (
                <div className="px-4 pb-4 border-t border-zinc-800">
                  {!config.model_id ? (
                    <div className="text-center py-6">
                      <Brain className="w-6 h-6 text-zinc-600 mx-auto mb-2" />
                      <p className="text-[12px] text-zinc-500">Select a model to see available tools</p>
                    </div>
                  ) : isLoadingTools ? (
                    <div className="flex items-center justify-center py-6">
                      <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
                      <span className="ml-2 text-[12px] text-zinc-500">Loading tools...</span>
                    </div>
                  ) : (
                    <>
                      <p className="text-[12px] text-zinc-500 mt-3 mb-3">
                        Enable tools to extend your assistant&apos;s capabilities
                      </p>

                      {/* Builtin Tools */}
                      {builtinTools.length > 0 && (
                        <div className="space-y-2 mb-4">
                          <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">Built-in Tools</p>
                          {builtinTools.map(tool => {
                            const isEnabled = config.tools.includes(tool.name);
                            const isAlwaysOn = tool.is_always_on;
                            const toolIcon = TOOL_ICONS[tool.icon || ''] || '🔧';

                            return (
                              <button
                                key={tool.id}
                                onClick={() => !isAlwaysOn && toggleTool(tool.name)}
                                disabled={isAlwaysOn}
                                className={`w-full flex items-center justify-between p-3 rounded-lg border transition-colors ${
                                  isEnabled || isAlwaysOn
                                    ? 'bg-blue-500/10 border-blue-500/30'
                                    : 'bg-zinc-900 border-zinc-800 hover:border-zinc-700'
                                } ${isAlwaysOn ? 'cursor-default' : ''}`}
                              >
                                <div className="flex items-center gap-3">
                                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-lg ${
                                    isEnabled || isAlwaysOn ? 'bg-blue-500/20' : 'bg-zinc-800'
                                  }`}>
                                    {toolIcon}
                                  </div>
                                  <div className="text-left">
                                    <div className="flex items-center gap-2">
                                      <p className="text-[13px] font-medium text-white">{tool.display_name}</p>
                                      {isAlwaysOn && (
                                        <span className="px-1.5 py-0.5 text-[9px] font-semibold bg-green-900/50 text-green-400 rounded">Always On</span>
                                      )}
                                      {tool.is_preview && (
                                        <span className="px-1.5 py-0.5 text-[9px] font-semibold bg-yellow-900/50 text-yellow-400 rounded">Preview</span>
                                      )}
                                      {tool.is_beta && (
                                        <span className="px-1.5 py-0.5 text-[9px] font-semibold bg-purple-900/50 text-purple-400 rounded">Beta</span>
                                      )}
                                    </div>
                                    <p className="text-[11px] text-zinc-500">{tool.description}</p>
                                  </div>
                                </div>
                                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                                  isEnabled || isAlwaysOn ? 'border-blue-500 bg-blue-500' : 'border-zinc-600'
                                }`}>
                                  {(isEnabled || isAlwaysOn) && <Check className="w-3 h-3 text-white" />}
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      )}

                      {/* Custom Tools */}
                      {customTools.length > 0 && (
                        <div className="space-y-2">
                          <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">Custom Tools</p>
                          {customTools.map(tool => {
                            const isEnabled = config.tools.includes(tool.id);
                            const isAvailable = tool.is_available;
                            const toolIcon = TOOL_ICONS[tool.icon || ''] || '🛠️';

                            return (
                              <button
                                key={tool.id}
                                onClick={() => isAvailable && toggleTool(tool.id)}
                                disabled={!isAvailable}
                                title={!isAvailable ? (tool.unavailable_reason || 'Not available for this model') : undefined}
                                className={`w-full flex items-center justify-between p-3 rounded-lg border transition-colors ${
                                  !isAvailable
                                    ? 'bg-zinc-900/50 border-zinc-800 opacity-50 cursor-not-allowed'
                                    : isEnabled
                                      ? 'bg-blue-500/10 border-blue-500/30'
                                      : 'bg-zinc-900 border-zinc-800 hover:border-zinc-700'
                                }`}
                              >
                                <div className="flex items-center gap-3">
                                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-lg ${
                                    isEnabled ? 'bg-blue-500/20' : 'bg-zinc-800'
                                  }`}>
                                    {toolIcon}
                                  </div>
                                  <div className="text-left">
                                    <p className="text-[13px] font-medium text-white">{tool.display_name || tool.name}</p>
                                    <p className="text-[11px] text-zinc-500">{tool.description || 'Custom tool'}</p>
                                  </div>
                                </div>
                                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                                  isEnabled ? 'border-blue-500 bg-blue-500' : 'border-zinc-600'
                                }`}>
                                  {isEnabled && <Check className="w-3 h-3 text-white" />}
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      )}

                      {builtinTools.length === 0 && customTools.length === 0 && (
                        <div className="text-center py-6">
                          <Wrench className="w-6 h-6 text-zinc-600 mx-auto mb-2" />
                          <p className="text-[12px] text-zinc-500">No tools available for this model</p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Advanced Settings - Collapsible */}
            <div className="bg-[#18181b] border border-zinc-800 rounded-lg overflow-hidden">
              <button
                onClick={() => toggleSection('advanced')}
                className="w-full flex items-center justify-between p-4 hover:bg-zinc-800/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Settings className="w-4 h-4 text-zinc-500" />
                  <span className="text-[13px] font-medium text-white">Advanced Settings</span>
                  <span className="text-[11px] text-zinc-500">
                    Temp: {config.temperature} · Max: {config.max_tokens}
                  </span>
                </div>
                <ChevronDown className={`w-4 h-4 text-zinc-500 transition-transform ${expandedSections.advanced ? 'rotate-180' : ''}`} />
              </button>

              {expandedSections.advanced && (
                <div className="px-4 pb-4 border-t border-zinc-800">
                  <div className="flex items-center gap-2 mt-3 mb-4">
                    <span className="text-[12px] text-zinc-500">Presets:</span>
                    {SETTING_PRESETS.map(preset => (
                      <button
                        key={preset.id}
                        onClick={() => applyPreset(preset.id)}
                        className={`px-3 py-1 rounded text-[11px] font-medium transition-colors ${
                          config.temperature === preset.temperature && config.top_p === preset.top_p
                            ? 'bg-white text-black'
                            : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                        }`}
                      >
                        {preset.name}
                      </button>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-[12px] font-medium text-zinc-400">Temperature</label>
                        <span className="text-[12px] text-zinc-500">{config.temperature.toFixed(1)}</span>
                      </div>
                      <input
                        type="range" min="0" max="2" step="0.1"
                        value={config.temperature}
                        onChange={(e) => updateConfig('temperature', parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-white"
                      />
                      <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
                        <span>Precise</span><span>Creative</span>
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-[12px] font-medium text-zinc-400">Top P</label>
                        <span className="text-[12px] text-zinc-500">{config.top_p.toFixed(2)}</span>
                      </div>
                      <input
                        type="range" min="0" max="1" step="0.05"
                        value={config.top_p}
                        onChange={(e) => updateConfig('top_p', parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-white"
                      />
                    </div>
                    <div>
                      <label className="block text-[12px] font-medium text-zinc-400 mb-2">Max Tokens</label>
                      <input
                        type="number"
                        value={config.max_tokens}
                        onChange={(e) => updateConfig('max_tokens', parseInt(e.target.value) || 4096)}
                        className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-[13px] text-white focus:border-zinc-600 focus:outline-none transition-colors"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Column - Live Preview */}
          <div className="lg:sticky lg:top-20 lg:h-[calc(100vh-120px)]">
            <div className="bg-[#18181b] border border-zinc-800 rounded-lg h-full flex flex-col">
              <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Eye className="w-4 h-4 text-zinc-500" />
                  <span className="text-[13px] font-medium text-white">Live Preview</span>
                </div>
                <button
                  onClick={() => setPreviewMessages(config.welcome_message ? [{ role: 'assistant', content: config.welcome_message }] : [])}
                  className="p-1.5 hover:bg-zinc-800 rounded transition-colors"
                  title="Reset preview"
                >
                  <RotateCcw className="w-3.5 h-3.5 text-zinc-500" />
                </button>
              </div>

              {/* Preview Header */}
              <div className="p-4 border-b border-zinc-800 bg-zinc-900/50">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-blue-600 flex items-center justify-center">
                    <Bot className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="text-[14px] font-medium text-white">
                      {config.name || 'Untitled Assistant'}
                    </p>
                    <p className="text-[11px] text-zinc-500">
                      {selectedModelObj?.display_name || 'No model'} · {selectedProviderObj?.display_name || ''}
                    </p>
                  </div>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {previewMessages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] px-3 py-2 rounded-lg ${
                      msg.role === 'user' ? 'bg-white text-black' : 'bg-zinc-800 text-zinc-200'
                    }`}>
                      <p className="text-[13px]">{msg.content}</p>
                    </div>
                  </div>
                ))}
                {previewMessages.length === 0 && (
                  <div className="text-center py-8">
                    <MessageSquare className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
                    <p className="text-[12px] text-zinc-600">No messages yet</p>
                  </div>
                )}
              </div>

              {/* Capabilities Summary */}
              <div className="px-4 py-3 border-t border-zinc-800 bg-zinc-900/50">
                <p className="text-[11px] font-medium text-zinc-500 mb-2">Active Capabilities</p>
                <div className="flex flex-wrap gap-1.5">
                  {selectedKB && (
                    <span className={`flex items-center gap-1 px-2 py-1 text-[10px] rounded ${
                      selectedKB.kb_type === 'provider_managed'
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'bg-emerald-500/20 text-emerald-400'
                    }`}>
                      <Database className="w-3 h-3" />
                      {selectedKB.name}
                    </span>
                  )}
                  {config.tools.map(toolId => {
                    const bt = builtinTools.find(t => t.name === toolId);
                    const ct = customTools.find(t => t.id === toolId);
                    const toolName = bt?.display_name || ct?.display_name || ct?.name || toolId;
                    const toolIcon = TOOL_ICONS[(bt?.icon || ct?.icon) || ''] || '🔧';
                    return (
                      <span key={toolId} className="flex items-center gap-1 px-2 py-1 bg-blue-500/20 text-blue-400 text-[10px] rounded">
                        <span className="text-[10px]">{toolIcon}</span>
                        {toolName}
                      </span>
                    );
                  })}
                  {!selectedKB && config.tools.length === 0 && (
                    <span className="text-[11px] text-zinc-600">No capabilities enabled</span>
                  )}
                </div>
              </div>

              {/* Input */}
              <div className="p-3 border-t border-zinc-800">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={previewInput}
                    onChange={(e) => setPreviewInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handlePreviewSend()}
                    placeholder="Test a message..."
                    className="flex-1 px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-md text-[13px] text-white placeholder-zinc-600 focus:border-zinc-600 focus:outline-none transition-colors"
                  />
                  <button
                    onClick={handlePreviewSend}
                    className="p-2 bg-white text-black rounded-md hover:bg-zinc-200 transition-colors"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Model Selector Modal */}
      {showModelSelector && (
        <ModelSelectorModal
          providers={getFilteredProviders()}
          models={dbModels}
          selectedProviderId={config.provider_id}
          selectedModelId={config.model_id}
          onSelect={(providerId, modelId) => {
            updateConfig('provider_id', providerId);
            updateConfig('model_id', modelId);
            setShowModelSelector(false);
          }}
          onClose={() => setShowModelSelector(false)}
        />
      )}
    </div>
  );
}

// ==================== Model Selector Modal (DB-Driven) ====================

function ModelSelectorModal({
  providers,
  models,
  selectedProviderId,
  selectedModelId,
  onSelect,
  onClose,
}: {
  providers: AIProvider[];
  models: AIModel[];
  selectedProviderId: string;
  selectedModelId: string;
  onSelect: (providerId: string, modelId: string) => void;
  onClose: () => void;
}) {
  const [activeProvider, setActiveProvider] = useState(selectedProviderId || providers[0]?.name || '');

  const currentProvider = providers.find(p => p.name === activeProvider);
  const providerModels = currentProvider
    ? models.filter(m => m.provider_id === currentProvider.id && m.status === 'active')
        .sort((a, b) => (a.sort_order ?? 100) - (b.sort_order ?? 100))
    : [];

  const getBadgeColor = (badge?: string) => {
    if (!badge) return '';
    const b = badge.toUpperCase();
    if (b.includes('BEST') || b.includes('RECOMMENDED')) return 'bg-emerald-500/20 text-emerald-400';
    if (b.includes('FAST') || b.includes('EFFICIENT')) return 'bg-yellow-500/20 text-yellow-400';
    if (b.includes('NEW')) return 'bg-blue-500/20 text-blue-400';
    if (b.includes('REASON')) return 'bg-purple-500/20 text-purple-400';
    return 'bg-zinc-500/20 text-zinc-400';
  };

  const getCapabilityTags = (model: AIModel): string[] => {
    const tags: string[] = [];
    if (model.supports_tools) tags.push('Tools');
    if (model.supports_vision) tags.push('Vision');
    if (model.supports_audio) tags.push('Audio');
    if (model.supports_streaming) tags.push('Streaming');
    if (model.supports_json_mode) tags.push('JSON');
    if (model.is_reasoning_model) tags.push('Reasoning');
    return tags;
  };

  const formatPrice = (price?: number) => {
    if (price === undefined || price === null) return null;
    return `$${Number(price).toFixed(2)}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="bg-[#18181b] border border-zinc-800 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <h2 className="text-[15px] font-semibold text-white">Select Model</h2>
          <button onClick={onClose} className="p-1 hover:bg-zinc-800 rounded transition-colors">
            <X className="w-5 h-5 text-zinc-400" />
          </button>
        </div>

        {/* Provider Tabs */}
        <div className="flex border-b border-zinc-800 overflow-x-auto">
          {providers.map(provider => (
            <button
              key={provider.id}
              onClick={() => setActiveProvider(provider.name)}
              className={`flex-shrink-0 px-4 py-3 text-[13px] font-medium transition-colors ${
                activeProvider === provider.name
                  ? 'text-white border-b-2 border-white'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {provider.display_name}
            </button>
          ))}
        </div>

        {/* Models List */}
        <div className="p-4 overflow-y-auto max-h-[50vh]">
          {providerModels.length === 0 ? (
            <div className="text-center py-8">
              <Brain className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
              <p className="text-[13px] text-zinc-500">No models available for this provider</p>
            </div>
          ) : (
            <div className="space-y-2">
              {providerModels.map(model => {
                const isSelected = selectedModelId === model.model_id;
                const tags = getCapabilityTags(model);

                return (
                  <button
                    key={model.id}
                    onClick={() => onSelect(activeProvider, model.model_id)}
                    className={`w-full p-4 rounded-lg border text-left transition-all ${
                      isSelected
                        ? 'border-white bg-white/5'
                        : 'border-zinc-800 hover:border-zinc-700 bg-zinc-900/50'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-[14px] font-medium text-white truncate">{model.display_name}</p>
                          {model.badge && (
                            <span className={`px-2 py-0.5 text-[10px] font-medium rounded flex-shrink-0 ${getBadgeColor(model.badge)}`}>
                              {model.badge}
                            </span>
                          )}
                        </div>
                        <p className="text-[12px] text-zinc-500 mt-1">
                          {model.context_window.toLocaleString()} context
                          {model.max_output_tokens && ` · ${model.max_output_tokens.toLocaleString()} max output`}
                          {formatPrice(model.input_price_per_1m) && ` · ${formatPrice(model.input_price_per_1m)}/1M input`}
                        </p>
                        {tags.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {tags.map(tag => (
                              <span key={tag} className="px-2 py-0.5 bg-zinc-800 text-zinc-400 text-[10px] rounded">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      {isSelected && (
                        <div className="w-5 h-5 rounded-full bg-white flex items-center justify-center flex-shrink-0 ml-3">
                          <Check className="w-3 h-3 text-black" />
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-4 border-t border-zinc-800">
          <button onClick={onClose} className="px-4 py-2 text-[13px] text-zinc-400 hover:text-white transition-colors">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
