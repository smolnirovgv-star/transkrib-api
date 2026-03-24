import React from 'react';
import { ArrowLeft, Shield } from 'lucide-react';

interface Props {
  onClose: () => void;
}

const SECTIONS = [
  {
    num: '1',
    title: 'Общие положения',
    content: `Настоящая Политика конфиденциальности описывает, как приложение Transkrib SmartCut AI собирает, использует и защищает данные пользователей.\n\nИспользуя Приложение, вы соглашаетесь с условиями настоящей Политики. Если вы не согласны с какими-либо положениями — прекратите использование Приложения.\n\nПриложение разработано для операционной системы Windows и предназначено для автоматической обработки видеозаписей с использованием технологий искусственного интеллекта.`,
  },
  {
    num: '2',
    title: 'Какие данные мы собираем',
    subsections: [
      {
        title: '2.1 Данные аккаунта (при регистрации)',
        items: ['Адрес электронной почты', 'Хэш пароля (никогда не хранится в открытом виде)', 'Дата регистрации и последнего входа'],
      },
      {
        title: '2.2 Лицензионные данные',
        items: ['Лицензионный ключ активации (формат TRSK-*)', 'Статус лицензии (тип плана, дата активации, срок действия)', 'Hardware fingerprint устройства (для привязки лицензии к машине)'],
      },
      {
        title: '2.3 Данные обработки (только локально)',
        items: ['Загружаемые видеофайлы — обрабатываются исключительно на вашем компьютере', 'Транскрипции речи — генерируются локально через Whisper AI', 'Результирующие видеофайлы — сохраняются только на вашем компьютере'],
      },
    ],
  },
  {
    num: '3',
    title: 'Как мы используем данные',
    table: [
      ['Email и пароль', 'Аутентификация и управление аккаунтом'],
      ['Лицензионный ключ', 'Проверка права использования Приложения'],
      ['Hardware fingerprint', 'Защита от несанкционированного копирования лицензии'],
      ['Транскрипция (текст)', 'Анализ ключевых моментов через Claude API'],
      ['Журналы ошибок', 'Диагностика и устранение технических проблем'],
    ],
    note: 'Мы НЕ используем ваши данные для таргетированной рекламы, продажи третьим лицам, обучения AI-моделей на ваших материалах или аналитики поведения без согласия.',
  },
  {
    num: '4',
    title: 'Передача данных третьим лицам',
    subsections: [
      { title: 'Supabase (аутентификация)', items: ['Передаётся: email, хэш пароля, данные лицензии', 'Цель: хранение аккаунта и управление сессиями'] },
      { title: 'Anthropic Claude API (анализ текста)', items: ['Передаётся: только текст транскрипции (не видеофайл)', 'Цель: определение ключевых моментов и оценка важности фраз'] },
      { title: 'Stability AI (генерация превью)', items: ['Передаётся: короткий текстовый фрагмент (до 200 символов)', 'Используется: только если задан ключ API в настройках'] },
    ],
  },
  {
    num: '5',
    title: 'Локальная обработка данных',
    highlight: 'Все видеофайлы обрабатываются локально на вашем компьютере.',
    items: [
      'Загруженные видеофайлы никогда не покидают ваш компьютер',
      'Транскрипция речи выполняется локально через встроенную модель Whisper AI',
      'Нарезка и монтаж видео выполняется локально через FFmpeg',
      'Готовые видеоролики сохраняются только на вашем устройстве',
    ],
  },
  {
    num: '6',
    title: 'Хранение и защита данных',
    items: [
      'Видео, транскрипты, результаты: %APPDATA%\\Transkrib\\storage\\',
      'Лицензионный ключ: %APPDATA%\\Transkrib\\storage\\.license\\license.key',
      'Облачные данные аккаунта хранятся на серверах Supabase (регион: EU West)',
      'Передача данных защищена протоколом TLS 1.3',
      'Пароли хранятся в виде bcrypt-хэша',
    ],
  },
  {
    num: '7',
    title: 'Права пользователя (GDPR)',
    items: [
      'Право на доступ — запросить, какие данные о вас хранятся',
      'Право на исправление — исправить неточные персональные данные',
      'Право на удаление — запросить удаление вашего аккаунта и данных',
      'Право на ограничение обработки — ограничить использование ваших данных',
      'Право на переносимость — получить ваши данные в машиночитаемом формате',
    ],
    note: 'Для реализации прав напишите нам: support@transkrib.ai. Срок ответа — 30 календарных дней.',
  },
  {
    num: '9',
    title: 'Дети и несовершеннолетние',
    content: 'Приложение не предназначено для использования лицами младше 16 лет. Мы сознательно не собираем персональные данные детей.',
  },
  {
    num: '10',
    title: 'Изменения в политике',
    content: 'Мы оставляем за собой право обновлять настоящую Политику конфиденциальности. При существенных изменениях уведомим вас при запуске приложения или на email.',
  },
  {
    num: '11',
    title: 'Контакты',
    content: 'По всем вопросам конфиденциальности и защиты данных:\n\nEmail: support@transkrib.ai\nМы стараемся отвечать в течение 3 рабочих дней.',
  },
];

export const PrivacyPolicy: React.FC<Props> = ({ onClose }) => {
  return (
    <div className="privacy-overlay">
      <div className="privacy-header">
        <button className="back-btn" onClick={onClose}>
          <ArrowLeft size={16} /> Назад
        </button>
        <div className="privacy-header-title">
          <Shield size={18} className="privacy-shield-icon" />
          <span>Политика конфиденциальности</span>
        </div>
        <div className="privacy-header-date">Обновлено: 14 марта 2026 г.</div>
      </div>

      <div className="privacy-body">
        <div className="privacy-hero">
          <div className="privacy-hero-icon">
            <Shield size={40} />
          </div>
          <h1 className="privacy-hero-title">Политика конфиденциальности</h1>
          <p className="privacy-hero-sub">Transkrib SmartCut AI · Дата вступления в силу: 14 марта 2026 г.</p>
        </div>

        <div className="privacy-sections">
          {SECTIONS.map((s) => (
            <div key={s.num} className="privacy-section">
              <div className="privacy-section-header">
                <span className="privacy-section-num">{s.num}</span>
                <h2 className="privacy-section-title">{s.title}</h2>
              </div>

              {'highlight' in s && s.highlight && (
                <div className="privacy-highlight">{s.highlight}</div>
              )}

              {'content' in s && s.content && (
                <p className="privacy-text">{s.content}</p>
              )}

              {'items' in s && s.items && (
                <ul className="privacy-list">
                  {s.items.map((item, i) => <li key={i}>{item}</li>)}
                </ul>
              )}

              {'subsections' in s && s.subsections && s.subsections.map((sub, i) => (
                <div key={i} className="privacy-subsection">
                  <h3 className="privacy-subsection-title">{sub.title}</h3>
                  <ul className="privacy-list">
                    {sub.items.map((item, j) => <li key={j}>{item}</li>)}
                  </ul>
                </div>
              ))}

              {'table' in s && s.table && (
                <div className="privacy-table-wrap">
                  <table className="privacy-table">
                    <thead>
                      <tr><th>Данные</th><th>Цель использования</th></tr>
                    </thead>
                    <tbody>
                      {s.table.map(([col1, col2], i) => (
                        <tr key={i}><td>{col1}</td><td>{col2}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {'note' in s && s.note && (
                <p className="privacy-note">{s.note}</p>
              )}
            </div>
          ))}
        </div>

        <div className="privacy-footer">
          <Shield size={16} />
          <span>© 2026 Transkrib SmartCut AI. Все права защищены.</span>
        </div>
      </div>
    </div>
  );
};
