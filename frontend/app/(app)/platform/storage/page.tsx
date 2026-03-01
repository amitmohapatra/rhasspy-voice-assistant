'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Database,
  Upload,
  FileText,
  Image,
  Video,
  Music,
  File,
  Trash2,
  Download,
  MoreVertical,
  Link2,
  Unlink,
  Loader2,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { api, type KnowledgeBase } from '@/lib/api';
import { SearchFilterBar } from '@/components/ui/search-filter-bar';
import { Pagination } from '@/components/ui/pagination';
import { DataLoading, DataEmpty, DataError } from '@/components/ui/data-states';
import { usePagination } from '@/hooks/use-pagination';
import { formatFileSize, getStatusColor } from '@/lib/format';
import { useToast } from '@/hooks/use-toast';

interface KBInfo {
  id: string;
  name: string;
}

interface FileItem {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  file_path: string;
  status: string;
  knowledge_bases: KBInfo[];
  uploaded_by_email: string | null;
  uploaded_by_name: string | null;
  created_at: string;
}

const FILE_TYPE_OPTIONS = [
  { value: 'all', label: 'All Types' },
  { value: 'pdf', label: 'PDF' },
  { value: 'txt', label: 'Text' },
  { value: 'md', label: 'Markdown' },
  { value: 'html', label: 'HTML' },
  { value: 'docx', label: 'Word' },
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
  { value: 'png', label: 'PNG' },
  { value: 'jpg', label: 'JPEG' },
];

const STATUS_OPTIONS = [
  { value: 'all', label: 'All Status' },
  { value: 'uploaded', label: 'Uploaded' },
  { value: 'pending', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'error', label: 'Error' },
];

const getFileIcon = (fileType: string) => {
  if (['png', 'jpg', 'jpeg', 'tiff', 'tif'].includes(fileType)) return Image;
  if (['mp4', 'webm', 'avi'].includes(fileType)) return Video;
  if (['mp3', 'wav', 'ogg'].includes(fileType)) return Music;
  if (['pdf', 'docx', 'doc', 'txt', 'md', 'html', 'rtf', 'epub'].includes(fileType)) return FileText;
  return File;
};

export default function StoragePage() {
  const { toast } = useToast();
  const [files, setFiles] = useState<FileItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [fileTypeFilter, setFileTypeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const debounceTimer = useRef<NodeJS.Timeout>();

  // Upload state
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Assign modal state
  const [assigningFileId, setAssigningFileId] = useState<string | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [isLoadingKBs, setIsLoadingKBs] = useState(false);

  const { page, pageSize, skip, total, setPage, setPageSize, setTotal } = usePagination({ initialPageSize: 20 });

  // Debounced search
  useEffect(() => {
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(debounceTimer.current);
  }, [searchQuery]);

  // Fetch data when pagination, search, or filter changes
  useEffect(() => {
    fetchFiles();
  }, [skip, pageSize, debouncedSearch, fileTypeFilter, statusFilter]);

  const fetchFiles = async () => {
    const token = api.getToken();
    if (!token) {
      setFiles([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const data = await api.listFiles({
        skip,
        limit: pageSize,
        search: debouncedSearch || undefined,
        file_type: fileTypeFilter !== 'all' ? fileTypeFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
      });
      setFiles(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load files');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;

    setIsUploading(true);
    let successCount = 0;
    for (const file of Array.from(fileList)) {
      try {
        await api.uploadFile(file);
        successCount++;
      } catch (err) {
        toast({
          variant: 'destructive',
          title: 'Upload Error',
          description: `Failed to upload ${file.name}: ${err instanceof Error ? err.message : 'Unknown error'}`,
        });
      }
    }
    setIsUploading(false);
    if (successCount > 0) {
      toast({ title: 'Success', description: `${successCount} file(s) uploaded` });
      fetchFiles();
    }
    // Reset the input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (fileId: string) => {
    if (!confirm('Delete this file permanently? It will be removed from all knowledge bases.')) return;
    try {
      await api.deleteFile(fileId);
      toast({ title: 'Deleted', description: 'File deleted successfully' });
      fetchFiles();
    } catch (err) {
      toast({ variant: 'destructive', title: 'Error', description: 'Failed to delete file' });
    }
  };

  const openAssignModal = async (fileId: string) => {
    setAssigningFileId(fileId);
    setIsLoadingKBs(true);
    try {
      const resp = await api.listKnowledgeBases({ limit: 100 });
      setKnowledgeBases(resp.items);
    } catch {
      toast({ variant: 'destructive', title: 'Error', description: 'Failed to load knowledge bases' });
    } finally {
      setIsLoadingKBs(false);
    }
  };

  const handleAssign = async (fileId: string, kbId: string) => {
    try {
      await api.assignFileToKB(fileId, kbId);
      toast({ title: 'Assigned', description: 'File assigned to knowledge base. Processing will begin automatically.' });
      setAssigningFileId(null);
      fetchFiles();
    } catch (err) {
      toast({ variant: 'destructive', title: 'Error', description: err instanceof Error ? err.message : 'Failed to assign' });
    }
  };

  const handleUnassign = async (fileId: string, kbId: string, kbName: string) => {
    if (!confirm(`Remove this file from "${kbName}"?`)) return;
    try {
      await api.unassignFileFromKB(fileId, kbId);
      toast({ title: 'Removed', description: `File removed from ${kbName}` });
      fetchFiles();
    } catch {
      toast({ variant: 'destructive', title: 'Error', description: 'Failed to unassign file' });
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Files</h1>
          <p className="text-[13px] text-zinc-500 mt-1">
            Upload and manage documents. Assign files to knowledge bases for RAG processing.
          </p>
        </div>
        <Button
          className="btn-primary"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
        >
          {isUploading ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Upload className="w-4 h-4 mr-2" />
          )}
          Upload Files
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.html,.htm,.docx,.doc,.pptx,.xlsx,.json,.csv,.epub,.png,.jpg,.jpeg,.tiff,.tif,.tex,.rtf"
          className="hidden"
          onChange={(e) => handleUpload(e.target.files)}
        />
      </div>

      {/* Search & Filter Bar */}
      <SearchFilterBar
        searchValue={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search files..."
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        showViewToggle
        filters={[
          {
            key: 'file_type',
            label: 'File Type',
            options: FILE_TYPE_OPTIONS,
            value: fileTypeFilter,
            onChange: (val) => {
              setFileTypeFilter(val);
              setPage(1);
            },
          },
          {
            key: 'status',
            label: 'Status',
            options: STATUS_OPTIONS,
            value: statusFilter,
            onChange: (val) => {
              setStatusFilter(val);
              setPage(1);
            },
          },
        ]}
        className="mb-6"
      />

      {/* Content */}
      {error ? (
        <DataError message={error} onRetry={fetchFiles} />
      ) : isLoading ? (
        <DataLoading message="Loading files..." />
      ) : files.length === 0 ? (
        <DataEmpty
          icon={<Database className="w-7 h-7 text-zinc-600" />}
          title={debouncedSearch || fileTypeFilter !== 'all' || statusFilter !== 'all' ? 'No results found' : 'No files yet'}
          description={
            debouncedSearch || fileTypeFilter !== 'all' || statusFilter !== 'all'
              ? 'Try adjusting your search or filters'
              : 'Upload files to get started. You can assign them to knowledge bases later.'
          }
          action={!debouncedSearch && fileTypeFilter === 'all' && statusFilter === 'all' ? {
            label: 'Upload Files',
            onClick: () => fileInputRef.current?.click(),
          } : undefined}
        />
      ) : viewMode === 'list' ? (
        <div className="space-y-2">
          {files.map((file) => {
            const FileIcon = getFileIcon(file.file_type);
            return (
              <div
                key={file.id}
                className="flex items-center justify-between p-3 rounded-xl bg-zinc-900/50 border border-zinc-800/50 hover:border-zinc-700 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center flex-shrink-0">
                    <FileIcon className="w-5 h-5 text-zinc-400" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-white truncate">{file.filename}</p>
                    <div className="flex items-center gap-2 text-[11px] text-zinc-500">
                      <span>{formatFileSize(file.file_size)}</span>
                      <span>{'\u00b7'}</span>
                      <span>{file.file_type.toUpperCase()}</span>
                      {file.knowledge_bases.length > 0 && (
                        <>
                          <span>{'\u00b7'}</span>
                          <span className="flex items-center gap-1">
                            <Link2 className="w-3 h-3" />
                            {file.knowledge_bases.map(kb => kb.name).join(', ')}
                          </span>
                        </>
                      )}
                      {file.uploaded_by_name && (
                        <>
                          <span>{'\u00b7'}</span>
                          <span>{file.uploaded_by_name}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span
                    className={cn(
                      'inline-flex items-center text-[11px] font-medium px-2 py-0.5 rounded capitalize',
                      getStatusColor(file.status)
                    )}
                  >
                    {file.status}
                  </span>
                  <span className="text-[11px] text-zinc-600">
                    {new Date(file.created_at).toLocaleDateString()}
                  </span>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="p-1.5 hover:bg-zinc-800 rounded transition-colors">
                        <MoreVertical className="w-4 h-4 text-zinc-500" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="bg-[#18181b] border-zinc-800">
                      <DropdownMenuItem
                        className="flex items-center gap-2"
                        onClick={() => openAssignModal(file.id)}
                      >
                        <Link2 className="w-3.5 h-3.5" /> Assign to KB
                      </DropdownMenuItem>
                      {file.knowledge_bases.map(kb => (
                        <DropdownMenuItem
                          key={kb.id}
                          className="flex items-center gap-2 text-orange-400 focus:text-orange-400"
                          onClick={() => handleUnassign(file.id, kb.id, kb.name)}
                        >
                          <Unlink className="w-3.5 h-3.5" /> Remove from {kb.name}
                        </DropdownMenuItem>
                      ))}
                      <DropdownMenuSeparator className="border-zinc-800" />
                      <DropdownMenuItem
                        className="flex items-center gap-2 text-red-400 focus:text-red-400"
                        onClick={() => handleDelete(file.id)}
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {files.map((file) => {
            const FileIcon = getFileIcon(file.file_type);
            return (
              <div
                key={file.id}
                className="card-interactive p-4 group"
              >
                <div className="aspect-square rounded-lg bg-zinc-800 flex items-center justify-center mb-3">
                  <FileIcon className="w-10 h-10 text-zinc-500" />
                </div>
                <p className="text-[13px] font-medium text-white truncate">{file.filename}</p>
                <p className="text-[11px] text-zinc-500">{formatFileSize(file.file_size)}</p>
                {file.knowledge_bases.length > 0 && (
                  <p className="text-[11px] text-zinc-600 truncate">
                    {file.knowledge_bases.map(kb => kb.name).join(', ')}
                  </p>
                )}
                <span
                  className={cn(
                    'inline-flex items-center text-[10px] font-medium px-2 py-0.5 rounded capitalize mt-2',
                    getStatusColor(file.status)
                  )}
                >
                  {file.status}
                </span>
              </div>
            );
          })}
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

      {/* Assign to KB Modal */}
      {assigningFileId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-md bg-[#0f0f10] border border-zinc-800 rounded-2xl p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[16px] font-semibold text-white">Assign to Knowledge Base</h3>
              <button onClick={() => setAssigningFileId(null)} className="text-zinc-500 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            {isLoadingKBs ? (
              <div className="flex items-center gap-2 py-8 justify-center">
                <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
                <span className="text-[13px] text-zinc-500">Loading knowledge bases...</span>
              </div>
            ) : knowledgeBases.length === 0 ? (
              <div className="text-center py-8">
                <Database className="w-8 h-8 mx-auto mb-2 text-zinc-600" />
                <p className="text-[13px] text-zinc-400">No knowledge bases available</p>
                <p className="text-[11px] text-zinc-600 mt-1">Create a knowledge base first</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {knowledgeBases.map(kb => {
                  const alreadyAssigned = files.find(f => f.id === assigningFileId)
                    ?.knowledge_bases.some(k => k.id === kb.id);
                  return (
                    <button
                      key={kb.id}
                      disabled={alreadyAssigned}
                      onClick={() => handleAssign(assigningFileId, kb.id)}
                      className={cn(
                        'w-full flex items-center gap-3 p-3 rounded-xl border text-left transition-colors',
                        alreadyAssigned
                          ? 'border-zinc-800 bg-zinc-900/30 opacity-50 cursor-not-allowed'
                          : 'border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/50 cursor-pointer'
                      )}
                    >
                      <Database className="w-5 h-5 text-blue-400 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-[13px] font-medium text-white truncate">{kb.name}</p>
                        <p className="text-[11px] text-zinc-500 truncate">
                          {alreadyAssigned ? 'Already assigned' : kb.description || 'No description'}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
