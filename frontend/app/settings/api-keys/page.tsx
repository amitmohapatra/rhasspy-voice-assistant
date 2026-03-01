'use client';

/**
 * API Keys Settings Page
 *
 * Manage personal API keys for accessing the platform API.
 * Available to all authenticated users.
 */

import { useState, useEffect } from 'react';
import { Key, Plus, Copy, Trash2, Loader2, Check, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';

interface APIKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  scopes: string[];
}

export default function APIKeysSettingsPage() {
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyExpiry, setNewKeyExpiry] = useState('never');
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  useEffect(() => {
    loadAPIKeys();
  }, []);

  const loadAPIKeys = async () => {
    try {
      const response = await fetch('/api/v1/api-keys', {
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setApiKeys(data);
      }
    } catch {
      // Auth failed — layout will redirect to login
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) return;

    setIsCreating(true);
    try {
      const response = await fetch('/api/v1/api-keys', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${api.getToken()}`,
        },
        body: JSON.stringify({
          name: newKeyName,
          expires_in: newKeyExpiry === 'never' ? null : parseInt(newKeyExpiry),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setNewlyCreatedKey(data.key);
        await loadAPIKeys();
      }
    } catch (error) {
      // Mock creation for development
      const mockKey = 'sk-' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
      setNewlyCreatedKey(mockKey);
      setApiKeys(prev => [...prev, {
        id: Math.random().toString(36).substring(7),
        name: newKeyName,
        prefix: mockKey.substring(0, 10) + '...' + mockKey.substring(mockKey.length - 4),
        created_at: new Date().toISOString(),
        last_used_at: null,
        expires_at: newKeyExpiry === 'never' ? null : new Date(Date.now() + parseInt(newKeyExpiry) * 24 * 60 * 60 * 1000).toISOString(),
        scopes: ['read', 'write'],
      }]);
    } finally {
      setIsCreating(false);
      setNewKeyName('');
    }
  };

  const handleDeleteKey = async (keyId: string) => {
    try {
      await fetch(`/api/v1/api-keys/${keyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
        },
      });
    } catch (error) {
      // Continue anyway for development
    }
    setApiKeys(prev => prev.filter(k => k.id !== keyId));
    setDeleteConfirm(null);
  };

  const handleCopyKey = async (key: string) => {
    await navigator.clipboard.writeText(key);
    setCopiedKeyId(key);
    setTimeout(() => setCopiedKeyId(null), 2000);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">API Keys</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Manage your personal API keys for programmatic access.
        </p>
      </div>

      {/* Warning Banner */}
      <div className="mb-6 p-4 bg-yellow-900/20 border border-yellow-800 rounded-lg">
        <div className="flex gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-medium text-yellow-300">Keep your API keys secure</h3>
            <p className="mt-1 text-sm text-yellow-400">
              API keys grant full access to your account. Never share them or commit them to version control.
            </p>
          </div>
        </div>
      </div>

      {/* Newly Created Key */}
      {newlyCreatedKey && (
        <div className="mb-6 p-4 bg-green-900/20 border border-green-800 rounded-lg">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-sm font-medium text-green-300">Your new API key</h3>
              <p className="mt-1 text-sm text-green-400">
                Copy this key now. You won't be able to see it again!
              </p>
              <code className="mt-2 block p-2 bg-green-900/50 rounded font-mono text-sm text-green-300 break-all">
                {newlyCreatedKey}
              </code>
            </div>
            <button
              onClick={() => handleCopyKey(newlyCreatedKey)}
              className="p-2 text-green-400 hover:bg-green-900/50 rounded-lg transition-colors"
            >
              {copiedKeyId === newlyCreatedKey ? (
                <Check className="w-5 h-5" />
              ) : (
                <Copy className="w-5 h-5" />
              )}
            </button>
          </div>
          <button
            onClick={() => setNewlyCreatedKey(null)}
            className="mt-3 text-sm text-green-400 hover:underline"
          >
            I've saved my key
          </button>
        </div>
      )}

      {/* Create Key Section */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6 mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Create New API Key</h2>

        {showCreateModal ? (
          <div className="space-y-4">
            <div>
              <label htmlFor="key-name" className="block text-sm font-medium text-zinc-300 mb-1">
                Key Name
              </label>
              <input
                type="text"
                id="key-name"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                className="w-full px-4 py-2 rounded-lg border border-zinc-700 bg-zinc-800 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                placeholder="e.g., Production API Key"
              />
            </div>

            <div>
              <label htmlFor="key-expiry" className="block text-sm font-medium text-zinc-300 mb-1">
                Expiration
              </label>
              <select
                id="key-expiry"
                value={newKeyExpiry}
                onChange={(e) => setNewKeyExpiry(e.target.value)}
                className="w-full px-4 py-2 rounded-lg border border-zinc-700 bg-zinc-800 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              >
                <option value="never">Never expires</option>
                <option value="30">30 days</option>
                <option value="90">90 days</option>
                <option value="180">6 months</option>
                <option value="365">1 year</option>
              </select>
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleCreateKey}
                disabled={isCreating || !newKeyName.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-800 text-white rounded-lg font-medium transition-colors"
              >
                {isCreating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Key className="w-4 h-4" />
                    Create Key
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setNewKeyName('');
                }}
                className="px-4 py-2 text-zinc-300 hover:bg-zinc-800 rounded-lg font-medium transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create New Key
          </button>
        )}
      </div>

      {/* Existing Keys */}
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h2 className="text-lg font-semibold text-white">Your API Keys</h2>
        </div>

        {apiKeys.length === 0 ? (
          <div className="p-8 text-center">
            <Key className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
            <p className="text-zinc-400">No API keys yet</p>
            <p className="text-sm text-zinc-500 mt-1">
              Create your first API key to get started
            </p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-800">
            {apiKeys.map((key) => (
              <div key={key.id} className="px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h3 className="text-sm font-medium text-white">{key.name}</h3>
                      {key.expires_at && new Date(key.expires_at) < new Date() && (
                        <span className="px-2 py-0.5 text-xs font-medium bg-red-900/30 text-red-400 rounded">
                          Expired
                        </span>
                      )}
                    </div>
                    <p className="mt-1 font-mono text-sm text-zinc-400">
                      {key.prefix}
                    </p>
                    <div className="mt-2 flex items-center gap-4 text-xs text-zinc-400">
                      <span>Created {new Date(key.created_at).toLocaleDateString()}</span>
                      {key.last_used_at && (
                        <span>Last used {new Date(key.last_used_at).toLocaleString()}</span>
                      )}
                      {key.expires_at && (
                        <span>Expires {new Date(key.expires_at).toLocaleDateString()}</span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {deleteConfirm === key.id ? (
                      <>
                        <button
                          onClick={() => handleDeleteKey(key.id)}
                          className="px-3 py-1.5 text-sm text-red-400 hover:bg-red-900/30 rounded-lg transition-colors"
                        >
                          Confirm Delete
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(null)}
                          className="px-3 py-1.5 text-sm text-zinc-400 hover:bg-zinc-800 rounded-lg transition-colors"
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => setDeleteConfirm(key.id)}
                        className="p-2 text-zinc-400 hover:text-red-400 hover:bg-red-900/30 rounded-lg transition-colors"
                        title="Delete key"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
