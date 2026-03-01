'use client';

import { useCallback } from 'react';
import type { EnrichedDocument, EnrichedElement } from './types';
import { ELEMENT_COLORS, getConfidenceBadgeColor } from './constants';

interface JsonViewProps {
  parsedDoc: EnrichedDocument;
  expandedNodes: Set<string>;
  toggleNode: (path: string) => void;
  highlightedId: string | null;
  selectedId: string | null;
  onHighlight: (id: string | null, source: 'image' | 'panel') => void;
  onSelect: (id: string | null) => void;
}

export function JsonView({
  parsedDoc, expandedNodes, toggleNode,
  highlightedId, selectedId,
  onHighlight, onSelect,
}: JsonViewProps) {
  const elements = Object.entries(parsedDoc.elements);

  const handleCopyAll = useCallback(() => {
    navigator.clipboard.writeText(JSON.stringify(parsedDoc, null, 2));
  }, [parsedDoc]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([JSON.stringify(parsedDoc, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${parsedDoc.filename || 'document'}_enriched.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [parsedDoc]);

  const handleCopyElement = useCallback((el: EnrichedElement) => {
    navigator.clipboard.writeText(JSON.stringify(el, null, 2));
  }, []);

  return (
    <div className="p-2 text-sm font-mono">
      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-2 px-1">
        <button
          onClick={handleCopyAll}
          className="px-2 py-1 text-[10px] bg-zinc-800 hover:bg-zinc-700 text-zinc-400 rounded transition-colors"
        >
          Copy All
        </button>
        <button
          onClick={handleDownload}
          className="px-2 py-1 text-[10px] bg-zinc-800 hover:bg-zinc-700 text-zinc-400 rounded transition-colors"
        >
          Download JSON
        </button>
      </div>

      {/* Quality scores */}
      {parsedDoc.quality && Object.keys(parsedDoc.quality).length > 0 && (
        <div className="mb-2 px-1">
          <button
            onClick={() => toggleNode('quality')}
            className="flex items-center gap-1 text-zinc-400 hover:text-white"
          >
            <span className="text-zinc-600 text-xs">{expandedNodes.has('quality') ? '\u25BC' : '\u25B6'}</span>
            <span className="text-yellow-400 text-xs">quality</span>
          </button>
          {expandedNodes.has('quality') && (
            <div className="ml-4 pl-2 border-l border-zinc-800">
              {Object.entries(parsedDoc.quality).map(([k, v]) => (
                <div key={k} className="py-0.5 px-1">
                  <span className="text-cyan-400 text-xs">{k}</span>
                  <span className="text-zinc-600 text-xs">: </span>
                  <span className={`text-xs ${typeof v === 'number' ? getConfidenceBadgeColor(v) : 'text-amber-400'}`}>
                    {typeof v === 'number' ? v.toFixed(3) : String(v)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Document metadata */}
      <JsonTreeNode label="filename" value={parsedDoc.filename} path="filename" expandedNodes={expandedNodes} toggleNode={toggleNode} />
      <JsonTreeNode label="page_count" value={parsedDoc.page_count} path="page_count" expandedNodes={expandedNodes} toggleNode={toggleNode} />
      <JsonTreeNode label="version" value={parsedDoc.version} path="version" expandedNodes={expandedNodes} toggleNode={toggleNode} />
      <JsonTreeNode label="conversion_status" value={parsedDoc.conversion_status} path="conversion_status" expandedNodes={expandedNodes} toggleNode={toggleNode} />

      {/* Elements */}
      <div className="mt-2">
        <button
          onClick={() => toggleNode('elements')}
          className="flex items-center gap-1 text-zinc-400 hover:text-white w-full"
        >
          <span className="text-zinc-600">{expandedNodes.has('elements') ? '\u25BC' : '\u25B6'}</span>
          <span className="text-purple-400">elements</span>
          <span className="text-zinc-600">[{elements.length}]</span>
        </button>

        {expandedNodes.has('elements') && (
          <div className="ml-4 border-l border-zinc-800 pl-2">
            {elements.map(([eid, el]) => {
              const isHovered = highlightedId === eid;
              const isSelected = selectedId === eid;
              const color = ELEMENT_COLORS[el.type] || '#6b7280';
              const nodePath = `elements.${eid}`;
              const confidence = el.metadata?.confidence as number | undefined;

              return (
                <div
                  key={eid}
                  data-element-id={eid}
                  data-pane="panel"
                  className={`my-0.5 rounded transition-colors ${
                    isHovered || isSelected ? 'bg-zinc-800/80' : ''
                  } ${el.skip_indexing ? 'opacity-50' : ''}`}
                  style={isHovered || isSelected ? { borderLeft: `2px solid ${color}` } : {}}
                  onMouseEnter={() => onHighlight(eid, 'panel')}
                  onMouseLeave={() => onHighlight(null, 'panel')}
                  onClick={() => onSelect(eid)}
                >
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleNode(nodePath); }}
                    className="flex items-center gap-1 text-zinc-400 hover:text-white w-full px-1 py-0.5"
                  >
                    <span className="text-zinc-600 text-xs">
                      {expandedNodes.has(nodePath) ? '\u25BC' : '\u25B6'}
                    </span>
                    <span className="text-zinc-500 text-xs">{eid}</span>
                    <span
                      className="text-xs px-1 rounded"
                      style={{ backgroundColor: `${color}30`, color }}
                    >
                      {el.type}
                    </span>
                    {el.skip_indexing && (
                      <span className="text-[9px] px-1 bg-zinc-700 text-zinc-500 rounded">skip</span>
                    )}
                    {confidence !== undefined && (
                      <span className={`text-[9px] ${getConfidenceBadgeColor(confidence)}`}>
                        {confidence.toFixed(2)}
                      </span>
                    )}
                    {!expandedNodes.has(nodePath) && (
                      <span className="text-zinc-600 text-xs truncate max-w-[200px]">
                        {el.content.substring(0, 40)}{el.content.length > 40 ? '...' : ''}
                      </span>
                    )}
                  </button>

                  {expandedNodes.has(nodePath) && (
                    <div className="ml-4 pl-2 border-l border-zinc-800 pb-1">
                      <div className="flex justify-end mb-1">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleCopyElement(el); }}
                          className="px-1.5 py-0.5 text-[9px] bg-zinc-800 hover:bg-zinc-700 text-zinc-500 rounded"
                        >
                          Copy
                        </button>
                      </div>
                      <JsonTreeNode label="element_id" value={el.element_id} path={`${nodePath}.element_id`} expandedNodes={expandedNodes} toggleNode={toggleNode} />
                      <JsonTreeNode label="type" value={el.type} path={`${nodePath}.type`} expandedNodes={expandedNodes} toggleNode={toggleNode} />
                      <JsonTreeNode label="label" value={el.label} path={`${nodePath}.label`} expandedNodes={expandedNodes} toggleNode={toggleNode} />
                      <JsonTreeNode label="page_number" value={el.page_number} path={`${nodePath}.page_number`} expandedNodes={expandedNodes} toggleNode={toggleNode} />
                      <div className="py-0.5 px-1">
                        <span className="text-blue-400 text-xs">content</span>
                        <span className="text-zinc-600 text-xs">: </span>
                        <span className="text-emerald-400 text-xs break-all">
                          &quot;{el.content.length > 200 ? el.content.substring(0, 200) + '...' : el.content}&quot;
                        </span>
                      </div>
                      {el.bbox && (
                        <JsonTreeNode label="bbox" value={el.bbox} path={`${nodePath}.bbox`} expandedNodes={expandedNodes} toggleNode={toggleNode} isObject />
                      )}
                      {el.bbox_normalized && (
                        <JsonTreeNode label="bbox_normalized" value={el.bbox_normalized} path={`${nodePath}.bbox_normalized`} expandedNodes={expandedNodes} toggleNode={toggleNode} isObject />
                      )}
                      {el.charspan && (
                        <JsonTreeNode label="charspan" value={el.charspan} path={`${nodePath}.charspan`} expandedNodes={expandedNodes} toggleNode={toggleNode} />
                      )}
                      {el.headings && el.headings.length > 0 && (
                        <JsonTreeNode label="headings" value={el.headings} path={`${nodePath}.headings`} expandedNodes={expandedNodes} toggleNode={toggleNode} />
                      )}
                      {Object.keys(el.metadata).length > 0 && (
                        <MetadataNode
                          metadata={el.metadata}
                          path={`${nodePath}.metadata`}
                          expandedNodes={expandedNodes}
                          toggleNode={toggleNode}
                        />
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Tables summary */}
      {Object.keys(parsedDoc.tables).length > 0 && (
        <JsonTreeNode
          label="tables"
          value={`[${Object.keys(parsedDoc.tables).length} items]`}
          path="tables"
          expandedNodes={expandedNodes}
          toggleNode={toggleNode}
        />
      )}

      {/* Images summary */}
      {Object.keys(parsedDoc.images).length > 0 && (
        <JsonTreeNode
          label="images"
          value={`[${Object.keys(parsedDoc.images).length} items]`}
          path="images"
          expandedNodes={expandedNodes}
          toggleNode={toggleNode}
        />
      )}
    </div>
  );
}

// ==================== JSON Tree Components ====================

function JsonTreeNode({
  label, value, path, expandedNodes, toggleNode, isObject,
}: {
  label: string;
  value: unknown;
  path: string;
  expandedNodes: Set<string>;
  toggleNode: (path: string) => void;
  isObject?: boolean;
}) {
  if (isObject && typeof value === 'object' && value !== null) {
    const entries = Object.entries(value as Record<string, unknown>);
    const isExpanded = expandedNodes.has(path);

    return (
      <div className="py-0.5">
        <button
          onClick={() => toggleNode(path)}
          className="flex items-center gap-1 text-zinc-400 hover:text-white px-1"
        >
          <span className="text-zinc-600 text-xs">{isExpanded ? '\u25BC' : '\u25B6'}</span>
          <span className="text-blue-400 text-xs">{label}</span>
          <span className="text-zinc-600 text-xs">{`{${entries.length}}`}</span>
        </button>
        {isExpanded && (
          <div className="ml-4 pl-2 border-l border-zinc-800">
            {entries.map(([k, v]) => (
              <div key={k} className="py-0.5 px-1">
                <span className="text-cyan-400 text-xs">{k}</span>
                <span className="text-zinc-600 text-xs">: </span>
                <span className="text-amber-400 text-xs">{JSON.stringify(v)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="py-0.5 px-1">
      <span className="text-blue-400 text-xs">{label}</span>
      <span className="text-zinc-600 text-xs">: </span>
      <span className={`text-xs ${typeof value === 'string' ? 'text-emerald-400' : 'text-amber-400'}`}>
        {typeof value === 'string' ? `"${value}"` : JSON.stringify(value)}
      </span>
    </div>
  );
}

function MetadataNode({
  metadata, path, expandedNodes, toggleNode,
}: {
  metadata: Record<string, unknown>;
  path: string;
  expandedNodes: Set<string>;
  toggleNode: (path: string) => void;
}) {
  const isExpanded = expandedNodes.has(path);
  const entries = Object.entries(metadata);

  return (
    <div className="py-0.5">
      <button
        onClick={(e) => { e.stopPropagation(); toggleNode(path); }}
        className="flex items-center gap-1 text-zinc-400 hover:text-white px-1"
      >
        <span className="text-zinc-600 text-xs">{isExpanded ? '\u25BC' : '\u25B6'}</span>
        <span className="text-blue-400 text-xs">metadata</span>
        <span className="text-zinc-600 text-xs">{`{${entries.length}}`}</span>
      </button>
      {isExpanded && (
        <div className="ml-4 pl-2 border-l border-zinc-800">
          {entries.map(([key, val]) => {
            if (key === 'image_b64' && typeof val === 'string') {
              return (
                <div key={key} className="py-1 px-1">
                  <span className="text-cyan-400 text-xs">{key}</span>
                  <span className="text-zinc-600 text-xs">: </span>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`data:image/png;base64,${val}`}
                    alt="Element image"
                    className="mt-1 max-w-[200px] max-h-[150px] rounded border border-zinc-700"
                  />
                </div>
              );
            }

            if (key === 'table_html' && typeof val === 'string') {
              return (
                <div key={key} className="py-1 px-1">
                  <span className="text-cyan-400 text-xs">{key}</span>
                  <span className="text-zinc-600 text-xs">: </span>
                  <div
                    className="mt-1 text-xs text-zinc-300 overflow-auto max-h-[200px] border border-zinc-700 rounded p-2 bg-zinc-800"
                    dangerouslySetInnerHTML={{ __html: val }}
                  />
                </div>
              );
            }

            const displayVal = typeof val === 'object' ? JSON.stringify(val) : String(val);
            return (
              <div key={key} className="py-0.5 px-1">
                <span className="text-cyan-400 text-xs">{key}</span>
                <span className="text-zinc-600 text-xs">: </span>
                <span className="text-amber-400 text-xs break-all">
                  {displayVal.length > 100 ? displayVal.substring(0, 100) + '...' : displayVal}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
