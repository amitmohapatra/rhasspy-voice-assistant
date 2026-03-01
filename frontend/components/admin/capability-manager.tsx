'use client';

/**
 * Capability Manager Component
 *
 * Interface for managing model capabilities, vendor mappings,
 * and tool requirements. Configure what each model can do.
 *
 * Features:
 * - View/edit capability definitions
 * - Configure model capabilities (enable/disable features)
 * - Manage vendor-specific mappings
 * - Auto-detect capabilities for new models
 * - View capability matrix across models
 */

import { useState, useEffect, useCallback } from 'react';
import {
  FileSearch,
  Code,
  Globe,
  Image,
  Eye,
  Mic,
  Volume2,
  Video,
  Film,
  FunctionSquare,
  GitBranch,
  Braces,
  Brain,
  ListOrdered,
  FileText,
  Activity,
  Box,
  Monitor,
  Plug,
  Check,
  X,
  Settings,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Info,
  AlertTriangle,
  Sparkles,
  Zap,
} from 'lucide-react';
import { api } from '@/lib/api';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function apiGet<T>(endpoint: string): Promise<T> {
  const token = api.getToken();
  const res = await fetch(`${API_URL}${endpoint}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Request failed: ${res.statusText}`);
  return res.json();
}

async function apiPost<T>(endpoint: string, body?: unknown): Promise<T> {
  const token = api.getToken();
  const res = await fetch(`${API_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`Request failed: ${res.statusText}`);
  return res.json();
}

import type {
  CapabilityDefinition,
  ModelCapability,
  ModelCapabilitySummary,
  VendorCapabilityMapping,
  CapabilityType,
  SetModelCapabilityRequest,
} from '@/types/capability';
import type { AIModel, AIProvider } from '@/types/api';

// ==================== Icon Mapping ====================

const CAPABILITY_ICONS: Record<CapabilityType, React.ComponentType<{ className?: string }>> = {
  file_search: FileSearch,
  code_interpreter: Code,
  web_search: Globe,
  image_generation: Image,
  vision: Eye,
  audio_input: Mic,
  audio_output: Volume2,
  video_input: Video,
  video_output: Film,
  function_calling: FunctionSquare,
  parallel_functions: GitBranch,
  structured_output: Braces,
  extended_thinking: Brain,
  chain_of_thought: ListOrdered,
  long_context: FileText,
  streaming: Activity,
  artifacts: Box,
  computer_use: Monitor,
  mcp: Plug,
};

// ==================== Sub-Components ====================

interface CapabilityBadgeProps {
  capability: CapabilityType;
  isEnabled: boolean;
  isPremium?: boolean;
  isBeta?: boolean;
  onClick?: () => void;
}

function CapabilityBadge({
  capability,
  isEnabled,
  isPremium,
  isBeta,
  onClick,
}: CapabilityBadgeProps) {
  const Icon = CAPABILITY_ICONS[capability] || FunctionSquare;

  return (
    <button
      onClick={onClick}
      className={`
        inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
        transition-colors duration-200
        ${isEnabled
          ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
          : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
        }
        ${onClick ? 'cursor-pointer hover:opacity-80' : 'cursor-default'}
      `}
    >
      <Icon className="w-3 h-3" />
      <span className="capitalize">{capability.replace(/_/g, ' ')}</span>
      {isPremium && <Sparkles className="w-3 h-3 text-amber-500" />}
      {isBeta && <Zap className="w-3 h-3 text-purple-500" />}
      {isEnabled ? (
        <Check className="w-3 h-3" />
      ) : (
        <X className="w-3 h-3 opacity-50" />
      )}
    </button>
  );
}

interface ModelCapabilityCardProps {
  model: AIModel;
  capabilities: ModelCapability[];
  definitions: CapabilityDefinition[];
  onToggleCapability: (modelId: string, capability: CapabilityType, enabled: boolean) => void;
  onAutoDetect: (modelId: string) => void;
}

function ModelCapabilityCard({
  model,
  capabilities,
  definitions,
  onToggleCapability,
  onAutoDetect,
}: ModelCapabilityCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const enabledCaps = capabilities.filter(c => c.is_enabled);
  const disabledCaps = capabilities.filter(c => !c.is_enabled);

  return (
    <div className="border rounded-lg bg-white dark:bg-gray-900 dark:border-gray-700">
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-400" />
          )}
          <div>
            <h3 className="font-medium text-gray-900 dark:text-gray-100">
              {model.display_name || model.name}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {model.model_id} • {model.provider_display_name}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-sm text-gray-500">
            <span className="text-green-600 font-medium">{enabledCaps.length}</span>
            {' / '}
            <span>{enabledCaps.length + disabledCaps.length}</span>
            {' capabilities'}
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onAutoDetect(model.id);
            }}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            title="Auto-detect capabilities"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t dark:border-gray-700 p-4">
          {/* Enabled Capabilities */}
          <div className="mb-4">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Enabled Capabilities
            </h4>
            <div className="flex flex-wrap gap-2">
              {enabledCaps.length > 0 ? (
                enabledCaps.map(cap => {
                  const def = definitions.find(d => d.capability_type === cap.capability_type);
                  return (
                    <CapabilityBadge
                      key={cap.id}
                      capability={cap.capability_type}
                      isEnabled={true}
                      isPremium={def?.is_premium}
                      isBeta={def?.is_beta}
                      onClick={() => onToggleCapability(model.id, cap.capability_type, false)}
                    />
                  );
                })
              ) : (
                <span className="text-sm text-gray-400">No capabilities enabled</span>
              )}
            </div>
          </div>

          {/* Disabled/Available Capabilities */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Available to Enable
            </h4>
            <div className="flex flex-wrap gap-2">
              {definitions
                .filter(def => !enabledCaps.some(c => c.capability_type === def.capability_type))
                .map(def => (
                  <CapabilityBadge
                    key={def.capability_type}
                    capability={def.capability_type}
                    isEnabled={false}
                    isPremium={def.is_premium}
                    isBeta={def.is_beta}
                    onClick={() => onToggleCapability(model.id, def.capability_type, true)}
                  />
                ))}
            </div>
          </div>

          {/* Configuration Panel */}
          {enabledCaps.length > 0 && (
            <div className="mt-4 pt-4 border-t dark:border-gray-700">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
                <Settings className="w-4 h-4" />
                Configuration
              </h4>
              <div className="bg-gray-50 dark:bg-gray-800 rounded p-3 text-sm">
                <pre className="text-xs overflow-auto">
                  {JSON.stringify(
                    enabledCaps.reduce((acc, cap) => ({
                      ...acc,
                      [cap.capability_type]: cap.config,
                    }), {}),
                    null,
                    2
                  )}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ==================== Main Component ====================

interface CapabilityManagerProps {
  className?: string;
}

export function CapabilityManager({ className }: CapabilityManagerProps) {
  const [activeTab, setActiveTab] = useState<'models' | 'definitions' | 'vendors' | 'matrix'>('models');
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [models, setModels] = useState<AIModel[]>([]);
  const [definitions, setDefinitions] = useState<CapabilityDefinition[]>([]);
  const [modelCapabilities, setModelCapabilities] = useState<Record<string, ModelCapability[]>>({});
  const [selectedProvider, setSelectedProvider] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch initial data
  useEffect(() => {
    async function fetchData() {
      setIsLoading(true);
      setError(null);

      try {
        const [providersRes, modelsRes, definitionsRes] = await Promise.all([
          apiGet<AIProvider[]>('/api/v1/ai/providers'),
          apiGet<{ models: AIModel[] }>('/api/v1/ai/models'),
          apiGet<CapabilityDefinition[]>('/api/v1/capabilities/definitions'),
        ]);

        setProviders(providersRes);
        setModels(modelsRes.models);
        setDefinitions(definitionsRes);

        // Fetch capabilities for each model
        const capabilitiesMap: Record<string, ModelCapability[]> = {};
        await Promise.all(
          modelsRes.models.slice(0, 20).map(async (model) => {
            try {
              const caps = await apiGet<ModelCapability[]>(
                `/api/v1/capabilities/models/${model.id}`
              );
              capabilitiesMap[model.id] = caps;
            } catch {
              capabilitiesMap[model.id] = [];
            }
          })
        );
        setModelCapabilities(capabilitiesMap);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, []);

  // Toggle capability for a model
  const handleToggleCapability = useCallback(async (
    modelId: string,
    capability: CapabilityType,
    enabled: boolean,
  ) => {
    try {
      const request: SetModelCapabilityRequest = {
        capability_type: capability,
        is_enabled: enabled,
      };

      const result = await apiPost<ModelCapability>(
        `/api/v1/capabilities/models/${modelId}`,
        request
      );

      setModelCapabilities(prev => ({
        ...prev,
        [modelId]: enabled
          ? [...(prev[modelId] || []), result]
          : (prev[modelId] || []).map(c =>
              c.capability_type === capability ? { ...c, is_enabled: false } : c
            ),
      }));
    } catch (err) {
      console.error('Failed to toggle capability:', err);
    }
  }, []);

  // Auto-detect capabilities for a model
  const handleAutoDetect = useCallback(async (modelId: string) => {
    try {
      const detected = await apiPost<ModelCapability[]>(
        `/api/v1/capabilities/models/${modelId}/auto-detect`
      );

      setModelCapabilities(prev => ({
        ...prev,
        [modelId]: detected,
      }));
    } catch (err) {
      console.error('Failed to auto-detect capabilities:', err);
    }
  }, []);

  // Filter models by provider
  const filteredModels = selectedProvider === 'all'
    ? models
    : models.filter(m => m.provider_id === selectedProvider);

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center h-64 ${className}`}>
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={`flex items-center justify-center h-64 ${className}`}>
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Capability Management
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">
          Configure model capabilities, vendor mappings, and tool requirements
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b dark:border-gray-700 mb-6">
        <nav className="flex gap-4">
          {[
            { id: 'models', label: 'Model Capabilities' },
            { id: 'definitions', label: 'Capability Definitions' },
            { id: 'vendors', label: 'Vendor Mappings' },
            { id: 'matrix', label: 'Capability Matrix' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`
                pb-3 px-1 text-sm font-medium border-b-2 transition-colors
                ${activeTab === tab.id
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      {activeTab === 'models' && (
        <div className="space-y-4">
          {/* Provider Filter */}
          <div className="flex items-center gap-4 mb-4">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Filter by Provider:
            </label>
            <select
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 text-sm"
            >
              <option value="all">All Providers</option>
              {providers.map(p => (
                <option key={p.id} value={p.id}>
                  {p.display_name}
                </option>
              ))}
            </select>
          </div>

          {/* Model List */}
          <div className="space-y-3">
            {filteredModels.map(model => (
              <ModelCapabilityCard
                key={model.id}
                model={model}
                capabilities={modelCapabilities[model.id] || []}
                definitions={definitions}
                onToggleCapability={handleToggleCapability}
                onAutoDetect={handleAutoDetect}
              />
            ))}
          </div>
        </div>
      )}

      {activeTab === 'definitions' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {definitions.map(def => {
            const Icon = CAPABILITY_ICONS[def.capability_type] || FunctionSquare;
            return (
              <div
                key={def.capability_type}
                className="border rounded-lg p-4 bg-white dark:bg-gray-900 dark:border-gray-700"
              >
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                    <Icon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-gray-900 dark:text-gray-100">
                        {def.display_name}
                      </h3>
                      {def.is_premium && (
                        <Sparkles className="w-4 h-4 text-amber-500" />
                      )}
                      {def.is_beta && (
                        <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">
                          Beta
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      {def.description}
                    </p>
                    <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
                      <span className="capitalize">{def.category}</span>
                      <span>•</span>
                      <span>{def.capability_type}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {activeTab === 'vendors' && (
        <div className="text-center py-12 text-gray-500">
          <Plug className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Vendor mapping configuration coming soon</p>
          <p className="text-sm mt-2">
            Configure how capabilities map to specific vendor APIs
          </p>
        </div>
      )}

      {activeTab === 'matrix' && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b dark:border-gray-700">
                <th className="text-left p-2 font-medium text-gray-700 dark:text-gray-300">
                  Model
                </th>
                {definitions.slice(0, 10).map(def => {
                  const Icon = CAPABILITY_ICONS[def.capability_type] || FunctionSquare;
                  return (
                    <th
                      key={def.capability_type}
                      className="p-2 text-center"
                      title={def.display_name}
                    >
                      <Icon className="w-4 h-4 mx-auto text-gray-500" />
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {filteredModels.slice(0, 15).map(model => {
                const caps = modelCapabilities[model.id] || [];
                return (
                  <tr key={model.id} className="border-b dark:border-gray-700">
                    <td className="p-2 font-medium text-gray-900 dark:text-gray-100">
                      {model.display_name || model.name}
                    </td>
                    {definitions.slice(0, 10).map(def => {
                      const hasCap = caps.some(
                        c => c.capability_type === def.capability_type && c.is_enabled
                      );
                      return (
                        <td key={def.capability_type} className="p-2 text-center">
                          {hasCap ? (
                            <Check className="w-4 h-4 mx-auto text-green-500" />
                          ) : (
                            <X className="w-4 h-4 mx-auto text-gray-300 dark:text-gray-600" />
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default CapabilityManager;
