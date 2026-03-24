import React, { useEffect, useState, useMemo } from "react";
import { ArrowLeft, Download, ToggleLeft, ToggleRight } from "lucide-react";
import { useTranslation } from "../i18n";
import { api } from "../services/api";

interface Segment {
  text: string;
  start: number;
  end: number;
  pause_before: number;
  score: number;
  reason?: string;
}

interface Props {
  filename: string;
  onClose: () => void;
}

function formatTimecode(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round((score / 10) * 100);
  const cls = score >= 8 ? "high" : score >= 5 ? "mid" : "low";
  return (
    <div className="transcript-score-bar">
      <div className={`transcript-score-fill ${cls}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export const TranscriptViewer: React.FC<Props> = ({ filename, onClose }) => {
  const { t } = useTranslation();
  const [segments, setSegments] = useState<Segment[]>([]);
  const [formattedText, setFormattedText] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"formatted" | "raw">("formatted");
  const [filter, setFilter] = useState<"all" | "important">("all");
  const [search, setSearch] = useState("");
  const [highlights, setHighlights] = useState<Array<{text: string, start: number, score: number}>>([]);

  const stem = filename.replace(/\.mp4$/i, "");

  useEffect(() => {
    setLoading(true);
    api.getTranscript(filename).then((data) => {
      if (data?.segments) setSegments(data.segments);
      if (data?.formatted_text) setFormattedText(data.formatted_text);
      setLoading(false);
    });
  }, [filename]);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/transcript/' + encodeURIComponent(filename) + '/highlights')
      .then(r => r.json())
      .then(d => setHighlights(d.highlights || []))
      .catch(() => setHighlights([]));
  }, [filename]);

  const displayed = useMemo(() => {
    return segments.filter(seg => {
      const matchesSearch = search.trim() === '' ||
        seg.text.toLowerCase().includes(search.toLowerCase());
      const matchesFilter = filter === 'all' ||
        (filter === 'important' && (
          highlights.length > 0
            ? highlights.some(h => h.start === seg.start)
            : seg.score >= 6
        ));
      return matchesSearch && matchesFilter;
    });
  }, [segments, filter, search, highlights]);

  const formattedParagraphs = useMemo(() => {
    if (!formattedText) return [];
    return formattedText.split(/\n\n+/).filter((p) => p.trim());
  }, [formattedText]);

  const handleDownload = async (format: "txt" | "srt" | "json" | "html") => {
    if (window.electronAPI) {
      await window.electronAPI.saveTranscript(filename, format);
    } else {
      const url = api.getTranscriptDownloadUrl(filename, format);
      const ext = format;
      const a = document.createElement("a");
      a.href = url;
      a.download = `${stem}.${ext}`;
      a.click();
    }
  };

  const highlightText = (text: string, query: string): React.ReactNode => {
    if (!query.trim()) return text;
    const idx = text.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) return text;
    return (
      <>
        {text.slice(0, idx)}
        <span className="transcript-highlight">{text.slice(idx, idx + query.length)}</span>
        {text.slice(idx + query.length)}
      </>
    );
  };

  return (
    <div className="transcript-viewer">
      {/* Header */}
      <div className="transcript-viewer-header">
        <button className="transcript-viewer-back" onClick={onClose}>
          <ArrowLeft size={14} />
          {t("transcript.back")}
        </button>
        <span className="transcript-viewer-title">
          📄 {stem}
        </span>
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
          {segments.length} фраз
        </span>
      </div>

      {/* Search bar */}
      <div className="transcript-search-bar">
        <input
          className="transcript-search-input"
          placeholder="Поиск по тексту..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button className={'transcript-filter-btn' + (filter === 'all' ? ' active' : '')} onClick={() => setFilter('all')}>Все</button>
        <button className={'transcript-filter-btn' + (filter === 'important' ? ' active' : '')} onClick={() => setFilter('important')}>Важные</button>
      </div>

      {/* Controls */}
      <div className="transcript-viewer-controls">
        {/* View mode toggle */}
        <button
          className={`transcript-filter-btn${viewMode === "formatted" ? " active" : ""}`}
          onClick={() => setViewMode("formatted")}
          title={t("transcript.formatted")}
        >
          {viewMode === "formatted" ? <ToggleRight size={13} /> : <ToggleLeft size={13} />}
          {t("transcript.formatted")}
        </button>
        <button
          className={`transcript-filter-btn${viewMode === "raw" ? " active" : ""}`}
          onClick={() => setViewMode("raw")}
          title={t("transcript.raw")}
        >
          {t("transcript.raw")}
        </button>

        {/* Raw-mode filters (only shown in raw view) */}
        {viewMode === "raw" && (
          <>
            <div style={{ width: 1, height: 16, background: "var(--border)", margin: "0 2px" }} />
            <button
              className={`transcript-filter-btn${filter === "all" ? " active" : ""}`}
              onClick={() => setFilter("all")}
            >
              {t("transcript.filterAll")}
            </button>
            <button
              className={`transcript-filter-btn${filter === "important" ? " active" : ""}`}
              onClick={() => setFilter("important")}
            >
              {t("transcript.filterImportant")}
            </button>
            <input
              className="transcript-search"
              placeholder={t("transcript.searchPlaceholder")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </>
        )}
      </div>

      {/* Body */}
      <div className="transcript-viewer-body">
        {loading ? (
          <div className="transcript-empty">{t("transcript.loading")}</div>
        ) : viewMode === "formatted" ? (
          formattedParagraphs.length > 0 ? (
            <div className="transcript-formatted-view">
              {formattedParagraphs.map((para, i) => (
                <p key={i} className="transcript-paragraph">{para}</p>
              ))}
            </div>
          ) : (
            <div className="transcript-empty">{t("transcript.noData")}</div>
          )
        ) : displayed.length === 0 ? (
          <div className="transcript-empty">
            {filter === 'important' ? 'Важные моменты не определены для этого видео' : t('transcript.noData')}
          </div>
        ) : (
          displayed.map((seg, i) => (
            <div key={i} className="transcript-segment">
              <div className="transcript-segment-header">
                <span className="transcript-timecode">{formatTimecode(seg.start)}</span>
                <ScoreBar score={seg.score} />
                <span className="transcript-score-label">{seg.score}/10</span>
              </div>
              <div className="transcript-segment-text">{highlightText(seg.text, search)}</div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="transcript-viewer-footer">
        <button className="btn-secondary" onClick={() => handleDownload("txt")}>
          <Download size={13} /> {t("transcript.downloadTxt")}
        </button>
        <button className="btn-secondary" onClick={() => handleDownload("srt")}>
          <Download size={13} /> {t("transcript.downloadSrt")}
        </button>
        <button className="btn-secondary" onClick={() => handleDownload("json")}>
          <Download size={13} /> {t("transcript.downloadJson")}
        </button>
        <button className="btn-secondary" onClick={() => handleDownload("html")}>
          <Download size={13} /> {t("transcript.downloadHtml")}
        </button>
      </div>
    </div>
  );
};
