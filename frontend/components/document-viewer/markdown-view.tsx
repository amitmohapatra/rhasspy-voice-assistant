'use client';

import { useCallback } from 'react';
import type { EnrichedDocument } from './types';
import { ELEMENT_COLORS } from './constants';

interface MarkdownViewProps {
  parsedDoc: EnrichedDocument;
  markdownContent: string;
  highlightedId: string | null;
  onHighlight: (id: string | null, source: 'image' | 'panel') => void;
  onSelect: (id: string | null) => void;
}

/**
 * Renders document elements as styled content blocks.
 * Each element is wrapped with data-element-id for bidirectional sync.
 */
export function MarkdownView({
  parsedDoc, markdownContent,
  highlightedId, onHighlight, onSelect,
}: MarkdownViewProps) {
  const elements = Object.values(parsedDoc.elements);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(markdownContent);
  }, [markdownContent]);

  if (elements.length === 0 && !markdownContent) {
    return (
      <div className="p-4 text-zinc-500 text-sm">
        No content available.
      </div>
    );
  }

  return (
    <div className="p-4">
      {/* Copy button */}
      <div className="flex justify-end mb-3">
        <button
          onClick={handleCopy}
          className="px-2 py-1 text-[10px] bg-zinc-800 hover:bg-zinc-700 text-zinc-400 rounded transition-colors"
        >
          Copy Markdown
        </button>
      </div>

      {/* Rendered elements */}
      <div className="space-y-3">
        {elements.map((el) => {
          if (el.skip_indexing) return null;

          const isHighlighted = highlightedId === el.element_id;
          const color = ELEMENT_COLORS[el.type] || '#6b7280';
          const content = el.content;
          if (!content?.trim()) return null;

          return (
            <div
              key={el.element_id}
              data-element-id={el.element_id}
              data-pane="panel"
              className={`rounded-lg border px-4 py-3 transition-all cursor-pointer ${
                isHighlighted ? 'ring-1 ring-emerald-500/50' : ''
              }`}
              style={{
                borderColor: isHighlighted ? color : 'rgb(39 39 42)',
                backgroundColor: isHighlighted ? `${color}08` : 'transparent',
              }}
              onMouseEnter={() => onHighlight(el.element_id, 'panel')}
              onMouseLeave={() => onHighlight(null, 'panel')}
              onClick={() => onSelect(el.element_id)}
            >
              {/* Type badge + page */}
              <div className="flex items-center gap-2 mb-1">
                <span
                  className="text-[9px] px-1.5 py-0.5 rounded font-medium"
                  style={{ backgroundColor: `${color}20`, color }}
                >
                  {el.type}
                </span>
                {el.page_number > 0 && (
                  <span className="text-[9px] text-zinc-600">p.{el.page_number}</span>
                )}
                {el.headings && el.headings.length > 0 && (
                  <span className="text-[9px] text-zinc-600 truncate max-w-[200px]">
                    {el.headings.join(' > ')}
                  </span>
                )}
              </div>

              {/* Content rendering */}
              {el.type === 'title' && (
                <h1 className="text-xl font-bold text-white">{content}</h1>
              )}
              {el.type === 'section_header' && (
                <h2 className="text-lg font-semibold text-white">{content}</h2>
              )}
              {el.type === 'table' && (
                <div className="overflow-x-auto text-xs text-zinc-300">
                  {el.metadata?.table_html ? (
                    <div
                      className="prose prose-invert prose-xs max-w-none [&_table]:border-collapse [&_td]:border [&_td]:border-zinc-700 [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-zinc-700 [&_th]:px-2 [&_th]:py-1 [&_th]:bg-zinc-800"
                      dangerouslySetInnerHTML={{ __html: el.metadata.table_html as string }}
                    />
                  ) : (
                    <pre className="whitespace-pre-wrap font-mono">{content}</pre>
                  )}
                </div>
              )}
              {el.type === 'code' && (
                <pre className="bg-zinc-950 rounded p-3 text-xs text-emerald-300 whitespace-pre-wrap font-mono overflow-x-auto">
                  {content}
                </pre>
              )}
              {el.type === 'equation' && (
                <div className="text-sm text-pink-300 font-mono bg-zinc-950 rounded p-2 text-center">
                  {content}
                </div>
              )}
              {(el.type === 'figure' || el.type === 'chart') && (
                <div>
                  {el.metadata?.image_b64 && (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={`data:image/png;base64,${el.metadata.image_b64}`}
                      alt={content || 'Figure'}
                      className="max-w-full max-h-[200px] rounded mb-2"
                    />
                  )}
                  {content && (
                    <p className="text-sm text-zinc-300 italic">{content}</p>
                  )}
                </div>
              )}
              {el.type === 'checkbox' && (
                <label className="flex items-center gap-2 text-sm text-zinc-300">
                  <input
                    type="checkbox"
                    checked={!!el.metadata?.checked}
                    readOnly
                    className="rounded border-zinc-600"
                  />
                  {content}
                </label>
              )}
              {el.type === 'list_item' && (
                <div className="text-sm text-zinc-300 pl-4">
                  <span className="text-zinc-500 mr-1">
                    {(el.metadata?.marker as string) || '-'}
                  </span>
                  {content}
                </div>
              )}
              {!['title', 'section_header', 'table', 'code', 'equation', 'figure', 'chart', 'checkbox', 'list_item'].includes(el.type) && (
                <p className="text-sm text-zinc-300 leading-relaxed">{content}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
