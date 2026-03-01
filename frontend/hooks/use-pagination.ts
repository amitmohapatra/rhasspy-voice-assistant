'use client';

import { useState, useMemo, useCallback } from 'react';

interface UsePaginationOptions {
  initialPageSize?: number;
}

interface UsePaginationReturn {
  page: number;
  pageSize: number;
  skip: number;
  total: number;
  totalPages: number;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  setTotal: (total: number) => void;
}

export function usePagination(opts?: UsePaginationOptions): UsePaginationReturn {
  const [page, setPageRaw] = useState(1);
  const [pageSize, setPageSizeRaw] = useState(opts?.initialPageSize ?? 12);
  const [total, setTotal] = useState(0);

  const skip = useMemo(() => (page - 1) * pageSize, [page, pageSize]);
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

  const setPage = useCallback((newPage: number) => {
    setPageRaw(Math.max(1, newPage));
  }, []);

  const setPageSize = useCallback((newSize: number) => {
    setPageSizeRaw(newSize);
    setPageRaw(1);
  }, []);

  return {
    page,
    pageSize,
    skip,
    total,
    totalPages,
    setPage,
    setPageSize,
    setTotal,
  };
}
