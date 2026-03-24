import React, { useState, useEffect } from 'react';
import { useTranslation } from '../i18n';

export interface TimelineSegment {
  index: number;
  text: string;
  start: number;
  end: number;
  score: number;
  reason?: string;
  included: boolean;
}

interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  seg: TimelineSegment | null;
}

interface Props {
  segments: TimelineSegment[];
  duration: number;
  onSegmentClick?: (seg: TimelineSegment) => void;
  onSegmentsChange?: (segments: TimelineSegment[]) => void;
}

function formatTime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export const SegmentTimeline: React.FC<Props> = ({ segments, duration, onSegmentClick, onSegmentsChange }) => {
  const { t } = useTranslation();
  const [localSegments, setLocalSegments] = useState<TimelineSegment[]>(segments);
  const [tooltip, setTooltip] = useState<TooltipState>({ visible: false, x: 0, y: 0, seg: null });

  useEffect(() => { setLocalSegments(segments); }, [segments]);

  const handleSegmentClick = (index: number) => {
    const updated = localSegments.map((seg, i) =>
      i === index ? { ...seg, included: !seg.included } : seg
    );
    setLocalSegments(updated);
    if (onSegmentsChange) onSegmentsChange(updated);
  };

  if (!segments.length || duration <= 0) return null;

  const labelCount = 5;
  const labels = Array.from({ length: labelCount }, (_, i) =>
    formatTime((duration / (labelCount - 1)) * i)
  );

  return (
    <div className="segment-timeline-wrap">
      <div className="segment-timeline-header">
        <span className="segment-timeline-title">{t('timeline.title')}</span>
        <div className="segment-timeline-legend">
          <span className="stl-dot stl-dot-green" />
          <span className="stl-legend-label">{t('timeline.included')}</span>
          <span className="stl-dot stl-dot-gray" />
          <span className="stl-legend-label">{t('timeline.excluded')}</span>
        </div>
      </div>

      <div className="segment-timeline-track-wrap">
        <div className="segment-timeline-track">
          {localSegments.map((seg, segIdx) => {
            const left = (seg.start / duration) * 100;
            const width = Math.max(0.5, ((seg.end - seg.start) / duration) * 100);
            return (
              <div
                key={seg.index}
                className={'stl-block' + (seg.included ? ' stl-block-on' : ' stl-block-off')}
                style={{ left: `${left}%`, width: `${width}%`, cursor: 'pointer', backgroundColor: seg.included ? '#22C55E' : '#94A3B8' }}
                onClick={() => { handleSegmentClick(segIdx); onSegmentClick?.(seg); }}
                onMouseEnter={e => {
                  const rect = (e.target as HTMLElement).getBoundingClientRect();
                  setTooltip({ visible: true, x: rect.left + rect.width / 2, y: rect.top, seg });
                }}
                onMouseLeave={() => setTooltip(t => ({ ...t, visible: false }))}
                title=""
              />
            );
          })}
        </div>
        <div className="segment-timeline-labels">
          {labels.map((lbl, i) => (
            <span key={i} className="stl-label">{lbl}</span>
          ))}
        </div>
      </div>

      {tooltip.visible && tooltip.seg && (
        <div
          className="stl-tooltip"
          style={{ left: tooltip.x, top: tooltip.y - 8 }}
        >
          <span className="stl-tooltip-time">{formatTime(tooltip.seg.start)} – {formatTime(tooltip.seg.end)}</span>
          <span className="stl-tooltip-score"> | score: {tooltip.seg.score}</span>
          {tooltip.seg.reason && <span className="stl-tooltip-reason"> | {tooltip.seg.reason}</span>}
        </div>
      )}
    </div>
  );
};
