'use client';

import { useState, useEffect } from 'react';
import { ProviderCard, ProviderCardSkeleton } from './ProviderCard';
import { ProviderConfigModal, ProviderConfiguration } from './ProviderConfigModal';

interface ProviderInfo {
  name: string;
  display_name: string;
  description: string;
  requires_api_key: boolean;
}

interface ProviderSelectorProps {
  providerType: 'llm' | 'stt' | 'tts' | 'embeddings' | 'vectorstore';
  selectedProvider?: string;
  onProviderChange?: (provider: string, config: ProviderConfiguration) => void;
  configuration?: ProviderConfiguration;
  className?: string;
}

const PROVIDER_TYPE_LABELS: Record<string, string> = {
  llm: 'Language Model',
  stt: 'Speech-to-Text',
  tts: 'Text-to-Speech',
  embeddings: 'Embeddings',
  vectorstore: 'Vector Store',
};

const PROVIDER_TYPE_ICONS: Record<string, JSX.Element> = {
  llm: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  ),
  stt: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
    </svg>
  ),
  tts: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
    </svg>
  ),
  embeddings: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
    </svg>
  ),
  vectorstore: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
  ),
};

export function ProviderSelector({
  providerType,
  selectedProvider,
  onProviderChange,
  configuration,
  className = '',
}: ProviderSelectorProps) {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [selectedForConfig, setSelectedForConfig] = useState<ProviderInfo | null>(null);
  const [currentConfig, setCurrentConfig] = useState<ProviderConfiguration | undefined>(configuration);

  useEffect(() => {
    loadProviders();
  }, [providerType]);

  const loadProviders = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/v1/providers/${providerType}`);
      if (!res.ok) throw new Error('Failed to load providers');
      const data = await res.json();
      setProviders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load providers');
    } finally {
      setIsLoading(false);
    }
  };

  const handleProviderSelect = (provider: ProviderInfo) => {
    if (provider.name === selectedProvider) return;

    // If provider requires config, open modal
    if (provider.requires_api_key) {
      setSelectedForConfig(provider);
      setConfigModalOpen(true);
    } else {
      // Select directly with default config
      onProviderChange?.(provider.name, {
        provider_name: provider.name,
        provider_type: providerType,
        settings: {},
      });
    }
  };

  const handleConfigure = (provider: ProviderInfo) => {
    setSelectedForConfig(provider);
    setCurrentConfig(
      provider.name === selectedProvider ? configuration : undefined
    );
    setConfigModalOpen(true);
  };

  const handleSaveConfig = (config: ProviderConfiguration) => {
    setCurrentConfig(config);
    onProviderChange?.(config.provider_name, config);
    setConfigModalOpen(false);
  };

  return (
    <div className={className}>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-blue-400">
          {PROVIDER_TYPE_ICONS[providerType]}
        </span>
        <h3 className="text-lg font-semibold text-white">
          {PROVIDER_TYPE_LABELS[providerType]}
        </h3>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/50 border border-red-700 rounded-md">
          <p className="text-red-300 text-sm">{error}</p>
          <button
            onClick={loadProviders}
            className="mt-2 text-sm text-red-400 hover:text-red-300 underline"
          >
            Retry
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {isLoading ? (
          <>
            <ProviderCardSkeleton />
            <ProviderCardSkeleton />
            <ProviderCardSkeleton />
          </>
        ) : (
          providers.map((provider) => (
            <ProviderCard
              key={provider.name}
              provider={provider}
              providerType={providerType}
              isSelected={provider.name === selectedProvider}
              onSelect={handleProviderSelect}
              onConfigure={handleConfigure}
            />
          ))
        )}
      </div>

      <ProviderConfigModal
        isOpen={configModalOpen}
        onClose={() => setConfigModalOpen(false)}
        provider={selectedForConfig}
        providerType={providerType}
        onSave={handleSaveConfig}
        initialConfig={currentConfig}
      />
    </div>
  );
}
