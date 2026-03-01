'use client';

import { useDocumentViewer } from '@/components/document-viewer/use-document-viewer';
import { useBidirectionalSync } from '@/components/document-viewer/use-bidirectional-sync';
import { PageViewer } from '@/components/document-viewer/page-viewer';
import { RightPane } from '@/components/document-viewer/right-pane';
import { MarkdownView } from '@/components/document-viewer/markdown-view';
import { JsonView } from '@/components/document-viewer/json-view';
import { DocumentChat } from '@/components/document-viewer/document-chat';
import { DataLoading, DataEmpty } from '@/components/ui/data-states';
import { ELEMENT_COLORS, ELEMENT_LABELS, FILE_ICONS } from '@/components/document-viewer/constants';
import type { ViewMode } from '@/components/document-viewer/types';

export default function AgenticDocsPage() {
  const viewer = useDocumentViewer();
  useBidirectionalSync(viewer.highlight.elementId, viewer.highlight.source);

  const getFileIcon = (fileType: string) => FILE_ICONS[fileType] || '\u{1F4C4}';

  const handleNavigateToElement = (elementId: string) => {
    viewer.highlightElement(elementId, 'panel');
    viewer.selectElement(elementId);
  };

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Top Bar */}
      <div className="border-b border-border px-4 py-3 flex items-center gap-4 flex-shrink-0">
        <h1 className="text-lg font-semibold text-white whitespace-nowrap">Agentic Docs</h1>

        {/* Document Selector */}
        <div className="flex-1 max-w-md">
          {viewer.filesLoading ? (
            <div className="h-9 bg-zinc-800 rounded-lg animate-pulse" />
          ) : (
            <select
              value={viewer.selectedFileId || ''}
              onChange={(e) => viewer.setSelectedFileId(e.target.value || null)}
              className="w-full h-9 bg-zinc-900 border border-zinc-700 rounded-lg px-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
            >
              <option value="">Select a document...</option>
              {viewer.files.map((f) => (
                <option key={f.id} value={f.id}>
                  {getFileIcon(f.file_type)} {f.filename}
                  {f.page_count ? ` (${f.page_count} pg)` : ''}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* View Mode Toggles */}
        {viewer.parsedDoc && (
          <div className="flex items-center gap-1 bg-zinc-800 rounded-lg p-0.5">
            {(['layout', 'detail'] as ViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => viewer.setViewMode(mode)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  viewer.viewMode === mode
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                {mode === 'layout' ? 'Layout' : 'Detail'}
              </button>
            ))}
          </div>
        )}

        {/* Element type legend */}
        {viewer.parsedDoc && viewer.elementTypesInDoc.length > 0 && (
          <div className="hidden lg:flex items-center gap-2 ml-2">
            {viewer.elementTypesInDoc.slice(0, 6).map((t) => (
              <div key={t} className="flex items-center gap-1">
                <div
                  className="w-2.5 h-2.5 rounded-sm"
                  style={{ backgroundColor: ELEMENT_COLORS[t] || '#6b7280' }}
                />
                <span className="text-[10px] text-zinc-500 capitalize">
                  {ELEMENT_LABELS[t] || t}
                </span>
              </div>
            ))}
            {viewer.elementTypesInDoc.length > 6 && (
              <span className="text-[10px] text-zinc-600">+{viewer.elementTypesInDoc.length - 6}</span>
            )}
          </div>
        )}
      </div>

      {/* Main Content */}
      {!viewer.selectedFileId ? (
        <div className="flex-1 flex items-center justify-center">
          <DataEmpty
            title="No document selected"
            description="Select a completed document from the dropdown above to view its parsed structure."
          />
        </div>
      ) : viewer.docLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <DataLoading message="Loading document structure..." />
        </div>
      ) : viewer.docError ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-red-400 text-sm">{viewer.docError}</p>
          </div>
        </div>
      ) : viewer.parsedDoc ? (
        <div ref={viewer.containerRef} className="flex-1 flex overflow-hidden relative">
          {/* Left Pane — Page Viewer */}
          <div style={{ width: `${viewer.splitPosition}%` }}>
            <PageViewer
              parsedDoc={viewer.parsedDoc}
              currentPage={viewer.currentPage}
              setCurrentPage={viewer.setCurrentPage}
              pageImageUrl={viewer.pageImageUrl}
              imageNaturalSize={viewer.imageNaturalSize}
              imageRef={viewer.imageRef}
              handleImageLoad={viewer.handleImageLoad}
              visibleBboxes={viewer.visibleBboxes}
              pageElements={viewer.pageElements}
              highlightedId={viewer.highlight.elementId}
              selectedId={viewer.selectedElementId}
              onHighlight={viewer.highlightElement}
              onSelect={viewer.selectElement}
            />
          </div>

          {/* Split Handle */}
          <div
            className="w-1 bg-zinc-800 hover:bg-emerald-500/50 cursor-col-resize flex-shrink-0 transition-colors"
            onMouseDown={viewer.handleSplitMouseDown}
          />

          {/* Right Pane — Parse/Chat tabs */}
          <div style={{ width: `${100 - viewer.splitPosition}%` }}>
            <RightPane
              activeTab={viewer.rightPaneTab}
              setActiveTab={viewer.setRightPaneTab}
              parseSubTab={viewer.parseSubTab}
              setParseSubTab={viewer.setParseSubTab}
              elementCount={viewer.elementsList.length}
              markdownView={
                <MarkdownView
                  parsedDoc={viewer.parsedDoc}
                  markdownContent={viewer.markdownContent}
                  highlightedId={viewer.highlight.elementId}
                  onHighlight={viewer.highlightElement}
                  onSelect={viewer.selectElement}
                />
              }
              jsonView={
                <JsonView
                  parsedDoc={viewer.parsedDoc}
                  expandedNodes={viewer.expandedNodes}
                  toggleNode={viewer.toggleNode}
                  highlightedId={viewer.highlight.elementId}
                  selectedId={viewer.selectedElementId}
                  onHighlight={viewer.highlightElement}
                  onSelect={viewer.selectElement}
                />
              }
              chatView={
                viewer.selectedFileId ? (
                  <DocumentChat
                    documentId={viewer.selectedFileId}
                    parsedDoc={viewer.parsedDoc}
                    onNavigateToElement={handleNavigateToElement}
                  />
                ) : null
              }
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
