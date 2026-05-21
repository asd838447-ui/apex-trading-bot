import React, { useState, useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';

const RANGES = [
  { label: '1D', days: 1 },
  { label: '1W', days: 7 },
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: 'All', days: Infinity },
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="custom-tooltip">
      <div className="label">{label}</div>
      <div className="value">${payload[0].value.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
    </div>
  );
}

export default function EquityCurve({ data }) {
  const [selectedRange, setSelectedRange] = useState('3M');

  const filtered = useMemo(() => {
    const range = RANGES.find((r) => r.label === selectedRange);
    if (!range || range.days === Infinity) return data;
    return data.slice(-range.days);
  }, [data, selectedRange]);

  const currentEquity = filtered.length ? filtered[filtered.length - 1].equity : 0;
  const startEquity = filtered.length ? filtered[0].equity : 0;
  const pnl = currentEquity - startEquity;
  const pnlPct = startEquity ? ((pnl / startEquity) * 100) : 0;
  const isPositive = pnl >= 0;

  return (
    <div className="glass-card glow-cyan" style={{ height: '100%' }}>
      <div className="card-header">
        <div className="card-title">
          <TrendingUp />
          Equity Curve
        </div>
        <div className="btn-group">
          {RANGES.map((r) => (
            <button
              key={r.label}
              className={`btn ${selectedRange === r.label ? 'active' : ''}`}
              onClick={() => setSelectedRange(r.label)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats row */}
      <div style={styles.statsRow}>
        <div>
          <span style={styles.statLabel}>Current Equity</span>
          <span className="mono" style={styles.statValue}>
            ${currentEquity.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </span>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span style={styles.statLabel}>P&L ({selectedRange})</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'flex-end' }}>
            {isPositive ? (
              <TrendingUp size={14} color="var(--emerald)" />
            ) : (
              <TrendingDown size={14} color="var(--rose)" />
            )}
            <span
              className="mono"
              style={{
                ...styles.pnlValue,
                color: isPositive ? 'var(--emerald)' : 'var(--rose)',
              }}
            >
              {isPositive ? '+' : ''}{pnlPct.toFixed(2)}%
              <span style={styles.pnlDollar}>
                ({isPositive ? '+' : ''}${Math.abs(pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })})
              </span>
            </span>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="chart-container" style={{ height: '240px', marginTop: '12px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={filtered} margin={{ top: 5, right: 5, left: 5, bottom: 0 }}>
            <defs>
              <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity={0.30} />
                <stop offset="50%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity={0.08} />
                <stop offset="100%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="equityLine" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity={0.6} />
                <stop offset="50%" stopColor={isPositive ? '#00d4ff' : '#ef4444'} stopOpacity={1} />
                <stop offset="100%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity={0.8} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="date"
              tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'JetBrains Mono' }}
              axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={60}
            />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'JetBrains Mono' }}
              axisLine={false}
              tickLine={false}
              domain={['auto', 'auto']}
              tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
              width={52}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="equity"
              stroke="url(#equityLine)"
              strokeWidth={2}
              fill="url(#equityGradient)"
              animationDuration={800}
              dot={false}
              activeDot={{
                r: 4,
                stroke: 'var(--cyan)',
                strokeWidth: 2,
                fill: 'var(--bg-primary)',
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

const styles = {
  statsRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  statLabel: {
    display: 'block',
    fontSize: 'var(--text-xs)',
    color: 'var(--text-muted)',
    marginBottom: '2px',
    fontWeight: 500,
  },
  statValue: {
    fontSize: 'var(--text-2xl)',
    fontWeight: 700,
    color: 'var(--text-primary)',
    letterSpacing: '-0.02em',
  },
  pnlValue: {
    fontSize: 'var(--text-md)',
    fontWeight: 700,
  },
  pnlDollar: {
    fontSize: 'var(--text-xs)',
    opacity: 0.7,
    marginLeft: '4px',
    fontWeight: 500,
  },
};
