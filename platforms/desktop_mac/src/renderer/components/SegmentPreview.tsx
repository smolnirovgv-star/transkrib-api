import React, { useRef, useEffect } from 'react';
import { X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useTranslation } from '../i18n';
import type { TimelineSegment } from './SegmentTimeline';

interface Props {
  segments: TimelineSegment[];
  currentIndex: number;
  videoSrc?: string;
  onClose: () => void;
  onNavigate: (index: number) => void;
  onToggleInclude?: (index: number) => void;
}

function formatTime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export const SegmentPreview: React.FC<Props> = ({
  segments, currentIndex, videoSrc, onClose, onNavigate, onToggleInclude,
}) => {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement>(null);
  const seg = segments[currentIndex];
  const total = segments.length;

  // Seek video to segment start when segment changes
  useEffect(() => {
    if (videoRef.current && seg) {
      videoRef.current.currentTime = seg.start;
      videoRef.current.play().catch(() => {});
    }
  }, [currentIndex, seg]);

  if (!seg) return null;

  const scoreColor = seg.score >= 8 ? 'var(--success)' : seg.score >= 5 ? 'var(--warning)' : 'var(--text-muted)';
  const scorePct = (seg.score / 10) * 100;

  return (
    <div className="seg-preview-backdrop" onClick={onClose}>
      <div className="seg-preview-modal" onClick={e => e.stopPropagation()}>
        <div className="seg-preview-header">
          <span className="seg-preview-title">
            {t('segment.preview')} {currentIndex + 1} / {total}
          </span>
          <button className="seg-preview-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="seg-preview-player">
          {videoSrc ? (
            <video
              ref={videoRef}
              src={videoSrc}
              className="seg-preview-video"
              controls
            />
          ) : (
            <div className="seg-preview-no-video">
              <span className="seg-preview-timecode">
                {formatTime(seg.start)} – {formatTime(seg.end)}
              </span>
            </div>
          )}
        </div>

        <div className="seg-preview-text">{seg.text}</div>

        <div className="seg-preview-score-row">
          <span className="seg-preview-score-label">Score: {seg.score}/10</span>
          <div className="seg-preview-score-bar-track">
            <div
              className="seg-preview-score-bar-fill"
              style={{ width: `${scorePct}%`, background: scoreColor }}
            />
          </div>
        </div>

        {seg.reason && <p className="seg-preview-reason">{seg.reason}</p>}

        <div className="seg-preview-actions">
          <button
            className="seg-nav-btn"
            onClick={() => onNavigate(currentIndex - 1)}
            disabled={currentIndex === 0}
          >
            <ChevronLeft size={16} />
            {t('segment.prev')}
          </button>

          <button
            className={'seg-toggle-btn' + (seg.included ? ' seg-toggle-exclude' : ' seg-toggle-include')}
            onClick={() => onToggleInclude?.(currentIndex)}
          >
            {seg.included ? t('segment.exclude') : t('segment.include')}
          </button>

          <button
            className="seg-nav-btn"
            onClick={() => onNavigate(currentIndex + 1)}
            disabled={currentIndex === total - 1}
          >
            {t('segment.next')}
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
};
