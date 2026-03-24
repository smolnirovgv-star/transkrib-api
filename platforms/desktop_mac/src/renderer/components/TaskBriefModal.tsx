import React, { useState } from 'react';
import { X } from 'lucide-react';

export type CutStyle = 'auto' | 'practice' | 'theory' | 'news';

export interface UserBrief {
  description: string;
  keywords: string;
  style: CutStyle;
}

interface Props {
  initialBrief?: UserBrief;
  onStart: (brief: UserBrief) => void;
  onSkip: () => void;
  onClose: () => void;
}

const STYLE_OPTIONS: { value: CutStyle; label: string; desc: string }[] = [
  { value: 'auto',     label: 'Авто (рекомендуется)',   desc: 'AI выбирает важные моменты самостоятельно' },
  { value: 'practice', label: 'Только практика',         desc: 'Советы, примеры, инструкции' },
  { value: 'theory',   label: 'Только теория',           desc: 'Концепции, объяснения, определения' },
  { value: 'news',     label: 'Новостной',               desc: 'Факты, выводы, ключевые данные' },
];

export const TaskBriefModal: React.FC<Props> = ({ initialBrief, onStart, onSkip, onClose }) => {
  const [description, setDescription] = useState(initialBrief?.description ?? '');
  const [keywords, setKeywords]       = useState(initialBrief?.keywords ?? '');
  const [style, setStyle]             = useState<CutStyle>(initialBrief?.style ?? 'auto');

  const handleStart = () => onStart({ description, keywords, style });

  return (
    <div className="brief-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="brief-modal">
        <div className="brief-header">
          <span className="brief-title">🎯 Настройте обработку видео</span>
          <button className="btn-icon" onClick={onClose}><X size={15} /></button>
        </div>

        <div className="brief-body">
          <div className="brief-hint">
            Опишите что важно сохранить в видео. Например: ключевые выводы, советы,
            определённые темы или спикеры, важные моменты которые нельзя пропустить.
          </div>

          <div className="brief-field">
            <label className="brief-label">Описание</label>
            <textarea
              className="brief-textarea"
              rows={4}
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Например: сохранить все практические советы и примеры, убрать вводную часть..."
            />
          </div>

          <div className="brief-field">
            <label className="brief-label">Ключевые слова (через запятую)</label>
            <input
              className="brief-input"
              type="text"
              value={keywords}
              onChange={e => setKeywords(e.target.value)}
              placeholder="продажи, конверсия, ROI"
            />
          </div>

          <div className="brief-field">
            <label className="brief-label">Стиль нарезки</label>
            <div className="brief-style-group">
              {STYLE_OPTIONS.map(opt => (
                <div
                  key={opt.value}
                  className={'brief-style-option' + (style === opt.value ? ' active' : '')}
                  onClick={() => setStyle(opt.value)}
                >
                  <input
                    type="radio"
                    className="brief-style-radio"
                    checked={style === opt.value}
                    onChange={() => setStyle(opt.value)}
                  />
                  <div>
                    <div className="brief-style-text">{opt.label}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{opt.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="brief-footer">
          <button className="btn-secondary" onClick={onSkip}>Пропустить</button>
          <button className="btn-primary" onClick={handleStart}>▶ Начать обработку</button>
        </div>
      </div>
    </div>
  );
};
