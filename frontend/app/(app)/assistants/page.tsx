'use client';

/**
 * Assistants List Page
 *
 * Features:
 * - Server-side search with debounce
 * - Pagination with page size selector
 * - Grid/List view toggle
 * - Execution mode badge on cards
 * - Shared components (SearchFilterBar, Pagination, DataLoading, DataEmpty)
 */

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Bot,
  Plus,
  Trash2,
  Edit,
  MessageSquare,
  Database,
  Wrench,
  User2,
  Copy,
  MoreHorizontal,
} from 'lucide-react';
import { api, type Assistant } from '@/lib/api';
import { SearchFilterBar } from '@/components/ui/search-filter-bar';
import { Pagination } from '@/components/ui/pagination';
import { DataLoading, DataEmpty, DataError } from '@/components/ui/data-states';
import { usePagination } from '@/hooks/use-pagination';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';


export default function AssistantsPage() {
  const router = useRouter();
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const debounceTimer = useRef<NodeJS.Timeout>();

  const { page, pageSize, skip, total, totalPages, setPage, setPageSize, setTotal } = usePagination({ initialPageSize: 12 });

  // Debounced search
  useEffect(() => {
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(debounceTimer.current);
  }, [searchQuery]);

  // Fetch data when pagination or search changes
  useEffect(() => {
    fetchAssistants();
  }, [skip, pageSize, debouncedSearch]);

  const fetchAssistants = async () => {
    const token = api.getToken();
    if (!token) {
      setAssistants([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const response = await api.listAssistants({
        skip,
        limit: pageSize,
        search: debouncedSearch || undefined,
      });
      setAssistants(response.items);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to load assistants:', err);
      setError('Failed to load assistants');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this assistant?')) return;
    try {
      await api.deleteAssistant(id);
      fetchAssistants();
    } catch {
      alert('Failed to delete assistant');
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
            {/* Page Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight text-foreground">Assistants</h1>
                <p className="text-[13px] text-zinc-500 mt-1">
                  Create and manage AI assistants with custom tools and knowledge
                </p>
              </div>
              <Link href="/assistants/builder">
                <button className="flex items-center gap-2 px-4 py-2 bg-white text-black hover:bg-zinc-200 rounded-md text-[13px] font-medium transition-colors">
                  <Plus className="w-4 h-4" />
                  Create Assistant
                </button>
              </Link>
            </div>

            {/* Search & Filter Bar */}
            <SearchFilterBar
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search assistants..."
              viewMode={viewMode}
              onViewModeChange={setViewMode}
              showViewToggle
              className="mb-6"
            />

            {/* Content */}
            {error ? (
              <DataError message={error} onRetry={fetchAssistants} />
            ) : isLoading ? (
              <DataLoading message="Loading assistants..." />
            ) : assistants.length === 0 ? (
              <DataEmpty
                icon={<Bot className="w-7 h-7 text-zinc-600" />}
                title={debouncedSearch ? 'No results found' : 'No assistants yet'}
                description={debouncedSearch ? 'Try adjusting your search query' : 'Create your first AI assistant to get started'}
                action={!debouncedSearch ? { label: 'Create Assistant', onClick: () => router.push('/assistants/builder') } : undefined}
              />
            ) : viewMode === 'grid' ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {assistants.map(assistant => (
                  <AssistantCard
                    key={assistant.id}
                    assistant={assistant}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            ) : (
              <AssistantsTable assistants={assistants} onDelete={handleDelete} />
            )}

            {/* Pagination */}
            <Pagination
              currentPage={page}
              totalItems={total}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
    </div>
  );
}

// ==================== Card ====================

function AssistantCard({
  assistant,
  onDelete,
}: {
  assistant: Assistant;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="card-interactive p-4 group">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-blue-600 flex items-center justify-center flex-shrink-0">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0">
            <h3 className="text-[14px] font-medium text-white truncate">{assistant.name}</h3>
            <p className="text-[11px] text-zinc-500">{assistant.model}</p>
          </div>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="p-1 hover:bg-zinc-800 rounded transition-colors opacity-0 group-hover:opacity-100">
              <MoreHorizontal className="w-4 h-4 text-zinc-500" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="bg-[#18181b] border-zinc-800">
            <DropdownMenuItem asChild>
              <Link href={`/assistants/${assistant.id}/edit`} className="flex items-center gap-2">
                <Edit className="w-3.5 h-3.5" /> Edit
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href={`/platform/chat?assistant=${assistant.id}`} className="flex items-center gap-2">
                <MessageSquare className="w-3.5 h-3.5" /> Open Chat
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href={`/platform/avatar?assistant=${assistant.id}`} className="flex items-center gap-2">
                <User2 className="w-3.5 h-3.5" /> Avatar Mode
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigator.clipboard.writeText(assistant.id)}>
              <Copy className="w-3.5 h-3.5 mr-2" /> Copy ID
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-zinc-800" />
            <DropdownMenuItem onClick={() => onDelete(assistant.id)} className="text-red-400 focus:text-red-400">
              <Trash2 className="w-3.5 h-3.5 mr-2" /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Description */}
      <p className="text-[12px] text-zinc-500 line-clamp-2 mb-3 min-h-[32px]">
        {assistant.description || 'No description'}
      </p>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        <span className="px-2 py-0.5 bg-zinc-800 text-zinc-400 text-[10px] rounded">
          {assistant.provider}
        </span>
        {assistant.knowledge_base_ids?.length > 0 && (
          <span className="flex items-center gap-1 px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-[10px] rounded">
            <Database className="w-3 h-3" />
            {assistant.knowledge_base_ids.length} KB
          </span>
        )}
        {assistant.tools?.length > 0 && (
          <span className="flex items-center gap-1 px-2 py-0.5 bg-blue-500/20 text-blue-400 text-[10px] rounded">
            <Wrench className="w-3 h-3" />
            {assistant.tools.length} Tools
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Link href={`/platform/chat?assistant=${assistant.id}`} className="flex-1">
          <button className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-md text-[12px] font-medium transition-colors">
            <MessageSquare className="w-3.5 h-3.5" />
            Chat
          </button>
        </Link>
        <Link href={`/platform/avatar?assistant=${assistant.id}`}>
          <button className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-md text-[12px] transition-colors">
            <User2 className="w-3.5 h-3.5" />
          </button>
        </Link>
      </div>
    </div>
  );
}

// ==================== Table View ====================

function AssistantsTable({
  assistants,
  onDelete,
}: {
  assistants: Assistant[];
  onDelete: (id: string) => void;
}) {
  return (
    <div className="bg-[#18181b] border border-zinc-800 rounded-lg overflow-hidden">
      <table className="table-modern">
        <thead>
          <tr>
            <th>Assistant</th>
            <th>Model</th>
            <th>Knowledge</th>
            <th>Tools</th>
            <th>Status</th>
            <th className="text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {assistants.map(assistant => (
            <tr key={assistant.id}>
              <td>
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-blue-600 flex items-center justify-center flex-shrink-0">
                    <Bot className="w-4 h-4 text-white" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-white truncate">{assistant.name}</p>
                    <p className="text-[11px] text-zinc-500 truncate max-w-[200px]">
                      {assistant.description || 'No description'}
                    </p>
                  </div>
                </div>
              </td>
              <td>
                <p className="text-[12px] text-zinc-300">{assistant.model}</p>
                <p className="text-[11px] text-zinc-600">{assistant.provider}</p>
              </td>
              <td>
                {assistant.knowledge_base_ids?.length > 0 ? (
                  <span className="flex items-center gap-1 text-[12px] text-emerald-400">
                    <Database className="w-3 h-3" />
                    {assistant.knowledge_base_ids.length}
                  </span>
                ) : (
                  <span className="text-[12px] text-zinc-600">None</span>
                )}
              </td>
              <td>
                {assistant.tools?.length > 0 ? (
                  <span className="flex items-center gap-1 text-[12px] text-blue-400">
                    <Wrench className="w-3 h-3" />
                    {assistant.tools.length}
                  </span>
                ) : (
                  <span className="text-[12px] text-zinc-600">None</span>
                )}
              </td>
              <td>
                <span className="flex items-center gap-1.5 text-[11px] text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  Active
                </span>
              </td>
              <td>
                <div className="flex items-center justify-end gap-1">
                  <Link href={`/platform/chat?assistant=${assistant.id}`}>
                    <button className="p-1.5 hover:bg-zinc-700 rounded transition-colors" title="Chat">
                      <MessageSquare className="w-4 h-4 text-zinc-400" />
                    </button>
                  </Link>
                  <Link href={`/platform/avatar?assistant=${assistant.id}`}>
                    <button className="p-1.5 hover:bg-zinc-700 rounded transition-colors" title="Avatar">
                      <User2 className="w-4 h-4 text-zinc-400" />
                    </button>
                  </Link>
                  <Link href={`/assistants/${assistant.id}/edit`}>
                    <button className="p-1.5 hover:bg-zinc-700 rounded transition-colors" title="Edit">
                      <Edit className="w-4 h-4 text-zinc-400" />
                    </button>
                  </Link>
                  <button
                    onClick={() => onDelete(assistant.id)}
                    className="p-1.5 hover:bg-zinc-700 rounded transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4 text-red-400" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
