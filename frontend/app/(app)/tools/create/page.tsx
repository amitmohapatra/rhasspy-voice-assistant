'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, AdhocToolTestResult } from '@/lib/api';

type HandlerType = 'http' | 'mcp' | 'code';

const HANDLER_OPTIONS: { id: HandlerType; label: string; description: string; icon: string }[] = [
  { id: 'http', label: 'HTTP Webhook', description: 'Call an external HTTP API endpoint', icon: '🌐' },
  { id: 'mcp', label: 'MCP Server', description: 'Connect to a Model Context Protocol server', icon: '🔌' },
  { id: 'code', label: 'Python Code', description: 'Execute custom Python code', icon: '🐍' },
];

const CATEGORIES = ['custom', 'productivity', 'communication', 'development', 'data', 'integration'];

export default function CreateToolPage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<AdhocToolTestResult | null>(null);
  const [error, setError] = useState('');

  // Basic info
  const [name, setName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('custom');
  const [icon, setIcon] = useState('');

  // Handler
  const [handlerType, setHandlerType] = useState<HandlerType>('http');

  // HTTP config
  const [httpMethod, setHttpMethod] = useState('GET');
  const [httpUrl, setHttpUrl] = useState('');
  const [httpHeaders, setHttpHeaders] = useState('{}');

  // MCP config
  const [mcpUrl, setMcpUrl] = useState('');
  const [mcpTransport, setMcpTransport] = useState('http');

  // Code config
  const [code, setCode] = useState('# params dict is available\n# set result = ... for output\nresult = {"message": "Hello from tool!"}');

  // Parameters schema
  const [parametersSchema, setParametersSchema] = useState(
    JSON.stringify({
      type: "object",
      properties: {
        query: { type: "string", description: "Input query" }
      },
      required: ["query"]
    }, null, 2)
  );

  // Required secrets
  const [requiredSecrets, setRequiredSecrets] = useState('');

  // Test params
  const [testParams, setTestParams] = useState('{}');

  function buildImplementation(): Record<string, unknown> {
    switch (handlerType) {
      case 'http':
        return {
          handler: 'http',
          method: httpMethod,
          url: httpUrl,
          headers: JSON.parse(httpHeaders || '{}'),
        };
      case 'mcp':
        return { handler: 'mcp' };
      case 'code':
        return { handler: 'code', code };
      default:
        return {};
    }
  }

  function buildMcpConfig(): Record<string, unknown> | undefined {
    if (handlerType !== 'mcp') return undefined;
    return {
      server_url: mcpUrl,
      transport: mcpTransport,
    };
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const impl = buildImplementation();
      const mcpConfig = buildMcpConfig();
      const params = JSON.parse(testParams || '{}');
      const result = await api.testToolAdhoc(
        { implementation: impl, mcp_config: mcpConfig },
        params,
      );
      setTestResult(result);
    } catch (err) {
      setTestResult({ success: false, error: String(err) });
    } finally {
      setTesting(false);
    }
  }

  async function handleSubmit() {
    setError('');
    if (!name.trim()) { setError('Name is required'); return; }

    let schema: Record<string, unknown>;
    try {
      schema = JSON.parse(parametersSchema);
    } catch {
      setError('Invalid JSON in parameters schema');
      return;
    }

    setSaving(true);
    try {
      const secrets = requiredSecrets
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);

      await api.createTool({
        name: name.trim(),
        display_name: displayName.trim() || name.trim(),
        description: description.trim() || undefined,
        category,
        icon: icon.trim() || undefined,
        schema_definition: {
          type: 'function',
          function: {
            name: name.trim(),
            description: description.trim(),
            parameters: schema,
          },
        },
        implementation: buildImplementation(),
        required_secrets: secrets.length > 0 ? secrets : undefined,
        mcp_config: buildMcpConfig(),
      });

      router.push('/tools');
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/tools" className="text-gray-400 hover:text-white">&larr;</Link>
          <div>
            <h1 className="text-2xl font-bold">Create Custom Tool</h1>
            <p className="text-gray-400 text-sm mt-1">
              Define a tool that your assistants can use
            </p>
          </div>
        </div>

        <div className="space-y-8">
          {/* Basic Info */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Basic Info</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Name *</label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="get_weather"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Display Name</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  placeholder="Get Weather"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-sm text-gray-400 mb-1">Description</label>
                <textarea
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder="Describe what this tool does..."
                  rows={2}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Category</label>
                <select
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                >
                  {CATEGORIES.map(c => (
                    <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Icon</label>
                <input
                  type="text"
                  value={icon}
                  onChange={e => setIcon(e.target.value)}
                  placeholder="cloud"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </section>

          {/* Handler Type */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Handler Type</h2>
            <div className="grid grid-cols-3 gap-3">
              {HANDLER_OPTIONS.map(opt => (
                <button
                  key={opt.id}
                  onClick={() => setHandlerType(opt.id)}
                  className={`p-4 rounded-lg border text-left transition-colors ${
                    handlerType === opt.id
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-gray-700 hover:border-gray-600'
                  }`}
                >
                  <span className="text-2xl">{opt.icon}</span>
                  <div className="mt-2 font-medium">{opt.label}</div>
                  <div className="text-xs text-gray-400 mt-1">{opt.description}</div>
                </button>
              ))}
            </div>
          </section>

          {/* Configuration */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Configuration</h2>

            {handlerType === 'http' && (
              <div className="space-y-4">
                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Method</label>
                    <select
                      value={httpMethod}
                      onChange={e => setHttpMethod(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                    >
                      {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  </div>
                  <div className="col-span-3">
                    <label className="block text-sm text-gray-400 mb-1">URL</label>
                    <input
                      type="text"
                      value={httpUrl}
                      onChange={e => setHttpUrl(e.target.value)}
                      placeholder="https://api.example.com/endpoint"
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Headers (JSON)</label>
                  <textarea
                    value={httpHeaders}
                    onChange={e => setHttpHeaders(e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-blue-500 resize-none"
                  />
                </div>
              </div>
            )}

            {handlerType === 'mcp' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Server URL</label>
                  <input
                    type="text"
                    value={mcpUrl}
                    onChange={e => setMcpUrl(e.target.value)}
                    placeholder="http://localhost:3000"
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Transport</label>
                  <select
                    value={mcpTransport}
                    onChange={e => setMcpTransport(e.target.value)}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="http">HTTP</option>
                    <option value="stdio">Stdio</option>
                  </select>
                </div>
              </div>
            )}

            {handlerType === 'code' && (
              <div>
                <label className="block text-sm text-gray-400 mb-1">Python Code</label>
                <textarea
                  value={code}
                  onChange={e => setCode(e.target.value)}
                  rows={10}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-blue-500 resize-y"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Access input via <code className="text-gray-400">params</code> dict. Set <code className="text-gray-400">result</code> for output.
                </p>
              </div>
            )}
          </section>

          {/* Parameters Schema */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Parameters (JSON Schema)</h2>
            <textarea
              value={parametersSchema}
              onChange={e => setParametersSchema(e.target.value)}
              rows={10}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-blue-500 resize-y"
            />
          </section>

          {/* Required Secrets */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Required Secrets</h2>
            <input
              type="text"
              value={requiredSecrets}
              onChange={e => setRequiredSecrets(e.target.value)}
              placeholder="WEATHER_API_KEY, ANOTHER_SECRET"
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">Comma-separated list of secret key names</p>
          </section>

          {/* Test Panel */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Test</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Test Parameters (JSON)</label>
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
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`w-2 h-2 rounded-full ${testResult.success ? 'bg-green-500' : 'bg-red-500'}`} />
                    <span className="text-sm font-medium">{testResult.success ? 'Success' : 'Failed'}</span>
                    {testResult.duration_ms && <span className="text-xs text-gray-500">{testResult.duration_ms}ms</span>}
                  </div>
                  {testResult.result && (
                    <pre className="text-xs text-gray-300 overflow-auto max-h-40">{JSON.stringify(testResult.result, null, 2)}</pre>
                  )}
                  {testResult.error && (
                    <p className="text-sm text-red-400">{testResult.error}</p>
                  )}
                </div>
              )}
            </div>
          </section>

          {/* Submit */}
          {error && (
            <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleSubmit}
              disabled={saving}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {saving ? 'Creating...' : 'Create Tool'}
            </button>
            <Link
              href="/tools"
              className="px-6 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg font-medium transition-colors"
            >
              Cancel
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
