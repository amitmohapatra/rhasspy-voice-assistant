'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { api, BuiltinToolDB, Tool, ToolExecution, IntegrationCatalog, UserIntegration, IntegrationTestResult } from '@/lib/api';
import { DataLoading, DataEmpty } from '@/components/ui/data-states';

const TOOL_ICONS: Record<string, string> = {
  'file-search': '📂', search: '🔍', globe: '🌐', code: '💻', image: '🖼️',
  monitor: '🖥️', box: '📦', plug: '🔌', function: '⚡', braces: '{ }',
  brain: '🧠', calculator: '🔢', file: '📄', database: '🗄️',
  slack: '💬', github: '🐙', jira: '📋', notion: '📝',
  linear: '📊', calendar: '📅', mail: '📧', cloud: '☁️',
};

const CATEGORY_LABELS: Record<string, string> = {
  retrieval: 'Retrieval', execution: 'Execution', generation: 'Generation',
  automation: 'Automation', output: 'Output', integration: 'Integration',
  reasoning: 'Reasoning', tools: 'Tools', custom: 'Custom',
};

const INTEGRATION_ICONS: Record<string, string> = {
  slack: '💬', microsoft_teams: '👥', outlook: '📧', jira: '📋',
  github: '🐙', notion: '📝', linear: '📊', google_calendar: '📅',
  salesforce: '☁️', hubspot: '🟠', zendesk: '🎫', confluence: '📖',
  trello: '📌', asana: '✅', discord: '🎮', zapier: '⚡',
};

type Tab = 'vendor' | 'integrations' | 'custom' | 'history';

export default function ToolsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('vendor');
  const [builtinTools, setBuiltinTools] = useState<BuiltinToolDB[]>([]);
  const [customTools, setCustomTools] = useState<Tool[]>([]);
  const [executions, setExecutions] = useState<ToolExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  // Integration state
  const [integrationCatalog, setIntegrationCatalog] = useState<IntegrationCatalog[]>([]);
  const [userIntegrations, setUserIntegrations] = useState<UserIntegration[]>([]);
  const [selectedCatalogEntry, setSelectedCatalogEntry] = useState<IntegrationCatalog | null>(null);
  const [selectedUserIntegration, setSelectedUserIntegration] = useState<UserIntegration | null>(null);
  const [sheetMode, setSheetMode] = useState<'connect' | 'manage' | null>(null);
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [testResult, setTestResult] = useState<IntegrationTestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [integrationSearch, setIntegrationSearch] = useState('');
  const [integrationCategoryFilter, setIntegrationCategoryFilter] = useState<string>('all');

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [builtin, custom, catalog, userIntgs] = await Promise.all([
        api.listBuiltinToolsDB().catch(() => []),
        api.listTools().catch(() => []),
        api.listIntegrationCatalog().catch(() => []),
        api.listUserIntegrations().catch(() => []),
      ]);
      setBuiltinTools(builtin);
      setCustomTools(custom);
      setIntegrationCatalog(catalog);
      setUserIntegrations(userIntgs);
    } catch (err) {
      console.error('Failed to load tools:', err);
    } finally {
      setLoading(false);
    }
  }

  const userIntegrationMap = useMemo(() => {
    const map: Record<string, UserIntegration> = {};
    for (const ui of userIntegrations) {
      map[ui.integration_id] = ui;
    }
    return map;
  }, [userIntegrations]);

  const integrationCategories = useMemo(() => {
    const cats = new Set<string>();
    for (const entry of integrationCatalog) {
      cats.add(entry.category);
    }
    return Array.from(cats).sort();
  }, [integrationCatalog]);

  const filteredIntegrations = useMemo(() => {
    let list = integrationCatalog.filter(e => e.is_active);
    if (integrationCategoryFilter !== 'all') {
      list = list.filter(e => e.category === integrationCategoryFilter);
    }
    if (integrationSearch) {
      const q = integrationSearch.toLowerCase();
      list = list.filter(
        e => e.display_name.toLowerCase().includes(q) || (e.description || '').toLowerCase().includes(q) || e.category.toLowerCase().includes(q)
      );
    }
    return list.sort((a, b) => a.sort_order - b.sort_order);
  }, [integrationCatalog, integrationCategoryFilter, integrationSearch]);

  const openConnectSheet = useCallback((entry: IntegrationCatalog) => {
    setSelectedCatalogEntry(entry);
    setSelectedUserIntegration(null);
    setSheetMode('connect');
    setCredentials({});
    setTestResult(null);
  }, []);

  const openManageSheet = useCallback((entry: IntegrationCatalog, userIntg: UserIntegration) => {
    setSelectedCatalogEntry(entry);
    setSelectedUserIntegration(userIntg);
    setSheetMode('manage');
    setCredentials({});
    setTestResult(null);
  }, []);

  const closeSheet = useCallback(() => {
    setSheetMode(null);
    setSelectedCatalogEntry(null);
    setSelectedUserIntegration(null);
    setCredentials({});
    setTestResult(null);
    setTesting(false);
    setSaving(false);
  }, []);

  const handleTestConnection = useCallback(async () => {
    if (!selectedCatalogEntry) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.testIntegration({
        integration_id: selectedCatalogEntry.id,
        credentials,
      });
      setTestResult(result);
    } catch (err) {
      setTestResult({ success: false, message: err instanceof Error ? err.message : 'Test failed' });
    } finally {
      setTesting(false);
    }
  }, [selectedCatalogEntry, credentials]);

  const handleEnableIntegration = useCallback(async () => {
    if (!selectedCatalogEntry) return;
    setSaving(true);
    try {
      const userIntg = await api.enableIntegration({
        integration_id: selectedCatalogEntry.id,
        credentials,
      });
      setUserIntegrations(prev => [...prev, userIntg]);
      closeSheet();
    } catch (err) {
      console.error('Failed to enable integration:', err);
      setTestResult({ success: false, message: err instanceof Error ? err.message : 'Failed to enable integration' });
    } finally {
      setSaving(false);
    }
  }, [selectedCatalogEntry, credentials, closeSheet]);

  const handleVerifyIntegration = useCallback(async () => {
    if (!selectedUserIntegration) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.verifyUserIntegration(selectedUserIntegration.id);
      setTestResult(result);
      if (result.success) {
        setUserIntegrations(prev => prev.map(ui =>
          ui.id === selectedUserIntegration.id ? { ...ui, is_verified: true, last_tested_at: new Date().toISOString(), test_error: undefined } : ui
        ));
        setSelectedUserIntegration(prev => prev ? { ...prev, is_verified: true, last_tested_at: new Date().toISOString(), test_error: undefined } : prev);
      }
    } catch (err) {
      setTestResult({ success: false, message: err instanceof Error ? err.message : 'Verification failed' });
    } finally {
      setTesting(false);
    }
  }, [selectedUserIntegration]);

  const handleToggleEnabled = useCallback(async (userIntg: UserIntegration) => {
    try {
      const updated = await api.updateUserIntegration(userIntg.id, { is_enabled: !userIntg.is_enabled });
      setUserIntegrations(prev => prev.map(ui => ui.id === userIntg.id ? updated : ui));
      if (selectedUserIntegration?.id === userIntg.id) {
        setSelectedUserIntegration(updated);
      }
    } catch (err) {
      console.error('Failed to toggle integration:', err);
    }
  }, [selectedUserIntegration]);

  const handleDeleteIntegration = useCallback(async () => {
    if (!selectedUserIntegration) return;
    try {
      await api.deleteUserIntegration(selectedUserIntegration.id);
      setUserIntegrations(prev => prev.filter(ui => ui.id !== selectedUserIntegration.id));
      closeSheet();
    } catch (err) {
      console.error('Failed to delete integration:', err);
    }
  }, [selectedUserIntegration, closeSheet]);

  const getAuthSchemaFields = useCallback((schema: Record<string, unknown>): { key: string; label: string; type: string; required: boolean; placeholder?: string }[] => {
    const properties = (schema.properties || {}) as Record<string, Record<string, unknown>>;
    const required = (schema.required || []) as string[];
    return Object.entries(properties).map(([key, prop]) => ({
      key,
      label: (prop.title as string) || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      type: (prop.format === 'password' || key.toLowerCase().includes('secret') || key.toLowerCase().includes('token') || key.toLowerCase().includes('key')) ? 'password' : 'text',
      required: required.includes(key),
      placeholder: prop.description as string | undefined,
    }));
  }, []);

  const handleToggleBuiltinTool = useCallback(async (tool: BuiltinToolDB) => {
    try {
      await api.updateBuiltinTool(tool.id, { is_active: !tool.is_active });
      setBuiltinTools(prev => prev.map(t => t.id === tool.id ? { ...t, is_active: !t.is_active } : t));
    } catch (err) {
      console.error('Failed to toggle tool:', err);
    }
  }, []);

  // Group builtin tools by vendor/provider
  const groupedBuiltinTools = useMemo(() => {
    const groups: Record<string, BuiltinToolDB[]> = {};
    for (const tool of builtinTools) {
      const vendor = tool.vendor || 'unknown';
      if (!groups[vendor]) groups[vendor] = [];
      groups[vendor].push(tool);
    }
    return groups;
  }, [builtinTools]);

  const filteredCustomTools = useMemo(() => {
    if (!search) return customTools;
    const q = search.toLowerCase();
    return customTools.filter(
      t => t.name.toLowerCase().includes(q) || (t.display_name || '').toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q)
    );
  }, [customTools, search]);

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: 'vendor', label: 'Vendor Tools', count: builtinTools.length },
    { id: 'integrations', label: 'Integrations', count: integrationCatalog.filter(e => e.is_active).length },
    { id: 'custom', label: 'Custom Tools', count: customTools.length },
    { id: 'history', label: 'Execution History', count: executions.length },
  ];

  return (
    <div className="bg-background text-foreground">
      <div className="max-w-6xl mx-auto px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Tools</h1>
            <p className="text-[13px] text-zinc-500 mt-1">
              Manage vendor built-in tools and custom tool integrations
            </p>
          </div>
          <Link href="/tools/create">
            <button className="flex items-center gap-2 px-4 py-2 bg-white text-black hover:bg-zinc-200 rounded-md text-[13px] font-medium transition-colors">
              + Create Custom Tool
            </button>
          </Link>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-zinc-900/50 border border-zinc-800/50 p-1 rounded-lg mb-6 w-fit">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-md text-[13px] font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-zinc-800 text-white'
                  : 'text-zinc-500 hover:text-white'
              }`}
            >
              {tab.label}
              <span className="ml-2 text-[11px] text-zinc-600">({tab.count})</span>
            </button>
          ))}
        </div>

        {loading ? (
          <DataLoading message="Loading tools..." />
        ) : (
          <>
            {/* Vendor Tools Tab */}
            {activeTab === 'vendor' && (
              <div className="space-y-8">
                {Object.entries(groupedBuiltinTools).length === 0 ? (
                  <DataEmpty
                    title="No vendor tools found"
                    description="Built-in tools will appear here once seeded."
                  />
                ) : (
                  Object.entries(groupedBuiltinTools)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([vendor, tools]) => (
                    <div key={vendor}>
                      <h2 className="text-lg font-semibold capitalize mb-3 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-blue-500" />
                        {vendor.replace('_', ' ')}
                        <span className="text-sm text-zinc-500 font-normal">({tools.length} tools)</span>
                      </h2>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {tools.sort((a, b) => a.sort_order - b.sort_order).map(tool => (
                          <div
                            key={tool.id}
                            className={`bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-zinc-700 transition-all ${
                              tool.is_active === false ? 'opacity-60' : ''
                            }`}
                          >
                            <div className="flex items-start gap-3">
                              <span className="text-2xl">{TOOL_ICONS[tool.icon || ''] || '🔧'}</span>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2">
                                  <div className="flex items-center gap-2 min-w-0">
                                    <h3 className="font-medium truncate">{tool.display_name}</h3>
                                    {tool.is_preview && (
                                      <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-yellow-900/50 text-yellow-400 rounded shrink-0">Preview</span>
                                    )}
                                    {tool.is_beta && (
                                      <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-purple-900/50 text-purple-400 rounded shrink-0">Beta</span>
                                    )}
                                    {tool.is_always_on && (
                                      <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-green-900/50 text-green-400 rounded shrink-0">Always On</span>
                                    )}
                                  </div>
                                  <button
                                    onClick={() => handleToggleBuiltinTool(tool)}
                                    disabled={tool.is_always_on}
                                    title={tool.is_always_on ? 'This tool is always enabled' : (tool.is_active !== false ? 'Disable tool' : 'Enable tool')}
                                    className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                                      tool.is_always_on ? 'opacity-50 cursor-not-allowed' : ''
                                    } ${tool.is_active !== false ? 'bg-green-600' : 'bg-zinc-600'}`}
                                  >
                                    <span
                                      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                        tool.is_active !== false ? 'translate-x-4' : 'translate-x-0'
                                      }`}
                                    />
                                  </button>
                                </div>
                                <p className="text-sm text-zinc-400 mt-1 line-clamp-2">{tool.description}</p>
                                <div className="flex flex-wrap items-center gap-1.5 mt-2">
                                  <span className="px-2 py-0.5 text-[10px] bg-zinc-800 text-zinc-400 rounded">
                                    {CATEGORY_LABELS[tool.category] || tool.category}
                                  </span>
                                  <span className="px-2 py-0.5 text-[10px] bg-zinc-800 text-zinc-400 rounded">
                                    {tool.capability_type}
                                  </span>
                                </div>
                                {/* Supported model patterns */}
                                <div className="flex flex-wrap items-center gap-1 mt-2">
                                  {tool.supported_model_patterns && tool.supported_model_patterns.length > 0 ? (
                                    tool.supported_model_patterns.map((pattern: string) => (
                                      <span key={pattern} className="px-1.5 py-0.5 text-[9px] bg-blue-900/30 text-blue-400 rounded font-mono">
                                        {pattern}
                                      </span>
                                    ))
                                  ) : (
                                    <span className="px-1.5 py-0.5 text-[9px] bg-zinc-800 text-zinc-500 rounded">All models</span>
                                  )}
                                  {tool.excluded_model_patterns && tool.excluded_model_patterns.length > 0 && (
                                    tool.excluded_model_patterns.map((pattern: string) => (
                                      <span key={pattern} className="px-1.5 py-0.5 text-[9px] bg-red-900/30 text-red-400 rounded font-mono line-through">
                                        {pattern}
                                      </span>
                                    ))
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Integrations Tab */}
            {activeTab === 'integrations' && (
              <div>
                {/* Filters */}
                <div className="flex flex-col sm:flex-row gap-3 mb-6">
                  <input
                    type="text"
                    placeholder="Search integrations..."
                    value={integrationSearch}
                    onChange={e => setIntegrationSearch(e.target.value)}
                    className="w-full max-w-md px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500/50"
                  />
                  <select
                    value={integrationCategoryFilter}
                    onChange={e => setIntegrationCategoryFilter(e.target.value)}
                    className="px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-white focus:outline-none focus:border-emerald-500/50"
                  >
                    <option value="all">All Categories</option>
                    {integrationCategories.map(cat => (
                      <option key={cat} value={cat}>{cat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</option>
                    ))}
                  </select>
                </div>

                {filteredIntegrations.length === 0 ? (
                  <DataEmpty
                    title="No integrations found"
                    description="Integration catalog entries will appear here once configured."
                  />
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredIntegrations.map(entry => {
                      const userIntg = userIntegrationMap[entry.id];
                      const isConnected = !!userIntg;
                      return (
                        <div
                          key={entry.id}
                          className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-zinc-700 transition-colors cursor-pointer"
                          onClick={() => isConnected ? openManageSheet(entry, userIntg) : openConnectSheet(entry)}
                        >
                          <div className="flex items-start gap-3">
                            <span className="text-2xl">{INTEGRATION_ICONS[entry.name] || TOOL_ICONS[entry.icon || ''] || '🔌'}</span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <h3 className="font-medium truncate">{entry.display_name}</h3>
                                {entry.is_featured && (
                                  <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-yellow-900/50 text-yellow-400 rounded">Featured</span>
                                )}
                                {isConnected && (
                                  <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-green-900/50 text-green-400 rounded">Connected</span>
                                )}
                              </div>
                              <p className="text-sm text-zinc-400 mt-1 line-clamp-2">{entry.description || 'No description'}</p>
                              <div className="flex items-center gap-2 mt-2">
                                <span className="px-2 py-0.5 text-[10px] bg-zinc-800 text-zinc-400 rounded">
                                  {entry.category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                                </span>
                                <span className="px-2 py-0.5 text-[10px] bg-zinc-800 text-zinc-400 rounded">
                                  {entry.auth_type}
                                </span>
                              </div>
                              {!isConnected && (
                                <button
                                  onClick={e => { e.stopPropagation(); openConnectSheet(entry); }}
                                  className="mt-3 px-3 py-1.5 text-xs font-medium bg-white text-black hover:bg-zinc-200 rounded-md transition-colors"
                                >
                                  Connect
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Integration Sheet/Dialog Overlay */}
                {sheetMode && selectedCatalogEntry && (
                  <div className="fixed inset-0 z-50 flex justify-end">
                    <div className="absolute inset-0 bg-black/60" onClick={closeSheet} />
                    <div className="relative w-full max-w-lg bg-zinc-900 border-l border-zinc-800 h-full overflow-y-auto">
                      <div className="p-6">
                        {/* Sheet Header */}
                        <div className="flex items-center justify-between mb-6">
                          <div className="flex items-center gap-3">
                            <span className="text-2xl">{INTEGRATION_ICONS[selectedCatalogEntry.name] || TOOL_ICONS[selectedCatalogEntry.icon || ''] || '🔌'}</span>
                            <div>
                              <h2 className="text-xl font-bold">{selectedCatalogEntry.display_name}</h2>
                              <p className="text-sm text-zinc-400">{sheetMode === 'connect' ? 'Connect Integration' : 'Manage Integration'}</p>
                            </div>
                          </div>
                          <button
                            onClick={closeSheet}
                            className="p-2 text-zinc-400 hover:text-foreground rounded-lg hover:bg-zinc-800 transition-colors"
                          >
                            ✕
                          </button>
                        </div>

                        {/* Connect Mode */}
                        {sheetMode === 'connect' && (
                          <div className="space-y-6">
                            {/* Setup Instructions */}
                            {selectedCatalogEntry.setup_instructions && (
                              <div className="bg-zinc-800/50 rounded-lg p-4">
                                <h3 className="text-sm font-semibold text-zinc-300 mb-2">Setup Instructions</h3>
                                <p className="text-sm text-zinc-400 whitespace-pre-wrap">{selectedCatalogEntry.setup_instructions}</p>
                              </div>
                            )}

                            {selectedCatalogEntry.docs_url && (
                              <a
                                href={selectedCatalogEntry.docs_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
                              >
                                View documentation &rarr;
                              </a>
                            )}

                            {/* Credential Fields */}
                            <div>
                              <h3 className="text-sm font-semibold text-zinc-300 mb-3">Credentials</h3>
                              <div className="space-y-3">
                                {getAuthSchemaFields(selectedCatalogEntry.auth_schema).map(field => (
                                  <div key={field.key}>
                                    <label className="block text-sm text-zinc-400 mb-1">
                                      {field.label}
                                      {field.required && <span className="text-red-400 ml-0.5">*</span>}
                                    </label>
                                    <input
                                      type={field.type}
                                      value={credentials[field.key] || ''}
                                      onChange={e => setCredentials(prev => ({ ...prev, [field.key]: e.target.value }))}
                                      placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
                                      className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500/50 text-sm"
                                    />
                                  </div>
                                ))}
                                {getAuthSchemaFields(selectedCatalogEntry.auth_schema).length === 0 && (
                                  <p className="text-sm text-zinc-500">No credentials required for this integration.</p>
                                )}
                              </div>
                            </div>

                            {/* Test Result */}
                            {testResult && (
                              <div className={`rounded-lg p-3 text-sm ${testResult.success ? 'bg-green-900/30 border border-green-800 text-green-400' : 'bg-red-900/30 border border-red-800 text-red-400'}`}>
                                <div className="flex items-center gap-2">
                                  <span>{testResult.success ? '✓' : '✗'}</span>
                                  <span className="font-medium">{testResult.success ? 'Connection successful' : 'Connection failed'}</span>
                                </div>
                                <p className="mt-1 text-xs opacity-80">{testResult.message}</p>
                                {testResult.duration_ms && (
                                  <p className="mt-1 text-xs opacity-60">Response time: {testResult.duration_ms}ms</p>
                                )}
                              </div>
                            )}

                            {/* Actions */}
                            <div className="flex gap-3 pt-2">
                              <button
                                onClick={handleTestConnection}
                                disabled={testing}
                                className="px-4 py-2 text-sm font-medium bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                              >
                                {testing ? 'Testing...' : 'Test Connection'}
                              </button>
                              <button
                                onClick={handleEnableIntegration}
                                disabled={saving || (testResult !== null && !testResult.success)}
                                className="px-4 py-2 text-sm font-medium bg-white text-black hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                              >
                                {saving ? 'Connecting...' : 'Enable Integration'}
                              </button>
                            </div>
                          </div>
                        )}

                        {/* Manage Mode */}
                        {sheetMode === 'manage' && selectedUserIntegration && (
                          <div className="space-y-6">
                            {/* Status */}
                            <div className="bg-zinc-800/50 rounded-lg p-4">
                              <h3 className="text-sm font-semibold text-zinc-300 mb-3">Status</h3>
                              <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                  <span className="text-sm text-zinc-400">Verification</span>
                                  <span className={`px-2 py-0.5 text-xs rounded font-medium ${selectedUserIntegration.is_verified ? 'bg-green-900/50 text-green-400' : 'bg-yellow-900/50 text-yellow-400'}`}>
                                    {selectedUserIntegration.is_verified ? 'Verified' : 'Unverified'}
                                  </span>
                                </div>
                                <div className="flex items-center justify-between">
                                  <span className="text-sm text-zinc-400">Enabled</span>
                                  <span className={`px-2 py-0.5 text-xs rounded font-medium ${selectedUserIntegration.is_enabled ? 'bg-green-900/50 text-green-400' : 'bg-zinc-700 text-zinc-400'}`}>
                                    {selectedUserIntegration.is_enabled ? 'Active' : 'Disabled'}
                                  </span>
                                </div>
                                {selectedUserIntegration.last_tested_at && (
                                  <div className="flex items-center justify-between">
                                    <span className="text-sm text-zinc-400">Last tested</span>
                                    <span className="text-xs text-zinc-500">{new Date(selectedUserIntegration.last_tested_at).toLocaleString()}</span>
                                  </div>
                                )}
                                {selectedUserIntegration.test_error && (
                                  <div className="mt-2 p-2 bg-red-900/20 border border-red-900/50 rounded text-xs text-red-400">
                                    {selectedUserIntegration.test_error}
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Test Result */}
                            {testResult && (
                              <div className={`rounded-lg p-3 text-sm ${testResult.success ? 'bg-green-900/30 border border-green-800 text-green-400' : 'bg-red-900/30 border border-red-800 text-red-400'}`}>
                                <div className="flex items-center gap-2">
                                  <span>{testResult.success ? '✓' : '✗'}</span>
                                  <span className="font-medium">{testResult.success ? 'Verification successful' : 'Verification failed'}</span>
                                </div>
                                <p className="mt-1 text-xs opacity-80">{testResult.message}</p>
                                {testResult.duration_ms && (
                                  <p className="mt-1 text-xs opacity-60">Response time: {testResult.duration_ms}ms</p>
                                )}
                              </div>
                            )}

                            {/* Actions */}
                            <div className="space-y-3">
                              <button
                                onClick={handleVerifyIntegration}
                                disabled={testing}
                                className="w-full px-4 py-2 text-sm font-medium bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                              >
                                {testing ? 'Testing...' : 'Test Connection'}
                              </button>

                              <div className="flex items-center justify-between bg-zinc-800/50 rounded-lg p-4">
                                <div>
                                  <p className="text-sm font-medium">Integration Enabled</p>
                                  <p className="text-xs text-zinc-500 mt-0.5">Toggle to enable or disable this integration</p>
                                </div>
                                <button
                                  onClick={() => handleToggleEnabled(selectedUserIntegration)}
                                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${selectedUserIntegration.is_enabled ? 'bg-emerald-600' : 'bg-zinc-600'}`}
                                >
                                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${selectedUserIntegration.is_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                                </button>
                              </div>

                              <div className="pt-4 border-t border-zinc-800">
                                <button
                                  onClick={handleDeleteIntegration}
                                  className="w-full px-4 py-2 text-sm font-medium bg-red-900/30 hover:bg-red-900/50 text-red-400 border border-red-900/50 rounded-lg transition-colors"
                                >
                                  Remove Integration
                                </button>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Custom Tools Tab */}
            {activeTab === 'custom' && (
              <div>
                <div className="mb-4">
                  <input
                    type="text"
                    placeholder="Search custom tools..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="w-full max-w-md px-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500/50"
                  />
                </div>

                {filteredCustomTools.length === 0 ? (
                  <DataEmpty
                    title="No custom tools yet"
                    description="Create your first custom tool to extend your assistants."
                    action={{ label: 'Create Custom Tool', onClick: () => window.location.href = '/tools/create' }}
                  />
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredCustomTools.map(tool => (
                      <div
                        key={tool.id}
                        className={`bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-zinc-700 transition-all ${
                          !tool.is_active ? 'opacity-60' : ''
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <span className="text-2xl">{TOOL_ICONS[tool.icon || ''] || '🛠️'}</span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2">
                              <Link href={`/tools/${tool.id}`} className="flex items-center gap-2 min-w-0">
                                <h3 className="font-medium truncate hover:text-blue-400 transition-colors">{tool.display_name || tool.name}</h3>
                              </Link>
                              <button
                                onClick={async (e) => {
                                  e.preventDefault();
                                  try {
                                    await api.updateTool(tool.id, { is_active: !tool.is_active });
                                    setCustomTools(prev => prev.map(t => t.id === tool.id ? { ...t, is_active: !t.is_active } : t));
                                  } catch (err) { console.error('Failed to toggle tool:', err); }
                                }}
                                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                                  tool.is_active ? 'bg-green-600' : 'bg-zinc-600'
                                }`}
                              >
                                <span
                                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                    tool.is_active ? 'translate-x-4' : 'translate-x-0'
                                  }`}
                                />
                              </button>
                            </div>
                            <p className="text-sm text-zinc-400 mt-1 line-clamp-2">{tool.description || 'No description'}</p>
                            <div className="flex items-center gap-2 mt-2">
                              <span className="px-2 py-0.5 text-[10px] bg-zinc-800 text-zinc-400 rounded">
                                {tool.category || 'custom'}
                              </span>
                              <span className="px-2 py-0.5 text-[10px] bg-zinc-800 text-zinc-400 rounded">
                                {(tool.implementation as Record<string, string>)?.handler || tool.type}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Execution History Tab */}
            {activeTab === 'history' && (
              <div>
                {executions.length === 0 ? (
                  <DataEmpty
                    title="No execution history"
                    description="Tool executions will appear here once tools are used."
                  />
                ) : (
                  <div className="space-y-2">
                    {executions.map(exec => (
                      <div key={exec.id} className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className={`w-2 h-2 rounded-full ${
                              exec.status === 'success' ? 'bg-green-500' :
                              exec.status === 'error' ? 'bg-red-500' :
                              exec.status === 'running' ? 'bg-yellow-500' : 'bg-zinc-500'
                            }`} />
                            <span className="font-medium">{exec.tool_id}</span>
                            <span className={`px-2 py-0.5 text-xs rounded ${
                              exec.status === 'success' ? 'bg-green-900/50 text-green-400' :
                              exec.status === 'error' ? 'bg-red-900/50 text-red-400' :
                              'bg-zinc-800 text-zinc-400'
                            }`}>
                              {exec.status}
                            </span>
                          </div>
                          <div className="flex items-center gap-4 text-sm text-zinc-500">
                            {exec.execution_time_ms && <span>{exec.execution_time_ms}ms</span>}
                            <span>{new Date(exec.created_at).toLocaleString()}</span>
                          </div>
                        </div>
                        {exec.error_message && (
                          <p className="text-sm text-red-400 mt-2">{exec.error_message}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
