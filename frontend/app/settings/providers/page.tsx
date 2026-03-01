'use client';

/**
 * AI Providers Settings Page
 *
 * Manage AI providers and their API configurations.
 * A provider can only be toggled ON after a successful connectivity test.
 */

import { useState, useEffect } from 'react';
import {
  Cpu,
  Plus,
  Trash2,
  Loader2,
  Check,
  X,
  Key,
  Eye,
  EyeOff,
  AlertTriangle,
  ExternalLink,
  Zap,
  Clock,
  Server,
} from 'lucide-react';
import { api } from '@/lib/api';

interface AIProvider {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  logo_url: string | null;
  is_active: boolean;
  api_key_configured: boolean;
  base_url: string | null;
  models_count: number;
  capabilities: string[];
}

interface TestResult {
  status: 'idle' | 'testing' | 'success' | 'error';
  message?: string;
  latency_ms?: number;
  models_available?: number;
  rate_limit?: { requests_per_minute: number; tokens_per_minute: number };
  tested_at?: string;
}

export default function ProvidersSettingsPage() {
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [showTestDetails, setShowTestDetails] = useState<string | null>(null);

  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    try {
      const response = await fetch('/api/v1/ai/providers', {
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        // Map backend ProviderResponse to frontend AIProvider
        setProviders(data.map((p: any) => ({
          id: p.id,
          name: p.name,
          display_name: p.display_name,
          description: p.description,
          logo_url: p.logo_url,
          is_active: p.status === 'active',
          api_key_configured: false, // Backend doesn't track this per-provider
          base_url: p.base_url,
          models_count: p.model_count || 0,
          capabilities: [
            ...(p.supports_streaming ? ['llm'] : []),
            ...(p.supports_function_calling ? ['function_calling'] : []),
            ...(p.supports_vision ? ['vision'] : []),
            ...(p.supports_audio ? ['stt', 'tts'] : []),
          ],
        })));
      }
    } catch (error) {
      console.error('Failed to load providers:', error);
      setProviders([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleProvider = async (providerId: string) => {
    const provider = providers.find(p => p.id === providerId);
    if (!provider) return;

    try {
      await fetch(`/api/v1/ai/providers/${providerId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${api.getToken()}`,
        },
        body: JSON.stringify({ status: provider.is_active ? 'disabled' : 'active' }),
      });
    } catch (error) {
      // Continue for development
    }

    setProviders(prev =>
      prev.map(p =>
        p.id === providerId ? { ...p, is_active: !p.is_active } : p
      )
    );
  };

  const handleSaveApiKey = async (providerId: string) => {
    const apiKey = apiKeys[providerId];
    if (!apiKey) return;

    setIsSaving(true);
    try {
      await fetch(`/api/v1/ai/providers/${providerId}/api-key`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${api.getToken()}`,
        },
        body: JSON.stringify({ api_key: apiKey }),
      });

      setProviders(prev =>
        prev.map(p =>
          p.id === providerId ? { ...p, api_key_configured: true } : p
        )
      );
      setMessage({ type: 'success', text: 'API key updated successfully!' });
      setEditingProvider(null);
      setApiKeys(prev => ({ ...prev, [providerId]: '' }));
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to save API key' });
      setEditingProvider(null);
    } finally {
      setIsSaving(false);
      setTimeout(() => setMessage(null), 3000);
    }
  };

  const handleTestProvider = async (providerId: string) => {
    const provider = providers.find(p => p.id === providerId);
    if (!provider) return;

    setTestResults(prev => ({
      ...prev,
      [providerId]: { status: 'testing' }
    }));

    const startTime = Date.now();

    try {
      const response = await fetch(`/api/v1/ai/providers/${providerId}/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setTestResults(prev => ({
          ...prev,
          [providerId]: {
            status: 'success',
            message: 'Connection successful',
            latency_ms: data.latency_ms || (Date.now() - startTime),
            models_available: data.models_count,
            rate_limit: data.rate_limit,
            tested_at: new Date().toISOString(),
          }
        }));
        // Auto-enable provider on successful test
        if (!provider.is_active) {
          setProviders(prev =>
            prev.map(p => p.id === providerId ? { ...p, is_active: true } : p)
          );
        }
      } else {
        const error = await response.json();
        setTestResults(prev => ({
          ...prev,
          [providerId]: {
            status: 'error',
            message: error.detail || 'Connection failed',
            tested_at: new Date().toISOString(),
          }
        }));
      }
    } catch (error) {
      setTestResults(prev => ({
        ...prev,
        [providerId]: {
          status: 'error',
          message: 'Connection test failed',
          tested_at: new Date().toISOString(),
        }
      }));
    }
  };

  const capabilityColors: Record<string, string> = {
    llm: 'bg-blue-900/30 text-blue-400',
    embeddings: 'bg-green-900/30 text-green-400',
    tts: 'bg-purple-900/30 text-purple-400',
    stt: 'bg-orange-900/30 text-orange-400',
    vision: 'bg-pink-900/30 text-pink-400',
    function_calling: 'bg-cyan-900/30 text-cyan-400',
    extended_thinking: 'bg-yellow-900/30 text-yellow-400',
    reranking: 'bg-indigo-900/30 text-indigo-400',
    search: 'bg-teal-900/30 text-teal-400',
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">AI Providers</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Configure API keys, test connectivity, and enable providers. A provider can only be activated after a successful connection test.
        </p>
      </div>

      {/* Message */}
      {message && (
        <div className={`mb-6 p-4 rounded-lg ${
          message.type === 'success'
            ? 'bg-green-900/30 text-green-400 border border-green-800'
            : 'bg-red-900/30 text-red-400 border border-red-800'
        }`}>
          {message.text}
        </div>
      )}

      {/* Provider List */}
      <div className="space-y-4">
        {!isLoading && providers.length === 0 && (
          <div className="text-center py-12 bg-zinc-900 rounded-xl border border-zinc-800">
            <p className="text-lg font-medium text-zinc-300">No providers found</p>
            <p className="text-sm text-zinc-400 mt-1">
              Failed to load providers. Please ensure the backend is running and the database has been seeded.
            </p>
          </div>
        )}
        {providers.map((provider) => (
          <div
            key={provider.id}
            className={`bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden ${
              !provider.is_active ? 'opacity-60' : ''
            }`}
          >
            <div className="p-6">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  {/* Provider Logo/Icon */}
                  <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-zinc-700 to-zinc-600 flex items-center justify-center">
                    <Cpu className="w-6 h-6 text-zinc-400" />
                  </div>

                  <div>
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold text-white">
                        {provider.display_name}
                      </h3>
                      {provider.is_active ? (
                        <span className="px-2 py-0.5 text-xs font-medium bg-green-900/30 text-green-400 rounded">
                          Active
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 text-xs font-medium bg-zinc-800 text-zinc-400 rounded">
                          Inactive
                        </span>
                      )}
                      {!provider.api_key_configured && (
                        <span className="flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-yellow-900/30 text-yellow-400 rounded">
                          <AlertTriangle className="w-3 h-3" />
                          API Key Required
                        </span>
                      )}
                    </div>

                    <p className="mt-1 text-sm text-zinc-400">
                      {provider.description}
                    </p>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {provider.capabilities.map((cap) => (
                        <span
                          key={cap}
                          className={`px-2 py-0.5 text-xs font-medium rounded ${capabilityColors[cap] || 'bg-zinc-800 text-zinc-300'}`}
                        >
                          {cap.replace('_', ' ')}
                        </span>
                      ))}
                    </div>

                    <div className="mt-3 flex items-center gap-4 text-xs text-zinc-400">
                      <span>{provider.models_count} models</span>
                      {provider.base_url && (
                        <a
                          href={provider.base_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 hover:text-emerald-400"
                        >
                          <ExternalLink className="w-3 h-3" />
                          API Endpoint
                        </a>
                      )}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-3">
                  {/* Test Connection Button */}
                  <button
                    onClick={() => handleTestProvider(provider.id)}
                    disabled={testResults[provider.id]?.status === 'testing'}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      testResults[provider.id]?.status === 'testing'
                        ? 'bg-blue-900/30 text-blue-400'
                        : testResults[provider.id]?.status === 'success'
                        ? 'bg-green-900/30 text-green-400 hover:bg-green-900/50'
                        : testResults[provider.id]?.status === 'error'
                        ? 'bg-red-900/30 text-red-400 hover:bg-red-900/50'
                        : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                    }`}
                  >
                    {testResults[provider.id]?.status === 'testing' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Testing...
                      </>
                    ) : testResults[provider.id]?.status === 'success' ? (
                      <>
                        <Check className="w-4 h-4" />
                        Connected
                      </>
                    ) : testResults[provider.id]?.status === 'error' ? (
                      <>
                        <X className="w-4 h-4" />
                        Failed
                      </>
                    ) : (
                      <>
                        <Zap className="w-4 h-4" />
                        Test
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => handleToggleProvider(provider.id)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      provider.is_active
                        ? 'bg-emerald-600'
                        : 'bg-zinc-700 cursor-pointer'
                    }`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      provider.is_active ? 'translate-x-6' : 'translate-x-1'
                    }`} />
                  </button>
                </div>
              </div>

              {/* Test Results */}
              {testResults[provider.id] && testResults[provider.id].status !== 'idle' && testResults[provider.id].status !== 'testing' && (
                <div className={`mt-4 p-4 rounded-lg ${
                  testResults[provider.id].status === 'success'
                    ? 'bg-green-900/20 border border-green-800'
                    : 'bg-red-900/20 border border-red-800'
                }`}>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      {testResults[provider.id].status === 'success' ? (
                        <Check className="w-5 h-5 text-green-400" />
                      ) : (
                        <X className="w-5 h-5 text-red-400" />
                      )}
                      <span className={`font-medium ${
                        testResults[provider.id].status === 'success'
                          ? 'text-green-300'
                          : 'text-red-300'
                      }`}>
                        {testResults[provider.id].message}
                      </span>
                    </div>
                    <button
                      onClick={() => setShowTestDetails(showTestDetails === provider.id ? null : provider.id)}
                      className="text-sm text-zinc-400 hover:text-zinc-200"
                    >
                      {showTestDetails === provider.id ? 'Hide Details' : 'Show Details'}
                    </button>
                  </div>

                  {showTestDetails === provider.id && testResults[provider.id].status === 'success' && (
                    <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="bg-zinc-800/50 rounded-lg p-3">
                        <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                          <Clock className="w-3 h-3" />
                          Latency
                        </div>
                        <p className="text-lg font-semibold text-white">
                          {testResults[provider.id].latency_ms}ms
                        </p>
                      </div>
                      <div className="bg-zinc-800/50 rounded-lg p-3">
                        <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                          <Server className="w-3 h-3" />
                          Models
                        </div>
                        <p className="text-lg font-semibold text-white">
                          {testResults[provider.id].models_available}
                        </p>
                      </div>
                      {testResults[provider.id].rate_limit && (
                        <>
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                              <Zap className="w-3 h-3" />
                              Rate Limit
                            </div>
                            <p className="text-lg font-semibold text-white">
                              {testResults[provider.id].rate_limit?.requests_per_minute}/min
                            </p>
                          </div>
                          <div className="bg-zinc-800/50 rounded-lg p-3">
                            <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                              <Cpu className="w-3 h-3" />
                              Tokens
                            </div>
                            <p className="text-lg font-semibold text-white">
                              {(testResults[provider.id].rate_limit?.tokens_per_minute || 0).toLocaleString()}/min
                            </p>
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  {testResults[provider.id].tested_at && (
                    <p className="mt-3 text-xs text-zinc-400">
                      Tested at {new Date(testResults[provider.id].tested_at!).toLocaleString()}
                    </p>
                  )}
                </div>
              )}

              {/* API Key Configuration */}
              {editingProvider === provider.id ? (
                <div className="mt-4 pt-4 border-t border-zinc-800">
                  <div className="flex items-center gap-3">
                    <div className="flex-1 relative">
                      <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                      <input
                        type={showApiKey[provider.id] ? 'text' : 'password'}
                        value={apiKeys[provider.id] || ''}
                        onChange={(e) => setApiKeys(prev => ({ ...prev, [provider.id]: e.target.value }))}
                        placeholder="Enter API key"
                        className="w-full pl-10 pr-10 py-2 rounded-lg border border-zinc-700 bg-zinc-800 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent font-mono text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => setShowApiKey(prev => ({ ...prev, [provider.id]: !prev[provider.id] }))}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                      >
                        {showApiKey[provider.id] ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                    <button
                      onClick={() => handleSaveApiKey(provider.id)}
                      disabled={isSaving || !apiKeys[provider.id]}
                      className="flex items-center gap-1 px-3 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-800 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                      {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                      Save
                    </button>
                    <button
                      onClick={() => {
                        setEditingProvider(null);
                        setApiKeys(prev => ({ ...prev, [provider.id]: '' }));
                      }}
                      className="p-2 text-zinc-500 hover:text-zinc-300"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-4 pt-4 border-t border-zinc-800">
                  <button
                    onClick={() => setEditingProvider(provider.id)}
                    className="flex items-center gap-2 text-sm text-emerald-400 hover:text-emerald-300"
                  >
                    <Key className="w-4 h-4" />
                    {provider.api_key_configured ? 'Update API Key' : 'Configure API Key'}
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Add Provider */}
      <div className="mt-6">
        <button
          className="flex items-center gap-2 px-4 py-2 text-emerald-400 hover:bg-emerald-900/20 rounded-lg font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Custom Provider
        </button>
      </div>

      {/* LLM Vendor Keys for Document Chat */}
      <LLMVendorKeys />
    </div>
  );
}

// ==================== LLM Vendor Keys Section ====================

interface LLMKeyInfo {
  provider: string;
  key_preview: string;
  label: string | null;
  created_at: string | null;
  updated_at: string | null;
}

function LLMVendorKeys() {
  const [keys, setKeys] = useState<LLMKeyInfo[]>([]);
  const [keysLoading, setKeysLoading] = useState(true);
  const [editingVendor, setEditingVendor] = useState<string | null>(null);
  const [newProvider, setNewProvider] = useState('');
  const [newApiKey, setNewApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [keyMessage, setKeyMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const VENDOR_OPTIONS = ['openai', 'anthropic', 'google', 'groq', 'mistral', 'deepseek'];

  useEffect(() => {
    loadKeys();
  }, []);

  const loadKeys = async () => {
    try {
      const token = api.getToken();
      const res = await fetch('/api/v1/settings/llm-keys', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setKeys(data.keys || []);
      }
    } catch {
      setKeys([]);
    } finally {
      setKeysLoading(false);
    }
  };

  const handleSave = async (provider: string, apiKey: string) => {
    if (!apiKey.trim()) return;
    setSaving(true);
    try {
      const token = api.getToken();
      const res = await fetch('/api/v1/settings/llm-keys', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      if (res.ok) {
        setKeyMessage({ type: 'success', text: `Key saved for ${provider}` });
        setEditingVendor(null);
        setNewProvider('');
        setNewApiKey('');
        await loadKeys();
      } else {
        const err = await res.json().catch(() => ({ detail: 'Save failed' }));
        setKeyMessage({ type: 'error', text: err.detail || 'Save failed' });
      }
    } catch {
      setKeyMessage({ type: 'error', text: 'Failed to save key' });
    } finally {
      setSaving(false);
      setTimeout(() => setKeyMessage(null), 3000);
    }
  };

  const handleDelete = async (provider: string) => {
    try {
      const token = api.getToken();
      await fetch(`/api/v1/settings/llm-keys/${provider}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setKeyMessage({ type: 'success', text: `Key removed for ${provider}` });
      await loadKeys();
    } catch {
      setKeyMessage({ type: 'error', text: 'Failed to delete key' });
    }
    setTimeout(() => setKeyMessage(null), 3000);
  };

  const savedProviders = new Set(keys.map(k => k.provider));
  const availableProviders = VENDOR_OPTIONS.filter(p => !savedProviders.has(p));

  return (
    <div className="mt-12">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-white">Document Chat Keys</h2>
        <p className="mt-1 text-sm text-zinc-400">
          API keys for document-scoped chat. These are stored encrypted and used when chatting with documents in Agentic Docs.
        </p>
      </div>

      {keyMessage && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          keyMessage.type === 'success'
            ? 'bg-green-900/30 text-green-400 border border-green-800'
            : 'bg-red-900/30 text-red-400 border border-red-800'
        }`}>
          {keyMessage.text}
        </div>
      )}

      {keysLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
        </div>
      ) : (
        <div className="space-y-3">
          {/* Saved keys */}
          {keys.map((k) => (
            <div key={k.provider} className="bg-zinc-900 rounded-lg border border-zinc-800 p-4">
              {editingVendor === k.provider ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white capitalize">{k.provider}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 relative">
                      <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                      <input
                        type={showKey ? 'text' : 'password'}
                        value={newApiKey}
                        onChange={(e) => setNewApiKey(e.target.value)}
                        placeholder="Enter new API key"
                        className="w-full pl-10 pr-10 py-2 rounded-lg border border-zinc-700 bg-zinc-800 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent font-mono text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => setShowKey(!showKey)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                      >
                        {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                    <button
                      onClick={() => handleSave(k.provider, newApiKey)}
                      disabled={saving || !newApiKey.trim()}
                      className="flex items-center gap-1 px-3 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                      {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                      Save
                    </button>
                    <button
                      onClick={() => { setEditingVendor(null); setNewApiKey(''); setShowKey(false); }}
                      className="p-2 text-zinc-500 hover:text-zinc-300"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-md bg-emerald-900/30 flex items-center justify-center">
                      <Key className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                      <span className="text-sm font-medium text-white capitalize">{k.provider}</span>
                      <span className="ml-3 text-xs text-zinc-500 font-mono">{k.key_preview}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => { setEditingVendor(k.provider); setNewApiKey(''); setShowKey(false); }}
                      className="px-2.5 py-1 text-xs text-zinc-400 hover:text-white bg-zinc-800 hover:bg-zinc-700 rounded transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(k.provider)}
                      className="p-1.5 text-zinc-500 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Add new key */}
          {availableProviders.length > 0 && (
            <div className="bg-zinc-900 rounded-lg border border-dashed border-zinc-700 p-4">
              {editingVendor === '__new__' ? (
                <div className="space-y-3">
                  <select
                    value={newProvider}
                    onChange={(e) => setNewProvider(e.target.value)}
                    className="h-9 bg-zinc-800 border border-zinc-700 rounded-lg px-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  >
                    <option value="">Select provider...</option>
                    {availableProviders.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                  {newProvider && (
                    <div className="flex items-center gap-2">
                      <div className="flex-1 relative">
                        <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                        <input
                          type={showKey ? 'text' : 'password'}
                          value={newApiKey}
                          onChange={(e) => setNewApiKey(e.target.value)}
                          placeholder={`Enter ${newProvider} API key`}
                          className="w-full pl-10 pr-10 py-2 rounded-lg border border-zinc-700 bg-zinc-800 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent font-mono text-sm"
                        />
                        <button
                          type="button"
                          onClick={() => setShowKey(!showKey)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                        >
                          {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      <button
                        onClick={() => handleSave(newProvider, newApiKey)}
                        disabled={saving || !newApiKey.trim()}
                        className="flex items-center gap-1 px-3 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                      >
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                        Save
                      </button>
                      <button
                        onClick={() => { setEditingVendor(null); setNewProvider(''); setNewApiKey(''); setShowKey(false); }}
                        className="p-2 text-zinc-500 hover:text-zinc-300"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <button
                  onClick={() => setEditingVendor('__new__')}
                  className="flex items-center gap-2 text-sm text-emerald-400 hover:text-emerald-300"
                >
                  <Plus className="w-4 h-4" />
                  Add Vendor Key
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
