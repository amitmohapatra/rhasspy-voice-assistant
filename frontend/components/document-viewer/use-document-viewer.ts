'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { api } from '@/lib/api';
import type {
  CompletedFile, EnrichedDocument, EnrichedElement,
  ViewMode, RightPaneTab, ParseSubTab, HighlightState, VisibleBbox,
} from './types';
import { ELEMENT_COLORS, ELEMENT_LABELS } from './constants';

export function useDocumentViewer() {
  // Document selector state
  const [files, setFiles] = useState<CompletedFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);

  // Parsed document state
  const [parsedDoc, setParsedDoc] = useState<EnrichedDocument | null>(null);
  const [docLoading, setDocLoading] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);

  // Markdown content
  const [markdownContent, setMarkdownContent] = useState<string>('');

  // Viewer state
  const [currentPage, setCurrentPage] = useState(1);
  const [viewMode, setViewMode] = useState<ViewMode>('layout');
  const [highlight, setHighlight] = useState<HighlightState>({ elementId: null, source: null });
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);

  // Pane state
  const [rightPaneTab, setRightPaneTab] = useState<RightPaneTab>('parse');
  const [parseSubTab, setParseSubTab] = useState<ParseSubTab>('json');
  const [splitPosition, setSplitPosition] = useState(60);
  const splitDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Page image
  const [pageImageUrl, setPageImageUrl] = useState<string | null>(null);
  const [imageNaturalSize, setImageNaturalSize] = useState<{ w: number; h: number } | null>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  // JSON tree expansion
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set(['root', 'elements']));

  // ==================== Load completed files ====================
  useEffect(() => {
    (async () => {
      try {
        const res = await api.listFiles({ status: 'completed', limit: 200 });
        setFiles(res.items as CompletedFile[]);
      } catch {
        setFiles([]);
      } finally {
        setFilesLoading(false);
      }
    })();
  }, []);

  // ==================== Load parsed document (v2) ====================
  useEffect(() => {
    if (!selectedFileId) {
      setParsedDoc(null);
      setDocError(null);
      setMarkdownContent('');
      return;
    }

    (async () => {
      setDocLoading(true);
      setDocError(null);
      setCurrentPage(1);
      setSelectedElementId(null);
      setHighlight({ elementId: null, source: null });

      try {
        const doc = await api.getDocumentEnriched(selectedFileId);
        setParsedDoc(doc);

        // Also fetch markdown
        try {
          const md = await api.getDocumentMarkdown(selectedFileId);
          setMarkdownContent(md);
        } catch {
          setMarkdownContent('');
        }
      } catch (e: any) {
        setDocError(e.message || 'Failed to load document');
        setParsedDoc(null);
      } finally {
        setDocLoading(false);
      }
    })();
  }, [selectedFileId]);

  // ==================== Page image URL ====================
  useEffect(() => {
    if (!selectedFileId || !parsedDoc) {
      setPageImageUrl(null);
      return;
    }

    const selectedFile = files.find(f => f.id === selectedFileId);
    const ext = selectedFile?.file_type?.toLowerCase() || '';
    const hasPageImage = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif'].includes(ext);

    if (!hasPageImage) {
      setPageImageUrl(null);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;

    (async () => {
      try {
        const blob = await api.getDocumentPageImageBlob(selectedFileId, currentPage);
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPageImageUrl(objectUrl);
      } catch {
        if (!cancelled) setPageImageUrl(null);
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [selectedFileId, currentPage, parsedDoc, files]);

  // ==================== Elements as ordered list ====================
  const elementsList = useMemo(() => {
    if (!parsedDoc) return [];
    return Object.values(parsedDoc.elements);
  }, [parsedDoc]);

  // ==================== Elements for current page ====================
  const pageElements = useMemo(() => {
    return elementsList.filter(
      (el) => el.page_number === currentPage || el.page_number === 0
    );
  }, [elementsList, currentPage]);

  // ==================== Visible bboxes ====================
  const visibleBboxes = useMemo((): VisibleBbox[] => {
    const result: VisibleBbox[] = [];

    pageElements.forEach((el) => {
      if (viewMode === 'layout') {
        if (el.bbox) {
          result.push({
            elementId: el.element_id,
            bbox: el.bbox,
            bboxNormalized: el.bbox_normalized || null,
            color: ELEMENT_COLORS[el.type] || '#6b7280',
            label: ELEMENT_LABELS[el.type] || el.type,
            element: el,
          });
        }
      } else if (viewMode === 'detail') {
        const tableCells = el.metadata?.table_cells as Array<{ value: string; bbox?: any }> | undefined;
        if (tableCells) {
          tableCells.forEach((cell, ci) => {
            if (cell.bbox) {
              result.push({
                elementId: `${el.element_id}-R${ci}`,
                bbox: cell.bbox,
                bboxNormalized: (cell as any).bbox_normalized || null,
                color: '#10b981',
                label: `Cell ${ci + 1}`,
                element: el,
              });
            }
          });
        } else if (el.bbox) {
          result.push({
            elementId: el.element_id,
            bbox: el.bbox,
            bboxNormalized: el.bbox_normalized || null,
            color: ELEMENT_COLORS[el.type] || '#6b7280',
            label: ELEMENT_LABELS[el.type] || el.type,
            element: el,
          });
        }
      }
    });

    return result;
  }, [pageElements, viewMode]);

  // ==================== Element types in doc ====================
  const elementTypesInDoc = useMemo(() => {
    const types = new Set(elementsList.map(e => e.type));
    return Array.from(types).sort();
  }, [elementsList]);

  // ==================== Split pane drag ====================
  const handleSplitMouseDown = useCallback(() => {
    splitDragging.current = true;
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!splitDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPosition(Math.min(80, Math.max(20, pct)));
    };
    const handleMouseUp = () => { splitDragging.current = false; };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  // ==================== Image load handler ====================
  const handleImageLoad = useCallback(() => {
    if (imageRef.current) {
      setImageNaturalSize({
        w: imageRef.current.naturalWidth,
        h: imageRef.current.naturalHeight,
      });
    }
  }, []);

  // ==================== JSON tree ====================
  const toggleNode = useCallback((path: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  // ==================== Highlight handlers ====================
  const highlightElement = useCallback((elementId: string | null, source: 'image' | 'panel') => {
    setHighlight({ elementId, source });
    // Navigate to page if element is on a different page
    if (elementId && parsedDoc) {
      const el = parsedDoc.elements[elementId];
      if (el && el.page_number > 0 && el.page_number !== currentPage) {
        setCurrentPage(el.page_number);
      }
    }
  }, [parsedDoc, currentPage]);

  const selectElement = useCallback((elementId: string | null) => {
    setSelectedElementId(prev => prev === elementId ? null : elementId);
  }, []);

  return {
    // File selection
    files, filesLoading, selectedFileId, setSelectedFileId,
    // Document data
    parsedDoc, docLoading, docError, markdownContent,
    // Viewer state
    currentPage, setCurrentPage, viewMode, setViewMode,
    highlight, highlightElement, selectedElementId, selectElement,
    // Pane state
    rightPaneTab, setRightPaneTab, parseSubTab, setParseSubTab,
    splitPosition, handleSplitMouseDown, containerRef,
    // Page image
    pageImageUrl, imageNaturalSize, imageRef, handleImageLoad,
    // Elements
    elementsList, pageElements, visibleBboxes, elementTypesInDoc,
    // JSON tree
    expandedNodes, toggleNode,
  };
}
