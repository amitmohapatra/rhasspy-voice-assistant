'use client';

import type { VisibleBbox } from './types';

interface BboxOverlayProps {
  item: VisibleBbox;
  scaleX: number;
  scaleY: number;
  factorX: number;
  factorY: number;
  isHovered: boolean;
  isSelected: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onClick: () => void;
}

/**
 * Single bbox overlay with LandingAI-style inverted hover behavior:
 * - Default: colored 2px border + colored fill ~10% opacity
 * - Hover: fill DISAPPEARS (transparent), content shows through
 * - Selected: 3px border, transparent fill, label pinned
 */
export function BboxOverlay({
  item, scaleX, scaleY, factorX, factorY,
  isHovered, isSelected, onMouseEnter, onMouseLeave, onClick,
}: BboxOverlayProps) {
  const { bbox, color, label } = item;

  const left = bbox.x0 * factorX * scaleX;
  const top = bbox.y0 * factorY * scaleY;
  const width = (bbox.x1 - bbox.x0) * factorX * scaleX;
  const height = (bbox.y1 - bbox.y0) * factorY * scaleY;

  const showLabel = isHovered || isSelected;
  // Inverted: fill visible by default, transparent on hover/select
  const fillOpacity = (isHovered || isSelected) ? 0 : 0.1;
  const borderWidth = isSelected ? 3 : 2;

  return (
    <div
      data-element-id={item.elementId}
      data-pane="image"
      className="absolute cursor-pointer transition-all duration-150"
      style={{
        left,
        top,
        width: Math.max(width, 2),
        height: Math.max(height, 2),
        border: `${borderWidth}px solid ${color}`,
        backgroundColor: `${color}${Math.round(fillOpacity * 255).toString(16).padStart(2, '0')}`,
        zIndex: (isHovered || isSelected) ? 20 : 10,
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
      title={`${label}: ${item.element.content.substring(0, 80)}...`}
    >
      {showLabel && (
        <span
          className="absolute -top-5 left-0 px-1.5 py-0.5 text-[10px] font-medium rounded whitespace-nowrap pointer-events-none"
          style={{ backgroundColor: color, color: 'white' }}
        >
          {label}
        </span>
      )}
    </div>
  );
}
