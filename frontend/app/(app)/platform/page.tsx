'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Bot,
  Users,
  BarChart3,
  Settings,
  Loader2,
  LogOut,
  Mic,
  FileText,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

type TabType = 'overview' | 'audit' | 'config';

interface PlatformStats {
  total_users: number;
  active_users_30d: number;
  total_voice_minutes_mtd: number;
}

interface AuditLog {
  id: string;
  user_email: string | null;
  action: string;
  description: string | null;
  severity: string;
  created_at: string;
}

export default function PlatformPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [isLoading, setIsLoading] = useState(true);

  // Data states
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  useEffect(() => {
    checkAccess();
  }, []);

  const checkAccess = async () => {
    const token = api.getToken();
    if (!token) {
      router.push('/auth/login');
      return;
    }

    try {
      await api.getMe();
      await loadData();
    } catch (error) {
      console.error('Access check failed:', error);
      router.push('/auth/login');
    } finally {
      setIsLoading(false);
    }
  };

  const loadData = async () => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const headers = { Authorization: `Bearer ${api.getToken()}` };

    try {
      // Load stats
      const statsRes = await fetch(`${baseUrl}/api/v1/platform/stats`, { headers });
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }

      // Load audit logs
      const logsRes = await fetch(`${baseUrl}/api/v1/platform/audit-logs?limit=50`, { headers });
      if (logsRes.ok) {
        setAuditLogs(await logsRes.json());
      }
    } catch (error) {
      console.error('Failed to load platform data:', error);
    }
  };

  const handleLogout = () => {
    api.logout();
    router.push('/auth/login');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-gradient-to-r from-primary/10 to-primary/5">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-8 w-8 text-primary" />
            <span className="text-xl font-bold">Platform</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <Button variant="outline" size="sm">
                <Bot className="h-4 w-4 mr-2" />
                Dashboard
              </Button>
            </Link>
            <Button variant="ghost" size="icon" onClick={handleLogout}>
              <LogOut className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="flex flex-col lg:flex-row gap-8">
          {/* Sidebar */}
          <div className="lg:w-64 shrink-0">
            <nav className="space-y-1">
              {[
                { id: 'overview', label: 'Overview', icon: BarChart3 },
                { id: 'audit', label: 'Audit Logs', icon: FileText },
                { id: 'config', label: 'Configuration', icon: Settings },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={cn(
                    'w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors',
                    activeTab === tab.id
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-muted'
                  )}
                >
                  <tab.icon className="h-5 w-5" />
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Main Content */}
          <div className="flex-1 min-w-0">
            {/* Overview Tab */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                <h2 className="text-2xl font-bold">Platform Overview</h2>

                {stats && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <Card>
                      <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm text-muted-foreground">Total Users</p>
                            <p className="text-3xl font-bold">{stats.total_users}</p>
                            <p className="text-xs text-green-600">
                              {stats.active_users_30d} active (30d)
                            </p>
                          </div>
                          <Users className="h-8 w-8 text-primary/50" />
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm text-muted-foreground">Voice Minutes (MTD)</p>
                            <p className="text-3xl font-bold">
                              {stats.total_voice_minutes_mtd.toFixed(0)}
                            </p>
                          </div>
                          <Mic className="h-8 w-8 text-primary/50" />
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* Recent Activity */}
                {auditLogs.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Recent Activity</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {auditLogs.slice(0, 5).map((log) => (
                          <div
                            key={log.id}
                            className="flex items-center gap-3 p-3 rounded-lg border"
                          >
                            <div className={cn(
                              'w-2 h-2 rounded-full',
                              log.severity === 'warning' ? 'bg-amber-500' :
                              log.severity === 'error' ? 'bg-red-500' : 'bg-green-500'
                            )} />
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">
                                {log.description || log.action}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {log.user_email || 'System'}
                              </p>
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {new Date(log.created_at).toLocaleString()}
                            </span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            )}

            {/* Audit Logs Tab */}
            {activeTab === 'audit' && (
              <div className="space-y-6">
                <h2 className="text-2xl font-bold">Audit Logs</h2>

                <Card>
                  <CardContent className="pt-6">
                    <div className="space-y-3">
                      {auditLogs.map((log) => (
                        <div
                          key={log.id}
                          className="flex items-start gap-3 p-3 rounded-lg border hover:bg-muted/50"
                        >
                          <div className={cn(
                            'w-2 h-2 rounded-full mt-2',
                            log.severity === 'warning' ? 'bg-amber-500' :
                            log.severity === 'error' ? 'bg-red-500' :
                            log.severity === 'critical' ? 'bg-red-700' : 'bg-green-500'
                          )} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium">{log.action}</span>
                              <span className={cn(
                                'px-1.5 py-0.5 text-xs rounded',
                                log.severity === 'warning' ? 'bg-amber-100 text-amber-800' :
                                log.severity === 'error' ? 'bg-red-100 text-red-800' : 'bg-gray-100'
                              )}>
                                {log.severity}
                              </span>
                            </div>
                            <p className="text-sm text-muted-foreground">
                              {log.description}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {log.user_email || 'System'} • {new Date(log.created_at).toLocaleString()}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Configuration Tab */}
            {activeTab === 'config' && (
              <div className="space-y-6">
                <h2 className="text-2xl font-bold">Platform Configuration</h2>

                <Card>
                  <CardHeader>
                    <CardTitle>General Settings</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label>Platform Name</Label>
                      <Input defaultValue="Rhasspy Voice Assistant" className="mt-1" />
                    </div>
                    <div>
                      <Label>Support Email</Label>
                      <Input defaultValue="support@rhasspy.ai" className="mt-1" />
                    </div>
                    <Button>Save Changes</Button>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </div>
      </div>

    </div>
  );
}
