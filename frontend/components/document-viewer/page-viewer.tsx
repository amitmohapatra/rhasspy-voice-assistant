'use client';

import { RefObject } from 'react';
import type { EnrichedDocument, EnrichedElement, VisibleBbox } from './types';
import { ELEMENT_COLORS, ELEMENT_LABELS } from './constants';
import { BboxOverlay } from './bbox-overlay';

interface PageViewerProps {
  parsedDoc: EnrichedDocument;
  currentPage: number;
  setCurrentPage: (p: number | ((prev: number) => number)) => void;
  pageImageUrl: string | null;
  imageNaturalSize: { w: number; h: number } | null;
  imageRef: RefObject<HTMLImageElement | null>;
  handleImageLoad: () => void;
  visibleBboxes: VisibleBbox[];
  pageElements: EnrichedElement[];
  highlightedId: string | null;
  selectedId: string | null;
  onHighlight: (id: string | null, source: 'image' | 'panel') => void;
  onSelect: (id: string | null) => void;
}

export function PageViewer({
  parsedDoc, currentPage, setCurrentPage,
  pageImageUrl, imageNaturalSize, imageRef, handleImageLoad,
  visibleBboxes, pageElements,
  highlightedId, selectedId, onHighlight, onSelect,
}: PageViewerProps) {
  const pageCount = parsedDoc.page_count || 1;

  return (
    <div className="overflow-auto bg-zinc-950 relative h-full">
      {/* Page Navigation */}
      {pageCount > 1 && (
        <div className="sticky top-0 z-10 bg-zinc-900/90 backdrop-blur border-b border-zinc-800 px-4 py-2 flex items-center gap-3">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage <= 1}
            className="px-2 py-1 text-xs bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 rounded text-white transition-colors"
          >
            Prev
          </button>
          <span className="text-xs text-zinc-400">
            Page {currentPage} of {pageCount}
          </span>
          <button
            onClick={() => setCurrentPage(p => Math.min(pageCount, p + 1))}
            disabled={currentPage >= pageCount}
            className="px-2 py-1 text-xs bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 rounded text-white transition-colors"
          >
            Next
          </button>
        </div>
      )}

      {/* Page Image + Overlays */}
      {pageImageUrl ? (
        <div className="relative inline-block p-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            ref={imageRef}
            src={pageImageUrl}
            alt={`Page ${currentPage}`}
            onLoad={handleImageLoad}
            className="max-w-full h-auto shadow-lg rounded"
            draggable={false}
          />

          {/* Bbox overlays */}
          {imageRef.current && imageNaturalSize && (
            <div
              className="absolute top-4 left-4"
              style={{
                width: imageRef.current.clientWidth,
                height: imageRef.current.clientHeight,
              }}
            >
              {visibleBboxes.map((item) => {
                if (!item.bbox || !imageNaturalSize) return null;

                const scaleX = imageRef.current!.clientWidth / imageNaturalSize.w;
                const scaleY = imageRef.current!.clientHeight / imageNaturalSize.h;

                const pageDims = parsedDoc.page_dimensions?.[String(currentPage)];
                let fx: number, fy: number;
                if (pageDims) {
                  fx = imageNaturalSize.w / pageDims.width;
                  fy = imageNaturalSize.h / pageDims.height;
                } else {
                  fx = 1;
                  fy = 1;
                }

                return (
                  <BboxOverlay
                    key={item.elementId}
                    item={item}
                    scaleX={scaleX}
                    scaleY={scaleY}
                    factorX={fx}
                    factorY={fy}
                    isHovered={highlightedId === item.elementId}
                    isSelected={selectedId === item.elementId}
                    onMouseEnter={() => onHighlight(item.elementId, 'image')}
                    onMouseLeave={() => onHighlight(null, 'image')}
                    onClick={() => onSelect(item.elementId)}
                  />
                );
              })}
            </div>
          )}
        </div>
      ) : (
        /* Text/code display for non-image documents */
        <div className="p-4 space-y-3">
          {pageElements.length > 0 ? (
            pageElements.map((el) => {
              const isHovered = highlightedId === el.element_id;
              const isSelected = selectedId === el.element_id;
              const color = ELEMENT_COLORS[el.type] || '#6b7280';

              return (
                <div
                  key={el.element_id}
                  data-element-id={el.element_id}
                  data-pane="image"
                  className={`rounded-lg border p-3 transition-all cursor-pointer ${
                    isHovered || isSelected ? 'ring-1' : ''
                  }`}
                  style={{
                    borderColor: isHovered || isSelected ? color : 'rgb(39 39 42)',
                    backgroundColor: isHovered || isSelected ? `${color}10` : 'rgb(24 24 27)',
                  }}
                  onMouseEnter={() => onHighlight(el.element_id, 'image')}
                  onMouseLeave={() => onHighlight(null, 'image')}
                  onClick={() => onSelect(el.element_id)}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                    <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color }}>
                      {ELEMENT_LABELS[el.type] || el.type}
                    </span>
                  </div>
                  <pre className={`text-sm text-zinc-300 whitespace-pre-wrap font-mono ${
                    el.type === 'code' ? 'bg-zinc-900 p-2 rounded' : ''
                  }`}>
                    {el.content.length > 500 ? el.content.substring(0, 500) + '...' : el.content}
                  </pre>
                </div>
              );
            })
          ) : (
            <p className="text-zinc-500 text-sm">No elements on this page.</p>
          )}
        </div>
      )}
    </div>
  );
}
