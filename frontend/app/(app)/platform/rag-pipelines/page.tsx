'use client';

/**
 * RAG Pipeline Info & Testing
 *
 * Shows the fixed automated RAG pipeline components and provides
 * connection testing and end-to-end pipeline testing.
 */

import { useState } from 'react';
import { api } from '@/lib/api';
import {
  Workflow,
  Zap,
  Database,
  Search,
  Layers,
  FileText,
  Upload,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Send,
  Server,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';

const PIPELINE_COMPONENTS = [
  {
    name: 'Docling HybridChunker',
    description: 'Structure-aware chunking that auto-adapts to document type (headings, tables, lists, code)',
    badge: 'Chunking',
    color: 'blue',
  },
  {
    name: 'Late Chunking (BGE-M3)',
    description: 'Document-context-aware embeddings — zero LLM calls, each chunk inherits full document context',
    badge: 'Embedding',
    color: 'amber',
  },
  {
    name: 'Parent-Child Retrieval',
    description: 'Index small chunks for precision, return parent sections for broader context',
    badge: 'Retrieval',
    color: 'violet',
  },
  {
    name: 'PaddleOCR-VL + img2table',
    description: 'Visual document enrichment: OCR for images/charts/tables, borderless table extraction',
    badge: 'Enrichment',
    color: 'purple',
  },
  {
    name: '4-Way Hybrid + RRF',
    description: 'Dense + Sparse + BM25 + Visual retrieval with Reciprocal Rank Fusion',
    badge: 'Retrieval',
    color: 'emerald',
  },
  {
    name: 'BGE-reranker-v2-m3',
    description: 'Cross-encoder reranking for final result quality',
    badge: 'Reranker',
    color: 'orange',
  },
  {
    name: 'Qdrant',
    description: 'High-performance vector database with named vectors',
    badge: 'Vector Store',
    color: 'cyan',
  },
  {
    name: 'Redis',
    description: 'Semantic query cache for fast repeated lookups',
    badge: 'Cache',
    color: 'red',
  },
];

const BADGE_COLORS: Record<string, string> = {
  blue: 'bg-blue-500/20 text-blue-400',
  amber: 'bg-amber-500/20 text-amber-400',
  violet: 'bg-violet-500/20 text-violet-400',
  purple: 'bg-purple-500/20 text-purple-400',
  emerald: 'bg-emerald-500/20 text-emerald-400',
  orange: 'bg-orange-500/20 text-orange-400',
  cyan: 'bg-cyan-500/20 text-cyan-400',
  red: 'bg-red-500/20 text-red-400',
};

export default function RAGPipelinesPage() {
  const { toast } = useToast();

  // Connection test state
  const [qdrantUrl, setQdrantUrl] = useState('http://localhost:6333');
  const [redisUrl, setRedisUrl] = useState('redis://localhost:6379');
  const [testingQdrant, setTestingQdrant] = useState(false);
  const [testingRedis, setTestingRedis] = useState(false);
  const [qdrantResult, setQdrantResult] = useState<{ success: boolean; message: string } | null>(null);
  const [redisResult, setRedisResult] = useState<{ success: boolean; message: string } | null>(null);

  // Pipeline test state
  const [testFile, setTestFile] = useState<File | null>(null);
  const [testQuery, setTestQuery] = useState('');
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    chunks_created?: number;
    results?: { content: string; score: number; element_type: string; page_number?: number }[];
    timings?: Record<string, number>;
    error?: string;
  } | null>(null);

  const testQdrant = async () => {
    setTestingQdrant(true);
    setQdrantResult(null);
    try {
      const token = api.getToken();
      const res = await fetch('/api/v1/rag-pipelines/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ connection_type: 'qdrant', config: { url: qdrantUrl } }),
      });
      const data = await res.json();
      setQdrantResult({ success: data.success, message: data.message });
    } catch (e) {
      setQdrantResult({ success: false, message: 'Connection failed' });
    } finally {
      setTestingQdrant(false);
    }
  };

  const testRedis = async () => {
    setTestingRedis(true);
    setRedisResult(null);
    try {
      const token = api.getToken();
      const res = await fetch('/api/v1/rag-pipelines/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ connection_type: 'redis', config: { url: redisUrl } }),
      });
      const data = await res.json();
      setRedisResult({ success: data.success, message: data.message });
    } catch (e) {
      setRedisResult({ success: false, message: 'Connection failed' });
    } finally {
      setTestingRedis(false);
    }
  };

  const testPipeline = async () => {
    if (!testFile || !testQuery.trim()) return;
    setIsTesting(true);
    setTestResult(null);
    try {
      const token = api.getToken();
      const formData = new FormData();
      formData.append('file', testFile);
      formData.append('query', testQuery);
      const res = await fetch('/api/v1/rag-pipelines/test', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const data = await res.json();
      setTestResult(data);
    } catch (e) {
      setTestResult({ success: false, error: 'Pipeline test failed' });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-6 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">RAG Pipeline</h1>
          <p className="text-[13px] text-zinc-500 mt-1">
            Fully automated document processing and retrieval. No configuration needed.
          </p>
        </div>

        {/* Pipeline Components */}
        <div>
          <h2 className="text-[15px] font-semibold text-white mb-4 flex items-center gap-2">
            <Workflow className="h-4 w-4 text-emerald-400" />
            Pipeline Components
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {PIPELINE_COMPONENTS.map((comp) => (
              <div
                key={comp.name}
                className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50 flex items-start gap-3"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[13px] font-semibold text-white">{comp.name}</span>
                    <Badge className={`text-[9px] font-medium border-0 ${BADGE_COLORS[comp.color]}`}>
                      {comp.badge}
                    </Badge>
                  </div>
                  <p className="text-[12px] text-zinc-500">{comp.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Connection Testing */}
        <div>
          <h2 className="text-[15px] font-semibold text-white mb-4 flex items-center gap-2">
            <Server className="h-4 w-4 text-emerald-400" />
            Connection Testing
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Qdrant */}
            <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50 space-y-3">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-cyan-400" />
                <span className="text-[13px] font-semibold text-white">Qdrant</span>
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-zinc-500">URL</Label>
                <Input
                  value={qdrantUrl}
                  onChange={(e) => setQdrantUrl(e.target.value)}
                  className="bg-zinc-800/50 border-zinc-700 text-[13px] text-white"
                  placeholder="http://localhost:6333"
                />
              </div>
              <Button
                onClick={testQdrant}
                disabled={testingQdrant}
                size="sm"
                className="w-full bg-cyan-600 hover:bg-cyan-700 text-white"
              >
                {testingQdrant ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Zap className="h-4 w-4 mr-2" />}
                Test Connection
              </Button>
              {qdrantResult && (
                <div className={`flex items-center gap-2 text-[12px] ${qdrantResult.success ? 'text-emerald-400' : 'text-red-400'}`}>
                  {qdrantResult.success ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                  {qdrantResult.message}
                </div>
              )}
            </div>

            {/* Redis */}
            <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50 space-y-3">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-red-400" />
                <span className="text-[13px] font-semibold text-white">Redis</span>
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-zinc-500">URL</Label>
                <Input
                  value={redisUrl}
                  onChange={(e) => setRedisUrl(e.target.value)}
                  className="bg-zinc-800/50 border-zinc-700 text-[13px] text-white"
                  placeholder="redis://localhost:6379"
                />
              </div>
              <Button
                onClick={testRedis}
                disabled={testingRedis}
                size="sm"
                className="w-full bg-red-600 hover:bg-red-700 text-white"
              >
                {testingRedis ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Zap className="h-4 w-4 mr-2" />}
                Test Connection
              </Button>
              {redisResult && (
                <div className={`flex items-center gap-2 text-[12px] ${redisResult.success ? 'text-emerald-400' : 'text-red-400'}`}>
                  {redisResult.success ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                  {redisResult.message}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* End-to-End Test */}
        <div>
          <h2 className="text-[15px] font-semibold text-white mb-4 flex items-center gap-2">
            <Search className="h-4 w-4 text-emerald-400" />
            End-to-End Pipeline Test
          </h2>
          <div className="p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50 space-y-4">
            <p className="text-[12px] text-zinc-500">
              Upload a document and query it to test the full pipeline: parse, chunk, embed, store, retrieve, rerank.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-[12px] text-zinc-500">Document</Label>
                <input
                  type="file"
                  onChange={(e) => setTestFile(e.target.files?.[0] || null)}
                  className="w-full text-[13px] text-zinc-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-[12px] file:font-medium file:bg-zinc-800 file:text-zinc-300 hover:file:bg-zinc-700"
                  accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.html,.csv"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[12px] text-zinc-500">Query</Label>
                <div className="flex gap-2">
                  <Input
                    value={testQuery}
                    onChange={(e) => setTestQuery(e.target.value)}
                    placeholder="What is this document about?"
                    className="bg-zinc-800/50 border-zinc-700 text-[13px] text-white"
                    onKeyDown={(e) => e.key === 'Enter' && testPipeline()}
                  />
                  <Button
                    onClick={testPipeline}
                    disabled={!testFile || !testQuery.trim() || isTesting}
                    className="btn-primary shrink-0"
                  >
                    {isTesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
            </div>

            {/* Test Results */}
            {testResult && (
              <div className="space-y-3 pt-3 border-t border-zinc-800">
                {testResult.success ? (
                  <>
                    <div className="flex items-center gap-2 text-[12px] text-emerald-400">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Pipeline test successful — {testResult.chunks_created} chunks created
                    </div>

                    {testResult.timings && (
                      <div className="flex flex-wrap gap-3 p-3 rounded-lg bg-zinc-800/50">
                        {Object.entries(testResult.timings).map(([key, value]) => (
                          <span key={key} className="text-[11px] text-zinc-500">
                            <span className="text-zinc-400 capitalize">{key.replace(/_/g, ' ')}</span>{' '}
                            <span className="font-mono text-emerald-400">{typeof value === 'number' ? value.toFixed(0) : value}ms</span>
                          </span>
                        ))}
                      </div>
                    )}

                    {testResult.results && testResult.results.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-[12px] text-zinc-500">{testResult.results.length} results:</p>
                        {testResult.results.map((r, i) => (
                          <div key={i} className="p-3 rounded-lg bg-zinc-800/50">
                            <div className="flex items-center justify-between mb-1">
                              <div className="flex items-center gap-2">
                                <Badge className="text-[9px] font-medium border-0 bg-purple-500/20 text-purple-400">
                                  {r.element_type}
                                </Badge>
                                {r.page_number && (
                                  <span className="text-[10px] text-zinc-500">page {r.page_number}</span>
                                )}
                              </div>
                              <span className="text-[10px] font-mono text-emerald-400">{r.score.toFixed(4)}</span>
                            </div>
                            <p className="text-[12px] text-zinc-300 leading-relaxed line-clamp-3">{r.content}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="flex items-center gap-2 text-[12px] text-red-400">
                    <XCircle className="h-3.5 w-3.5" />
                    {testResult.error || 'Pipeline test failed'}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
