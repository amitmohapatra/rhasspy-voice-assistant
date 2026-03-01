/**
 * Constants for the Document Viewer — color map, labels, thresholds.
 */

/** Color map for all 23 element types + legacy aliases */
export const ELEMENT_COLORS: Record<string, string> = {
  title: '#f59e0b',
  section_header: '#8b5cf6',
  paragraph: '#3b82f6',
  list_item: '#06b6d4',
  table: '#10b981',
  figure: '#f43f5e',
  chart: '#e11d48',
  code: '#a855f7',
  equation: '#ec4899',
  key_value: '#14b8a6',
  form_field: '#f97316',
  caption: '#6b7280',
  footnote: '#78716c',
  reference: '#a3a3a3',
  document_index: '#737373',
  page_header: '#525252',
  page_footer: '#525252',
  checkbox: '#22c55e',
  handwritten: '#fb923c',
  grading_scale: '#facc15',
  // Legacy compat
  heading: '#8b5cf6',
  text: '#3b82f6',
  image: '#f43f5e',
};

/** Human-readable labels for element types */
export const ELEMENT_LABELS: Record<string, string> = {
  title: 'Title',
  section_header: 'Section Header',
  paragraph: 'Paragraph',
  list_item: 'List Item',
  table: 'Table',
  figure: 'Figure',
  chart: 'Chart',
  code: 'Code',
  equation: 'Equation',
  key_value: 'Key-Value',
  form_field: 'Form Field',
  caption: 'Caption',
  footnote: 'Footnote',
  reference: 'Reference',
  document_index: 'Index/TOC',
  page_header: 'Page Header',
  page_footer: 'Page Footer',
  checkbox: 'Checkbox',
  handwritten: 'Handwritten',
  grading_scale: 'Grading Scale',
  heading: 'Heading',
  text: 'Text',
  image: 'Image',
};

/** Confidence thresholds for badge coloring */
export const CONFIDENCE_THRESHOLDS = {
  HIGH: 0.8,    // green
  MEDIUM: 0.5,  // yellow
  LOW: 0,       // red
} as const;

/** Get confidence badge color */
export function getConfidenceBadgeColor(score: number | undefined): string {
  if (score === undefined) return 'text-zinc-500';
  if (score >= CONFIDENCE_THRESHOLDS.HIGH) return 'text-emerald-400';
  if (score >= CONFIDENCE_THRESHOLDS.MEDIUM) return 'text-yellow-400';
  return 'text-red-400';
}

/** File type icons */
export const FILE_ICONS: Record<string, string> = {
  '.pdf': '\u{1F4C4}',
  '.png': '\u{1F5BC}',
  '.jpg': '\u{1F5BC}',
  '.jpeg': '\u{1F5BC}',
  '.docx': '\u{1F4DD}',
  '.txt': '\u{1F4C3}',
  '.md': '\u{1F4C3}',
  '.csv': '\u{1F4CA}',
  '.json': '\u{1F4CB}',
  '.html': '\u{1F310}',
  '.pptx': '\u{1F4CA}',
};
