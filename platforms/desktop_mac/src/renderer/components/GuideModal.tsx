import React, { useState } from 'react';
import { X } from 'lucide-react';
import { useTranslation } from '../i18n';

interface Props {
  onClose: () => void;
}

type Tab = 0 | 1 | 2 | 3;

const TABS = ['guide.tabQuickStart', 'guide.tabFeatures', 'guide.tabAccount', 'guide.tabFaq'];
const ICONS = ['🚀', '⚙️', '👤', '❓'];

export const GuideModal: React.FC<Props> = ({ onClose }) => {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>(0);

  return (
    <div className="guide-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="guide-modal glass-card">
        <div className="guide-modal-header">
          <h2 className="guide-modal-title">{t('guide.title')}</h2>
          <button className="guide-modal-close btn-icon" onClick={onClose} type="button"><X size={16} /></button>
        </div>

        <div className="guide-tabs">
          {TABS.map((key, i) => (
            <button
              key={i}
              type="button"
              className={'guide-tab' + (tab === i ? ' active' : '')}
              onClick={() => setTab(i as Tab)}
            >
              {ICONS[i]} {t(key as any)}
            </button>
          ))}
        </div>

        <div className="guide-body">
          {tab === 0 && (
            <div className="guide-content">
              <div className="guide-step">
                <span className="guide-step-icon">📥</span>
                <div>
                  <p className="guide-step-title">Шаг 1: Загрузите видео</p>
                  <p className="guide-step-text">Перетащите файл или вставьте YouTube ссылку. Форматы: MP4, AVI, MOV, MKV, WebM. До 2 ГБ.</p>
                </div>
              </div>
              <div className="guide-step">
                <span className="guide-step-icon">▶️</span>
                <div>
                  <p className="guide-step-title">Шаг 2: Нажмите Обработать</p>
                  <p className="guide-step-text">Приложение транскрибирует речь, найдёт ключевые моменты и соберёт видео.</p>
                </div>
              </div>
              <div className="guide-step">
                <span className="guide-step-icon">📤</span>
                <div>
                  <p className="guide-step-title">Шаг 3: Скачайте результат</p>
                  <p className="guide-step-text">Готовое видео, субтитры (.srt) или текстовый транскрипт (.txt / .json).</p>
                </div>
              </div>
              <p className="guide-note">⏱ Время обработки: 10 мин видео ≈ 3–5 мин.</p>
            </div>
          )}

          {tab === 1 && (
            <div className="guide-content">
              {[
                ['🎬', 'Обработка видео', 'Файл или YouTube ссылка'],
                ['✂️', 'Умная нарезка', 'Только важные моменты (score ≥ 6)'],
                ['📄', 'Транскрипт', 'TXT / SRT / JSON форматы'],
                ['🖼️', 'AI превью', 'Автогенерация обложки'],
                ['📊', 'Карта сегментов', 'Визуальная шкала что вошло'],
                ['⚙️', 'Настройки', 'Скорость, длина итогового видео'],
              ].map(([icon, name, desc], i) => (
                <div key={i} className="guide-feature">
                  <span className="guide-feature-icon">{icon}</span>
                  <div>
                    <p className="guide-feature-name">{name}</p>
                    <p className="guide-feature-desc">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === 2 && (
            <div className="guide-content">
              <div className="guide-account-section">
                <p className="guide-account-head">Регистрация и вход</p>
                <p className="guide-account-text">Кнопка "Войти" → вкладка "Регистрация" → email + пароль</p>
                <p className="guide-account-text">Забыли пароль: "Войти" → "Забыл пароль" → письмо на email</p>
                <p className="guide-account-text">Смена пароля: иконка профиля → "Сменить пароль"</p>
              </div>
              <div className="guide-account-section">
                <p className="guide-account-head">Тарифы</p>
                {[
                  ['Trial', '7 дней бесплатно, 3 видео/день'],
                  ['Base', '$5 — 10 дней'],
                  ['Standard', '$19/мес — безлимит (рекомендуем)'],
                  ['Pro', '$99/год — все функции'],
                ].map(([plan, desc], i) => (
                  <div key={i} className="guide-plan">
                    <span className="guide-plan-name">{plan}</span>
                    <span className="guide-plan-desc">{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 3 && (
            <div className="guide-content">
              {[
                ['Видео долго обрабатывается?', '10 мин ≈ 3–5 мин. 60 мин ≈ 15–20 мин. Это нормально.'],
                ['Транскрипция неточная?', 'Откройте ⚙️ → выберите SLOW (модель small/medium).'],
                ['Антивирус блокирует приложение?', 'Добавьте папку Transkrib в исключения антивируса.'],
                ['Где хранятся мои видео?', 'Только на вашем компьютере: C:\Users\[Имя]\AppData\Roaming\Transkrib\storage'],
                ['Как перенести лицензию?', 'Напишите на support@transkrib.ai'],
              ].map(([q, a], i) => (
                <div key={i} className="guide-faq-item">
                  <p className="guide-faq-q">Q: {q}</p>
                  <p className="guide-faq-a">A: {a}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="guide-modal-footer">
          <button
            type="button"
            className="btn-secondary"
            disabled={tab === 0}
            onClick={() => setTab((tab - 1) as Tab)}
          >
            {t('guide.prev')}
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={tab === 3}
            onClick={() => setTab((tab + 1) as Tab)}
          >
            {t('guide.next')}
          </button>
        </div>
      </div>
    </div>
  );
};
