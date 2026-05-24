import React, { useState, useEffect, useRef } from 'react';
import { Activity, Wifi, WifiOff, Zap, Clock } from 'lucide-react';

export default function Header({
  prices = {},
  btcPrice,
  isConnected,
  systemStatus,
  botMode,
  onToggleMode,
  feedStatuses = {},
  lastActiveSource = 'Local Server',
  ticksPerSecond = 0
}) {
  const [currentTime, setCurrentTime] = useState(new Date());
  
  const [priceColors, setPriceColors] = useState({
    BTCUSDT: 'var(--text-primary)',
    ETHUSDT: 'var(--text-primary)',
    SOLUSDT: 'var(--text-primary)',
    HYPEUSDT: 'var(--text-primary)',
    TONUSDT: 'var(--text-primary)',
  });
  const prevPricesRef = useRef({ BTCUSDT: 0.0, ETHUSDT: 0.0, SOLUSDT: 0.0, HYPEUSDT: 0.0, TONUSDT: 0.0 });

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'HYPEUSDT', 'TONUSDT'];
    let changed = false;
    const nextColors = { ...priceColors };

    symbols.forEach((symbol) => {
      const price = prices[symbol] || (symbol === 'BTCUSDT' ? btcPrice : 0.0);
      const prevPrice = prevPricesRef.current[symbol];

      if (price > 0 && prevPrice > 0 && price !== prevPrice) {
        nextColors[symbol] = price > prevPrice ? 'var(--emerald)' : 'var(--rose)';
        changed = true;

        setTimeout(() => {
          setPriceColors((prev) => ({ ...prev, [symbol]: 'var(--text-primary)' }));
        }, 500);
      }
      if (price > 0) {
        prevPricesRef.current[symbol] = price;
      }
    });

    if (changed) {
      setPriceColors(nextColors);
    }
  }, [prices, btcPrice]);

  const formatTime = (d) =>
    d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const formatDate = (d) =>
    d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  const feedLabels = {
    binanceFutures: 'Binance Fut',
    binanceSpot: 'Binance Spot',
    bybitFutures: 'Bybit Fut',
    bybitSpot: 'Bybit Spot',
    okxSpot: 'OKX Spot',
  };

  return (
    <header className="header glass-card" style={styles.header}>
      {/* Left: Logo */}
      <div style={styles.logoSection}>
        <div style={styles.logoIcon}>
          <Zap size={18} color="var(--cyan)" />
        </div>
        <div>
          <h1 style={styles.logoText}>
            <span className="gradient-text" style={styles.apexText}>APEX</span>
          </h1>
          <span style={styles.tagline}>Trading Bot</span>
        </div>
      </div>

      {/* Center: Multi-Asset Prices + Multi-Feed Panel */}
      <div style={styles.centerSection}>
        <div style={styles.pricesRow}>
          {['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'HYPEUSDT', 'TONUSDT'].map((symbol) => {
            const price = prices[symbol] || (symbol === 'BTCUSDT' ? btcPrice : 0.0);
            const formattedPrice = typeof price === 'number' && price > 0
              ? price.toLocaleString('en-US', {
                  style: 'currency',
                  currency: 'USD',
                  minimumFractionDigits: symbol === 'TONUSDT' ? 4 : (symbol === 'SOLUSDT' || symbol === 'HYPEUSDT' ? 3 : 2),
                })
              : '—';

            return (
              <div key={symbol} style={styles.priceBlockCompact}>
                <span style={styles.priceLabelCompact}>
                  {symbol.replace('USDT', '')}/USDT
                </span>
                <span className="mono" style={{ 
                  ...styles.priceValueCompact, 
                  color: priceColors[symbol], 
                  transition: 'color 0.15s ease' 
                }}>
                  {formattedPrice}
                </span>
              </div>
            );
          })}
        </div>

        <div className="divider" />

        {/* Parallel Feeds Stream Panel */}
        <div style={styles.feedsSection}>
          <div style={styles.feedsHeader}>
            <span style={styles.priceLabel}>PARALLEL PRICE SOURCES</span>
            <span style={styles.speedValue} className="mono">
              <Zap size={10} color="var(--cyan)" className="pulse-slow" style={{ marginRight: '3px' }} />
              {ticksPerSecond} <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>t/s</span>
            </span>
          </div>
          <div style={styles.feedsRow}>
            {Object.entries(feedLabels).map(([key, label]) => {
              const status = feedStatuses[key] || 'disconnected';
              const isCurrent = lastActiveSource.toLowerCase() === label.toLowerCase();
              let glowColor = 'rgba(255, 255, 255, 0.15)';
              if (status === 'connected') glowColor = 'var(--cyan)';
              else if (status === 'connecting') glowColor = 'var(--amber)';

              return (
                <div key={key} style={{
                  ...styles.feedBadge,
                  borderColor: status === 'connected' 
                    ? (isCurrent ? 'rgba(0, 212, 255, 0.4)' : 'rgba(0, 212, 255, 0.15)') 
                    : 'rgba(255, 255, 255, 0.04)',
                  background: status === 'connected' 
                    ? (isCurrent ? 'rgba(0, 212, 255, 0.06)' : 'rgba(0, 212, 255, 0.02)') 
                    : 'rgba(255, 255, 255, 0.01)',
                  color: status === 'connected' ? 'var(--text-primary)' : 'var(--text-muted)',
                  boxShadow: isCurrent && status === 'connected' ? '0 0 10px rgba(0, 212, 255, 0.1)' : 'none'
                }}>
                  <span style={{
                    ...styles.feedDot,
                    background: glowColor,
                    boxShadow: status === 'connected' ? `0 0 6px ${glowColor}` : 'none',
                    animation: isCurrent && status === 'connected' ? 'pulse-fast 0.6s infinite alternate' : 'none'
                  }} />
                  {label}
                </div>
              );
            })}
          </div>
        </div>

        <div className="divider" />

        <div style={styles.statusBadges}>
          <div style={{
            ...styles.statusChip,
            background: systemStatus === 'running'
              ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)',
            borderColor: systemStatus === 'running'
              ? 'rgba(16, 185, 129, 0.25)' : 'rgba(245, 158, 11, 0.25)',
            color: systemStatus === 'running' ? 'var(--emerald)' : 'var(--amber)',
          }}>
            <span className={`status-dot ${systemStatus === 'running' ? 'active' : 'warning'}`} />
            {systemStatus === 'running' ? 'Running' : 'Paused'}
          </div>

          <div style={{
            ...styles.statusChip,
            background: 'rgba(239, 68, 68, 0.12)',
            borderColor: 'rgba(239, 68, 68, 0.25)',
            color: 'var(--rose)',
            boxShadow: '0 0 10px rgba(239, 68, 68, 0.15)',
          }}>
            LIVE COMBAT
          </div>
        </div>
      </div>

      {/* Right: Connection + Clock */}
      <div style={styles.rightSection}>
        <div style={{
          ...styles.liveBadge,
          background: 'rgba(239, 68, 68, 0.08)',
          borderColor: 'rgba(239, 68, 68, 0.2)',
          boxShadow: '0 0 10px rgba(239, 68, 68, 0.1)',
        }} title="Strictly running in Live Combat Mode">
          <Zap size={14} color="var(--rose)" />
          <span style={{
            ...styles.liveBadgeLabel,
            color: 'var(--rose)',
          }}>COMBAT ACTIVE</span>
        </div>

        <div className="divider" />

        <div style={styles.connectionStatus}>
          {isConnected ? (
            <Wifi size={14} color="var(--emerald)" />
          ) : (
            <WifiOff size={14} color="var(--text-dim)" />
          )}
          <span style={{
            fontSize: 'var(--text-xs)',
            color: isConnected ? 'var(--emerald)' : 'var(--text-dim)',
          }}>
            {isConnected ? 'Online' : 'Offline'}
          </span>
        </div>

        <div className="divider" />

        <div style={styles.clockBlock}>
          <Clock size={12} color="var(--text-muted)" />
          <div style={styles.clockText}>
            <span className="mono" style={styles.time}>{formatTime(currentTime)}</span>
            <span style={styles.date}>{formatDate(currentTime)}</span>
          </div>
        </div>
      </div>
    </header>
  );
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 24px',
    borderRadius: 'var(--radius-lg)',
    gap: '16px',
    flexWrap: 'wrap',
    animation: 'slideDown 0.4s ease forwards',
  },
  logoSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    minWidth: 'fit-content',
  },
  logoIcon: {
    width: '36px',
    height: '36px',
    borderRadius: '10px',
    background: 'rgba(0, 212, 255, 0.10)',
    border: '1px solid rgba(0, 212, 255, 0.20)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 0 15px rgba(0, 212, 255, 0.10)',
  },
  logoText: {
    margin: 0,
    fontSize: '1.2rem',
    fontWeight: 800,
    letterSpacing: '0.06em',
    lineHeight: 1,
  },
  apexText: {
    fontSize: '1.2rem',
    fontWeight: 800,
  },
  tagline: {
    fontSize: 'var(--text-xs)',
    color: 'var(--text-muted)',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    fontWeight: 500,
  },
  centerSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
    flex: '1 1 auto',
    justifyContent: 'center',
  },
  priceBlock: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    minWidth: '150px',
  },
  priceLabel: {
    fontSize: 'var(--text-xs)',
    color: 'var(--text-muted)',
    fontWeight: 500,
    letterSpacing: '0.04em',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  sourceBadge: {
    fontSize: '9px',
    fontWeight: 700,
    padding: '1px 5px',
    borderRadius: '4px',
    border: '1px solid',
    transition: 'all 0.2s ease',
  },
  priceValue: {
    fontSize: 'var(--text-xl)',
    fontWeight: 700,
    color: 'var(--text-primary)',
    letterSpacing: '-0.02em',
  },
  feedsSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    flex: '1 1 auto',
    maxWidth: '460px',
  },
  feedsHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  feedsRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    flexWrap: 'wrap',
  },
  feedBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    fontSize: '10px',
    fontWeight: 600,
    padding: '3px 8px',
    borderRadius: '6px',
    border: '1px solid',
    transition: 'all 0.15s ease',
  },
  feedDot: {
    width: '5px',
    height: '5px',
    borderRadius: '50%',
    display: 'inline-block',
  },
  speedValue: {
    fontSize: 'var(--text-xs)',
    fontWeight: 600,
    color: 'var(--cyan)',
    display: 'flex',
    alignItems: 'center',
  },
  statusBadges: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  statusChip: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: 'var(--text-xs)',
    fontWeight: 600,
    padding: '4px 12px',
    borderRadius: '999px',
    border: '1px solid',
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
  },
  rightSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
    minWidth: 'fit-content',
  },
  liveBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    background: 'rgba(239, 68, 68, 0.08)',
    border: '1px solid rgba(239, 68, 68, 0.2)',
    padding: '4px 10px',
    borderRadius: 'var(--radius-sm)',
    boxShadow: '0 0 10px rgba(239, 68, 68, 0.1)',
  },
  liveBadgeLabel: {
    fontSize: 'var(--text-xs)',
    fontWeight: 700,
    color: 'var(--rose)',
    letterSpacing: '0.04em',
  },
  connectionStatus: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
  },
  clockBlock: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  clockText: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
  },
  time: {
    fontSize: 'var(--text-sm)',
    fontWeight: 600,
    color: 'var(--text-primary)',
    lineHeight: 1.2,
  },
  date: {
    fontSize: '10px',
    color: 'var(--text-muted)',
    lineHeight: 1.2,
  },
  pricesRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
  },
  priceBlockCompact: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    minWidth: '100px',
    background: 'rgba(255, 255, 255, 0.01)',
    border: '1px solid rgba(255, 255, 255, 0.03)',
    borderRadius: '8px',
    padding: '4px 10px',
  },
  priceLabelCompact: {
    fontSize: '10px',
    color: 'var(--text-muted)',
    fontWeight: 600,
    letterSpacing: '0.04em',
  },
  priceValueCompact: {
    fontSize: 'var(--text-md)',
    fontWeight: 700,
    color: 'var(--text-primary)',
    letterSpacing: '-0.01em',
  },
};
