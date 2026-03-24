import React from 'react';
import { ArrowLeft, BookOpen, FileText, Shield, RefreshCw } from 'lucide-react';
import { TitleBar } from './TitleBar';

export type DocId = 'guide' | 'eula' | 'privacy' | 'refund';

interface DocCard {
  id: DocId;
  icon: React.ReactNode;
  title: string;
  desc: string;
  badge?: string;
}

const DOCS: DocCard[] = [
  {
    id: 'guide',
    icon: <BookOpen size={28} />,
    title: 'Руководство пользователя',
    desc: 'Установка, настройка, обработка видео, экспорт результатов и FAQ.',
    badge: '10 разделов',
  },
  {
    id: 'eula',
    icon: <FileText size={28} />,
    title: 'Лицензионное соглашение',
    desc: 'Условия использования, ограничения, права и обязанности пользователя.',
    badge: 'EULA',
  },
  {
    id: 'privacy',
    icon: <Shield size={28} />,
    title: 'Политика конфиденциальности',
    desc: 'Какие данные собираются, как хранятся и защищаются.',
  },
  {
    id: 'refund',
    icon: <RefreshCw size={28} />,
    title: 'Политика возврата средств',
    desc: 'Условия и сроки возврата оплаты за лицензию.',
    badge: '7 дней',
  },
];

interface Props {
  onClose: () => void;
  onOpenDoc: (id: DocId) => void;
}

export const DocsPage: React.FC<Props> = ({ onClose, onOpenDoc }) => (
  <div className="docs-overlay">
    <TitleBar />
    <div className="docs-shell">
      <div className="docs-header">
        <button className="docs-back-btn" onClick={onClose}>
          <ArrowLeft size={16} /> Назад
        </button>
        <div className="docs-header-title">
          <BookOpen size={20} />
          <h1>Документация</h1>
        </div>
        <span />
      </div>

      <div className="docs-index-content">
        <p className="docs-index-subtitle">Выберите документ для просмотра</p>
        <div className="docs-grid">
          {DOCS.map(doc => (
            <div key={doc.id} className="docs-card" onClick={() => onOpenDoc(doc.id)}>
              <div className="docs-card-icon">{doc.icon}</div>
              <div className="docs-card-body">
                <div className="docs-card-title-row">
                  <h3 className="docs-card-title">{doc.title}</h3>
                  {doc.badge && <span className="docs-card-badge">{doc.badge}</span>}
                </div>
                <p className="docs-card-desc">{doc.desc}</p>
              </div>
              <button className="docs-card-btn">Открыть →</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  </div>
);
