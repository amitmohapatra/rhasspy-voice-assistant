'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { api, Tool, ToolExecution } from '@/lib/api';

export default function ToolDetailPage() {
  const router = useRouter();
  const params = useParams();
  const toolId = params.id as string;

  const [tool, setTool] = useState<Tool | null>(null);
  const [executions, setExecutions] = useState<ToolExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; result?: any; error?: string } | null>(null);
  const [error, setError] = useState('');
  const [editMode, setEditMode] = useState(false);

  // Editable fields
  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');
  const [implementation, setImplementation] = useState('{}');
  const [schemaDefinition, setSchemaDefinition] = useState('{}');
  const [testParams, setTestParams] = useState('{}');

  useEffect(() => {
    loadTool();
  }, [toolId]);

  async function loadTool() {
    setLoading(true);
    try {
      const [toolData, execData] = await Promise.all([
        api.getTool(toolId),
        api.getToolExecutions(toolId).catch(() => []),
      ]);
      setTool(toolData);
      setDisplayName(toolData.display_name || toolData.name);
      setDescription(toolData.description || '');
      setImplementation(JSON.stringify(toolData.implementation || {}, null, 2));
      setSchemaDefinition(JSON.stringify(toolData.schema_definition || {}, null, 2));
      setExecutions(execData);
    } catch (err) {
      setError('Failed to load tool');
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setError('');
    setSaving(true);
    try {
      let impl: Record<string, unknown>;
      let schema: Record<string, unknown>;
      try {
        impl = JSON.parse(implementation);
        schema = JSON.parse(schemaDefinition);
      } catch {
        setError('Invalid JSON');
        setSaving(false);
        return;
      }

      await api.updateTool(toolId, {
        display_name: displayName,
        description: description || undefined,
        implementation: impl,
        schema_definition: schema,
      });

      setEditMode(false);
      await loadTool();
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const params = JSON.parse(testParams || '{}');
      const result = await api.testTool(toolId, params);
      setTestResult(result);
    } catch (err) {
      setTestResult({ success: false, error: String(err) });
    } finally {
      setTesting(false);
    }
  }

  async function handleDelete() {
    if (!confirm('Are you sure you want to delete this tool?')) return;
    try {
      await api.deleteTool(toolId);
      router.push('/tools');
    } catch (err) {
      setError(String(err));
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (!tool) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400">
        Tool not found
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <Link href="/tools" className="text-gray-400 hover:text-white">&larr;</Link>
            <div>
              <h1 className="text-2xl font-bold">{tool.display_name || tool.name}</h1>
              <p className="text-gray-400 text-sm mt-1">
                {tool.type} tool &middot; {tool.category}
                <span className={`ml-2 w-2 h-2 rounded-full inline-block ${tool.is_active ? 'bg-green-500' : 'bg-gray-600'}`} />
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {!editMode ? (
              <>
                <button
                  onClick={() => setEditMode(true)}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
                >
                  Edit
                </button>
                <button
                  onClick={handleDelete}
                  className="px-4 py-2 bg-red-900/50 hover:bg-red-900 text-red-400 rounded-lg text-sm font-medium transition-colors"
                >
                  Delete
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={() => { setEditMode(false); loadTool(); }}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
                >
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-sm text-red-400 mb-6">
            {error}
          </div>
        )}

        <div className="space-y-6">
          {/* Basic Info */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Details</h2>
            {editMode ? (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Display Name</label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={e => setDisplayName(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Description</label>
                  <textarea
                    value={description}
                    onChange={e => setDescription(e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500 resize-none"
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-2 text-sm">
                <div className="flex gap-4">
                  <span className="text-gray-400 w-32">Name:</span>
                  <span className="font-mono">{tool.name}</span>
                </div>
                <div className="flex gap-4">
                  <span className="text-gray-400 w-32">Display Name:</span>
                  <span>{tool.display_name || '-'}</span>
                </div>
                <div className="flex gap-4">
                  <span className="text-gray-400 w-32">Description:</span>
                  <span>{tool.description || '-'}</span>
                </div>
                <div className="flex gap-4">
                  <span className="text-gray-400 w-32">Handler:</span>
                  <span className="font-mono">{(tool.implementation as Record<string, string>)?.handler || tool.type}</span>
                </div>
                {tool.required_secrets?.length > 0 && (
                  <div className="flex gap-4">
                    <span className="text-gray-400 w-32">Secrets:</span>
                    <span className="font-mono">{tool.required_secrets.join(', ')}</span>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Implementation */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Implementation</h2>
            {editMode ? (
              <textarea
                value={implementation}
                onChange={e => setImplementation(e.target.value)}
                rows={10}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-blue-500 resize-y"
              />
            ) : (
              <pre className="bg-gray-800 rounded-lg p-4 text-sm text-gray-300 overflow-auto max-h-60">
                {JSON.stringify(tool.implementation, null, 2)}
              </pre>
            )}
          </section>

          {/* Schema */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Schema Definition</h2>
            {editMode ? (
              <textarea
                value={schemaDefinition}
                onChange={e => setSchemaDefinition(e.target.value)}
                rows={10}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-blue-500 resize-y"
              />
            ) : (
              <pre className="bg-gray-800 rounded-lg p-4 text-sm text-gray-300 overflow-auto max-h-60">
                {JSON.stringify(tool.schema_definition, null, 2)}
              </pre>
            )}
          </section>

          {/* Test Panel */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Test Tool</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Parameters (JSON)</label>
                <textarea
                  value={testParams}
                  onChange={e => setTestParams(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-blue-500 resize-none"
                />
              </div>
              <button
                onClick={handleTest}
                disabled={testing}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {testing ? 'Testing...' : 'Run Test'}
              </button>

              {testResult && (
                <div className={`p-4 rounded-lg ${testResult.success ? 'bg-green-900/20 border border-green-800' : 'bg-red-900/20 border border-red-800'}`}>
                  <span className={`text-sm font-medium ${testResult.success ? 'text-green-400' : 'text-red-400'}`}>
                    {testResult.success ? 'Success' : 'Failed'}
                  </span>
                  {testResult.result && (
                    <pre className="text-xs text-gray-300 mt-2 overflow-auto max-h-40">{JSON.stringify(testResult.result, null, 2)}</pre>
                  )}
                  {testResult.error && (
                    <p className="text-sm text-red-400 mt-2">{testResult.error}</p>
                  )}
                </div>
              )}
            </div>
          </section>

          {/* Execution History */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Execution History</h2>
            {executions.length === 0 ? (
              <p className="text-gray-500 text-sm">No executions yet</p>
            ) : (
              <div className="space-y-2">
                {executions.slice(0, 10).map(exec => (
                  <div key={exec.id} className="flex items-center justify-between bg-gray-800 rounded-lg p-3">
                    <div className="flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${
                        exec.status === 'success' ? 'bg-green-500' :
                        exec.status === 'error' ? 'bg-red-500' : 'bg-gray-500'
                      }`} />
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        exec.status === 'success' ? 'bg-green-900/50 text-green-400' :
                        exec.status === 'error' ? 'bg-red-900/50 text-red-400' :
                        'bg-gray-700 text-gray-400'
                      }`}>
                        {exec.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      {exec.execution_time_ms && <span>{exec.execution_time_ms}ms</span>}
                      <span>{new Date(exec.created_at).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
