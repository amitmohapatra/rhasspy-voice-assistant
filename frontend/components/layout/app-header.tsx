'use client';

/**
 * Top Header Navigation
 *
 * Features:
 * 1. Breadcrumbs - Context-aware navigation path
 * 2. User Menu - Quick profile access, settings, logout
 * 3. External links - Docs & API reference
 */

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Settings,
  ChevronDown,
  ChevronRight,
  User,
  LogOut,
  Key,
  Home,
  BookOpen,
  FileCode2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { User as UserType } from '@/types/user';

// Breadcrumb mapping
const BREADCRUMB_MAP: Record<string, string> = {
  dashboard: 'Dashboard',
  assistants: 'Assistants',
  builder: 'Builder',
  'knowledge-bases': 'Knowledge Bases',
  chat: 'Chat',
  avatar: 'Avatar Chat',
  settings: 'Settings',
  profile: 'Profile',
  'api-keys': 'API Keys',
  members: 'Members',
  billing: 'Billing',
  providers: 'Providers',
  tools: 'Tools',
  projects: 'Projects',
  docs: 'Documentation',
  'api-reference': 'API Reference',
  storage: 'Files',
  'rag-pipelines': 'RAG Pipelines',
  voice: 'Voice',
  manage: 'Manage',
};

interface AppHeaderProps {
  user?: UserType | null;
  onLogout?: () => void;
}

export function AppHeader({ user, onLogout }: AppHeaderProps) {
  const pathname = usePathname();
  const [showUserMenu, setShowUserMenu] = useState(false);

  // Generate breadcrumbs from pathname (skip organizational segments like "platform")
  const SKIP_SEGMENTS = new Set(['platform', 'manage']);

  const getBreadcrumbs = () => {
    const segments = pathname.split('/').filter(Boolean);
    return segments
      .filter(seg => !SKIP_SEGMENTS.has(seg))
      .map((segment) => {
        const label = BREADCRUMB_MAP[segment] || segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, ' ');
        const idx = segments.indexOf(segment);
        const path = '/' + segments.slice(0, idx + 1).join('/');
        return { label, path, segment };
      });
  };

  const breadcrumbs = getBreadcrumbs();

  // Get user initials
  const getInitials = () => {
    if (user?.full_name) {
      return user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
    }
    return user?.email?.[0]?.toUpperCase() || 'U';
  };

  return (
    <header className="h-12 bg-background border-b border-border flex items-center justify-between px-4">
      {/* Left: Breadcrumbs */}
      <nav className="flex items-center gap-1 text-[13px] min-w-0">
        <Link
          href="/dashboard"
          className="text-zinc-500 hover:text-white transition-colors flex-shrink-0"
        >
          <Home className="w-4 h-4" />
        </Link>

        {breadcrumbs.map((crumb, index) => (
          <div key={crumb.path} className="flex items-center gap-1 min-w-0">
            <ChevronRight className="w-3.5 h-3.5 text-zinc-600 flex-shrink-0" />
            {index === breadcrumbs.length - 1 ? (
              <span className="text-white font-medium truncate">
                {crumb.label}
              </span>
            ) : (
              <Link
                href={crumb.path}
                className="text-zinc-400 hover:text-white transition-colors truncate"
              >
                {crumb.label}
              </Link>
            )}
          </div>
        ))}
      </nav>

      {/* Right: Actions */}
      <div className="flex items-center gap-1">
        {/* Docs & API */}
        <Link
          href="/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-all text-[12px] font-medium"
        >
          <BookOpen className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Docs</span>
        </Link>
        <Link
          href="/api-reference"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-all text-[12px] font-medium"
        >
          <FileCode2 className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">API</span>
        </Link>

        {/* Divider */}
        <div className="w-px h-5 bg-zinc-800 mx-1" />

        {/* Settings */}
        <Link href="/settings">
          <button className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-all">
            <Settings className="w-[18px] h-[18px]" />
          </button>
        </Link>

        {/* Divider */}
        <div className="w-px h-5 bg-zinc-800 mx-1" />

        {/* User Menu */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-lg hover:bg-zinc-800 transition-all"
          >
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-zinc-600 to-zinc-700 flex items-center justify-center text-[11px] font-semibold text-white">
              {getInitials()}
            </div>
            <ChevronDown className={cn('w-3.5 h-3.5 text-zinc-500 transition-transform', showUserMenu && 'rotate-180')} />
          </button>

          {showUserMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
              <div className="absolute right-0 mt-2 w-64 bg-card border border-border rounded-xl shadow-2xl z-50 overflow-hidden">
                {/* User Info */}
                <div className="p-4 border-b border-border">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-zinc-600 to-zinc-700 flex items-center justify-center text-sm font-semibold text-white">
                      {getInitials()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[14px] font-medium text-white truncate">
                        {user?.full_name || 'User'}
                      </p>
                      <p className="text-[12px] text-zinc-500 truncate">{user?.email}</p>
                    </div>
                  </div>
                </div>

                {/* Menu Items */}
                <div className="p-1">
                  <Link
                    href="/settings/profile"
                    onClick={() => setShowUserMenu(false)}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors"
                  >
                    <User className="w-4 h-4 text-zinc-500" />
                    Profile
                  </Link>
                  <Link
                    href="/settings/api-keys"
                    onClick={() => setShowUserMenu(false)}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors"
                  >
                    <Key className="w-4 h-4 text-zinc-500" />
                    API Keys
                  </Link>
                </div>

                {/* Logout */}
                <div className="p-1 border-t border-border">
                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      onLogout?.();
                    }}
                    className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-[13px] text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                    Log out
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
