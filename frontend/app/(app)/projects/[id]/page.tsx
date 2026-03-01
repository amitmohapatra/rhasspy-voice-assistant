'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ProviderSelector, ProviderConfiguration } from '@/components/providers';

interface Project {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  icon: string | null;
  color: string | null;
  provider_config: Record<string, ProviderConfiguration>;
  settings: Record<string, any>;
}

interface Secret {
  id: string;
  key: string;
  description: string | null;
  category: string;
  used_by: string | null;
  is_required: boolean;
  is_set: boolean;
}

interface RequiredSecret {
  key: string;
  description: string;
  category: string;
  is_set: boolean;
  used_by: string;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [requiredSecrets, setRequiredSecrets] = useState<RequiredSecret[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'providers' | 'secrets' | 'assistants'>('overview');
  const [isLoading, setIsLoading] = useState(true);

  // Secret modal state
  const [secretModalOpen, setSecretModalOpen] = useState(false);
  const [editingSecret, setEditingSecret] = useState<{ key: string; value: string; description: string }>({
    key: '',
    value: '',
    description: '',
  });

  useEffect(() => {
    loadProject();
  }, [projectId]);

  const loadProject = async () => {
    try {
      const [projectRes, secretsRes, requiredRes] = await Promise.all([
        fetch(`/api/v1/projects/${projectId}`),
        fetch(`/api/v1/projects/${projectId}/secrets`),
        fetch(`/api/v1/projects/${projectId}/secrets/required`),
      ]);

      if (projectRes.ok) setProject(await projectRes.json());
      if (secretsRes.ok) setSecrets(await secretsRes.json());
      if (requiredRes.ok) setRequiredSecrets(await requiredRes.json());
    } catch (error) {
      console.error('Failed to load project:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleProviderChange = async (type: string, provider: string, config: ProviderConfiguration) => {
    if (!project) return;

    const newConfig = {
      ...project.provider_config,
      [type]: config,
    };

    try {
      const res = await fetch(`/api/v1/projects/${projectId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider_config: newConfig }),
      });

      if (res.ok) {
        setProject({ ...project, provider_config: newConfig });
        // Reload required secrets
        const requiredRes = await fetch(`/api/v1/projects/${projectId}/secrets/required`);
        if (requiredRes.ok) setRequiredSecrets(await requiredRes.json());
      }
    } catch (error) {
      console.error('Failed to update provider:', error);
    }
  };

  const handleSaveSecret = async () => {
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/secrets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingSecret),
      });

      if (res.ok) {
        setSecretModalOpen(false);
        setEditingSecret({ key: '', value: '', description: '' });
        // Reload secrets
        const [secretsRes, requiredRes] = await Promise.all([
          fetch(`/api/v1/projects/${projectId}/secrets`),
          fetch(`/api/v1/projects/${projectId}/secrets/required`),
        ]);
        if (secretsRes.ok) setSecrets(await secretsRes.json());
        if (requiredRes.ok) setRequiredSecrets(await requiredRes.json());
      }
    } catch (error) {
      console.error('Failed to save secret:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-white mb-2">Project not found</h2>
          <Link href="/projects" className="text-blue-400 hover:text-blue-300">
            Back to Projects
          </Link>
        </div>
      </div>
    );
  }

  const missingSecrets = requiredSecrets.filter((s) => !s.is_set);

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link href="/projects" className="text-gray-400 hover:text-white">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
              </Link>
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-lg"
                style={{ backgroundColor: project.color || '#3B82F6' }}
              >
                {project.icon || '📁'}
              </div>
              <h1 className="text-xl font-semibold text-white">{project.name}</h1>
            </div>
          </div>
        </div>
      </header>

      {/* Missing Secrets Warning */}
      {missingSecrets.length > 0 && (
        <div className="bg-yellow-900/30 border-b border-yellow-700/50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <span className="text-yellow-300 text-sm">
                {missingSecrets.length} API key(s) need to be configured
              </span>
              <button
                onClick={() => setActiveTab('secrets')}
                className="ml-auto text-yellow-400 hover:text-yellow-300 text-sm underline"
              >
                Configure Now
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Tabs */}
        <div className="border-b border-gray-700 mb-8">
          <nav className="flex gap-8">
            {[
              { id: 'overview', label: 'Overview' },
              { id: 'providers', label: 'AI Providers' },
              { id: 'secrets', label: 'Secrets & API Keys' },
              { id: 'assistants', label: 'Assistants' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300'
                }`}
              >
                {tab.label}
                {tab.id === 'secrets' && missingSecrets.length > 0 && (
                  <span className="ml-2 px-1.5 py-0.5 text-xs bg-yellow-600 text-white rounded-full">
                    {missingSecrets.length}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-6">
              <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
                <h2 className="text-lg font-semibold text-white mb-4">Project Details</h2>
                <div className="space-y-4">
                  <div>
                    <label className="text-sm text-gray-400">Description</label>
                    <p className="text-white">{project.description || 'No description'}</p>
                  </div>
                </div>
              </div>

              <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
                <h2 className="text-lg font-semibold text-white mb-4">Configured Providers</h2>
                <div className="grid grid-cols-2 gap-4">
                  {['llm', 'stt', 'tts', 'embeddings', 'vectorstore'].map((type) => {
                    const config = project.provider_config[type];
                    return (
                      <div key={type} className="p-3 bg-gray-700/50 rounded-lg">
                        <span className="text-xs text-gray-400 uppercase">{type}</span>
                        <p className="text-white font-medium">
                          {config?.provider_name || 'Not configured'}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
                <h2 className="text-lg font-semibold text-white mb-4">Quick Actions</h2>
                <div className="space-y-2">
                  <Link
                    href={`/knowledge-bases?project=${projectId}`}
                    className="block w-full p-3 bg-gray-700/50 hover:bg-gray-700 rounded-lg text-white text-left transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                      </svg>
                      Create Knowledge Base
                    </span>
                  </Link>
                  <Link
                    href={`/tools?project=${projectId}`}
                    className="block w-full p-3 bg-gray-700/50 hover:bg-gray-700 rounded-lg text-white text-left transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      Configure Tools
                    </span>
                  </Link>
                  <Link
                    href={`/assistants/new?project=${projectId}`}
                    className="block w-full p-3 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-600/30 rounded-lg text-blue-400 text-left transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      Create Assistant
                    </span>
                  </Link>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Providers Tab */}
        {activeTab === 'providers' && (
          <div className="space-y-8">
            {['llm', 'stt', 'tts', 'embeddings', 'vectorstore'].map((type) => (
              <div key={type} className="p-6 bg-gray-800/50 rounded-xl border border-gray-700">
                <ProviderSelector
                  providerType={type as any}
                  selectedProvider={project.provider_config[type]?.provider_name}
                  configuration={project.provider_config[type]}
                  onProviderChange={(provider, config) => handleProviderChange(type, provider, config)}
                />
              </div>
            ))}
          </div>
        )}

        {/* Secrets Tab */}
        {activeTab === 'secrets' && (
          <div className="space-y-6">
            {/* Required Secrets */}
            {requiredSecrets.length > 0 && (
              <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
                <h2 className="text-lg font-semibold text-white mb-4">Required API Keys</h2>
                <p className="text-gray-400 text-sm mb-4">
                  These API keys are required for your configured providers to work.
                </p>
                <div className="space-y-3">
                  {requiredSecrets.map((secret) => (
                    <div
                      key={secret.key}
                      className={`p-4 rounded-lg border ${
                        secret.is_set
                          ? 'bg-green-900/20 border-green-700/50'
                          : 'bg-yellow-900/20 border-yellow-700/50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <code className="text-sm font-mono text-white">{secret.key}</code>
                            {secret.is_set ? (
                              <span className="px-2 py-0.5 text-xs bg-green-600 text-white rounded">
                                Configured
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 text-xs bg-yellow-600 text-white rounded">
                                Missing
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-400 mt-1">{secret.description}</p>
                          <p className="text-xs text-gray-500 mt-1">Used by: {secret.used_by}</p>
                        </div>
                        <button
                          onClick={() => {
                            setEditingSecret({ key: secret.key, value: '', description: secret.description });
                            setSecretModalOpen(true);
                          }}
                          className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded transition-colors"
                        >
                          {secret.is_set ? 'Update' : 'Set Value'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* All Secrets */}
            <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-white">All Secrets</h2>
                <button
                  onClick={() => {
                    setEditingSecret({ key: '', value: '', description: '' });
                    setSecretModalOpen(true);
                  }}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded transition-colors flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add Secret
                </button>
              </div>

              {secrets.length === 0 ? (
                <p className="text-gray-500 text-sm">No secrets configured yet.</p>
              ) : (
                <div className="space-y-2">
                  {secrets.map((secret) => (
                    <div
                      key={secret.id}
                      className="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg"
                    >
                      <div>
                        <code className="text-sm font-mono text-white">{secret.key}</code>
                        <p className="text-xs text-gray-500">{secret.category}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${secret.is_set ? 'bg-green-500' : 'bg-gray-500'}`}></span>
                        <button
                          onClick={() => {
                            setEditingSecret({ key: secret.key, value: '', description: secret.description || '' });
                            setSecretModalOpen(true);
                          }}
                          className="text-gray-400 hover:text-white"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Environment Variables Reference */}
            <div className="bg-blue-900/20 rounded-xl p-6 border border-blue-700/30">
              <h3 className="text-blue-400 font-medium mb-2">Environment Variables</h3>
              <p className="text-blue-300/70 text-sm">
                Alternatively, you can set these secrets as environment variables on your server.
                Secrets configured here will override environment variables.
              </p>
            </div>
          </div>
        )}

        {/* Assistants Tab */}
        {activeTab === 'assistants' && (
          <div className="text-center py-12">
            <p className="text-gray-400 mb-4">No assistants in this project yet.</p>
            <Link
              href={`/assistants/new?project=${projectId}`}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create Assistant
            </Link>
          </div>
        )}
      </div>

      {/* Secret Modal */}
      {secretModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-gray-800 rounded-xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-white mb-4">
              {editingSecret.key ? `Set ${editingSecret.key}` : 'Add Secret'}
            </h2>
            <div className="space-y-4">
              {!editingSecret.key && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">Key Name</label>
                  <input
                    type="text"
                    value={editingSecret.key}
                    onChange={(e) => setEditingSecret({ ...editingSecret, key: e.target.value.toUpperCase() })}
                    placeholder="MY_API_KEY"
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white font-mono placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Value</label>
                <input
                  type="password"
                  value={editingSecret.value}
                  onChange={(e) => setEditingSecret({ ...editingSecret, value: e.target.value })}
                  placeholder="Enter secret value"
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Description</label>
                <input
                  type="text"
                  value={editingSecret.description}
                  onChange={(e) => setEditingSecret({ ...editingSecret, description: e.target.value })}
                  placeholder="What is this secret for?"
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setSecretModalOpen(false)}
                className="px-4 py-2 text-gray-300 hover:text-white bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveSecret}
                disabled={!editingSecret.key || !editingSecret.value}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors disabled:opacity-50"
              >
                Save Secret
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
