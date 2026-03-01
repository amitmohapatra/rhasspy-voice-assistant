'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Sparkles } from 'lucide-react';
import { AppSidebar } from '@/components/layout/app-sidebar';
import { AppHeader } from '@/components/layout/app-header';
import { api } from '@/lib/api';
import type { User } from '@/types/user';

interface AppLayoutProps {
  children: React.ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadUser = async () => {
      const token = api.getToken();
      if (!token) {
        // Middleware handles redirect — just stay on loading screen
        return;
      }

      try {
        const userData = await api.getMe();
        setUser({
          id: userData.id || '1',
          email: userData.email,
          full_name: userData.full_name || userData.name,
          is_active: true,
          created_at: userData.created_at || new Date().toISOString(),
          updated_at: userData.updated_at || new Date().toISOString(),
          preferences: userData.preferences as any || {
            theme: 'dark',
            language: 'en',
            timezone: 'UTC',
          },
        });
      } catch {
        // Token invalid — clear and let middleware redirect on next load
        api.setToken(null);
        window.location.reload();
        return;
      } finally {
        setIsLoading(false);
      }
    };

    loadUser();
  }, []);

  const handleLogout = () => {
    api.logout();
    router.push('/auth/login');
  };

  return (
    <div className="min-h-screen flex bg-background">
      <AppSidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <AppHeader user={user} onLogout={handleLogout} />
        <main className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center min-h-[400px]">
              <div className="flex flex-col items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center animate-pulse">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
                <p className="text-muted-foreground text-sm">Loading...</p>
              </div>
            </div>
          ) : (
            children
          )}
        </main>
      </div>
    </div>
  );
}
