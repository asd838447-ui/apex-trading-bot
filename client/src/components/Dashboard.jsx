import React, { Suspense, lazy } from 'react';
import SignalPanel from './SignalPanel';
import SkillWeights from './SkillWeights';
import RegimeIndicator from './RegimeIndicator';

// Lazy loaded components for code splitting
const EquityCurve = lazy(() => import('./EquityCurve'));
const RiskMonitor = lazy(() => import('./RiskMonitor'));
const TradeHistory = lazy(() => import('./TradeHistory'));
const QuantAlphas = lazy(() => import('./QuantAlphas'));
const ChatWidget = lazy(() => import('./ChatWidget'));

function DashboardLoader() {
  return (
    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px' }}>
      <span style={{ color: 'var(--text-muted)' }}>Loading module...</span>
    </div>
  );
}

export default function Dashboard({ 
  selectedSymbol, 
  setSelectedSymbol, 
  multiSignals, 
  multiRisks, 
  multiRegimes, 
  multiQuantAlphas = {},
  prices, 
  equityCurve, 
  tradeHistory 
}) {
  const currentPrice = prices[selectedSymbol] || 0.0;
  const currentSignals = multiSignals[selectedSymbol] || { skills: [], compositeScore: 0.0, action: 'WAIT', confidence: 0 };
  const currentRisk = multiRisks[selectedSymbol] || { positionSize: 0.0, leverage: 5, stopLoss: 0.0, takeProfit: 0.0, dailyPnl: 0.0, maxDrawdown: 3.0, riskPerTrade: 1.0, tiltGuard: { active: false, cooldownSec: 0, consecutiveLosses: 0, dailyStops: 0 }, lossStreak: 0 };
  const currentRegime = multiRegimes[selectedSymbol] || { current: 'FLAT', confidence: 100.0, history: [] };
  const currentQuantAlphas = multiQuantAlphas[selectedSymbol] || { obi: 0.0, funding_divergence: 0.0 };

  const tabs = [
    { id: 'BTCUSDT', label: 'BTC / Биткоин', icon: '₿' },
    { id: 'ETHUSDT', label: 'ETH / Эфириум', icon: 'Ξ' },
    { id: 'SOLUSDT', label: 'SOL / Солана', icon: '☼' },
    { id: 'HYPEUSDT', label: 'HYPE / Гипер', icon: '⚡' },
    { id: 'TONUSDT', label: 'TON / Тон', icon: '💎' }
  ];

  return (
    <main className="flex flex-col gap-lg">
      {/* Premium Multi-Asset Tabs */}
      <div className="tabs-container animate-slideUp">
        {tabs.map((tab) => {
          const isActive = selectedSymbol === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setSelectedSymbol(tab.id)}
              className={`tab-btn ${isActive ? 'active' : ''}`}
            >
              <span style={{ fontSize: '1.1rem' }}>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      <div className="dashboard-grid stagger">
        {/* Row 1: Equity (wide) + Signals (narrow) */}
        <div className="span-2 animate-slideUp">
          <Suspense fallback={<DashboardLoader />}>
            <EquityCurve data={equityCurve} />
          </Suspense>
        </div>
        <div className="animate-slideUp">
          <SignalPanel signals={currentSignals} />
        </div>

        {/* Row 2: SkillWeights, RegimeIndicator, RiskMonitor */}
        <div className="animate-slideUp">
          <SkillWeights signals={currentSignals} />
        </div>
        <div className="animate-slideUp">
          <RegimeIndicator regime={currentRegime} />
        </div>
        <div className="animate-slideUp">
          <Suspense fallback={<DashboardLoader />}>
            <RiskMonitor risk={currentRisk} btcPrice={currentPrice} />
          </Suspense>
        </div>

        {/* Row 3: Trade History (span-2) + QuantAlphas (span-1) */}
        <div className="span-2 animate-slideUp">
          <Suspense fallback={<DashboardLoader />}>
            <TradeHistory trades={tradeHistory} />
          </Suspense>
        </div>
        <div className="animate-slideUp">
          <Suspense fallback={<DashboardLoader />}>
            <QuantAlphas metrics={currentQuantAlphas} symbol={selectedSymbol} />
          </Suspense>
        </div>
      </div>

      <Suspense fallback={null}>
        <ChatWidget />
      </Suspense>
    </main>
  );
}
