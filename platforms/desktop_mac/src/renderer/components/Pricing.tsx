import React from 'react';
import { useTranslation } from '../i18n';

interface Props {
  onSelect?: (planId: string) => void;
}

export const Pricing: React.FC<Props> = ({ onSelect }) => {
  const { t } = useTranslation();

  const PLANS = [
    {
      id: 'trial',
      name: t('pricing.trialName'),
      price: t('pricing.free'),
      period: '',
      days: t('pricing.trialDays'),
      videosPerDay: t('pricing.trialVideos'),
      maxDuration: t('pricing.trialDuration'),
      color: '#64748B',
      btnLabel: t('pricing.trialBtn'),
      features: [t('pricing.trialF1'), t('pricing.trialF2'), t('pricing.trialF3'), t('pricing.trialF4')],
    },
    {
      id: 'basic',
      name: t('pricing.basicName'),
      price: '400₽',
      period: '',
      days: t('pricing.basicDays'),
      videosPerDay: t('pricing.basicVideos'),
      maxDuration: t('pricing.basicDuration'),
      color: '#3B82F6',
      btnLabel: t('pricing.basicBtn'),
      features: [t('pricing.basicF1'), t('pricing.basicF2'), t('pricing.basicF3'), t('pricing.basicF4')],
    },
    {
      id: 'standard',
      name: t('pricing.standardName'),
      price: '1 520₽',
      period: t('pricing.perMonth'),
      days: t('pricing.standardDays'),
      videosPerDay: t('pricing.standardVideos'),
      maxDuration: t('pricing.standardDuration'),
      color: '#8B5CF6',
      recommended: true,
      btnLabel: t('pricing.standardBtn'),
      features: [t('pricing.standardF1'), t('pricing.standardF2'), t('pricing.standardF3'), t('pricing.standardF4')],
    },
    {
      id: 'pro',
      name: t('pricing.proName'),
      price: '7 920₽',
      period: t('pricing.perYear'),
      days: t('pricing.proDays'),
      videosPerDay: t('pricing.proVideos'),
      maxDuration: t('pricing.proDuration'),
      color: '#F59E0B',
      btnLabel: t('pricing.proBtn'),
      saving: t('pricing.proSaving'),
      features: [t('pricing.proF1'), t('pricing.proF2'), t('pricing.proF3'), t('pricing.proF4')],
    },
  ];

  return (
    <div className="pricing-section">
      <p className="pricing-eyebrow">{t('pricing.eyebrow')}</p>
      <h2 className="pricing-title">{t('pricing.title')}</h2>
      <p className="pricing-subtitle">{t('pricing.subtitle')}</p>
      <div className="pricing-cards">
        {PLANS.map(plan => (
          <div
            key={plan.id}
            className={'pricing-card' + ((plan as any).recommended ? ' pricing-card-recommended' : '')}
            style={{ '--plan-color': plan.color } as React.CSSProperties}
          >
            {(plan as any).recommended && (
              <div className="pricing-badge">{t('pricing.recommended')}</div>
            )}
            <div className="pricing-card-header">
              <p className="pricing-plan-name">{plan.name}</p>
              <div className="pricing-price">
                <span className="pricing-price-amount">{plan.price}</span>
                {plan.period && <span className="pricing-price-period">{plan.period}</span>}
              </div>
            </div>
            <div className="pricing-card-stats">
              <div className="pricing-stat"><span className="pricing-stat-icon">📅</span><span>{plan.days}</span></div>
              <div className="pricing-stat"><span className="pricing-stat-icon">🎬</span><span>{plan.videosPerDay}</span></div>
              <div className="pricing-stat"><span className="pricing-stat-icon">⏱</span><span>{plan.maxDuration}</span></div>
            </div>
            <ul className="pricing-features">
              {plan.features.map((f, i) => (
                <li key={i} className="pricing-feature">
                  <span className="pricing-feature-check">✓</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            {(plan as any).saving && (
              <p className="pricing-saving">{(plan as any).saving}</p>
            )}
            <button
              className={'pricing-cta' + ((plan as any).recommended ? ' pricing-cta-recommended' : '')}
              onClick={() => onSelect?.(plan.id)}
            >
              {plan.btnLabel}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
