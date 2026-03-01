'use client';

import * as React from 'react';
import { Search, LayoutGrid, List } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

interface FilterConfig {
  key: string;
  label: string;
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
}

interface SearchFilterBarProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  viewMode?: 'grid' | 'list';
  onViewModeChange?: (mode: 'grid' | 'list') => void;
  showViewToggle?: boolean;
  actions?: React.ReactNode;
  filters?: FilterConfig[];
  className?: string;
}

export function SearchFilterBar({
  searchValue,
  onSearchChange,
  searchPlaceholder = 'Search...',
  viewMode,
  onViewModeChange,
  showViewToggle = false,
  actions,
  filters,
  className,
}: SearchFilterBarProps) {
  return (
    <div className={cn('flex items-center gap-3', className)}>
      {/* Search */}
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
        <input
          type="text"
          placeholder={searchPlaceholder}
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full input-search"
        />
      </div>

      {/* Filters */}
      {filters?.map((filter) => (
        <Select
          key={filter.key}
          value={filter.value}
          onValueChange={filter.onChange}
        >
          <SelectTrigger className="h-9 w-[140px] bg-zinc-900 border-zinc-800 text-[13px]">
            <SelectValue placeholder={filter.label} />
          </SelectTrigger>
          <SelectContent className="bg-zinc-900 border-zinc-800">
            {filter.options.map((opt) => (
              <SelectItem key={opt.value} value={opt.value} className="text-[13px]">
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ))}

      {/* View Toggle */}
      {showViewToggle && onViewModeChange && (
        <div className="flex items-center border border-zinc-800 rounded-lg overflow-hidden">
          <button
            onClick={() => onViewModeChange('grid')}
            className={cn(
              'p-2 transition-colors',
              viewMode === 'grid'
                ? 'bg-zinc-800 text-white'
                : 'text-zinc-500 hover:text-white'
            )}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            onClick={() => onViewModeChange('list')}
            className={cn(
              'p-2 transition-colors',
              viewMode === 'list'
                ? 'bg-zinc-800 text-white'
                : 'text-zinc-500 hover:text-white'
            )}
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Actions slot */}
      {actions}
    </div>
  );
}
