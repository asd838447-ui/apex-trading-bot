import React from 'react';
import EquityCurve from './EquityCurve';
import SignalPanel from './SignalPanel';
import SkillWeights from './SkillWeights';
import RegimeIndicator from './RegimeIndicator';
import RiskMonitor from './RiskMonitor';
import TradeHistory from './TradeHistory';

export default function Dashboard({ equityCurve, tradeHistory, signals, risk, regime, btcPrice }) {
  return (
    <div className="dashboard-grid stagger">
      {/* Row 1: Equity (wide) + Signals (narrow) */}
      <div className="span-2 animate-slideUp">
        <EquityCurve data={equityCurve} />
      </div>
      <div className="animate-slideUp">
        <SignalPanel signals={signals} />
      </div>

      {/* Row 2: SkillWeights, RegimeIndicator, RiskMonitor */}
      <div className="animate-slideUp">
        <SkillWeights signals={signals} />
      </div>
      <div className="animate-slideUp">
        <RegimeIndicator regime={regime} />
      </div>
      <div className="animate-slideUp">
        <RiskMonitor risk={risk} btcPrice={btcPrice} />
      </div>

      {/* Row 3: Trade History (full width) */}
      <div className="span-3 animate-slideUp">
        <TradeHistory trades={tradeHistory} />
      </div>
    </div>
  );
}
