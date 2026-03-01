/**
 * TypeScript interfaces for the Document Viewer (Agentic Docs).
 * Supports both v1 (legacy) and v2 enriched.json formats.
 */

// ==================== BBox Types ====================

/** v1 bbox format (absolute pixel coordinates) */
export interface BBoxV1 {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  page: number;
}

/** v2 bbox format (normalized 0-1 coordinates) */
export interface BBoxV2 {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

// ==================== Element Types ====================

/** v2 enriched element */
export interface EnrichedElement {
  element_id: string;
  type: string;
  label: string;
  content: string;
  page_number: number;
  bbox: BBoxV1 | null;
  bbox_normalized: BBoxV2 | null;
  metadata: Record<string, unknown>;
  charspan?: [number, number];
  hierarchy?: { parent?: string; children?: string[] };
  skip_indexing?: boolean;
  headings?: string[];
}

/** v2 enriched document response */
export interface EnrichedDocument {
  version: string;
  document_id?: string;
  filename?: string;
  text?: string;
  elements: Record<string, EnrichedElement>;
  tables: Record<string, EnrichedElement>;
  images: Record<string, EnrichedElement>;
  page_count: number;
  page_dimensions: Record<string, { width: number; height: number }>;
  pages: Record<string, Record<string, number>>;
  quality: QualityScores;
  conversion_status: string;
  timings: Record<string, number>;
  metadata: Record<string, unknown>;
}

export interface QualityScores {
  layout_score?: number;
  ocr_score?: number;
  table_score?: number;
  parse_score?: number;
  mean_grade?: number | string;
  low_grade?: number | string;
}

// ==================== Viewer State ====================

export type ViewMode = 'layout' | 'detail' | 'ocr';
export type RightPaneTab = 'parse' | 'chat';
export type ParseSubTab = 'markdown' | 'json';

export interface HighlightState {
  elementId: string | null;
  source: 'image' | 'panel' | null;
}

export interface CompletedFile {
  id: string;
  filename: string;
  file_type: string;
  page_count: number | null;
  status: string;
  meta_data?: Record<string, unknown>;
}

// ==================== BBox Overlay ====================

export interface VisibleBbox {
  elementId: string;
  bbox: BBoxV1;
  bboxNormalized: BBoxV2 | null;
  color: string;
  label: string;
  element: EnrichedElement;
}

// ==================== Chat Types ====================

export interface LLMKeyInfo {
  provider: string;
  key_preview: string;
  label: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DocumentChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  isStreaming?: boolean;
  sources?: SourceCitation[];
}

export interface SourceCitation {
  element_id: string;
  page_number: number;
  type: string;
  preview: string;
}
