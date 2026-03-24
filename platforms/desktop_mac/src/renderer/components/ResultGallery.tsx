import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, Download, Eye, FileJson, FileText, FolderOpen, RefreshCw, Trash2, Upload, X } from 'lucide-react';
import { useTranslation } from '../i18n';
import { ExportModal } from './ExportModal';
import { TranscriptViewer } from './TranscriptViewer';
import { SegmentTimeline, TimelineSegment } from './SegmentTimeline';
import { SegmentPreview } from './SegmentPreview';
import { api } from '../services/api';

interface ResultItem {
  filename: string;
  size_mb: number;
  duration_formatted: string;
  created_at: string;
}

interface SegPreviewState {
  filename: string;
  segIndex: number;
}

function parseDuration(formatted: string): number {
  const parts = formatted.split(':').map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}

interface GalleryProps { onResultCountChange?: (count: number) => void; }

export const ResultGallery: React.FC<GalleryProps> = ({ onResultCountChange }) => {
  const { t } = useTranslation();
  const [results, setResults] = useState<ResultItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [exportFile, setExportFile] = useState<string | null>(null);
  const [transcriptFile, setTranscriptFile] = useState<string | null>(null);
  const [openDropdown, setOpenDropdown] = useState(false);
  const [expandedTimeline, setExpandedTimeline] = useState(false);
  const [timelineData, setTimelineData] = useState<Record<string, TimelineSegment[]>>({});
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [segPreview, setSegPreview] = useState<SegPreviewState | null>(null);
  const [videoSrc, setVideoSrc] = useState<string>('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const load = () => {
      if (window.electronAPI) {
        window.electronAPI.listResults().then(r => {
          setResults(r);
          onResultCountChange?.(r.length);
        }).catch(() => {});
      } else {
        api.listResults().then(r => {
          setResults(r as any);
          onResultCountChange?.(r.length);
        }).catch(() => {});
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpenDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const selected = results[selectedIndex] || null;

  const getVideoSrc = (filename: string): string => {
    if (window.electronAPI) {
      return 'transkrib://results/' + encodeURIComponent(filename);
    }
    return 'http://127.0.0.1:8000/api/tasks/result/' + encodeURIComponent(filename);
  };

  const getVideoUrl = async (filename: string): Promise<string> => {
    if (window.electronAPI && window.electronAPI.getResultPath) {
      const filePath = await window.electronAPI.getResultPath(filename);
      if (filePath) {
        return 'file:///' + filePath.replace(/\\/g, '/');
      }
    }
    return 'http://127.0.0.1:8000/api/tasks/result/' + encodeURIComponent(filename);
  };

  const fetchTimeline = async (filename: string, duration: number) => {
    if (timelineData[filename]) return;
    setTimelineLoading(true);
    try {
      const data = await api.getTranscript(filename);
      if (data && data.segments.length > 0) {
        const segs: TimelineSegment[] = data.segments.map((s: any, i: number) => ({
          index: i,
          text: s.text || '',
          start: typeof s.start === 'number' ? s.start : parseFloat(s.start) || 0,
          end: typeof s.end === 'number' ? s.end : parseFloat(s.end) || 0,
          score: s.score ?? 5,
          reason: s.reason,
          included: (s.score ?? 5) >= 6,
        }));
        setTimelineData(prev => ({ ...prev, [filename]: segs }));
      }
    } catch {}
    setTimelineLoading(false);
  };

  useEffect(() => {
    if (!selected) return;
    getVideoUrl(selected.filename).then(setVideoSrc);
  }, [selected && selected.filename]);

  const handleDownloadTranscript = async (filename: string, format: 'txt' | 'srt' | 'json' | 'html') => {
    setOpenDropdown(false);
    if (window.electronAPI && window.electronAPI.saveTranscript) {
      await window.electronAPI.saveTranscript(filename, format);
    } else {
      const url = 'http://127.0.0.1:8000/api/transcript/' + encodeURIComponent(filename) + '/download?format=' + format;
      const stem = filename.replace(/\.mp4$/i, '');
      const a = document.createElement('a');
      a.href = url;
      a.download = stem + '.' + format;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };

  const handleDelete = async (filename: string) => {
    try {
      if (window.electronAPI && window.electronAPI.deleteResult) {
        await window.electronAPI.deleteResult(filename);
      } else {
        await fetch('http://127.0.0.1:8000/api/tasks/result/' + encodeURIComponent(filename), { method: 'DELETE' });
      }
      const next = results.filter(r => r.filename !== filename);
      setResults(next);
      onResultCountChange?.(next.length);
      setSelectedIndex(0);
    } catch (e) { console.error('Delete error:', e); }
  };

  const handleSelectArchive = (idx: number) => {
    setSelectedIndex(idx);
    setArchiveOpen(false);
    setExpandedTimeline(false);
    setOpenDropdown(false);
  };

  const handleDownload = () => {
    if (!selected) return;
    if (window.electronAPI && (window.electronAPI as any).downloadResult) {
      (window.electronAPI as any).downloadResult(selected.filename);
    } else {
      const url = 'http://127.0.0.1:8000/api/tasks/result/' + encodeURIComponent(selected.filename);
      const a = document.createElement('a');
      a.href = url;
      a.download = selected.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };

  if (!results.length) return null;

  if (transcriptFile) {
    return <TranscriptViewer filename={transcriptFile} onClose={() => setTranscriptFile(null)} />;
  }

  const dur = selected ? parseDuration(selected.duration_formatted) : 0;
  const segs = selected ? timelineData[selected.filename] : undefined;

  return (
    <div className="result-main-container">

      {selected && (
        <div className="result-player-wrap">
          <video
            key={selected.filename}
            className="result-player-video"
            src={videoSrc}
            controls
          />
        </div>
      )}

      {selected && (
        <div className="result-meta">
          <span className="result-meta-name" title={selected.filename}>{selected.filename}</span>
          <span className="result-meta-info">{selected.duration_formatted} · {selected.size_mb} МБ</span>
        </div>
      )}

      {selected && (
        <div className="result-actions">
          <div className="transcript-dropdown" ref={openDropdown ? dropdownRef : undefined}>
            <button className="btn-secondary" onClick={(e) => { e.stopPropagation(); setOpenDropdown(!openDropdown); }}>
              <FileText size={14} /> {t('transcript.title')} <ChevronDown size={12} />
            </button>
            {openDropdown && (
              <div className="transcript-dropdown-menu" style={{ position: "absolute", right: 0, left: "auto", minWidth: "220px", zIndex: 1000 }}>
                <button onClick={() => { setOpenDropdown(false); setTranscriptFile(selected.filename); }}>
                  <Eye size={13} /> {t('transcript.viewInApp')}
                </button>
                <div className="transcript-dropdown-divider" />
                <button onClick={() => handleDownloadTranscript(selected.filename, 'txt')}>
                  <FileText size={13} /> {t('transcript.downloadTxt')}
                </button>
                <button onClick={() => handleDownloadTranscript(selected.filename, 'srt')}>
                  <FileText size={13} /> {t('transcript.downloadSrt')}
                </button>
                <button onClick={() => handleDownloadTranscript(selected.filename, 'json')}>
                  <FileJson size={13} /> {t('transcript.downloadJson')}
                </button>
                <button onClick={() => handleDownloadTranscript(selected.filename, 'html')}>
                  <FileText size={13} /> {t('transcript.downloadHtml')}
                </button>
              </div>
            )}
          </div>

          <button className="btn-secondary" onClick={() => setExportFile(selected.filename)}>
            <Upload size={14} /> {t('export.title')}
          </button>

          <button className="btn-secondary" onClick={handleDownload}>
            <Download size={14} /> {t('results.download')}
          </button>

          <button className="btn-secondary btn-danger" onClick={() => handleDelete(selected.filename)}>
            <Trash2 size={14} /> {t('results.delete')}
          </button>
        </div>
      )}

      {selected && dur > 0 && (
        <div className="result-timeline-section">
          <button className="stl-toggle-btn" onClick={() => {
            if (!expandedTimeline) fetchTimeline(selected.filename, dur);
            setExpandedTimeline(!expandedTimeline);
          }}>
            {t('timeline.title')} <ChevronDown size={12} className={expandedTimeline ? 'stl-chevron-open' : ''} />
          </button>
          {expandedTimeline && (
            <div className="result-card-timeline">
              {timelineLoading ? (
                <div className="stl-loading"><RefreshCw size={12} className="spin" /> Loading...</div>
              ) : segs && segs.length > 0 ? (
                <SegmentTimeline
                  segments={segs}
                  duration={dur}
                  onSegmentClick={(seg) => setSegPreview({ filename: selected.filename, segIndex: seg.index })}
                />
              ) : (
                <p className="stl-no-data">{t('transcript.noData')}</p>
              )}
            </div>
          )}
        </div>
      )}

      <button className="result-folder-btn" onClick={() => setArchiveOpen(!archiveOpen)} title="Обработанные видео">
        <FolderOpen size={24} color="white" />
        {results.length > 0 && <span className="result-folder-badge">{results.length}</span>}
      </button>

      <div className={"result-archive-panel" + (archiveOpen ? " open" : "")}>
        <div className="result-archive-header">
          <span>Обработанные видео</span>
          <button className="result-archive-close" onClick={() => setArchiveOpen(false)}><X size={16} /></button>
        </div>
        <div className="result-archive-list">
          {results.map((r, idx) => (
            <div
              key={r.filename}
              className={"result-archive-item" + (idx === selectedIndex ? " active" : "")}
              onClick={() => handleSelectArchive(idx)}
            >
              <video className="result-archive-thumb" src={getVideoSrc(r.filename)} muted />
              <div className="result-archive-info">
                <span className="result-archive-name">{r.filename}</span>
                <span className="result-archive-date">{r.created_at ? r.created_at.slice(0, 10) : ''}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {archiveOpen && (
        <div className="result-archive-overlay" onClick={() => setArchiveOpen(false)} />
      )}

      {exportFile && (
        <ExportModal filename={exportFile} onClose={() => setExportFile(null)} />
      )}

      {segPreview && selected && timelineData[selected.filename] && (
        <SegmentPreview
          segments={timelineData[selected.filename]}
          currentIndex={segPreview.segIndex}
          videoSrc={api.getStreamUrl(segPreview.filename)}
          onClose={() => setSegPreview(null)}
          onNavigate={(idx) => setSegPreview({ ...segPreview, segIndex: idx })}
          onToggleInclude={(idx) => {
            setTimelineData(prev => {
              const s = [...(prev[segPreview.filename] || [])];
              s[idx] = { ...s[idx], included: !s[idx].included };
              return { ...prev, [segPreview.filename]: s };
            });
          }}
        />
      )}
    </div>
  );
};
