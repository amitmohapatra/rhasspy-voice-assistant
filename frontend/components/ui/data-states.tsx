'use client';

import * as React from 'react';
import { Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface DataLoadingProps {
  message?: string;
  className?: string;
}

export function DataLoading({ message = 'Loading...', className }: DataLoadingProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-20', className)}>
      <Loader2 className="h-8 w-8 animate-spin text-zinc-500 mb-3" />
      <p className="text-[13px] text-zinc-500">{message}</p>
    </div>
  );
}

interface DataEmptyProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function DataEmpty({
  icon,
  title,
  description,
  action,
  className,
}: DataEmptyProps) {
  return (
    <div className={cn('empty-state', className)}>
      {icon && <div className="empty-state-icon">{icon}</div>}
      <p className="empty-state-title">{title}</p>
      {description && <p className="empty-state-description">{description}</p>}
      {action && (
        <Button onClick={action.onClick} className="btn-primary mt-4">
          {action.label}
        </Button>
      )}
    </div>
  );
}

interface DataErrorProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function DataError({
  message = 'Something went wrong',
  onRetry,
  className,
}: DataErrorProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-20', className)}>
      <div className="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center mb-4">
        <AlertCircle className="h-7 w-7 text-red-400" />
      </div>
      <p className="text-[14px] font-medium text-white mb-1">Error</p>
      <p className="text-[13px] text-zinc-500 mb-4">{message}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry} className="btn-outline">
          Try Again
        </Button>
      )}
    </div>
  );
}
