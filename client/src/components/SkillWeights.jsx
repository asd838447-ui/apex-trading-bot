import React, { useMemo } from 'react';
import { BarChart3, Clock } from 'lucide-react';
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Radar, ResponsiveContainer, Tooltip,
} from 'recharts';

const SKILL_COLORS = [
  '#00d4ff', // S1 cyan
  '#8b5cf6', // S2 purple
  '#10b981', // S3 emerald
  '#f59e0b', // S4 amber
  '#ec4899', // S5 pink
  '#ef4444', // S6 rose
  '#06b6d4', // S7 teal
];

function BarRow({ skill, index, maxWeight }) {
  const pct = maxWeight > 0 ? (skill.weight / maxWeight) * 100 : 0;
  const color = SKILL_COLORS[index % SKILL_COLORS.length];

  return (
    <div style={styles.barRow}>
      <div style={styles.barLabel}>
        <span style={{ ...styles.barDot, background: color }} />
        <span style={styles.barName}>S{skill.id}</span>
      </div>
      <div style={styles.barTrack}>
        <div
          style={{
            ...styles.barFill,
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${color}80, ${color})`,
          }}
        />
      </div>
      <span className="mono" style={styles.barValue}>{typeof skill.weight === 'number' ? `${skill.weight.toFixed(1)}%` : '0.0%'}</span>
      <span className="mono" style={{
        ...styles.barAccuracy,
        color: (skill.accuracy || 0) >= 70 ? 'var(--emerald)' : (skill.accuracy || 0) >= 55 ? 'var(--amber)' : 'var(--rose)',
      }}>
        {typeof skill.accuracy === 'number' ? `${skill.accuracy.toFixed(0)}%` : '0%'}
      </span>
    </div>
  );
}

function RadarTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="custom-tooltip">
      <div className="label">{d.name}</div>
      <div className="value">Weight: {d.weight.toFixed(1)}%</div>
    </div>
  );
}

export default function SkillWeights({ signals }) {
  const { skills = [] } = signals || {};

  const maxWeight = useMemo(() => Math.max(...skills.map((s) => s.weight || 0), 1), [skills]);

  const radarData = useMemo(() => {
    return skills.map((s) => ({
      name: `S${s.id}`,
      fullName: s.name,
      weight: s.weight,
      accuracy: s.accuracy,
    }));
  }, [skills]);

  const lastUpdate = useMemo(() => {
    return new Date().toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }, [skills]);

  return (
    <div className="glass-card glow-purple" style={{ height: '100%' }}>
      <div className="card-header">
        <div className="card-title">
          <BarChart3 />
          Skill Weights
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Clock size={10} color="var(--text-dim)" />
          <span className="mono" style={{ fontSize: '10px', color: 'var(--text-dim)' }}>
            {lastUpdate}
          </span>
        </div>
      </div>

      {/* Radar chart */}
      <div style={{ height: '170px', marginBottom: '12px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
            <PolarGrid
              stroke="rgba(255,255,255,0.06)"
              strokeDasharray="3 3"
            />
            <PolarAngleAxis
              dataKey="name"
              tick={{
                fill: '#94a3b8',
                fontSize: 10,
                fontFamily: 'JetBrains Mono',
                fontWeight: 600,
              }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, Math.ceil(maxWeight * 1.2)]}
              tick={false}
              axisLine={false}
            />
            <Tooltip content={<RadarTooltip />} />
            <Radar
              name="Weight"
              dataKey="weight"
              stroke="#00d4ff"
              fill="#00d4ff"
              fillOpacity={0.15}
              strokeWidth={2}
              animationDuration={600}
              dot={{
                r: 3,
                fill: '#00d4ff',
                stroke: '#0a0e17',
                strokeWidth: 2,
              }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Bar breakdown */}
      <div style={styles.barHeader}>
        <span style={{ flex: 1 }}>Skill</span>
        <span style={{ width: '44px', textAlign: 'right' }}>Weight</span>
        <span style={{ width: '36px', textAlign: 'right' }}>Acc</span>
      </div>
      <div style={styles.barList}>
        {skills.map((skill, idx) => (
          <BarRow key={skill.id} skill={skill} index={idx} maxWeight={maxWeight} />
        ))}
      </div>
    </div>
  );
}

const styles = {
  barHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '10px',
    fontWeight: 600,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    paddingBottom: '6px',
    borderBottom: '1px solid var(--border-subtle)',
    marginBottom: '4px',
    padding: '0 4px 6px 4px',
  },
  barList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '3px',
  },
  barRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '4px',
    borderRadius: '4px',
    transition: 'background var(--transition-fast)',
  },
  barLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    minWidth: '34px',
  },
  barDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  barName: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 600,
    color: 'var(--text-secondary)',
  },
  barTrack: {
    flex: 1,
    height: '4px',
    background: 'var(--bg-input)',
    borderRadius: '2px',
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    borderRadius: '2px',
    transition: 'width 0.5s ease',
  },
  barValue: {
    fontSize: '10px',
    color: 'var(--text-muted)',
    width: '44px',
    textAlign: 'right',
  },
  barAccuracy: {
    fontSize: '10px',
    fontWeight: 600,
    width: '36px',
    textAlign: 'right',
  },
};
