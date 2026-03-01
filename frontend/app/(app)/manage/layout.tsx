'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { Volume2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const MANAGE_ITEMS = [
  { name: 'Voice', href: '/manage/voice', icon: Volume2 },
];

export default function ManageLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Sub-nav */}
      <div className="border-b border-border px-6 py-2 flex items-center gap-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mr-4">
          Manage
        </span>
        {MANAGE_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted'
              )}
            >
              <item.icon className="w-4 h-4" />
              {item.name}
            </Link>
          );
        })}
      </div>

      {/* Page content */}
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}
