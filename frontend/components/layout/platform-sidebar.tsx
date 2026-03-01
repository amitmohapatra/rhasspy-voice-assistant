'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  MessageSquare,
  Bot,
  Mic,
  Image,
  Video,
  BarChart2,
  Key,
  FileText,
  Database,
  ChevronLeft,
  ChevronRight,
  Settings,
  User,
  LogOut,
  Menu,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { logout } from '@/lib/auth';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const sidebarItems = [
  {
    name: 'Chat',
    href: '/platform/chat',
    icon: MessageSquare,
    description: 'Chat with AI assistants'
  },
  {
    name: 'Agent Builder',
    href: '/platform/agent-builder',
    icon: Bot,
    description: 'Create and configure AI agents'
  },
  {
    name: 'Audio',
    href: '/platform/audio',
    icon: Mic,
    description: 'Speech-to-text and text-to-speech'
  },
  {
    name: 'Images',
    href: '/platform/images',
    icon: Image,
    description: 'Generate and edit images'
  },
  {
    name: 'Videos',
    href: '/platform/videos',
    icon: Video,
    description: 'Create AI-generated videos'
  },
  {
    name: 'Usage',
    href: '/platform/usage',
    icon: BarChart2,
    description: 'View usage and billing'
  },
  {
    name: 'API Keys',
    href: '/platform/api-keys',
    icon: Key,
    description: 'Manage API keys'
  },
  {
    name: 'Logs',
    href: '/platform/logs',
    icon: FileText,
    description: 'View API request logs'
  },
  {
    name: 'Storage',
    href: '/platform/storage',
    icon: Database,
    description: 'Manage file storage'
  },
];

interface PlatformSidebarProps {
  defaultCollapsed?: boolean;
}

export function PlatformSidebar({ defaultCollapsed = false }: PlatformSidebarProps) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <>
      {/* Mobile Menu Button */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed top-4 left-4 z-50 md:hidden"
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
      >
        {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </Button>

      {/* Mobile Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed md:sticky top-0 left-0 h-screen bg-background border-r flex flex-col z-50 transition-all duration-300',
          isCollapsed ? 'w-16' : 'w-64',
          isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        )}
      >
        {/* Logo */}
        <div className={cn(
          'h-14 border-b flex items-center shrink-0',
          isCollapsed ? 'justify-center px-2' : 'px-4'
        )}>
          <Link href="/platform/chat" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Bot className="w-5 h-5 text-primary-foreground" />
            </div>
            {!isCollapsed && (
              <span className="font-semibold text-lg">Rhasspy</span>
            )}
          </Link>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto py-4">
          <ul className="space-y-1 px-2">
            {sidebarItems.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
              return (
                <li key={item.name}>
                  <Link
                    href={item.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                    )}
                    title={isCollapsed ? item.name : undefined}
                  >
                    <item.icon className="w-5 h-5 shrink-0" />
                    {!isCollapsed && <span>{item.name}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* User Menu & Collapse Toggle */}
        <div className="border-t p-2 space-y-2">
          {/* Collapse Toggle - Desktop only */}
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-center hidden md:flex"
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            {isCollapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <>
                <ChevronLeft className="w-4 h-4 mr-2" />
                <span>Collapse</span>
              </>
            )}
          </Button>

          {/* User Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className={cn(
                  'w-full',
                  isCollapsed ? 'justify-center px-0' : 'justify-start'
                )}
              >
                <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                  <User className="w-4 h-4" />
                </div>
                {!isCollapsed && (
                  <div className="ml-2 text-left">
                    <p className="text-sm font-medium">Account</p>
                    <p className="text-xs text-muted-foreground">Settings</p>
                  </div>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align={isCollapsed ? 'center' : 'start'} className="w-56">
              <DropdownMenuItem asChild>
                <Link href="/settings/profile" className="flex items-center">
                  <User className="w-4 h-4 mr-2" />
                  Profile
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href="/settings" className="flex items-center">
                  <Settings className="w-4 h-4 mr-2" />
                  Settings
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-destructive" onClick={logout}>
                <LogOut className="w-4 h-4 mr-2" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>
    </>
  );
}
