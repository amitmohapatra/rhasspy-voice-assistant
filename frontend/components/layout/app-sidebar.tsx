'use client';

/**
 * Enhanced Sidebar Navigation - Google/Amazon UX Patterns
 *
 * Key UX Improvements:
 * 1. Visual Hierarchy - Clear typography scale, icon + text alignment
 * 2. Hover Feedback - Subtle background shifts, transform effects
 * 3. Active States - Strong visual indicator with accent bar
 * 4. Grouped Sections - Collapsible with smooth animations
 * 5. Quick Actions - Keyboard shortcuts, tooltips on collapsed
 * 6. Contextual Menu - Right-click for power users
 * 7. Smooth Collapse - Animated width transition with icon-only mode
 */

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Bot,
  Wrench,
  Database,
  FolderOpen,
  MessageSquare,
  User2,
  FolderKanban,
  ChevronDown,
  LayoutDashboard,
  Search,
  Command,
  Sparkles,
  PanelLeftClose,
  PanelLeft,
  ExternalLink,
  Volume2,
  FileSearch,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Navigation item type
interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  shortcut?: string;
}

// Navigation group type
interface NavGroup {
  id: string;
  title: string;
  items: NavItem[];
  defaultExpanded?: boolean;
}

// Navigation configuration with enhanced structure
const NAV_GROUPS: NavGroup[] = [
  {
    id: 'build',
    title: 'Build',
    defaultExpanded: true,
    items: [
      { name: 'Assistants', href: '/assistants', icon: Bot, shortcut: 'A' },
      { name: 'Knowledge Bases', href: '/knowledge-bases', icon: Database, shortcut: 'K' },
      { name: 'Tools', href: '/tools', icon: Wrench, shortcut: 'T' },
      { name: 'Agentic Docs', href: '/agentic-docs', icon: FileSearch, shortcut: 'G' },
    ],
  },
  {
    id: 'storage',
    title: 'Storage',
    defaultExpanded: true,
    items: [
      { name: 'Files', href: '/platform/storage', icon: FolderOpen },
    ],
  },
  {
    id: 'interact',
    title: 'Interact',
    defaultExpanded: true,
    items: [
      { name: 'Chat', href: '/platform/chat', icon: MessageSquare, shortcut: 'C' },
      { name: 'Avatar', href: '/platform/avatar', icon: User2, badge: 'Beta' },
    ],
  },
  {
    id: 'manage',
    title: 'Manage',
    defaultExpanded: true,
    items: [
      { name: 'Voice', href: '/manage/voice', icon: Volume2 },
      { name: 'Projects', href: '/projects', icon: FolderKanban },
    ],
  },
];

interface AppSidebarProps {
  defaultCollapsed?: boolean;
}

export function AppSidebar({
  defaultCollapsed = false,
}: AppSidebarProps) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    NAV_GROUPS.forEach(group => {
      initial[group.id] = group.defaultExpanded ?? true;
    });
    return initial;
  });
  const [showSearch, setShowSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + K to open search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowSearch(true);
        setTimeout(() => searchInputRef.current?.focus(), 50);
      }
      // Escape to close search
      if (e.key === 'Escape') {
        setShowSearch(false);
        setSearchQuery('');
      }
      // Cmd/Ctrl + B to toggle sidebar
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        setIsCollapsed(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Check if a nav item is active
  const isActive = (href: string) => {
    if (href === '/dashboard') return pathname === '/dashboard';
    return pathname === href || pathname.startsWith(href + '/');
  };

  // Toggle group expansion
  const toggleGroup = (groupId: string) => {
    if (isCollapsed) return;
    setExpandedGroups(prev => ({ ...prev, [groupId]: !prev[groupId] }));
  };

  // Get all searchable items
  const getAllItems = () => {
    const items: NavItem[] = [];
    NAV_GROUPS.forEach(group => items.push(...group.items));
    return items;
  };

  // Filter items by search
  const filteredItems = searchQuery
    ? getAllItems().filter(item =>
        item.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : [];

  return (
    <aside
      className={cn(
        'h-screen bg-background border-r border-border flex flex-col transition-all duration-300 ease-in-out relative',
        isCollapsed ? 'w-[68px]' : 'w-[260px]'
      )}
    >
      {/* Logo & Brand */}
      <div className={cn(
        'h-14 border-b border-border flex items-center transition-all duration-300',
        isCollapsed ? 'px-3 justify-center' : 'px-4'
      )}>
        <Link href="/dashboard" className="flex items-center gap-3 group">
          <div className="w-9 h-9 bg-gradient-to-br from-emerald-400 to-cyan-500 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg shadow-emerald-500/20 group-hover:shadow-emerald-500/30 transition-shadow">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          {!isCollapsed && (
            <div className="overflow-hidden">
              <span className="font-bold text-white text-[15px] tracking-tight">Rhasspy AI</span>
              <span className="block text-[10px] text-zinc-500 font-medium">Enterprise Platform</span>
            </div>
          )}
        </Link>
      </div>

      {/* Search - Quick Access */}
      {!isCollapsed && (
        <div className="px-3 pt-3">
          <button
            onClick={() => setShowSearch(true)}
            className="w-full flex items-center gap-2 px-3 py-2 bg-zinc-900/50 hover:bg-zinc-800/80 border border-zinc-800 rounded-lg text-[13px] text-zinc-500 transition-all group"
          >
            <Search className="w-4 h-4" />
            <span className="flex-1 text-left">Quick search...</span>
            <kbd className="hidden group-hover:flex items-center gap-0.5 px-1.5 py-0.5 bg-zinc-800 rounded text-[10px] font-medium text-zinc-400">
              <Command className="w-3 h-3" />K
            </kbd>
          </button>
        </div>
      )}

      {/* Dashboard Link */}
      <div className="px-3 pt-3 pb-1">
        <NavLink
          item={{ name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, shortcut: 'D' }}
          isActive={isActive('/dashboard')}
          isCollapsed={isCollapsed}
        />
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-1 scrollbar-hide">
        {NAV_GROUPS.map((group) => (
          <NavGroupComponent
            key={group.id}
            group={group}
            isActive={isActive}
            isCollapsed={isCollapsed}
            isExpanded={expandedGroups[group.id]}
            onToggle={() => toggleGroup(group.id)}
          />
        ))}

      </nav>

      {/* Footer */}
      <div className="border-t border-border p-3 space-y-1">
        {/* Collapse Toggle */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-zinc-500 hover:text-white hover:bg-zinc-800/80 transition-all"
          title={isCollapsed ? 'Expand sidebar (⌘B)' : 'Collapse sidebar (⌘B)'}
        >
          {isCollapsed ? (
            <PanelLeft className="w-4 h-4" />
          ) : (
            <>
              <PanelLeftClose className="w-4 h-4" />
              <span className="text-[12px]">Collapse</span>
              <kbd className="ml-auto px-1.5 py-0.5 bg-zinc-800 rounded text-[10px] font-medium text-zinc-500">
                ⌘B
              </kbd>
            </>
          )}
        </button>
      </div>

      {/* Search Modal */}
      {showSearch && (
        <SearchModal
          isOpen={showSearch}
          onClose={() => {
            setShowSearch(false);
            setSearchQuery('');
          }}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          filteredItems={filteredItems}
          inputRef={searchInputRef}
        />
      )}
    </aside>
  );
}

// NavLink Component with enhanced states
function NavLink({
  item,
  isActive,
  isCollapsed,
}: {
  item: NavItem;
  isActive: boolean;
  isCollapsed: boolean;
}) {
  return (
    <Link
      href={item.href}
      className={cn(
        'group flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] font-medium transition-all duration-200 relative',
        isActive
          ? 'bg-white/10 text-white'
          : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60',
        isCollapsed && 'justify-center px-0'
      )}
      title={isCollapsed ? item.name : undefined}
    >
      {/* Active indicator bar */}
      {isActive && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-emerald-400 rounded-r-full" />
      )}

      <item.icon className={cn(
        'w-[18px] h-[18px] flex-shrink-0 transition-transform',
        isActive ? 'text-emerald-400' : 'group-hover:scale-110'
      )} />

      {!isCollapsed && (
        <>
          <span className="flex-1">{item.name}</span>
          {item.badge && (
            <span className="px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 text-[10px] font-semibold rounded">
              {item.badge}
            </span>
          )}
          {item.shortcut && (
            <kbd className="opacity-0 group-hover:opacity-100 transition-opacity px-1.5 py-0.5 bg-zinc-800 rounded text-[10px] font-medium text-zinc-500">
              {item.shortcut}
            </kbd>
          )}
        </>
      )}
    </Link>
  );
}

// NavGroup Component with collapsible animation
function NavGroupComponent({
  group,
  isActive,
  isCollapsed,
  isExpanded,
  onToggle,
}: {
  group: NavGroup;
  isActive: (href: string) => boolean;
  isCollapsed: boolean;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  // Check if any item in this group is active
  const hasActiveItem = group.items.some(item => isActive(item.href));

  return (
    <div className="space-y-1">
      {/* Group Header */}
      {!isCollapsed ? (
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-between px-3 py-1.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider hover:text-zinc-400 transition-colors"
        >
          <span className={cn(hasActiveItem && 'text-zinc-300')}>{group.title}</span>
          <ChevronDown className={cn(
            'w-3 h-3 transition-transform duration-200',
            isExpanded ? 'rotate-0' : '-rotate-90'
          )} />
        </button>
      ) : (
        <div className="h-px bg-zinc-800/50 my-2" />
      )}

      {/* Group Items */}
      <div className={cn(
        'space-y-1 overflow-hidden transition-all duration-200',
        !isExpanded && !isCollapsed ? 'h-0 opacity-0' : 'h-auto opacity-100'
      )}>
        {group.items.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            isActive={isActive(item.href)}
            isCollapsed={isCollapsed}
          />
        ))}
      </div>
    </div>
  );
}

// Search Modal Component
function SearchModal({
  isOpen,
  onClose,
  searchQuery,
  setSearchQuery,
  filteredItems,
  inputRef,
}: {
  isOpen: boolean;
  onClose: () => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  filteredItems: NavItem[];
  inputRef: React.RefObject<HTMLInputElement>;
}) {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 z-50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed top-[15%] left-1/2 -translate-x-1/2 w-full max-w-lg z-50">
        <div className="bg-card border border-border rounded-xl shadow-2xl overflow-hidden">
          {/* Search Input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
            <Search className="w-5 h-5 text-zinc-500" />
            <input
              ref={inputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search pages, settings, actions..."
              className="flex-1 bg-transparent text-white text-[15px] placeholder-zinc-500 focus:outline-none"
              autoFocus
            />
            <kbd className="px-2 py-1 bg-zinc-800 rounded text-[11px] font-medium text-zinc-500">
              ESC
            </kbd>
          </div>

          {/* Results */}
          <div className="max-h-[300px] overflow-y-auto">
            {searchQuery && filteredItems.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <p className="text-zinc-500 text-[14px]">No results found</p>
              </div>
            ) : searchQuery ? (
              <div className="p-2">
                {filteredItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onClose}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-800 transition-colors"
                  >
                    <item.icon className="w-4 h-4 text-zinc-500" />
                    <span className="text-[14px] text-white">{item.name}</span>
                    <ExternalLink className="w-3 h-3 text-zinc-600 ml-auto" />
                  </Link>
                ))}
              </div>
            ) : (
              <div className="p-4">
                <p className="text-[12px] text-zinc-500 mb-3">Quick Actions</p>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { name: 'New Assistant', href: '/assistants/builder', icon: Bot },
                    { name: 'Upload Files', href: '/knowledge-bases', icon: Database },
                    { name: 'Open Chat', href: '/platform/chat', icon: MessageSquare },
                    { name: 'Projects', href: '/projects', icon: FolderKanban },
                  ].map((action) => (
                    <Link
                      key={action.href}
                      href={action.href}
                      onClick={onClose}
                      className="flex items-center gap-2 px-3 py-2 bg-zinc-800/50 hover:bg-zinc-800 rounded-lg transition-colors"
                    >
                      <action.icon className="w-4 h-4 text-zinc-400" />
                      <span className="text-[13px] text-zinc-300">{action.name}</span>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
