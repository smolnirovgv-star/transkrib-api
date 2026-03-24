import React, { useEffect, useState } from "react";
import { X, Play, Clock, Zap, FileVideo, TrendingUp } from "lucide-react";

interface DemoModalProps {
  onClose: () => void;
}

export const DemoModal: React.FC<DemoModalProps> = ({ onClose }) => {
  const [step, setStep] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    // Auto-animate through demo stages
    const t1 = setTimeout(() => setStep(1), 400);
    const t2 = setTimeout(() => setStep(2), 1200);
    const t3 = setTimeout(() => setStep(3), 2400);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, []);

  useEffect(() => {
    if (step < 1) return;
    let val = 0;
    const target = step === 1 ? 35 : step === 2 ? 72 : 100;
    const interval = setInterval(() => {
      val = Math.min(val + 2, target);
      setProgress(val);
      if (val >= target) clearInterval(interval);
    }, 30);
    return () => clearInterval(interval);
  }, [step]);

  const stages = [
    { label: "Загрузка видео", icon: FileVideo, done: step > 0 },
    { label: "Транскрипция аудио", icon: Zap, done: step > 1 },
    { label: "Анализ контента", icon: TrendingUp, done: step > 2 },
  ];

  return (
    <div className="demo-overlay" onClick={onClose}>
      <div className="demo-card glass-card" onClick={(e) => e.stopPropagation()}>
        <div className="demo-header">
          <span className="demo-badge">Пример</span>
          <h2 className="demo-title">Как работает SmartCut AI</h2>
          <button className="btn-icon demo-close" onClick={onClose}><X size={16} /></button>
        </div>

        <div className="demo-source">
          <div className="demo-source-icon"><FileVideo size={20} /></div>
          <div className="demo-source-info">
            <span className="demo-source-name">interview_founders_2h.mp4</span>
            <span className="demo-source-size">2 ч 14 мин · 1.8 ГБ</span>
          </div>
          <div className="demo-source-arrow">→</div>
          <div className="demo-result-info">
            <span className="demo-source-name demo-result-highlight">highlights_final.mp4</span>
            <span className="demo-source-size">4 мин 30 сек · 38 МБ</span>
          </div>
        </div>

        <div className="demo-stages">
          {stages.map((s, i) => (
            <div key={i} className={"demo-stage" + (step === i + 0 && !s.done ? " demo-stage-active" : "") + (s.done ? " demo-stage-done" : "")}>
              <div className="demo-stage-icon-wrap">
                <s.icon size={16} />
              </div>
              <span className="demo-stage-label">{s.label}</span>
              {s.done && <span className="demo-stage-check">✓</span>}
            </div>
          ))}
        </div>

        <div className="demo-progress-row">
          <span className="demo-progress-label">{step < 3 ? "Обработка..." : "Готово!"}</span>
          <span className="demo-progress-pct">{progress}%</span>
        </div>
        <div className="demo-progress-track">
          <div className="demo-progress-fill" style={{ width: progress + "%" }} />
        </div>

        {step >= 3 && (
          <div className="demo-result-card">
            <div className="demo-result-thumb">
              <Play size={28} />
            </div>
            <div className="demo-stats">
              <div className="demo-stat"><Clock size={14} /><span>2 ч 14 мин → <b>4 мин 30 сек</b></span></div>
              <div className="demo-stat"><Zap size={14} /><span><b>12</b> ключевых моментов</span></div>
              <div className="demo-stat"><TrendingUp size={14} /><span>Экономия <b>97%</b> времени</span></div>
            </div>
          </div>
        )}

        <button className="btn-primary demo-cta" onClick={onClose}>
          Попробовать на своём видео
        </button>
      </div>
    </div>
  );
};
