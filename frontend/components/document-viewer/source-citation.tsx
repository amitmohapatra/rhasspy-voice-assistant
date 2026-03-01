'use client';

import type { SourceCitation } from './types';
import { ELEMENT_COLORS, ELEMENT_LABELS } from './constants';

interface SourceCitationChipProps {
  citation: SourceCitation;
  onClick: (citation: SourceCitation) => void;
}

/**
 * Clickable citation chip: [p.9 - table] "Revenue data..."
 * onClick navigates to the page and highlights the bbox.
 */
export function SourceCitationChip({ citation, onClick }: SourceCitationChipProps) {
  const color = ELEMENT_COLORS[citation.type] || '#6b7280';
  const label = ELEMENT_LABELS[citation.type] || citation.type;

  return (
    <button
      onClick={() => onClick(citation)}
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-zinc-700 hover:border-zinc-500 bg-zinc-800/60 hover:bg-zinc-800 transition-colors text-left max-w-full"
    >
      <span
        className="text-[9px] px-1 py-0.5 rounded font-medium shrink-0"
        style={{ backgroundColor: `${color}20`, color }}
      >
        p.{citation.page_number} {label}
      </span>
      <span className="text-[11px] text-zinc-400 truncate">
        &quot;{citation.preview}&quot;
      </span>
    </button>
  );
}
