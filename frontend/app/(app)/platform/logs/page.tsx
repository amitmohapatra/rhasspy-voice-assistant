'use client';

import { useState } from 'react';
import { FileText, Search, Filter, Download, RefreshCw, ChevronRight, Check, X, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface LogEntry {
  id: string;
  timestamp: string;
  endpoint: string;
  method: string;
  status: number;
  duration: number;
  model?: string;
  tokens?: number;
}

const mockLogs: LogEntry[] = [
  {
    id: '1',
    timestamp: '2024-01-30 14:32:15',
    endpoint: '/v1/chat/completions',
    method: 'POST',
    status: 200,
    duration: 1234,
    model: 'gpt-4o',
    tokens: 856,
  },
  {
    id: '2',
    timestamp: '2024-01-30 14:31:42',
    endpoint: '/v1/embeddings',
    method: 'POST',
    status: 200,
    duration: 245,
    model: 'text-embedding-3-small',
    tokens: 128,
  },
  {
    id: '3',
    timestamp: '2024-01-30 14:30:55',
    endpoint: '/v1/audio/transcriptions',
    method: 'POST',
    status: 200,
    duration: 3456,
    model: 'whisper-1',
  },
  {
    id: '4',
    timestamp: '2024-01-30 14:29:18',
    endpoint: '/v1/chat/completions',
    method: 'POST',
    status: 429,
    duration: 12,
    model: 'gpt-4o',
  },
  {
    id: '5',
    timestamp: '2024-01-30 14:28:03',
    endpoint: '/v1/images/generations',
    method: 'POST',
    status: 200,
    duration: 8923,
    model: 'dall-e-3',
  },
];

export default function LogsPage() {
  const [logs] = useState<LogEntry[]>(mockLogs);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);

  const getStatusColor = (status: number) => {
    if (status >= 200 && status < 300) return 'text-green-500';
    if (status >= 400 && status < 500) return 'text-yellow-500';
    return 'text-red-500';
  };

  const getStatusBadge = (status: number) => {
    if (status >= 200 && status < 300) return 'bg-green-500/10 text-green-500';
    if (status >= 400 && status < 500) return 'bg-yellow-500/10 text-yellow-500';
    return 'bg-red-500/10 text-red-500';
  };

  const filteredLogs = logs.filter((log) => {
    if (statusFilter !== 'all') {
      if (statusFilter === 'success' && (log.status < 200 || log.status >= 300)) return false;
      if (statusFilter === 'error' && log.status < 400) return false;
    }
    if (search && !log.endpoint.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="flex-1 p-6 overflow-y-auto">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold flex items-center gap-2">
              <FileText className="w-6 h-6" />
              Logs
            </h1>
            <p className="text-muted-foreground mt-1">
              View API request logs and debug issues
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="icon">
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>
        </div>

        {/* Filters */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by endpoint..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[150px]">
                  <Filter className="w-4 h-4 mr-2" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="success">Success (2xx)</SelectItem>
                  <SelectItem value="error">Error (4xx, 5xx)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Logs Table */}
        <Card>
          <CardHeader>
            <CardTitle>Request Logs</CardTitle>
            <CardDescription>
              Showing {filteredLogs.length} of {logs.length} requests
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {filteredLogs.map((log) => (
                <button
                  key={log.id}
                  onClick={() => setSelectedLog(selectedLog?.id === log.id ? null : log)}
                  className="w-full text-left p-4 rounded-lg border hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <Badge variant="outline" className={getStatusBadge(log.status)}>
                        {log.status}
                      </Badge>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{log.method}</span>
                          <span className="text-sm">{log.endpoint}</span>
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                          <span>{log.timestamp}</span>
                          {log.model && <span>{log.model}</span>}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right text-sm">
                        <div className="flex items-center gap-1 text-muted-foreground">
                          <Clock className="w-3 h-3" />
                          {log.duration}ms
                        </div>
                        {log.tokens && (
                          <div className="text-xs text-muted-foreground">
                            {log.tokens} tokens
                          </div>
                        )}
                      </div>
                      <ChevronRight
                        className={cn(
                          'w-4 h-4 text-muted-foreground transition-transform',
                          selectedLog?.id === log.id && 'rotate-90'
                        )}
                      />
                    </div>
                  </div>

                  {selectedLog?.id === log.id && (
                    <div className="mt-4 pt-4 border-t space-y-4">
                      <div>
                        <h4 className="text-sm font-medium mb-2">Request Details</h4>
                        <pre className="p-3 bg-muted rounded-lg text-xs overflow-x-auto">
{`{
  "model": "${log.model}",
  "messages": [
    {
      "role": "user",
      "content": "..."
    }
  ],
  "temperature": 0.7
}`}
                        </pre>
                      </div>
                      <div>
                        <h4 className="text-sm font-medium mb-2">Response</h4>
                        <pre className="p-3 bg-muted rounded-lg text-xs overflow-x-auto">
{`{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": 1706625135,
  "model": "${log.model}",
  "usage": {
    "prompt_tokens": 128,
    "completion_tokens": ${log.tokens || 256},
    "total_tokens": ${(log.tokens || 256) + 128}
  }
}`}
                        </pre>
                      </div>
                    </div>
                  )}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
