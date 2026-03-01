'use client';

/**
 * Main Navigation Component
 *
 * Top navigation bar similar to OpenAI Platform:
 * [Logo] [Dashboard] [Docs] [API Reference] [Settings] [Profile Avatar]
 */

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  BookOpen,
  Code,
  Settings,
  ChevronDown,
  LogOut,
  User,
  Moon,
  Sun,
  Bell,
  HelpCircle,
  MessageSquare,
  Bot,
  Database,
  Wrench,
  Key,
} from 'lucide-react';
import type { User as UserType } from '@/types/user';

// ==================== Types ====================

interface NavItem {
  id: string;
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  children?: NavItem[];
}

interface MainNavProps {
  user: UserType | null;
  onLogout?: () => void;
}

// ==================== Navigation Items ====================

const NAV_ITEMS: NavItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    id: 'assistants',
    label: 'Assistants',
    href: '/assistants',
    icon: Bot,
  },
  {
    id: 'chat',
    label: 'Chat',
    href: '/chat',
    icon: MessageSquare,
  },
  {
    id: 'tools',
    label: 'Tools',
    href: '/tools',
    icon: Wrench,
  },
  {
    id: 'knowledge-bases',
    label: 'Knowledge Bases',
    href: '/knowledge-bases',
    icon: Database,
  },
  {
    id: 'docs',
    label: 'Docs',
    href: '/docs',
    icon: BookOpen,
  },
  {
    id: 'api-reference',
    label: 'API Reference',
    href: '/api-reference',
    icon: Code,
  },
];

// ==================== Sub-Components ====================

function NavLink({ item, isActive }: { item: NavItem; isActive: boolean }) {
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      className={`
        flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg
        transition-colors duration-200
        ${isActive
          ? 'bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-white'
          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50 dark:text-gray-400 dark:hover:text-white dark:hover:bg-gray-800'
        }
      `}
    >
      <Icon className="w-4 h-4" />
      <span>{item.label}</span>
      {item.badge && (
        <span className="ml-1 px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 rounded dark:bg-blue-900/30 dark:text-blue-400">
          {item.badge}
        </span>
      )}
    </Link>
  );
}

function UserMenu({ user, onLogout }: { user: UserType; onLogout?: () => void }) {
  const [isOpen, setIsOpen] = useState(false);

  const initials = user.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : user.email[0].toUpperCase();

  const avatarColor = 'bg-gray-500';

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      >
        {user.avatar_url ? (
          <img
            src={user.avatar_url}
            alt={user.full_name || user.email}
            className="w-8 h-8 rounded-full object-cover"
          />
        ) : (
          <div className={`w-8 h-8 rounded-full ${avatarColor} flex items-center justify-center text-white text-sm font-medium`}>
            {initials}
          </div>
        )}
        <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-gray-900 rounded-lg shadow-lg border dark:border-gray-700 z-50 py-2">
            {/* User Info */}
            <div className="px-4 py-3 border-b dark:border-gray-700">
              <div className="flex items-center gap-3">
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.full_name || user.email}
                    className="w-10 h-10 rounded-full object-cover"
                  />
                ) : (
                  <div className={`w-10 h-10 rounded-full ${avatarColor} flex items-center justify-center text-white font-medium`}>
                    {initials}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                    {user.full_name || 'User'}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {user.email}
                  </p>
                </div>
              </div>
            </div>

            {/* Menu Items */}
            <div className="py-2">
              <Link
                href="/settings/profile"
                onClick={() => setIsOpen(false)}
                className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <User className="w-4 h-4" />
                Profile
              </Link>
              <Link
                href="/settings"
                onClick={() => setIsOpen(false)}
                className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <Settings className="w-4 h-4" />
                Settings
              </Link>
              <Link
                href="/settings/api-keys"
                onClick={() => setIsOpen(false)}
                className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <Key className="w-4 h-4" />
                API Keys
              </Link>
            </div>

            {/* Logout */}
            <div className="border-t dark:border-gray-700 pt-2">
              <button
                onClick={() => {
                  setIsOpen(false);
                  onLogout?.();
                }}
                className="flex items-center gap-3 w-full px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                <LogOut className="w-4 h-4" />
                Log out
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ==================== Main Component ====================

export function MainNav({ user, onLogout }: MainNavProps) {
  const pathname = usePathname();
  const [isDark, setIsDark] = useState(false);

  return (
    <nav className="sticky top-0 z-50 bg-white dark:bg-gray-900 border-b dark:border-gray-800">
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <span className="text-lg font-semibold text-gray-900 dark:text-white">
              Rhasspy AI
            </span>
          </Link>

          {/* Main Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {NAV_ITEMS.map(item => (
              <NavLink
                key={item.id}
                item={item}
                isActive={pathname.startsWith(item.href)}
              />
            ))}
          </div>

          {/* Right Side */}
          <div className="flex items-center gap-2">
            {/* Theme Toggle */}
            <button
              onClick={() => setIsDark(!isDark)}
              className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>

            {/* Notifications */}
            <button className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 relative">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
            </button>

            {/* Help */}
            <button className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
              <HelpCircle className="w-5 h-5" />
            </button>

            {/* User Menu */}
            {user ? (
              <UserMenu user={user} onLogout={onLogout} />
            ) : (
              <Link
                href="/auth/login"
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

export default MainNav;
