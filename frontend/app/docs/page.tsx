'use client';

/**
 * Documentation Page
 *
 * Platform documentation with categories and search.
 * Similar to OpenAI Platform documentation.
 */

import { useState } from 'react';
import Link from 'next/link';
import {
  BookOpen,
  Search,
  ChevronRight,
  Bot,
  Database,
  Key,
  MessageSquare,
  Wrench,
  Code,
  Zap,
  Shield,
  Users,
  ExternalLink,
  FileText,
  Video,
  Lightbulb,
} from 'lucide-react';

interface DocCategory {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  articles: DocArticle[];
}

interface DocArticle {
  id: string;
  title: string;
  description: string;
  href: string;
  isNew?: boolean;
}

const DOC_CATEGORIES: DocCategory[] = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    description: 'Learn the basics and set up your first assistant',
    icon: Zap,
    articles: [
      { id: 'quickstart', title: 'Quickstart', description: 'Create your first AI assistant in 5 minutes', href: '/docs/quickstart', isNew: true },
      { id: 'concepts', title: 'Core Concepts', description: 'Understand the key concepts of the platform', href: '/docs/concepts' },
      { id: 'authentication', title: 'Authentication', description: 'Set up API keys and authentication', href: '/docs/authentication' },
    ],
  },
  {
    id: 'assistants',
    title: 'Assistants',
    description: 'Create and configure AI assistants',
    icon: Bot,
    articles: [
      { id: 'create-assistant', title: 'Creating Assistants', description: 'Step-by-step guide to creating assistants', href: '/docs/assistants/create' },
      { id: 'configure', title: 'Configuration Options', description: 'Customize behavior, personality, and capabilities', href: '/docs/assistants/configure' },
      { id: 'tools', title: 'Using Tools', description: 'Enable built-in and custom tools', href: '/docs/assistants/tools' },
      { id: 'conversations', title: 'Managing Conversations', description: 'Handle threads and message history', href: '/docs/assistants/conversations' },
    ],
  },
  {
    id: 'knowledge',
    title: 'Knowledge Bases',
    description: 'Build and manage document collections',
    icon: Database,
    articles: [
      { id: 'create-kb', title: 'Creating Knowledge Bases', description: 'Set up document collections', href: '/docs/knowledge/create' },
      { id: 'upload', title: 'Uploading Documents', description: 'Supported formats and best practices', href: '/docs/knowledge/upload' },
      { id: 'retrieval', title: 'Retrieval Settings', description: 'Configure chunking and search parameters', href: '/docs/knowledge/retrieval' },
    ],
  },
  {
    id: 'tools',
    title: 'Tools & Functions',
    description: 'Extend assistant capabilities',
    icon: Wrench,
    articles: [
      { id: 'builtin-tools', title: 'Built-in Tools', description: 'File search, code interpreter, web search', href: '/docs/tools/builtin' },
      { id: 'custom-tools', title: 'Custom Tools', description: 'Create your own function definitions', href: '/docs/tools/custom' },
      { id: 'mcp', title: 'MCP Integration', description: 'Connect external tool servers', href: '/docs/tools/mcp', isNew: true },
    ],
  },
  {
    id: 'api',
    title: 'API Reference',
    description: 'Complete API documentation',
    icon: Code,
    articles: [
      { id: 'overview', title: 'API Overview', description: 'Authentication, rate limits, and errors', href: '/api-reference' },
      { id: 'assistants-api', title: 'Assistants API', description: 'Create, update, and delete assistants', href: '/api-reference#assistants' },
      { id: 'messages-api', title: 'Messages API', description: 'Send and receive messages', href: '/api-reference#messages' },
      { id: 'files-api', title: 'Files API', description: 'Upload and manage files', href: '/api-reference#files' },
    ],
  },
  {
    id: 'security',
    title: 'Security & Compliance',
    description: 'Best practices and compliance information',
    icon: Shield,
    articles: [
      { id: 'best-practices', title: 'Security Best Practices', description: 'Secure your implementation', href: '/docs/security/best-practices' },
      { id: 'data-privacy', title: 'Data Privacy', description: 'How we handle your data', href: '/docs/security/privacy' },
      { id: 'compliance', title: 'Compliance', description: 'SOC 2, GDPR, and other certifications', href: '/docs/security/compliance' },
    ],
  },
];

const QUICK_LINKS = [
  { title: 'API Reference', href: '/api-reference', icon: Code },
  { title: 'SDK Libraries', href: '/docs/sdks', icon: FileText },
  { title: 'Video Tutorials', href: '/docs/tutorials', icon: Video },
  { title: 'Examples', href: '/docs/examples', icon: Lightbulb },
];

export default function DocsPage() {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredCategories = DOC_CATEGORIES.map(category => ({
    ...category,
    articles: category.articles.filter(article =>
      article.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      article.description.toLowerCase().includes(searchQuery.toLowerCase())
    ),
  })).filter(category => category.articles.length > 0 || searchQuery === '');

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b dark:border-gray-700">
        <div className="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
              Documentation
            </h1>
            <p className="text-lg text-gray-500 dark:text-gray-400 mb-8 max-w-2xl mx-auto">
              Learn how to build powerful AI assistants with our comprehensive guides and API reference.
            </p>

            {/* Search */}
            <div className="max-w-xl mx-auto">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search documentation..."
                  className="w-full pl-12 pr-4 py-3 rounded-xl border dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-screen-xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Quick Links */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
          {QUICK_LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <Link
                key={link.title}
                href={link.href}
                className="flex items-center gap-3 p-4 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 hover:border-blue-500 dark:hover:border-blue-500 transition-colors"
              >
                <div className="p-2 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
                  <Icon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                </div>
                <span className="text-sm font-medium text-gray-900 dark:text-white">{link.title}</span>
              </Link>
            );
          })}
        </div>

        {/* Categories */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {filteredCategories.map((category) => {
            const Icon = category.icon;
            return (
              <div
                key={category.id}
                className="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 overflow-hidden"
              >
                <div className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 bg-gray-100 dark:bg-gray-700 rounded-lg">
                      <Icon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                    </div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                      {category.title}
                    </h2>
                  </div>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                    {category.description}
                  </p>

                  <ul className="space-y-2">
                    {category.articles.map((article) => (
                      <li key={article.id}>
                        <Link
                          href={article.href}
                          className="group flex items-start gap-2 p-2 -mx-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                        >
                          <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-blue-500 mt-0.5 flex-shrink-0" />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400">
                                {article.title}
                              </span>
                              {article.isNew && (
                                <span className="px-1.5 py-0.5 text-[10px] font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded">
                                  NEW
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                              {article.description}
                            </p>
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>

        {/* Help Section */}
        <div className="mt-12 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-8 text-center">
          <h3 className="text-2xl font-bold text-white mb-3">Need Help?</h3>
          <p className="text-blue-100 mb-6 max-w-lg mx-auto">
            Can't find what you're looking for? Our support team is here to help.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link
              href="/support"
              className="px-6 py-2.5 bg-white text-blue-600 rounded-lg font-medium hover:bg-blue-50 transition-colors"
            >
              Contact Support
            </Link>
            <a
              href="https://github.com/rhasspy/rhasspy-voice-assistant"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-6 py-2.5 bg-white/10 text-white rounded-lg font-medium hover:bg-white/20 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              GitHub
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
