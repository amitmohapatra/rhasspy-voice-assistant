'use client';

/**
 * API Reference Page
 *
 * Interactive API documentation with endpoints, parameters, and examples.
 * Similar to OpenAI API Reference.
 */

import { useState } from 'react';
import Link from 'next/link';
import {
  Code,
  ChevronRight,
  ChevronDown,
  Copy,
  Check,
  ExternalLink,
  Search,
  Bot,
  MessageSquare,
  FileText,
  Database,
  Key,
  Wrench,
} from 'lucide-react';

interface APIEndpoint {
  id: string;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  path: string;
  title: string;
  description: string;
  parameters?: APIParameter[];
  requestBody?: object;
  responseExample?: object;
}

interface APIParameter {
  name: string;
  type: string;
  required: boolean;
  description: string;
}

interface APISection {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  baseUrl: string;
  endpoints: APIEndpoint[];
}

const API_SECTIONS: APISection[] = [
  {
    id: 'assistants',
    title: 'Assistants',
    description: 'Create and manage AI assistants',
    icon: Bot,
    baseUrl: '/api/v1/assistants',
    endpoints: [
      {
        id: 'list-assistants',
        method: 'GET',
        path: '',
        title: 'List assistants',
        description: 'Returns a list of assistants.',
        parameters: [
          { name: 'limit', type: 'integer', required: false, description: 'Number of results to return (default: 20, max: 100)' },
          { name: 'order', type: 'string', required: false, description: 'Sort order: asc or desc' },
          { name: 'after', type: 'string', required: false, description: 'Cursor for pagination' },
        ],
        responseExample: {
          data: [{ id: 'asst_abc123', name: 'My Assistant', model: 'gpt-4o' }],
          has_more: false,
        },
      },
      {
        id: 'create-assistant',
        method: 'POST',
        path: '',
        title: 'Create assistant',
        description: 'Create a new assistant with the specified configuration.',
        requestBody: {
          name: 'My Assistant',
          model: 'gpt-4o',
          instructions: 'You are a helpful assistant.',
          tools: [{ type: 'file_search' }],
        },
        responseExample: {
          id: 'asst_abc123',
          name: 'My Assistant',
          model: 'gpt-4o',
          created_at: 1699999999,
        },
      },
      {
        id: 'get-assistant',
        method: 'GET',
        path: '/{assistant_id}',
        title: 'Retrieve assistant',
        description: 'Retrieves an assistant by ID.',
        parameters: [
          { name: 'assistant_id', type: 'string', required: true, description: 'The ID of the assistant to retrieve' },
        ],
      },
      {
        id: 'update-assistant',
        method: 'PUT',
        path: '/{assistant_id}',
        title: 'Update assistant',
        description: 'Modifies an assistant.',
        parameters: [
          { name: 'assistant_id', type: 'string', required: true, description: 'The ID of the assistant to update' },
        ],
      },
      {
        id: 'delete-assistant',
        method: 'DELETE',
        path: '/{assistant_id}',
        title: 'Delete assistant',
        description: 'Deletes an assistant.',
        parameters: [
          { name: 'assistant_id', type: 'string', required: true, description: 'The ID of the assistant to delete' },
        ],
      },
    ],
  },
  {
    id: 'messages',
    title: 'Messages',
    description: 'Send and receive messages in conversations',
    icon: MessageSquare,
    baseUrl: '/api/v1/threads/{thread_id}/messages',
    endpoints: [
      {
        id: 'list-messages',
        method: 'GET',
        path: '',
        title: 'List messages',
        description: 'Returns a list of messages in a thread.',
        parameters: [
          { name: 'thread_id', type: 'string', required: true, description: 'The ID of the thread' },
          { name: 'limit', type: 'integer', required: false, description: 'Number of results to return' },
        ],
      },
      {
        id: 'create-message',
        method: 'POST',
        path: '',
        title: 'Create message',
        description: 'Create a new message in a thread.',
        requestBody: {
          role: 'user',
          content: 'Hello, how can you help me?',
        },
      },
    ],
  },
  {
    id: 'files',
    title: 'Files',
    description: 'Upload and manage files',
    icon: FileText,
    baseUrl: '/api/v1/files',
    endpoints: [
      {
        id: 'list-files',
        method: 'GET',
        path: '',
        title: 'List files',
        description: 'Returns a list of files.',
      },
      {
        id: 'upload-file',
        method: 'POST',
        path: '',
        title: 'Upload file',
        description: 'Upload a file for use with assistants or knowledge bases.',
      },
      {
        id: 'delete-file',
        method: 'DELETE',
        path: '/{file_id}',
        title: 'Delete file',
        description: 'Deletes a file.',
      },
    ],
  },
  {
    id: 'knowledge-bases',
    title: 'Knowledge Bases',
    description: 'Manage document collections for RAG',
    icon: Database,
    baseUrl: '/api/v1/knowledge-bases',
    endpoints: [
      {
        id: 'list-kbs',
        method: 'GET',
        path: '',
        title: 'List knowledge bases',
        description: 'Returns a list of knowledge bases.',
      },
      {
        id: 'create-kb',
        method: 'POST',
        path: '',
        title: 'Create knowledge base',
        description: 'Create a new knowledge base.',
      },
      {
        id: 'search-kb',
        method: 'POST',
        path: '/{kb_id}/search',
        title: 'Search knowledge base',
        description: 'Search documents in a knowledge base.',
        requestBody: {
          query: 'How do I authenticate?',
          limit: 10,
        },
      },
    ],
  },
  {
    id: 'tools',
    title: 'Tools',
    description: 'Manage custom tools and functions',
    icon: Wrench,
    baseUrl: '/api/v1/tools',
    endpoints: [
      {
        id: 'list-tools',
        method: 'GET',
        path: '',
        title: 'List tools',
        description: 'Returns a list of available tools.',
      },
      {
        id: 'create-tool',
        method: 'POST',
        path: '',
        title: 'Create tool',
        description: 'Create a custom tool definition.',
      },
    ],
  },
];

const METHOD_COLORS = {
  GET: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  POST: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  PUT: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  PATCH: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  DELETE: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

export default function APIReferencePage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    assistants: true,
  });
  const [expandedEndpoints, setExpandedEndpoints] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev => ({ ...prev, [sectionId]: !prev[sectionId] }));
  };

  const toggleEndpoint = (endpointId: string) => {
    setExpandedEndpoints(prev => ({ ...prev, [endpointId]: !prev[endpointId] }));
  };

  const handleCopy = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b dark:border-gray-700">
        <div className="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                API Reference
              </h1>
              <p className="mt-2 text-gray-500 dark:text-gray-400">
                Complete API documentation for the Rhasspy AI Platform
              </p>
            </div>

            <div className="flex items-center gap-4">
              <a
                href="/api/v1/openapi.json"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
                OpenAPI Spec
              </a>
            </div>
          </div>

          {/* Search */}
          <div className="mt-6 max-w-md">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search endpoints..."
                className="w-full pl-10 pr-4 py-2 rounded-lg border dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              />
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-8">
          {/* Sidebar */}
          <aside className="w-64 flex-shrink-0 hidden lg:block">
            <div className="sticky top-24">
              <nav className="space-y-4">
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                    Overview
                  </h3>
                  <ul className="space-y-1">
                    <li>
                      <a href="#authentication" className="block px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
                        Authentication
                      </a>
                    </li>
                    <li>
                      <a href="#rate-limits" className="block px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
                        Rate Limits
                      </a>
                    </li>
                    <li>
                      <a href="#errors" className="block px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400">
                        Errors
                      </a>
                    </li>
                  </ul>
                </div>

                <div>
                  <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                    Endpoints
                  </h3>
                  <ul className="space-y-1">
                    {API_SECTIONS.map((section) => (
                      <li key={section.id}>
                        <a
                          href={`#${section.id}`}
                          className="block px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400"
                        >
                          {section.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              </nav>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1 min-w-0">
            {/* Authentication Section */}
            <section id="authentication" className="mb-12">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Authentication</h2>
              <div className="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-6">
                <p className="text-gray-600 dark:text-gray-300 mb-4">
                  The Rhasspy API uses API keys for authentication. Include your API key in the Authorization header:
                </p>
                <div className="relative">
                  <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm">
                    <code>Authorization: Bearer YOUR_API_KEY</code>
                  </pre>
                  <button
                    onClick={() => handleCopy('Authorization: Bearer YOUR_API_KEY', 'auth-header')}
                    className="absolute top-2 right-2 p-2 text-gray-400 hover:text-white"
                  >
                    {copiedId === 'auth-header' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
                <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
                  You can generate API keys in your{' '}
                  <Link href="/settings/api-keys" className="text-blue-600 hover:underline">
                    Settings
                  </Link>
                  .
                </p>
              </div>
            </section>

            {/* Base URL */}
            <section className="mb-12">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Base URL</h2>
              <div className="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-6">
                <div className="relative">
                  <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm">
                    <code>https://api.rhasspy.ai/v1</code>
                  </pre>
                  <button
                    onClick={() => handleCopy('https://api.rhasspy.ai/v1', 'base-url')}
                    className="absolute top-2 right-2 p-2 text-gray-400 hover:text-white"
                  >
                    {copiedId === 'base-url' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </section>

            {/* API Sections */}
            {API_SECTIONS.map((section) => {
              const Icon = section.icon;
              const isExpanded = expandedSections[section.id];

              return (
                <section key={section.id} id={section.id} className="mb-8">
                  <button
                    onClick={() => toggleSection(section.id)}
                    className="w-full flex items-center justify-between p-4 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 hover:border-blue-500 dark:hover:border-blue-500 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-gray-100 dark:bg-gray-700 rounded-lg">
                        <Icon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                      </div>
                      <div className="text-left">
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                          {section.title}
                        </h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {section.description}
                        </p>
                      </div>
                    </div>
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5 text-gray-400" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-gray-400" />
                    )}
                  </button>

                  {isExpanded && (
                    <div className="mt-4 space-y-4">
                      {section.endpoints.map((endpoint) => {
                        const isEndpointExpanded = expandedEndpoints[endpoint.id];
                        const fullPath = `${section.baseUrl}${endpoint.path}`;

                        return (
                          <div
                            key={endpoint.id}
                            className="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 overflow-hidden"
                          >
                            <button
                              onClick={() => toggleEndpoint(endpoint.id)}
                              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                            >
                              <div className="flex items-center gap-3">
                                <span className={`px-2 py-1 text-xs font-bold rounded ${METHOD_COLORS[endpoint.method]}`}>
                                  {endpoint.method}
                                </span>
                                <code className="text-sm font-mono text-gray-700 dark:text-gray-300">
                                  {fullPath}
                                </code>
                              </div>
                              <div className="flex items-center gap-3">
                                <span className="text-sm text-gray-500 dark:text-gray-400">
                                  {endpoint.title}
                                </span>
                                {isEndpointExpanded ? (
                                  <ChevronDown className="w-4 h-4 text-gray-400" />
                                ) : (
                                  <ChevronRight className="w-4 h-4 text-gray-400" />
                                )}
                              </div>
                            </button>

                            {isEndpointExpanded && (
                              <div className="border-t dark:border-gray-700 p-4">
                                <p className="text-gray-600 dark:text-gray-300 mb-4">
                                  {endpoint.description}
                                </p>

                                {endpoint.parameters && endpoint.parameters.length > 0 && (
                                  <div className="mb-4">
                                    <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">
                                      Parameters
                                    </h4>
                                    <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg overflow-hidden">
                                      <table className="w-full text-sm">
                                        <thead>
                                          <tr className="border-b dark:border-gray-600">
                                            <th className="px-4 py-2 text-left text-gray-500 dark:text-gray-400 font-medium">Name</th>
                                            <th className="px-4 py-2 text-left text-gray-500 dark:text-gray-400 font-medium">Type</th>
                                            <th className="px-4 py-2 text-left text-gray-500 dark:text-gray-400 font-medium">Required</th>
                                            <th className="px-4 py-2 text-left text-gray-500 dark:text-gray-400 font-medium">Description</th>
                                          </tr>
                                        </thead>
                                        <tbody>
                                          {endpoint.parameters.map((param) => (
                                            <tr key={param.name} className="border-b dark:border-gray-600 last:border-0">
                                              <td className="px-4 py-2 font-mono text-gray-900 dark:text-white">{param.name}</td>
                                              <td className="px-4 py-2 text-gray-600 dark:text-gray-300">{param.type}</td>
                                              <td className="px-4 py-2">
                                                {param.required ? (
                                                  <span className="text-red-600 dark:text-red-400">Required</span>
                                                ) : (
                                                  <span className="text-gray-400">Optional</span>
                                                )}
                                              </td>
                                              <td className="px-4 py-2 text-gray-600 dark:text-gray-300">{param.description}</td>
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </div>
                                  </div>
                                )}

                                {endpoint.requestBody && (
                                  <div className="mb-4">
                                    <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">
                                      Request Body
                                    </h4>
                                    <div className="relative">
                                      <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm">
                                        <code>{JSON.stringify(endpoint.requestBody, null, 2)}</code>
                                      </pre>
                                      <button
                                        onClick={() => handleCopy(JSON.stringify(endpoint.requestBody, null, 2), `${endpoint.id}-request`)}
                                        className="absolute top-2 right-2 p-2 text-gray-400 hover:text-white"
                                      >
                                        {copiedId === `${endpoint.id}-request` ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                                      </button>
                                    </div>
                                  </div>
                                )}

                                {endpoint.responseExample && (
                                  <div>
                                    <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">
                                      Response Example
                                    </h4>
                                    <div className="relative">
                                      <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto text-sm">
                                        <code>{JSON.stringify(endpoint.responseExample, null, 2)}</code>
                                      </pre>
                                      <button
                                        onClick={() => handleCopy(JSON.stringify(endpoint.responseExample, null, 2), `${endpoint.id}-response`)}
                                        className="absolute top-2 right-2 p-2 text-gray-400 hover:text-white"
                                      >
                                        {copiedId === `${endpoint.id}-response` ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                                      </button>
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </section>
              );
            })}
          </main>
        </div>
      </div>
    </div>
  );
}
