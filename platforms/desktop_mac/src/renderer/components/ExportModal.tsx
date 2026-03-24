import React, { useState } from 'react';
import { X } from 'lucide-react';
import { useTranslation } from '../i18n';

type Format = 'mp4' | 'mkv' | 'webm';
type SubMode = 'embed' | 'srt' | 'both' | 'none';

interface Props {
  filename: string;
  onClose: () => void;
}

export const ExportModal: React.FC<Props> = ({ filename, onClose }) => {
  const { t } = useTranslation();

  const [format, setFormat] = useState<Format>('mp4');
  const [crf, setCrf] = useState<18 | 23 | 28>(23);
  const [resolution, setResolution] = useState('original');
  const [subMode, setSubMode] = useState<SubMode>('embed');
  const [outputFolder, setOutputFolder] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  const handleChooseFolder = async () => {
    if (!window.electronAPI) return;
    const folder = await window.electronAPI.selectFolder();
    if (folder) setOutputFolder(folder);
  };

  const handleExport = async () => {
    if (!window.electronAPI) {
      setStatus({ type: 'error', msg: 'Not available in browser mode' });
      return;
    }
    setStatus(null);
    setLoading(true);
    try {
      const result = await window.electronAPI.exportVideo({
        sourceFilename: filename,
        format,
        crf,
        resolution,
        subtitleMode: subMode,
        outputFolder: outputFolder || '',
      });
      if (result.success) {
        setStatus({ type: 'success', msg: t('export.success') });
      } else {
        setStatus({ type: 'error', msg: result.error || t('export.error') });
      }
    } catch (e: any) {
      setStatus({ type: 'error', msg: e?.message || t('export.error') });
    } finally {
      setLoading(false);
    }
  };

  const SUB_OPTS: { value: SubMode; label: string }[] = [
    { value: 'embed', label: t('export.sub_embed') },
    { value: 'srt',   label: t('export.sub_srt') },
    { value: 'both',  label: t('export.sub_both') },
    { value: 'none',  label: t('export.sub_none') },
  ];

  return (
    <div className="export-modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="export-modal glass-card">
        <div className="export-modal-header">
          <span className="export-modal-title">{t('export.title')}</span>
          <button className="btn-icon" onClick={onClose}><X size={15} /></button>
        </div>

        <div className="export-modal-body">
          {/* Format */}
          <div className="export-field">
            <label className="export-label">{t('export.format')}</label>
            <select className="export-select" value={format} onChange={e => setFormat(e.target.value as Format)}>
              <option value="mp4">MP4</option>
              <option value="mkv">MKV</option>
              <option value="webm">WebM</option>
            </select>
          </div>

          {/* Quality */}
          <div className="export-field">
            <label className="export-label">{t('export.quality')}</label>
            <select className="export-select" value={crf} onChange={e => setCrf(Number(e.target.value) as 18 | 23 | 28)}>
              <option value={18}>{t('export.quality_high')} (CRF 18)</option>
              <option value={23}>{t('export.quality_medium')} (CRF 23)</option>
              <option value={28}>{t('export.quality_low')} (CRF 28)</option>
            </select>
          </div>

          {/* Resolution */}
          <div className="export-field">
            <label className="export-label">{t('export.resolution')}</label>
            <select className="export-select" value={resolution} onChange={e => setResolution(e.target.value)}>
              <option value="original">{t('export.res_original')}</option>
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
              <option value="480p">480p</option>
            </select>
          </div>

          {/* Subtitles */}
          <div className="export-field">
            <label className="export-label">{t('export.subtitles')}</label>
            <div className="export-radio-group">
              {SUB_OPTS.map(o => (
                <button
                  key={o.value}
                  className={`export-radio-btn${subMode === o.value ? ' active' : ''}`}
                  onClick={() => setSubMode(o.value)}
                  title={o.label}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          {/* Output folder */}
          <div className="export-field">
            <label className="export-label">{t('export.outputFolder')}</label>
            <div className="export-folder">
              <span className="export-folder-path">
                {outputFolder || t('export.noFolder')}
              </span>
              <button className="btn-secondary" onClick={handleChooseFolder} style={{ flexShrink: 0 }}>
                {t('export.chooseFolder')}
              </button>
            </div>
          </div>

          {/* Status */}
          {status && (
            <div className={`export-status export-status-${status.type}`}>{status.msg}</div>
          )}
        </div>

        <div className="export-modal-footer">
          <button className="btn-secondary" onClick={onClose}>{t('export.cancel')}</button>
          <button
            className="btn-primary"
            onClick={handleExport}
            disabled={loading}
          >
            {loading ? t('export.exporting') : t('export.btn')}
          </button>
        </div>
      </div>
    </div>
  );
};
