import React from 'react';
import { Shield, AlertTriangle, Lock, Unlock, Flame, Target, ArrowDown } from 'lucide-react';

function RiskMetric({ label, value, unit, color, icon: Icon }) {
  return (
    <div style={styles.metric}>
      <div style={styles.metricHeader}>
        {Icon && <Icon size={12} color={color || 'var(--text-muted)'} />}
        <span style={styles.metricLabel}>{label}</span>
      </div>
      <span className="mono" style={{ ...styles.metricValue, color: color || 'var(--text-primary)' }}>
        {value}
        {unit && <span style={styles.metricUnit}>{unit}</span>}
      </span>
    </div>
  );
}

function RiskLevel({ value, max = 10 }) {
  const pct = Math.min((value / max) * 100, 100);
  let color = 'var(--emerald)';
  if (pct > 70) color = 'var(--rose)';
  else if (pct > 40) color = 'var(--amber)';

  return (
    <div style={styles.riskBar}>
      <div style={styles.riskBarTrack}>
        <div
          style={{
            ...styles.riskBarFill,
            width: `${pct}%`,
            background: `linear-gradient(90deg, var(--emerald), ${color})`,
          }}
        />
      </div>
    </div>
  );
}

export default function RiskMonitor({ risk, btcPrice }) {
  const {
    positionSize, leverage, stopLoss, takeProfit,
    dailyPnl, maxDrawdown, riskPerTrade,
    tiltGuard, lossStreak,
  } = risk;

  const formatMin = (sec) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="glass-card glow-cyan" style={{ height: '100%' }}>
      <div className="card-header">
        <div className="card-title">
          <Shield />
          Risk Monitor
        </div>
        <span
          className="card-badge"
          style={{
            background: maxDrawdown > 10 ? 'rgba(239,68,68,0.12)' : 'rgba(16,185,129,0.12)',
            color: maxDrawdown > 10 ? 'var(--rose)' : 'var(--emerald)',
            borderColor: maxDrawdown > 10 ? 'rgba(239,68,68,0.25)' : 'rgba(16,185,129,0.25)',
          }}
        >
          {maxDrawdown > 10 ? 'HIGH RISK' : 'NORMAL'}
        </span>
      </div>

      <div style={styles.metricsGrid}>
        <RiskMetric
          label="Position Size"
          value={positionSize.toFixed(3)}
          unit=" BTC"
          icon={Target}
        />
        <RiskMetric
          label="Leverage"
          value={`${leverage}×`}
          color={leverage > 5 ? 'var(--amber)' : 'var(--text-primary)'}
          icon={Flame}
        />
        <RiskMetric
          label="Stop Loss"
          value={`$${stopLoss.toLocaleString('en-US', { minimumFractionDigits: 0 })}`}
          color="var(--rose)"
          icon={ArrowDown}
        />
        <RiskMetric
          label="Take Profit"
          value={`$${takeProfit.toLocaleString('en-US', { minimumFractionDigits: 0 })}`}
          color="var(--emerald)"
          icon={Target}
        />
      </div>

      {/* Daily PnL bar */}
      <div style={styles.dailyPnlSection}>
        <div style={styles.dailyPnlHeader}>
          <span style={styles.metricLabel}>Daily P&L</span>
          <span className="mono" style={{
            fontSize: 'var(--text-sm)',
            fontWeight: 700,
            color: dailyPnl >= 0 ? 'var(--emerald)' : 'var(--rose)',
          }}>
            {dailyPnl >= 0 ? '+' : ''}${dailyPnl.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
        </div>
        <div style={styles.dailyPnlBar}>
          <div style={styles.dailyPnlCenter} />
          <div style={{
            position: 'absolute',
            [dailyPnl >= 0 ? 'left' : 'right']: '50%',
            width: `${Math.min(Math.abs(dailyPnl) / 10, 50)}%`,
            height: '100%',
            background: dailyPnl >= 0 ? 'var(--emerald)' : 'var(--rose)',
            borderRadius: '2px',
            transition: 'width 0.5s ease',
            opacity: 0.7,
          }} />
        </div>
      </div>

      {/* Bottom metrics */}
      <div style={styles.bottomRow}>
        <div style={styles.bottomMetric}>
          <span style={styles.metricLabel}>Max DD</span>
          <span className="mono" style={{
            ...styles.bottomValue,
            color: maxDrawdown > 10 ? 'var(--rose)' : maxDrawdown > 5 ? 'var(--amber)' : 'var(--emerald)',
          }}>
            {maxDrawdown.toFixed(1)}%
          </span>
          <RiskLevel value={maxDrawdown} max={15} />
        </div>

        <div style={styles.bottomMetric}>
          <span style={styles.metricLabel}>Risk/Trade</span>
          <span className="mono" style={styles.bottomValue}>
            {riskPerTrade.toFixed(1)}%
          </span>
        </div>

        <div style={styles.bottomMetric}>
          <span style={styles.metricLabel}>Loss Streak</span>
          <span className="mono" style={{
            ...styles.bottomValue,
            color: lossStreak >= 3 ? 'var(--rose)' : 'var(--text-primary)',
          }}>
            {lossStreak}
          </span>
        </div>
      </div>

      {/* Tilt Guard */}
      <div style={{
        ...styles.tiltGuard,
        borderColor: tiltGuard.active ? 'rgba(239,68,68,0.25)' : 'rgba(255,255,255,0.06)',
        background: tiltGuard.active ? 'rgba(239,68,68,0.06)' : 'rgba(255,255,255,0.02)',
      }}>
        {tiltGuard.active ? (
          <Lock size={13} color="var(--rose)" />
        ) : (
          <Unlock size={13} color="var(--emerald)" />
        )}
        <span style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 600,
          color: tiltGuard.active ? 'var(--rose)' : 'var(--emerald)',
        }}>
          Tilt Guard: {tiltGuard.active ? 'LOCKED' : 'OK'}
        </span>
        {tiltGuard.active && (
          <span className="mono" style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
            {formatMin(tiltGuard.cooldownSec)} remaining
          </span>
        )}
      </div>
    </div>
  );
}

const styles = {
  metricsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
    marginBottom: '16px',
  },
  metric: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  metricHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
  },
  metricLabel: {
    fontSize: 'var(--text-xs)',
    color: 'var(--text-muted)',
    fontWeight: 500,
  },
  metricValue: {
    fontSize: 'var(--text-md)',
    fontWeight: 700,
  },
  metricUnit: {
    fontSize: 'var(--text-xs)',
    opacity: 0.6,
    marginLeft: '2px',
  },
  dailyPnlSection: {
    marginBottom: '16px',
    paddingBottom: '12px',
    borderBottom: '1px solid var(--border-subtle)',
  },
  dailyPnlHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '6px',
  },
  dailyPnlBar: {
    position: 'relative',
    height: '8px',
    background: 'var(--bg-input)',
    borderRadius: '4px',
    overflow: 'hidden',
  },
  dailyPnlCenter: {
    position: 'absolute',
    left: '50%',
    top: 0,
    width: '1px',
    height: '100%',
    background: 'var(--text-dim)',
  },
  bottomRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1fr',
    gap: '12px',
    marginBottom: '12px',
  },
  bottomMetric: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  bottomValue: {
    fontSize: 'var(--text-sm)',
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  riskBar: {
    marginTop: '4px',
  },
  riskBarTrack: {
    width: '100%',
    height: '3px',
    background: 'var(--bg-input)',
    borderRadius: '2px',
    overflow: 'hidden',
  },
  riskBarFill: {
    height: '100%',
    borderRadius: '2px',
    transition: 'width 0.5s ease',
  },
  tiltGuard: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid',
    transition: 'all var(--transition-base)',
  },
};
