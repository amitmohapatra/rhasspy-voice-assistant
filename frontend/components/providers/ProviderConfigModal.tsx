'use client';

import { useState, useEffect } from 'react';

interface ProviderInfo {
  name: string;
  display_name: string;
  description: string;
  requires_api_key: boolean;
}

interface ProviderModel {
  id: string;
  name: string;
  description?: string;
  dimensions?: number;
}

interface ProviderConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  provider: ProviderInfo | null;
  providerType: string;
  onSave: (config: ProviderConfiguration) => void;
  initialConfig?: ProviderConfiguration;
}

export interface ProviderConfiguration {
  provider_name: string;
  provider_type: string;
  api_key?: string;
  model?: string;
  settings: Record<string, any>;
}

export function ProviderConfigModal({
  isOpen,
  onClose,
  provider,
  providerType,
  onSave,
  initialConfig,
}: ProviderConfigModalProps) {
  const [apiKey, setApiKey] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [models, setModels] = useState<ProviderModel[]>([]);
  const [settingsSchema, setSettingsSchema] = useState<any>(null);
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    if (provider && isOpen) {
      loadProviderDetails();
      if (initialConfig) {
        setApiKey(initialConfig.api_key || '');
        setSelectedModel(initialConfig.model || '');
        setSettings(initialConfig.settings || {});
      }
    }
  }, [provider, isOpen]);

  const loadProviderDetails = async () => {
    if (!provider) return;

    setIsLoading(true);
    try {
      const [modelsRes, settingsRes] = await Promise.all([
        fetch(`/api/v1/providers/${providerType}/${provider.name}/models`),
        fetch(`/api/v1/providers/${providerType}/${provider.name}/settings`),
      ]);

      if (modelsRes.ok) {
        const modelsData = await modelsRes.json();
        setModels(modelsData);
        if (modelsData.length > 0 && !selectedModel) {
          setSelectedModel(modelsData[0].id);
        }
      }

      if (settingsRes.ok) {
        const settingsData = await settingsRes.json();
        setSettingsSchema(settingsData.schema_json);
        // Initialize settings with defaults
        const defaults: Record<string, any> = {};
        const props = settingsData.schema_json?.properties || {};
        for (const [key, prop] of Object.entries(props) as [string, any][]) {
          if (prop.default !== undefined) {
            defaults[key] = prop.default;
          }
        }
        setSettings((prev) => ({ ...defaults, ...prev }));
      }
    } catch (error) {
      console.error('Failed to load provider details:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestConnection = async () => {
    if (!provider) return;

    setIsTesting(true);
    setTestResult(null);

    try {
      const res = await fetch('/api/v1/providers/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider_type: providerType,
          provider_name: provider.name,
          api_key: apiKey || undefined,
          model: selectedModel || undefined,
          settings,
        }),
      });

      const result = await res.json();
      setTestResult(result);
    } catch (error) {
      setTestResult({
        success: false,
        message: error instanceof Error ? error.message : 'Connection test failed',
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = () => {
    if (!provider) return;

    onSave({
      provider_name: provider.name,
      provider_type: providerType,
      api_key: apiKey || undefined,
      model: selectedModel || undefined,
      settings,
    });
    onClose();
  };

  const renderSettingsField = (key: string, schema: any) => {
    const value = settings[key];

    if (schema.enum) {
      return (
        <select
          value={value ?? schema.default ?? ''}
          onChange={(e) => setSettings((prev) => ({ ...prev, [key]: e.target.value }))}
          className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {schema.enum.map((opt: string) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      );
    }

    if (schema.type === 'boolean') {
      return (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={value ?? schema.default ?? false}
            onChange={(e) => setSettings((prev) => ({ ...prev, [key]: e.target.checked }))}
            className="w-4 h-4 rounded border-gray-600 text-blue-500 focus:ring-blue-500 bg-gray-700"
          />
          <span className="text-gray-300">{schema.description}</span>
        </label>
      );
    }

    if (schema.type === 'integer' || schema.type === 'number') {
      return (
        <input
          type="number"
          value={value ?? schema.default ?? ''}
          onChange={(e) => setSettings((prev) => ({ ...prev, [key]: parseFloat(e.target.value) }))}
          className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      );
    }

    return (
      <input
        type="text"
        value={value ?? schema.default ?? ''}
        onChange={(e) => setSettings((prev) => ({ ...prev, [key]: e.target.value }))}
        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    );
  };

  if (!isOpen || !provider) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-gray-800 rounded-xl w-full max-w-lg max-h-[90vh] overflow-hidden shadow-xl">
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white">
            Configure {provider.display_name}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-gray-700 text-gray-400 hover:text-white"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="p-4 overflow-y-auto max-h-[calc(90vh-140px)] space-y-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          ) : (
            <>
              {provider.requires_api_key && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    API Key
                  </label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Enter your API key"
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}

              {models.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Model
                  </label>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {models.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name}
                        {model.dimensions ? ` (${model.dimensions}d)` : ''}
                      </option>
                    ))}
                  </select>
                  {models.find((m) => m.id === selectedModel)?.description && (
                    <p className="mt-1 text-xs text-gray-500">
                      {models.find((m) => m.id === selectedModel)?.description}
                    </p>
                  )}
                </div>
              )}

              {settingsSchema?.properties && Object.keys(settingsSchema.properties).length > 0 && (
                <div className="border-t border-gray-700 pt-4">
                  <h3 className="text-sm font-medium text-gray-300 mb-3">Advanced Settings</h3>
                  <div className="space-y-3">
                    {Object.entries(settingsSchema.properties).map(([key, schema]: [string, any]) => (
                      <div key={key}>
                        {schema.type !== 'boolean' && (
                          <label className="block text-sm font-medium text-gray-400 mb-1">
                            {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                          </label>
                        )}
                        {renderSettingsField(key, schema)}
                        {schema.type !== 'boolean' && schema.description && (
                          <p className="mt-1 text-xs text-gray-500">{schema.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {testResult && (
                <div
                  className={`p-3 rounded-md ${
                    testResult.success
                      ? 'bg-green-900/50 border border-green-700'
                      : 'bg-red-900/50 border border-red-700'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {testResult.success ? (
                      <svg className="w-5 h-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                      </svg>
                    )}
                    <span className={testResult.success ? 'text-green-300' : 'text-red-300'}>
                      {testResult.message}
                    </span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="flex items-center justify-between p-4 border-t border-gray-700 bg-gray-800/50">
          <button
            onClick={handleTestConnection}
            disabled={isTesting || isLoading}
            className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white bg-gray-700 hover:bg-gray-600 rounded-md transition-colors disabled:opacity-50"
          >
            {isTesting ? (
              <span className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current"></div>
                Testing...
              </span>
            ) : (
              'Test Connection'
            )}
          </button>

          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors disabled:opacity-50"
            >
              Save Configuration
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
