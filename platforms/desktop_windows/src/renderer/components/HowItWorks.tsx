import React from 'react';

const steps = [
  { num: 1, icon: '📥', title: 'Загрузите видео', desc: 'Перетащите файл или вставьте YouTube ссылку' },
  { num: 2, icon: '🎙️', title: 'AI Анализ', desc: 'Нейросеть определяет ключевые моменты' },
  { num: 3, icon: '✂️', title: 'Умная нарезка', desc: 'Автоматическое создание highlights' },
  { num: 4, icon: '📝', title: 'Транскрипция', desc: 'Whisper распознаёт речь с высокой точностью' },
  { num: 5, icon: '⬇️', title: 'Скачайте результат', desc: 'Готовое видео, субтитры и транскрипт' },
  { num: 6, icon: '🔄', title: 'Переобработка', desc: 'Уточните ТЗ и получите новый вариант' },
];

export const HowItWorks: React.FC = () => {
  return (
    <div className='how-section'>
      <div className='how-header'>
        <span className='how-label'>ПРОЦЕСС</span>
        <h2 className='how-title'>Как это работает</h2>
      </div>
      <div className='how-it-works-grid'>
        {steps.map((step, i) => (
          <React.Fragment key={step.num}>
            <div className='how-card'>
              <div className='how-card-icon'>{step.icon}</div>
              <div className='how-card-num'>ШАГ {step.num}</div>
              <h3 className='how-card-title'>{step.title}</h3>
              <p className='how-card-desc'>{step.desc}</p>
            </div>
            {i < steps.length - 1 && i % 3 !== 2 && (
              <div className='how-connector'>→</div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
