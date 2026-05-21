import React from 'react';
import { Brain, ArrowUp, ArrowDown, Minus, Target } from 'lucide-react';

function SignalIcon({ signal }) {
  if (signal === 1)
    return <ArrowUp size={14} color="var(--emerald)" strokeWidth={3} />;
  if (signal === -1)
    return <ArrowDown size={14} color="var(--rose)" strokeWidth={3} />;
  return <Minus size={14} color="var(--text-dim)" strokeWidth={3} />;
}

function ConfidenceBar({ value, color }) {
  return (
    <div style={styles.confBarTrack}>
      <div
        style={{
          ...styles.confBarFill,
          width: `${value}%`,
          background: color,
        }}
      />
    </div>
  );
}

function getActionColor(action) {
  switch (action) {
    case 'LONG': return 'var(--emerald)';
    case 'SHORT': return 'var(--rose)';
    default: return 'var(--amber)';
  }
}

function getActionBg(action) {
  switch (action) {
    case 'LONG': return 'rgba(16, 185, 129, 0.12)';
    case 'SHORT': return 'rgba(239, 68, 68, 0.12)';
    default: return 'rgba(245, 158, 11, 0.12)';
  }
}

function getActionBorder(action) {
  switch (action) {
    case 'LONG': return 'rgba(16, 185, 129, 0.30)';
    case 'SHORT': return 'rgba(239, 68, 68, 0.30)';
    default: return 'rgba(245, 158, 11, 0.30)';
  }
}

const SKILL_COLORS = {
  momentum: 'var(--cyan)',
  reversion: 'var(--purple)',
  volume: 'var(--amber)',
  flow: 'var(--emerald)',
  regime: 'var(--rose)',
  sentiment: '#ec4899',
};

export default function SignalPanel({ signals }) {
  const { skills = [], compositeScore = 0.0, action = 'WAIT', confidence = 0 } = signals || {};

  return (
    <div className="glass-card glow-purple" style={{ height: '100%' }}>
      <div className="card-header">
        <div className="card-title">
          <Brain />
          Signal Panel
        </div>
        <span className="card-badge">7 Skills</span>
      </div>

      {/* Composite Score & Action */}
      <div style={styles.compositeSection}>
        <div style={styles.compositeLeft}>
          <span style={styles.compositeLabel}>Composite Score</span>
          <span
            className="mono"
            style={{
              ...styles.compositeValue,
              color: compositeScore > 0 ? 'var(--emerald)' : compositeScore < 0 ? 'var(--rose)' : 'var(--amber)',
            }}
          >
            {typeof compositeScore === 'number' ? `${compositeScore > 0 ? '+' : ''}${compositeScore.toFixed(1)}` : '0.0'}
          </span>
        </div>

        <div style={{
          ...styles.actionBadge,
          color: getActionColor(action),
          background: getActionBg(action),
          borderColor: getActionBorder(action),
          boxShadow: `0 0 15px ${getActionBg(action)}`,
        }}>
          <Target size={14} />
          {action}
        </div>
      </div>

      {/* Confidence Arc */}
      <div style={styles.confidenceRow}>
        <span style={styles.confLabel}>Confidence</span>
        <div style={styles.confGauge}>
          <div style={styles.confGaugeTrack}>
            <div
              style={{
                ...styles.confGaugeFill,
                width: `${confidence || 0}%`,
                background: (confidence || 0) > 70
                  ? 'var(--emerald)' : (confidence || 0) > 40
                    ? 'var(--amber)' : 'var(--rose)',
              }}
            />
          </div>
          <span className="mono" style={styles.confValue}>{confidence || 0}%</span>
        </div>
      </div>

      {/* Skills list */}
      <div style={styles.skillList}>
        {skills.map((skill) => (
          <div key={skill.id} style={styles.skillRow}>
            <div style={styles.skillInfo}>
              <span style={{
                ...styles.skillNum,
                color: SKILL_COLORS[skill.category] || 'var(--text-muted)',
              }}>
                S{skill.id}
              </span>
              <span style={styles.skillName}>{skill.name}</span>
            </div>

            <div style={styles.skillSignal}>
              <SignalIcon signal={skill.signal} />
            </div>

            <div style={styles.skillMeta}>
              <span className="mono" style={styles.skillWeight}>{typeof skill.weight === 'number' ? `${skill.weight.toFixed(1)}%` : '0.0%'}</span>
              <ConfidenceBar
                value={skill.confidence || 0}
                color={SKILL_COLORS[skill.category] || 'var(--cyan)'}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const styles = {
  compositeSection: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '16px',
  },
  compositeLeft: {
    display: 'flex',
    flexDirection: 'column',
  },
  compositeLabel: {
    fontSize: 'var(--text-xs)',
    color: 'var(--text-muted)',
    fontWeight: 500,
  },
  compositeValue: {
    fontSize: 'var(--text-3xl)',
    fontWeight: 800,
    letterSpacing: '-0.03em',
    lineHeight: 1.1,
  },
  actionBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: 'var(--text-sm)',
    fontWeight: 700,
    padding: '8px 18px',
    borderRadius: '10px',
    border: '1px solid',
    letterSpacing: '0.06em',
    animation: 'breathe 2.5s ease-in-out infinite',
  },
  confidenceRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '12px',
    marginBottom: '16px',
    paddingBottom: '12px',
    borderBottom: '1px solid var(--border-subtle)',
  },
  confLabel: {
    fontSize: 'var(--text-xs)',
    color: 'var(--text-muted)',
    fontWeight: 500,
    whiteSpace: 'nowrap',
  },
  confGauge: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    flex: 1,
  },
  confGaugeTrack: {
    flex: 1,
    height: '6px',
    background: 'var(--bg-input)',
    borderRadius: '3px',
    overflow: 'hidden',
  },
  confGaugeFill: {
    height: '100%',
    borderRadius: '3px',
    transition: 'width 0.6s ease, background 0.3s ease',
  },
  confValue: {
    fontSize: 'var(--text-xs)',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    minWidth: '32px',
    textAlign: 'right',
  },
  skillList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  skillRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '6px 8px',
    borderRadius: 'var(--radius-sm)',
    transition: 'background var(--transition-fast)',
    cursor: 'default',
  },
  skillInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    minWidth: '120px',
  },
  skillNum: {
    fontSize: 'var(--text-xs)',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    opacity: 0.8,
  },
  skillName: {
    fontSize: 'var(--text-xs)',
    color: 'var(--text-secondary)',
    fontWeight: 500,
  },
  skillSignal: {
    width: '24px',
    display: 'flex',
    justifyContent: 'center',
  },
  skillMeta: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  skillWeight: {
    fontSize: '10px',
    color: 'var(--text-muted)',
    minWidth: '34px',
    textAlign: 'right',
  },
  confBarTrack: {
    flex: 1,
    height: '3px',
    background: 'var(--bg-input)',
    borderRadius: '2px',
    overflow: 'hidden',
  },
  confBarFill: {
    height: '100%',
    borderRadius: '2px',
    transition: 'width 0.5s ease',
    opacity: 0.7,
  },
};
