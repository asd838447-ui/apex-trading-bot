import React, { useMemo } from 'react';
import { Compass, TrendingUp, Minus, Zap } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';

const REGIME_CONFIG = {
  TREND: {
    color: 'var(--emerald)',
    bg: 'rgba(16, 185, 129, 0.12)',
    border: 'rgba(16, 185, 129, 0.30)',
    glow: '0 0 30px rgba(16, 185, 129, 0.15)',
    icon: TrendingUp,
    description: 'Directional move detected',
  },
  FLAT: {
    color: 'var(--amber)',
    bg: 'rgba(245, 158, 11, 0.12)',
    border: 'rgba(245, 158, 11, 0.30)',
    glow: '0 0 30px rgba(245, 158, 11, 0.15)',
    icon: Minus,
    description: 'Range-bound market',
  },
  VOLATILE: {
    color: 'var(--rose)',
    bg: 'rgba(239, 68, 68, 0.12)',
    border: 'rgba(239, 68, 68, 0.30)',
    glow: '0 0 30px rgba(239, 68, 68, 0.15)',
    icon: Zap,
    description: 'High volatility detected',
  },
};

const REGIME_NUM = { TREND: 3, FLAT: 1, VOLATILE: 2 };
const REGIME_COLORS_RAW = { TREND: '#10b981', FLAT: '#f59e0b', VOLATILE: '#ef4444' };

function RegimeTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="custom-tooltip">
      <div className="label">{new Date(d.time).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })}</div>
      <div className="value" style={{ color: REGIME_COLORS_RAW[d.regime] }}>{d.regime}</div>
    </div>
  );
}

export default function RegimeIndicator({ regime }) {
  const { current = 'FLAT', confidence = 0, history = [] } = regime || {};
  const config = REGIME_CONFIG[current] || REGIME_CONFIG.FLAT;
  const IconComponent = config.icon;

  const chartData = useMemo(() => {
    return history.map((h) => ({
      ...h,
      value: REGIME_NUM[h.regime] || 1,
      hour: new Date(h.time).getHours() + ':00',
    }));
  }, [history]);

  return (
    <div className="glass-card glow-emerald" style={{ height: '100%' }}>
      <div className="card-header">
        <div className="card-title">
          <Compass />
          Market Regime
        </div>
        <span className="card-badge" style={{
          background: config.bg,
          color: config.color,
          borderColor: config.border,
        }}>
          LIVE
        </span>
      </div>

      {/* Current Regime Display */}
      <div style={{
        ...styles.regimeDisplay,
        background: config.bg,
        border: `1px solid ${config.border}`,
        boxShadow: config.glow,
      }}>
        <IconComponent size={28} color={config.color} />
        <div>
          <div className="mono" style={{
            fontSize: 'var(--text-2xl)',
            fontWeight: 800,
            color: config.color,
            letterSpacing: '0.04em',
            lineHeight: 1.1,
          }}>
            {current}
          </div>
          <div style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--text-muted)',
            marginTop: '2px',
          }}>
            {config.description}
          </div>
        </div>
      </div>

      {/* Confidence */}
      <div style={styles.confidenceSection}>
        <div style={styles.confHeader}>
          <span style={styles.confLabel}>Regime Confidence</span>
          <span className="mono" style={{
            fontSize: 'var(--text-sm)',
            fontWeight: 700,
            color: config.color,
          }}>
            {typeof confidence === 'number' ? confidence.toFixed(1) : '0.0'}%
          </span>
        </div>
        <div style={styles.confTrack}>
          <div style={{
            ...styles.confFill,
            width: `${confidence || 0}%`,
            background: `linear-gradient(90deg, ${config.color}99, ${config.color})`,
          }} />
        </div>
      </div>

      {/* Regime History Mini-Chart */}
      <div style={styles.chartSection}>
        <span style={styles.chartLabel}>24h Regime History</span>
        <div style={{ height: '70px', marginTop: '6px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
              <XAxis dataKey="hour" hide />
              <YAxis domain={[0, 4]} hide />
              <Tooltip content={<RegimeTooltip />} cursor={false} />
              <Bar dataKey="value" radius={[2, 2, 0, 0]} barSize={8}>
                {chartData.map((entry, idx) => (
                  <Cell
                    key={idx}
                    fill={REGIME_COLORS_RAW[entry.regime] || 'var(--text-muted)'}
                    fillOpacity={0.6}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

const styles = {
  regimeDisplay: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
    padding: '16px 20px',
    borderRadius: 'var(--radius-md)',
    marginBottom: '16px',
    transition: 'all 0.5s ease',
  },
  confidenceSection: {
    marginBottom: '16px',
  },
  confHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '6px',
  },
  confLabel: {
    fontSize: 'var(--text-xs)',
    color: 'var(--text-muted)',
    fontWeight: 500,
  },
  confTrack: {
    width: '100%',
    height: '5px',
    background: 'var(--bg-input)',
    borderRadius: '3px',
    overflow: 'hidden',
  },
  confFill: {
    height: '100%',
    borderRadius: '3px',
    transition: 'width 0.6s ease',
  },
  chartSection: {
    paddingTop: '12px',
    borderTop: '1px solid var(--border-subtle)',
  },
  chartLabel: {
    fontSize: 'var(--text-xs)',
    color: 'var(--text-muted)',
    fontWeight: 500,
  },
};
