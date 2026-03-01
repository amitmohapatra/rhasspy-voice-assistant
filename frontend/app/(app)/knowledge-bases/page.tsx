'use client';

/**
 * Knowledge Bases Page
 *
 * RAG pipeline is fully automated (Docling + BGE-M3 + Qdrant + BGE-reranker).
 * No user-configurable chunking strategy, chunk size, etc.
 */

import { useState, useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Database,
  Plus,
  Trash2,
  Loader2,
  FileText,
  File,
  Settings2,
  Scissors,
  Workflow,
  X,
  MoreHorizontal,
  Upload,
  Eye,
  Zap,
  CheckCircle2,
  AlertCircle,
  Info,
  Star,
  Search,
  Clock,
  Send,
  Check,
  FolderOpen,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useToast } from '@/hooks/use-toast';
import { api, type KnowledgeBase, type AIProvider, type KBType, type Document as APIDocument } from '@/lib/api';
import { cn } from '@/lib/utils';
import { SearchFilterBar } from '@/components/ui/search-filter-bar';
import { Pagination } from '@/components/ui/pagination';
import { DataLoading, DataEmpty } from '@/components/ui/data-states';
import { usePagination } from '@/hooks/use-pagination';
import { formatFileSize, getStatusColor } from '@/lib/format';

// Form validation schema
const kbSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  description: z.string().optional(),
});

type KBForm = z.infer<typeof kbSchema>;

// Pending file for upload
interface PendingFile {
  file: File;
  name: string;
  size: number;
}

const SUPPORTED_FILE_TYPES = 'PDF, DOCX, PPTX, XLSX, TXT, MD, HTML, CSV, JSON, PNG, JPG, TIFF, LaTeX, RTF, EPUB';

function InfoTip({ text }: { text: string }) {
  return (
    <span className="relative group inline-flex">
      <Info className="h-3.5 w-3.5 text-zinc-600 hover:text-zinc-400 cursor-help transition-colors" />
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-[11px] text-zinc-300 leading-relaxed w-56 text-center opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 pointer-events-none z-50 shadow-xl">
        {text}
      </span>
    </span>
  );
}

export default function KnowledgeBasesPage() {
  const { toast } = useToast();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKB, setSelectedKB] = useState<KnowledgeBase | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [showCreateSheet, setShowCreateSheet] = useState(false);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  const { page, pageSize, skip, total, setPage, setPageSize, setTotal } = usePagination({ initialPageSize: 12 });
  const debounceTimer = useRef<NodeJS.Timeout>();

  // KB type: provider_managed (provider handles vector store) or platform_managed (saved pipeline)
  const [kbMode, setKbMode] = useState<'provider_managed' | 'platform_managed'>('provider_managed');

  // Provider selector state (provider_managed mode)
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<string>('');
  const [isLoadingProviders, setIsLoadingProviders] = useState(false);

  // Test query state
  const [testQuery, setTestQuery] = useState('');
  const [testResults, setTestResults] = useState<{ content: string; score: number; element_type: string; page_number?: number; filename?: string }[] | null>(null);
  const [isQuerying, setIsQuerying] = useState(false);
  const [queryTimings, setQueryTimings] = useState<Record<string, number> | null>(null);

  // File upload state
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const detailFileInputRef = useRef<HTMLInputElement>(null);

  // Existing files selection state (for KB creation)
  const [existingFiles, setExistingFiles] = useState<APIDocument[]>([]);
  const [selectedExistingFileIds, setSelectedExistingFileIds] = useState<Set<string>>(new Set());
  const [isLoadingExistingFiles, setIsLoadingExistingFiles] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<KBForm>({
    resolver: zodResolver(kbSchema),
  });

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
    loadKnowledgeBases();
  }, [skip, pageSize, debouncedSearch]);

  const loadKnowledgeBases = async () => {
    const token = api.getToken();
    if (!token) {
      setKnowledgeBases([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const response = await api.listKnowledgeBases({
        skip,
        limit: pageSize,
        search: debouncedSearch || undefined,
      });
      setKnowledgeBases(response.items);
      setTotal(response.total);
    } catch (error) {
      console.error('Failed to load knowledge bases:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadKnowledgeBase = async (id: string) => {
    try {
      const data = await api.getKnowledgeBase(id);
      setSelectedKB(data);
      setTestResults(null);
      setQueryTimings(null);
      setTestQuery('');
    } catch (error) {
      console.error('Failed to load knowledge base:', error);
    }
  };

  const loadProviders = async () => {
    setIsLoadingProviders(true);
    try {
      const allProviders = await api.listProviders();
      const fcProviders = allProviders.filter((p) => p.supports_function_calling);
      setProviders(fcProviders);
      if (fcProviders.length > 0 && !selectedProviderId) {
        setSelectedProviderId(fcProviders[0].id);
      }
    } catch (error) {
      console.error('Failed to load providers:', error);
    } finally {
      setIsLoadingProviders(false);
    }
  };

  const loadExistingFiles = async () => {
    setIsLoadingExistingFiles(true);
    try {
      const response = await api.listFiles({ limit: 100 });
      setExistingFiles(response.items);
    } catch (error) {
      console.error('Failed to load existing files:', error);
    } finally {
      setIsLoadingExistingFiles(false);
    }
  };

  const toggleExistingFile = (fileId: string) => {
    setSelectedExistingFileIds(prev => {
      const next = new Set(prev);
      if (next.has(fileId)) {
        next.delete(fileId);
      } else {
        next.add(fileId);
      }
      return next;
    });
  };

  useEffect(() => {
    if (showCreateSheet) {
      loadProviders();
      loadExistingFiles();
    }
  }, [showCreateSheet]);

  const handleFilesSelected = (files: FileList | null) => {
    if (!files) return;
    const newFiles: PendingFile[] = Array.from(files).map(f => ({
      file: f,
      name: f.name,
      size: f.size,
    }));
    setPendingFiles(prev => [...prev, ...newFiles]);
  };

  const removePendingFile = (index: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUploadToKB = async (kbId: string, files: PendingFile[]) => {
    setIsUploading(true);
    let successCount = 0;
    for (const pf of files) {
      try {
        await api.uploadFile(pf.file, kbId);
        successCount++;
      } catch (error) {
        console.error(`Failed to upload ${pf.name}:`, error);
        toast({
          variant: 'destructive',
          title: 'Upload Error',
          description: `Failed to upload ${pf.name}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        });
      }
    }
    setIsUploading(false);
    if (successCount > 0) {
      toast({ title: 'Success', description: `${successCount} file(s) uploaded successfully` });
    }
    return successCount;
  };

  const handleDetailFileUpload = async (files: FileList | null) => {
    if (!files || !selectedKB) return;
    const pending = Array.from(files).map(f => ({ file: f, name: f.name, size: f.size }));
    const count = await handleUploadToKB(selectedKB.id, pending);
    if (count > 0) {
      loadKnowledgeBase(selectedKB.id);
    }
  };

  const onSubmit = async (data: KBForm) => {
    setIsCreating(true);
    try {
      const createData: Record<string, unknown> = {
        name: data.name,
        description: data.description,
        kb_type: kbMode,
      };

      if (kbMode === 'provider_managed' && selectedProviderId) {
        createData.provider_id = selectedProviderId;
      }

      const kb = await api.createKnowledgeBase(createData as any);

      // Upload any pending files to the new KB
      if (pendingFiles.length > 0) {
        await handleUploadToKB(kb.id, pendingFiles);
      }

      // Assign selected existing files to the new KB
      if (selectedExistingFileIds.size > 0) {
        let assignCount = 0;
        for (const fileId of Array.from(selectedExistingFileIds)) {
          try {
            await api.assignFileToKB(fileId, kb.id);
            assignCount++;
          } catch (error) {
            console.error(`Failed to assign file ${fileId}:`, error);
          }
        }
        if (assignCount > 0) {
          toast({ title: 'Files Assigned', description: `${assignCount} existing file(s) assigned to KB` });
        }
      }

      toast({
        title: 'Success',
        description: 'Knowledge base created successfully',
      });
      setShowCreateSheet(false);
      setKbMode('provider_managed');
      setSelectedProviderId('');
      setPendingFiles([]);
      setSelectedExistingFileIds(new Set());
      reset();
      loadKnowledgeBases();
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to create knowledge base',
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this knowledge base?')) return;

    try {
      await api.deleteKnowledgeBase(id);
      toast({
        title: 'Success',
        description: 'Knowledge base deleted successfully',
      });
      if (selectedKB?.id === id) {
        setSelectedKB(null);
      }
      loadKnowledgeBases();
    } catch {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Failed to delete knowledge base',
      });
    }
  };

  const handleTestQuery = async () => {
    if (!selectedKB || !testQuery.trim()) return;
    setIsQuerying(true);
    setTestResults(null);
    setQueryTimings(null);
    try {
      const response = await fetch(`/api/v1/knowledge-bases/${selectedKB.id}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${api.getToken()}`,
        },
        body: JSON.stringify({ query: testQuery, top_k: 5 }),
      });
      const data = await response.json();
      setTestResults(data.results || []);
      setQueryTimings(data.timings || null);
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Query failed',
        description: error instanceof Error ? error.message : 'Failed to run query',
      });
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
            {/* Page Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight text-white">Knowledge Bases</h1>
                <p className="text-[13px] text-zinc-500 mt-1">
                  Manage document collections for RAG-powered assistants
                </p>
              </div>
              <Button
                onClick={() => setShowCreateSheet(true)}
                className="btn-primary"
              >
                <Plus className="h-4 w-4 mr-2" />
                New Knowledge Base
              </Button>
            </div>

            {/* Search & Filter Bar */}
            <SearchFilterBar
              searchValue={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search knowledge bases..."
              viewMode={viewMode}
              onViewModeChange={setViewMode}
              showViewToggle
              className="mb-6"
            />

            {/* Knowledge Bases Grid/List */}
            {isLoading ? (
              <DataLoading message="Loading knowledge bases..." />
            ) : knowledgeBases.length === 0 ? (
              <DataEmpty
                icon={<Database className="w-7 h-7 text-zinc-600" />}
                title={debouncedSearch ? 'No results found' : 'No knowledge bases yet'}
                description={debouncedSearch ? 'Try adjusting your search query' : 'Create your first knowledge base to start building RAG-powered assistants'}
                action={!debouncedSearch ? { label: 'Create Knowledge Base', onClick: () => setShowCreateSheet(true) } : undefined}
              />
            ) : viewMode === 'grid' ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {knowledgeBases.map((kb) => (
                  <div
                    key={kb.id}
                    onClick={() => loadKnowledgeBase(kb.id)}
                    className={cn(
                      'card-interactive p-5 cursor-pointer',
                      selectedKB?.id === kb.id && 'ring-1 ring-emerald-500/50 border-emerald-500/30'
                    )}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-blue-500/20">
                        <Database className="w-5 h-5 text-blue-400" />
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-zinc-500">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="dropdown-menu">
                          <DropdownMenuItem className="dropdown-item">
                            <Eye className="h-4 w-4 mr-2" />
                            View Details
                          </DropdownMenuItem>
                          <DropdownMenuItem className="dropdown-item">
                            <Settings2 className="h-4 w-4 mr-2" />
                            Settings
                          </DropdownMenuItem>
                          <DropdownMenuSeparator className="border-zinc-800" />
                          <DropdownMenuItem
                            className="dropdown-item-danger"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(kb.id);
                            }}
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>

                    <h3 className="text-[15px] font-semibold text-white mb-1">{kb.name}</h3>
                    <p className="text-[12px] text-zinc-500 mb-4 line-clamp-2">
                      {kb.description || 'No description'}
                    </p>

                    <div className="flex items-center gap-4 mb-4">
                      <div className="flex items-center gap-1.5 text-[12px] text-zinc-400">
                        <FileText className="h-3.5 w-3.5" />
                        <span>{kb.document_count} docs</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[12px] text-zinc-400">
                        <Scissors className="h-3.5 w-3.5" />
                        <span>{kb.total_chunks} chunks</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="flex gap-1">
                        <Badge className={cn(
                          'text-[10px] font-medium border-0',
                          kb.kb_type === 'provider_managed'
                            ? 'bg-blue-500/20 text-blue-400'
                            : 'bg-emerald-500/20 text-emerald-400'
                        )}>
                          {kb.kb_type === 'provider_managed' ? 'Provider Managed' : 'Platform Managed'}
                        </Badge>
                        {kb.kb_type === 'platform_managed' && (
                          <Badge className="text-[10px] font-medium border-0 bg-purple-500/20 text-purple-400">
                            Auto Pipeline
                          </Badge>
                        )}
                      </div>
                      <span className={cn(
                        'inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded',
                        getStatusColor(kb.status || 'ready')
                      )}>
                        {kb.status === 'processing' ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : kb.status === 'error' ? (
                          <AlertCircle className="w-3 h-3" />
                        ) : (
                          <CheckCircle2 className="w-3 h-3" />
                        )}
                        {kb.status || 'Ready'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="card-elevated overflow-hidden">
                <table className="table-modern">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Pipeline</th>
                      <th>Documents</th>
                      <th>Chunks</th>
                      <th>Status</th>
                      <th className="w-10"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {knowledgeBases.map((kb) => (
                      <tr
                        key={kb.id}
                        onClick={() => loadKnowledgeBase(kb.id)}
                        className="cursor-pointer"
                      >
                        <td>
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-blue-500/20">
                              <Database className="w-4 h-4 text-blue-400" />
                            </div>
                            <div>
                              <p className="font-medium text-white">{kb.name}</p>
                              <p className="text-[11px] text-zinc-500">{kb.description || 'No description'}</p>
                            </div>
                          </div>
                        </td>
                        <td>
                          <Badge className={cn(
                            'text-[10px] font-medium border-0',
                            kb.kb_type === 'provider_managed'
                              ? 'bg-blue-500/20 text-blue-400'
                              : 'bg-emerald-500/20 text-emerald-400'
                          )}>
                            {kb.kb_type === 'provider_managed' ? 'Provider Managed' : 'Platform Managed'}
                          </Badge>
                        </td>
                        <td>
                          {kb.kb_type === 'platform_managed' ? (
                            <Badge className="text-[10px] font-medium border-0 bg-purple-500/20 text-purple-400">
                              Auto Pipeline
                            </Badge>
                          ) : (
                            <span className="text-[12px] text-zinc-500">-</span>
                          )}
                        </td>
                        <td>{kb.document_count}</td>
                        <td>{kb.total_chunks}</td>
                        <td>
                          <span className={cn(
                            'inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded',
                            getStatusColor(kb.status || 'ready')
                          )}>
                            {kb.status || 'Ready'}
                          </span>
                        </td>
                        <td>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-8 w-8 text-zinc-500">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="dropdown-menu">
                              <DropdownMenuItem className="dropdown-item">
                                <Eye className="h-4 w-4 mr-2" />
                                View Details
                              </DropdownMenuItem>
                              <DropdownMenuItem className="dropdown-item">
                                <Settings2 className="h-4 w-4 mr-2" />
                                Settings
                              </DropdownMenuItem>
                              <DropdownMenuSeparator className="border-zinc-800" />
                              <DropdownMenuItem
                                className="dropdown-item-danger"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDelete(kb.id);
                                }}
                              >
                                <Trash2 className="h-4 w-4 mr-2" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            <Pagination
              currentPage={page}
              totalItems={total}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />

            {/* Detail Panel (when KB selected) */}
            {selectedKB && (
              <div className="mt-6">
                <div className="card-elevated p-6">
                  <div className="flex items-start justify-between mb-6">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <h2 className="text-[18px] font-semibold text-white">{selectedKB.name}</h2>
                        <Badge className={cn(
                          'text-[10px] font-medium border-0',
                          selectedKB.kb_type === 'provider_managed'
                            ? 'bg-blue-500/20 text-blue-400'
                            : 'bg-emerald-500/20 text-emerald-400'
                        )}>
                          {selectedKB.kb_type === 'provider_managed' ? 'Provider Managed' : 'Platform Managed'}
                        </Badge>
                      </div>
                      <p className="text-[13px] text-zinc-500">{selectedKB.description || 'No description'}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setSelectedKB(null)}
                      className="text-zinc-500"
                    >
                      <X className="h-5 w-5" />
                    </Button>
                  </div>

                  {/* Stats Grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                      <div className="flex items-center gap-2 mb-2">
                        <FileText className="h-4 w-4 text-blue-400" />
                        <span className="text-[11px] font-medium text-zinc-500 uppercase">Documents</span>
                        <InfoTip text="Total number of files uploaded and indexed in this knowledge base." />
                      </div>
                      <p className="text-2xl font-bold text-white">{selectedKB.document_count}</p>
                    </div>
                    <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                      <div className="flex items-center gap-2 mb-2">
                        <Scissors className="h-4 w-4 text-purple-400" />
                        <span className="text-[11px] font-medium text-zinc-500 uppercase">Chunks</span>
                        <InfoTip text="Documents are split into smaller chunks for precise retrieval. Each chunk is embedded and stored in the vector database." />
                      </div>
                      <p className="text-2xl font-bold text-white">{selectedKB.total_chunks}</p>
                    </div>
                    {selectedKB.kb_type === 'provider_managed' ? (
                      <>
                        <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                          <div className="flex items-center gap-2 mb-2">
                            <Zap className="h-4 w-4 text-emerald-400" />
                            <span className="text-[11px] font-medium text-zinc-500 uppercase">Provider</span>
                          </div>
                          <p className="text-lg font-bold text-white capitalize">
                            {providers.find((p) => p.id === selectedKB.provider_id)?.display_name || selectedKB.provider_id || 'N/A'}
                          </p>
                        </div>
                        <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                          <div className="flex items-center gap-2 mb-2">
                            <CheckCircle2 className="h-4 w-4 text-cyan-400" />
                            <span className="text-[11px] font-medium text-zinc-500 uppercase">Status</span>
                          </div>
                          <p className="text-2xl font-bold text-white capitalize">{selectedKB.status || 'ready'}</p>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                          <div className="flex items-center gap-2 mb-2">
                            <Zap className="h-4 w-4 text-emerald-400" />
                            <span className="text-[11px] font-medium text-zinc-500 uppercase">Pipeline</span>
                            <InfoTip text="Fully automated: Docling chunking, contextual enrichment, BGE-M3 embeddings, 3-way hybrid retrieval + RRF, and BGE-reranker." />
                          </div>
                          <p className="text-sm font-bold text-white">Automated</p>
                        </div>
                        <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                          <div className="flex items-center gap-2 mb-2">
                            <CheckCircle2 className="h-4 w-4 text-cyan-400" />
                            <span className="text-[11px] font-medium text-zinc-500 uppercase">Status</span>
                          </div>
                          <p className="text-2xl font-bold text-white capitalize">{selectedKB.status || 'ready'}</p>
                        </div>
                      </>
                    )}
                  </div>

                  {/* Documents List */}
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-[14px] font-semibold text-white">Documents</h3>
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-zinc-800 text-zinc-400"
                        onClick={() => detailFileInputRef.current?.click()}
                        disabled={isUploading}
                      >
                        {isUploading ? (
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <Upload className="h-4 w-4 mr-2" />
                        )}
                        Add Files
                      </Button>
                      <input
                        ref={detailFileInputRef}
                        type="file"
                        multiple
                        accept=".pdf,.txt,.md,.html,.htm,.docx,.doc,.pptx,.xlsx,.json,.csv,.epub,.png,.jpg,.jpeg,.tiff,.tif,.tex,.rtf"
                        className="hidden"
                        onChange={(e) => handleDetailFileUpload(e.target.files)}
                      />
                    </div>
                    {selectedKB.documents.length === 0 ? (
                      <div className="text-center py-8 border-2 border-dashed border-zinc-800 rounded-xl">
                        <FileText className="w-8 h-8 mx-auto mb-2 text-zinc-600" />
                        <p className="text-[13px] text-zinc-500">No documents yet</p>
                        <p className="text-[12px] text-zinc-600">
                          Supports {SUPPORTED_FILE_TYPES}
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {selectedKB.documents.map((doc) => (
                          <div
                            key={doc.id}
                            className="flex items-center justify-between p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50"
                          >
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-lg bg-zinc-800 flex items-center justify-center">
                                <File className="w-4 h-4 text-zinc-400" />
                              </div>
                              <div>
                                <p className="text-[13px] font-medium text-white">{doc.filename}</p>
                                <p className="text-[11px] text-zinc-500">
                                  {doc.chunk_count} chunks
                                  {doc.page_count && ` | ${doc.page_count} pages`}
                                  {doc.language && ` | ${doc.language}`}
                                </p>
                              </div>
                            </div>
                            <span className={cn(
                              'inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded',
                              getStatusColor(doc.status)
                            )}>
                              {doc.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Test Query Section */}
                  {selectedKB.documents.length > 0 && (
                    <div className="mt-6">
                      <h3 className="text-[14px] font-semibold text-white mb-4 flex items-center gap-2">
                        <Search className="h-4 w-4 text-emerald-400" />
                        Test Query
                        <InfoTip text="Test your knowledge base by asking a question. Results show the most relevant chunks with their relevance scores and retrieval timings." />
                      </h3>
                      <div className="flex gap-2 mb-4">
                        <div className="flex-1 relative">
                          <input
                            type="text"
                            value={testQuery}
                            onChange={(e) => setTestQuery(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleTestQuery()}
                            placeholder="Ask a question about your documents..."
                            className="w-full px-4 py-2.5 rounded-xl bg-zinc-900/50 border border-zinc-800 text-[13px] text-white placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500/50"
                          />
                        </div>
                        <Button
                          onClick={handleTestQuery}
                          disabled={!testQuery.trim() || isQuerying}
                          className="btn-primary px-4"
                        >
                          {isQuerying ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Send className="h-4 w-4" />
                          )}
                        </Button>
                      </div>

                      {/* Query Timings */}
                      {queryTimings && (
                        <div className="flex flex-wrap gap-3 mb-4 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                          <div className="flex items-center gap-1.5 text-[11px] text-zinc-400">
                            <Clock className="h-3 w-3" />
                            <span>Timings:</span>
                          </div>
                          {Object.entries(queryTimings).map(([key, value]) => (
                            <span key={key} className="text-[11px] text-zinc-500">
                              <span className="text-zinc-400 capitalize">{key.replace(/_/g, ' ')}</span>{' '}
                              <span className="font-mono text-emerald-400">{value.toFixed(0)}ms</span>
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Query Results */}
                      {testResults && (
                        <div className="space-y-2">
                          {testResults.length === 0 ? (
                            <div className="text-center py-6 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                              <Search className="w-6 h-6 mx-auto mb-2 text-zinc-600" />
                              <p className="text-[13px] text-zinc-500">No results found</p>
                              <p className="text-[12px] text-zinc-600">Try a different query</p>
                            </div>
                          ) : (
                            <>
                              <p className="text-[12px] text-zinc-500 mb-2">
                                {testResults.length} result{testResults.length !== 1 ? 's' : ''} from your documents
                              </p>
                              {testResults.map((result, i) => (
                                <div
                                  key={i}
                                  className="p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50"
                                >
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                      <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded bg-purple-500/20 text-purple-400">
                                        {result.element_type}
                                      </span>
                                      {result.page_number && (
                                        <span className="text-[10px] text-zinc-500">
                                          page {result.page_number}
                                        </span>
                                      )}
                                      {result.filename && (
                                        <span className="text-[10px] text-zinc-600 flex items-center gap-1">
                                          <File className="h-2.5 w-2.5" />
                                          {result.filename}
                                        </span>
                                      )}
                                    </div>
                                    <span className="text-[10px] font-mono text-emerald-400">
                                      {result.score.toFixed(3)}
                                    </span>
                                  </div>
                                  <p className="text-[12px] text-zinc-300 leading-relaxed line-clamp-4">
                                    {result.content}
                                  </p>
                                </div>
                              ))}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
      {/* Create Knowledge Base Sheet */}
      <Sheet open={showCreateSheet} onOpenChange={setShowCreateSheet}>
        <SheetContent className="w-full sm:max-w-xl bg-[#0f0f10] border-zinc-800 overflow-y-auto">
          <SheetHeader className="pb-6">
            <SheetTitle className="text-[18px] text-white">Create Knowledge Base</SheetTitle>
          </SheetHeader>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Basic Info */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-[13px] text-zinc-400">Name *</Label>
                <Input
                  {...register('name')}
                  placeholder="Product Documentation"
                  className="input-standard"
                />
                {errors.name && (
                  <p className="text-[12px] text-red-400">{errors.name.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label className="text-[13px] text-zinc-400">Description</Label>
                <Input
                  {...register('description')}
                  placeholder="Company product docs and guides"
                  className="input-standard"
                />
              </div>
            </div>

            {/* Mode Toggle: Provider Managed / Platform Managed */}
            <div className="space-y-3">
              <Label className="text-[13px] text-zinc-400 flex items-center gap-1.5">
                Type
                <InfoTip text="Provider Managed: the AI provider (e.g. OpenAI) hosts the vector store. Platform Managed: documents are processed and stored locally using our automated RAG pipeline." />
              </Label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setKbMode('provider_managed')}
                  className={cn(
                    'p-3 rounded-xl border text-left transition-all',
                    kbMode === 'provider_managed'
                      ? 'border-emerald-500/50 bg-emerald-500/10'
                      : 'border-zinc-800 bg-zinc-900/50 hover:border-zinc-700'
                  )}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Settings2 className="h-4 w-4 text-blue-400" />
                    <span className="text-[13px] font-medium text-white">Provider Managed</span>
                  </div>
                  <p className="text-[11px] text-zinc-500">Provider handles vector store</p>
                </button>
                <button
                  type="button"
                  onClick={() => setKbMode('platform_managed')}
                  className={cn(
                    'p-3 rounded-xl border text-left transition-all',
                    kbMode === 'platform_managed'
                      ? 'border-emerald-500/50 bg-emerald-500/10'
                      : 'border-zinc-800 bg-zinc-900/50 hover:border-zinc-700'
                  )}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Workflow className="h-4 w-4 text-emerald-400" />
                    <span className="text-[13px] font-medium text-white">Platform Managed</span>
                  </div>
                  <p className="text-[11px] text-zinc-500">Use a saved RAG pipeline</p>
                </button>
              </div>
            </div>

            {kbMode === 'platform_managed' && (
              <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
                <div className="flex items-center gap-2 mb-2">
                  <Workflow className="h-4 w-4 text-emerald-400" />
                  <span className="text-[13px] font-medium text-white">Automated RAG Pipeline</span>
                  <InfoTip text="Pipeline: Docling HybridChunker for structure-aware chunking, contextual enrichment for +49% accuracy, BGE-M3 triple embeddings (dense+sparse+ColBERT), 3-way hybrid retrieval with RRF, and BGE-reranker-v2-m3." />
                </div>
                <p className="text-[12px] text-zinc-400">
                  Documents are processed automatically using Docling, BGE-M3 embeddings,
                  3-way hybrid retrieval, and BGE-reranker. No configuration needed.
                </p>
              </div>
            )}

            {/* Provider Managed Mode: Provider selector + info */}
            {kbMode === 'provider_managed' && (
              <div className="space-y-3">
                <Label className="text-[13px] text-zinc-400 flex items-center gap-2">
                  <Settings2 className="h-4 w-4" />
                  Provider
                  <InfoTip text="Select an AI provider that supports file search. The provider will manage document storage, chunking, and retrieval using its own vector store." />
                </Label>
                {isLoadingProviders ? (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                    <Loader2 className="h-4 w-4 animate-spin text-zinc-500" />
                    <span className="text-[13px] text-zinc-500">Loading providers...</span>
                  </div>
                ) : providers.length === 0 ? (
                  <div className="p-4 rounded-xl bg-zinc-900/50 border border-dashed border-zinc-700 text-center">
                    <Settings2 className="w-8 h-8 mx-auto mb-2 text-zinc-600" />
                    <p className="text-[13px] text-zinc-400 mb-1">No providers available</p>
                    <p className="text-[11px] text-zinc-600">
                      No providers with function calling support were found.
                    </p>
                  </div>
                ) : (
                  <Select value={selectedProviderId} onValueChange={setSelectedProviderId}>
                    <SelectTrigger className="w-full bg-zinc-900/50 border-zinc-800 text-[13px]">
                      <SelectValue placeholder="Select a provider..." />
                    </SelectTrigger>
                    <SelectContent>
                      {providers.map((provider) => (
                        <SelectItem key={provider.id} value={provider.id}>
                          {provider.display_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                <div className="p-3 rounded-xl bg-blue-500/5 border border-blue-500/20">
                  <p className="text-[12px] text-zinc-400">
                    Files are managed by the provider&apos;s vector store. Knowledge base configuration is handled by the provider.
                  </p>
                </div>
              </div>
            )}

            {/* Upload Files */}
            <div className="space-y-3">
              <Label className="text-[13px] text-zinc-400 flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Upload Files
                <InfoTip text="Upload files to this knowledge base. Files are automatically parsed, chunked, and indexed for retrieval." />
              </Label>
              <p className="text-[11px] text-zinc-600">
                Supported: {SUPPORTED_FILE_TYPES}
              </p>
              <div
                className="rounded-xl border-2 border-dashed border-zinc-700 hover:border-zinc-600 transition-colors cursor-pointer p-6 text-center"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="w-8 h-8 mx-auto mb-2 text-zinc-500" />
                <p className="text-[13px] text-zinc-400">Click to select files or drag & drop</p>
                <p className="text-[11px] text-zinc-600 mt-1">Max 50MB per file</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.txt,.md,.html,.htm,.docx,.doc,.pptx,.xlsx,.json,.csv,.epub,.png,.jpg,.jpeg,.tiff,.tif,.tex,.rtf"
                  className="hidden"
                  onChange={(e) => handleFilesSelected(e.target.files)}
                />
              </div>
              {pendingFiles.length > 0 && (
                <div className="rounded-xl border border-zinc-800 overflow-hidden max-h-48 overflow-y-auto">
                  <div className="divide-y divide-zinc-800">
                    {pendingFiles.map((pf, i) => (
                      <div key={i} className="flex items-center gap-3 p-3">
                        <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                          <File className="h-4 w-4 text-zinc-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-[13px] font-medium text-white truncate">{pf.name}</p>
                          <p className="text-[11px] text-zinc-500">{formatFileSize(pf.size)}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => removePendingFile(i)}
                          className="text-zinc-500 hover:text-red-400 transition-colors"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {pendingFiles.length > 0 && (
                <p className="text-[12px] text-emerald-400">
                  {pendingFiles.length} file(s) selected
                </p>
              )}
            </div>

            {/* Select Existing Files */}
            {existingFiles.length > 0 && (
              <div className="space-y-3">
                <Label className="text-[13px] text-zinc-400 flex items-center gap-2">
                  <FolderOpen className="h-4 w-4" />
                  Existing Files
                  <InfoTip text="Select files already uploaded to your account. They will be assigned to this knowledge base and processed if not already." />
                </Label>
                {isLoadingExistingFiles ? (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                    <Loader2 className="h-4 w-4 animate-spin text-zinc-500" />
                    <span className="text-[13px] text-zinc-500">Loading files...</span>
                  </div>
                ) : (
                  <div className="rounded-xl border border-zinc-800 overflow-hidden max-h-48 overflow-y-auto">
                    <div className="divide-y divide-zinc-800">
                      {existingFiles.map((ef) => {
                        const isSelected = selectedExistingFileIds.has(ef.id);
                        return (
                          <div
                            key={ef.id}
                            onClick={() => toggleExistingFile(ef.id)}
                            className={cn(
                              'flex items-center gap-3 p-3 cursor-pointer transition-colors',
                              isSelected ? 'bg-emerald-500/10' : 'hover:bg-zinc-900/50'
                            )}
                          >
                            <div className={cn(
                              'w-5 h-5 rounded border flex items-center justify-center flex-shrink-0 transition-colors',
                              isSelected ? 'bg-emerald-500 border-emerald-500' : 'border-zinc-700'
                            )}>
                              {isSelected && <Check className="h-3 w-3 text-white" />}
                            </div>
                            <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center flex-shrink-0">
                              <File className="h-4 w-4 text-zinc-400" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-[13px] font-medium text-white truncate">{ef.filename}</p>
                              <p className="text-[11px] text-zinc-500">
                                {ef.status}
                                {ef.chunk_count > 0 && ` | ${ef.chunk_count} chunks`}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                {selectedExistingFileIds.size > 0 && (
                  <p className="text-[12px] text-emerald-400">
                    {selectedExistingFileIds.size} existing file(s) selected
                  </p>
                )}
              </div>
            )}

            {/* Submit Buttons */}
            <div className="flex gap-3 pt-4 border-t border-zinc-800">
              <Button
                type="submit"
                disabled={isCreating}
                className="flex-1 btn-primary"
              >
                {isCreating && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                Create Knowledge Base
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowCreateSheet(false);
                  setKbMode('provider_managed');
                  setSelectedProviderId('');
                  setPendingFiles([]);
                  setSelectedExistingFileIds(new Set());
                  reset();
                }}
                className="btn-outline"
              >
                Cancel
              </Button>
            </div>
          </form>
        </SheetContent>
      </Sheet>
    </div>
  );
}
