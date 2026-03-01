'use client';

import { useEffect, useCallback } from 'react';

/**
 * Hook for bidirectional scroll-into-view sync between image and right pane.
 * Uses data-element-id attributes on DOM elements.
 */
export function useBidirectionalSync(
  highlightedId: string | null,
  source: 'image' | 'panel' | null,
) {
  useEffect(() => {
    if (!highlightedId || !source) return;

    // Scroll the OTHER pane's corresponding element into view
    const targetPrefix = source === 'image' ? 'panel' : 'image';
    const targetEl = document.querySelector(
      `[data-element-id="${highlightedId}"][data-pane="${targetPrefix}"]`
    );

    if (targetEl) {
      targetEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [highlightedId, source]);

  const scrollToElement = useCallback((elementId: string, pane: 'image' | 'panel') => {
    const el = document.querySelector(
      `[data-element-id="${elementId}"][data-pane="${pane}"]`
    );
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, []);

  return { scrollToElement };
}
