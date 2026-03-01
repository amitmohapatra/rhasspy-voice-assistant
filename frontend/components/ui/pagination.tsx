'use client';

import * as React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

interface PaginationProps {
  currentPage: number;
  totalItems: number;
  pageSize: number;
  pageSizeOptions?: number[];
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  showPageSizeSelector?: boolean;
  className?: string;
}

function getPageNumbers(current: number, total: number): (number | 'ellipsis')[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | 'ellipsis')[] = [1];

  if (current <= 3) {
    pages.push(2, 3, 4, 'ellipsis', total);
  } else if (current >= total - 2) {
    pages.push('ellipsis', total - 3, total - 2, total - 1, total);
  } else {
    pages.push('ellipsis', current - 1, current, current + 1, 'ellipsis', total);
  }

  return pages;
}

export function Pagination({
  currentPage,
  totalItems,
  pageSize,
  pageSizeOptions = [12, 24, 48, 96],
  onPageChange,
  onPageSizeChange,
  showPageSizeSelector = true,
  className,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);
  const pages = getPageNumbers(currentPage, totalPages);

  if (totalItems === 0) return null;

  return (
    <div className={cn('flex items-center justify-between pt-4', className)}>
      <p className="text-[13px] text-zinc-500">
        Showing {startItem}-{endItem} of {totalItems}
      </p>

      <div className="flex items-center gap-3">
        {showPageSizeSelector && onPageSizeChange && (
          <div className="flex items-center gap-2">
            <span className="text-[12px] text-zinc-500">Per page</span>
            <Select
              value={String(pageSize)}
              onValueChange={(v) => onPageSizeChange(Number(v))}
            >
              <SelectTrigger className="h-8 w-[70px] bg-zinc-900 border-zinc-800 text-[12px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-zinc-900 border-zinc-800">
                {pageSizeOptions.map((size) => (
                  <SelectItem key={size} value={String(size)} className="text-[12px]">
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8 bg-zinc-900 border-zinc-800 hover:bg-zinc-800"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          {pages.map((p, i) =>
            p === 'ellipsis' ? (
              <span key={`ellipsis-${i}`} className="px-1 text-zinc-600 text-[12px]">
                ...
              </span>
            ) : (
              <Button
                key={p}
                variant="outline"
                size="icon"
                className={cn(
                  'h-8 w-8 text-[12px]',
                  p === currentPage
                    ? 'bg-white text-black border-white hover:bg-zinc-200 hover:text-black'
                    : 'bg-zinc-900 border-zinc-800 hover:bg-zinc-800'
                )}
                onClick={() => onPageChange(p)}
              >
                {p}
              </Button>
            )
          )}

          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8 bg-zinc-900 border-zinc-800 hover:bg-zinc-800"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
