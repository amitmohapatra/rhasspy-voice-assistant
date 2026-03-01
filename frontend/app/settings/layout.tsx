'use client';

/**
 * Settings Layout - OpenAI Platform Style
 *
 * Design: Top header with nav + profile, collapsible sidebar for settings
 * - Header: Logo | Dashboard Docs API Reference | Settings Profile
 * - Sidebar: Collapsible settings navigation (flat list, all items visible)
 * - Clean, modern look like OpenAI Platform
 */

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  User,
  Settings,
  Key,
  Cpu,
  ChevronDown,
  Sparkles,
  LogOut,
  PanelLeftClose,
  PanelLeft,
  BookOpen,
  Code2,
  ExternalLink,
} from 'lucide-react';
import type { User as UserType } from '@/types/user';
import { SETTINGS_SECTIONS } from '@/types/user';
import { cn } from '@/lib/utils';
import { logout } from '@/lib/auth';
import { api } from '@/lib/api';

// Icon mapping for settings sections
const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  User,
  Key,
  Cpu,
};

// Top header navigation (OpenAI style)
const HEADER_NAV = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/docs', label: 'Docs', external: false },
  { href: '/api-reference', label: 'API Reference', external: false },
];

interface SettingsLayoutProps {
  children: React.ReactNode;
}

export default function SettingsLayout({ children }: SettingsLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<UserType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    const loadUser = async () => {
      try {
        const userData = await api.getMe();
        setUser({
          id: userData.id,
          email: userData.email,
          full_name: userData.full_name || userData.name,
          is_active: userData.is_active,
          created_at: userData.created_at,
          updated_at: userData.updated_at,
          preferences: userData.preferences as any || {
            theme: 'dark',
            language: 'en',
            timezone: 'UTC',
          },
        });
      } catch (error) {
        router.push('/auth/login');
      } finally {
        setIsLoading(false);
      }
    };

    loadUser();
  }, [router]);

  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);

  // Load collapsed state from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('settings-sidebar-collapsed');
    if (saved) setIsCollapsed(JSON.parse(saved));
  }, []);

  // Close profile menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) {
        setShowProfileMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Save collapsed state
  const toggleCollapse = () => {
    const newState = !isCollapsed;
    setIsCollapsed(newState);
    localStorage.setItem('settings-sidebar-collapsed', JSON.stringify(newState));
  };

  const handleLogout = () => {
    logout();
  };

  // Get current page title
  const getCurrentTitle = () => {
    const segment = pathname.split('/').pop() || 'profile';
    const section = SETTINGS_SECTIONS.find(s => s.id === segment || s.path === pathname);
    return section?.title || segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, ' ');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center animate-pulse">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <p className="text-muted-foreground text-sm">Loading settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Top Header Bar - OpenAI Platform Style */}
      <header className="h-14 bg-background border-b border-border flex items-center justify-between px-4 flex-shrink-0 sticky top-0 z-50">
        {/* Left: Logo + Nav */}
        <div className="flex items-center gap-8">
          {/* Logo */}
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <span className="text-[15px] font-semibold text-white">Rhasspy</span>
          </Link>

          {/* Main Navigation */}
          <nav className="flex items-center gap-1">
            {HEADER_NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all',
                  pathname === item.href
                    ? 'text-white bg-zinc-800/60'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800/40'
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>

        {/* Right: Settings + Profile */}
        <div className="flex items-center gap-2">
          {/* Settings Icon - Active state */}
          <Link
            href="/settings/profile"
            className="w-9 h-9 rounded-lg flex items-center justify-center bg-emerald-500/20 text-emerald-400 transition-all"
          >
            <Settings className="w-[18px] h-[18px]" />
          </Link>

          {/* Profile Dropdown */}
          <div className="relative" ref={profileMenuRef}>
            <button
              onClick={() => setShowProfileMenu(!showProfileMenu)}
              className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-lg hover:bg-zinc-800/60 transition-all"
            >
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-zinc-700 to-zinc-600 flex items-center justify-center text-sm font-semibold text-white">
                {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
              </div>
              <ChevronDown className={cn(
                'w-4 h-4 text-zinc-400 transition-transform',
                showProfileMenu && 'rotate-180'
              )} />
            </button>

            {/* Dropdown Menu */}
            {showProfileMenu && (
              <div className="absolute right-0 top-full mt-2 w-64 bg-[#18181b] border border-zinc-800 rounded-xl shadow-2xl overflow-hidden animate-scale-in">
                {/* User Info */}
                <div className="p-4 border-b border-zinc-800/80">
                  <p className="text-[13px] font-medium text-white">{user?.full_name || 'User'}</p>
                  <p className="text-[12px] text-zinc-500">{user?.email}</p>
                </div>

                {/* Menu Items */}
                <div className="p-2">
                  <Link
                    href="/settings/profile"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors"
                    onClick={() => setShowProfileMenu(false)}
                  >
                    <User className="w-4 h-4" />
                    Profile Settings
                  </Link>
                  <Link
                    href="/settings/api-keys"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors"
                    onClick={() => setShowProfileMenu(false)}
                  >
                    <Key className="w-4 h-4" />
                    API Keys
                  </Link>
                  <div className="h-px bg-zinc-800 my-2" />
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Area: Sidebar + Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Collapsible Settings Sidebar */}
        <aside
          className={cn(
            'bg-[#0f0f10] border-r border-zinc-800/80 flex flex-col flex-shrink-0 transition-all duration-300',
            isCollapsed ? 'w-16' : 'w-60'
          )}
        >
          {/* Sidebar Header */}
          <div className={cn(
            'h-12 border-b border-zinc-800/80 flex items-center',
            isCollapsed ? 'justify-center px-2' : 'justify-between px-4'
          )}>
            {!isCollapsed && (
              <span className="text-[13px] font-semibold text-white">Settings</span>
            )}
            <button
              onClick={toggleCollapse}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-500 hover:text-white hover:bg-zinc-800/60 transition-all"
            >
              {isCollapsed ? <PanelLeft className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
            </button>
          </div>

          {/* Settings Items - Flat List */}
          <div className={cn('flex-1 overflow-y-auto', isCollapsed ? 'p-2' : 'p-3')}>
            <div className="space-y-0.5">
              {SETTINGS_SECTIONS.map((section) => {
                const Icon = ICON_MAP[section.icon] || Settings;
                const isActive = pathname === section.path;

                // Collapsed view: show icon only
                if (isCollapsed) {
                  return (
                    <Link
                      key={section.id}
                      href={section.path}
                      className={cn(
                        'w-10 h-10 mx-auto rounded-xl flex items-center justify-center transition-all relative group',
                        isActive
                          ? 'text-emerald-400 bg-emerald-500/20'
                          : 'text-zinc-500 hover:text-white hover:bg-zinc-800/60'
                      )}
                    >
                      <Icon className="w-5 h-5" />
                      {isActive && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-emerald-400 rounded-r-full" />
                      )}
                      <span className="absolute left-full ml-2 px-2 py-1 bg-zinc-800 text-white text-[12px] rounded-md opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity">
                        {section.title}
                      </span>
                    </Link>
                  );
                }

                // Expanded view: show icon + title
                return (
                  <Link
                    key={section.id}
                    href={section.path}
                    className={cn(
                      'flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-[13px] transition-all relative',
                      isActive
                        ? 'bg-white/10 text-white font-medium'
                        : 'text-zinc-400 hover:text-white hover:bg-zinc-800/40'
                    )}
                  >
                    {isActive && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 bg-emerald-400 rounded-r-full" />
                    )}
                    <Icon className={cn(
                      'w-4 h-4 flex-shrink-0',
                      isActive ? 'text-emerald-400' : 'text-zinc-500'
                    )} />
                    {section.title}
                  </Link>
                );
              })}
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 min-w-0 flex flex-col overflow-hidden">
          {/* Page Title Bar */}
          <div className="h-12 bg-background border-b border-border flex items-center px-6 flex-shrink-0">
            <h2 className="text-sm font-semibold text-foreground">{getCurrentTitle()}</h2>
          </div>

          {/* Page Content */}
          <div className="flex-1 overflow-y-auto bg-background">
            <div className="max-w-4xl mx-auto px-6 py-6">
              {children}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
