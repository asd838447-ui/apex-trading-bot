import React from 'react';
import { AreaChart, Brain, RefreshCw, Layers, TrendingUp, AlertTriangle, Cpu, Globe } from 'lucide-react';

export default function QuantAlphas({ metrics = {}, symbol = 'BTCUSDT' }) {
  const cleanSymbol = symbol.replace('USDT', '');
  
  // Destructure common metrics
  const { 
    obi = 0.0, 
    funding_divergence = 0.0,
    last_update 
  } = metrics;

  // Compute OBI bar widths
  const bidPercentage = Math.round(((obi + 1) / 2) * 100);
  const askPercentage = 100 - bidPercentage;

  // Custom styles for dynamic colors
  const getObiColor = (val) => {
    if (val > 0.15) return 'var(--emerald)';
    if (val < -0.15) return 'var(--rose)';
    return 'var(--text-muted)';
  };

  const getFundingColor = (val) => {
    if (Math.abs(val) > 0.08) return 'var(--amber)';
    return 'var(--text-dim)';
  };

  return (
    <div className="glass-card" style={styles.card}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.titleBlock}>
          <div style={styles.iconContainer}>
            <Brain size={16} color="var(--cyan)" className="pulse" />
          </div>
          <div>
            <div style={styles.title}>QUANT ALPHAS</div>
            <span style={styles.subtitle}>Microstructure & Ecosystem Metrics</span>
          </div>
        </div>
        <span className="mono" style={styles.symbolBadge}>{cleanSymbol}</span>
      </div>

      {/* Main metrics grid */}
      <div style={styles.content}>
        
        {/* Metric 1: Order Book Imbalance (OBI) */}
        <div style={styles.metricSection}>
          <div style={styles.metricLabelRow}>
            <span style={styles.label}>
              <Layers size={13} style={{ marginRight: '6px' }} color="var(--text-muted)" />
              Order Book Imbalance (OBI)
            </span>
            <span className="mono" style={{ ...styles.value, color: getObiColor(obi) }}>
              {obi > 0 ? `+${obi.toFixed(2)}` : obi.toFixed(2)}
            </span>
          </div>
          
          {/* OBI Bid/Ask Visual Bar */}
          <div style={styles.obiBarContainer}>
            <div style={{ ...styles.obiBarBid, width: `${bidPercentage}%` }} />
            <div style={{ ...styles.obiBarCenter }} />
            <div style={{ ...styles.obiBarAsk, width: `${askPercentage}%` }} />
          </div>
          <div style={styles.obiLabelsRow}>
            <span style={{ fontSize: '9px', color: 'var(--emerald)', fontWeight: 600 }}>Bids ({bidPercentage}%)</span>
            <span style={{ fontSize: '9px', color: 'var(--rose)', fontWeight: 600 }}>Asks ({askPercentage}%)</span>
          </div>
        </div>

        {/* Metric 2: Funding Rate Divergence */}
        <div style={styles.metricRowContainer}>
          <div style={styles.smallCard}>
            <span style={styles.label}>
              <RefreshCw size={12} style={{ marginRight: '5px' }} color="var(--text-muted)" />
              Funding Divergence
            </span>
            <span className="mono" style={{ ...styles.largeValue, color: getFundingColor(funding_divergence) }}>
              {funding_divergence > 0 ? `+${funding_divergence.toFixed(3)}%` : `${funding_divergence.toFixed(3)}%`}
            </span>
            <span style={styles.cardDesc}>Native vs Binance spread</span>
          </div>

          <div style={styles.smallCard}>
            <span style={styles.label}>
              <TrendingUp size={12} style={{ marginRight: '5px' }} color="var(--text-muted)" />
              Execution Speed
            </span>
            <span className="mono" style={{ ...styles.largeValue, color: 'var(--cyan)' }}>
              {symbol === 'TONUSDT' ? 'Asynchronous' : 'Low Latency'}
            </span>
            <span style={styles.cardDesc}>{symbol === 'TONUSDT' ? 'Multi-block finality' : 'Direct sub-50ms connection'}</span>
          </div>
        </div>

        <div className="divider" style={{ margin: '14px 0' }} />

        {/* Metric 3: Symbol-Specific Advanced Metrics */}
        
        {symbol === 'HYPEUSDT' && (
          <div style={styles.specificContainer}>
            <div style={styles.specificTitle}>HYPERLIQUID L1 ECOSYSTEM ALPHAS</div>
            
            <div style={styles.specificRow}>
              <div style={styles.specificItem}>
                <span style={styles.specLabel}>Hayashi-Yoshida Lag</span>
                <span className="mono" style={styles.specValue}>+{metrics.hayashi_yoshida_lag || 0.42}s</span>
                <span style={styles.specSub}>HYPE leads {metrics.ecosystem_lead_symbol || 'PURR'}</span>
              </div>
              <div style={styles.specificItem}>
                <span style={styles.specLabel}>L1 TVL Weekly Growth</span>
                <span className="mono" style={{ ...styles.specValue, color: 'var(--emerald)' }}>+{metrics.l1_tvl_growth || 8.4}%</span>
                <span style={styles.specSub}>HyperEVM staking demand</span>
              </div>
            </div>

            <div style={{ ...styles.specificItemWide, marginTop: '10px' }}>
              <div style={styles.specWideLabelRow}>
                <span style={styles.specLabel}>Assistance Fund Buybacks</span>
                <span className="mono" style={{ fontSize: '12px', fontWeight: 700, color: 'var(--cyan)' }}>
                  ${metrics.assistance_fund_buybacks_m || 2.4}M <span style={{ fontSize: '9px', fontWeight: 500, color: 'var(--text-muted)' }}>/ 24h</span>
                </span>
              </div>
              <div style={styles.progressTrack}>
                <div style={{ ...styles.progressFill, width: '68%', background: 'var(--cyan-glow)' }} />
              </div>
              <span style={styles.specSub}>Fee buybacks continuously absorb open market supply</span>
            </div>
          </div>
        )}

        {symbol === 'TONUSDT' && (
          <div style={styles.specificContainer}>
            <div style={styles.specificTitle}>THE OPEN NETWORK (TON) ALPHAS</div>

            <div style={styles.specificRow}>
              <div style={styles.specificItem}>
                <span style={styles.specLabel}>TMA Coint Spread</span>
                <span className="mono" style={{ ...styles.specValue, color: metrics.tma_spread_pct < -2 ? 'var(--rose)' : 'var(--emerald)' }}>
                  {metrics.tma_spread_pct || -1.8}%
                </span>
                <span style={styles.specSub}>Gaming token deviation</span>
              </div>
              <div style={styles.specificItem}>
                <span style={styles.specLabel}>USDT-on-TON Volume</span>
                <span className="mono" style={styles.specValue}>${metrics.usdt_on_ton_volume_m || 1042.5}M</span>
                <span style={styles.specSub}>Telegram remittance circulation</span>
              </div>
            </div>

            <div style={{ ...styles.specificItemWide, marginTop: '10px' }}>
              <div style={styles.specWideLabelRow}>
                <span style={styles.specLabel}>Telegram Network Congestion</span>
                <div style={{
                  ...styles.congestionBadge,
                  background: metrics.telegram_congestion_status === 'CRITICAL' ? 'rgba(239, 68, 68, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                  borderColor: metrics.telegram_congestion_status === 'CRITICAL' ? 'rgba(239, 68, 68, 0.25)' : 'rgba(16, 185, 129, 0.25)',
                  color: metrics.telegram_congestion_status === 'CRITICAL' ? 'var(--rose)' : 'var(--emerald)'
                }}>
                  {metrics.telegram_congestion_status === 'CRITICAL' ? <AlertTriangle size={10} /> : <Cpu size={10} />}
                  Z-Score: {metrics.telegram_congestion_z || 0.6} ({metrics.telegram_congestion_status || 'NORMAL'})
                </div>
              </div>
              <div style={styles.progressTrack}>
                <div style={{ 
                  ...styles.progressFill, 
                  width: `${Math.min((metrics.telegram_congestion_z || 0.6) * 33, 100)}%`, 
                  background: metrics.telegram_congestion_status === 'CRITICAL' ? 'var(--rose)' : 'var(--emerald)' 
                }} />
              </div>
              <span style={styles.specSub}>High congestion delays swaps; triggers short-hedges against TON</span>
            </div>
          </div>
        )}

        {symbol !== 'HYPEUSDT' && symbol !== 'TONUSDT' && (
          <div style={styles.specificContainer}>
            <div style={styles.specificTitle}>MACRO & ORDER FLOW METRICS</div>

            <div style={styles.specificRow}>
              <div style={styles.specificItem}>
                <span style={styles.specLabel}>Correlation with BTC</span>
                <span className="mono" style={styles.specValue}>{metrics.correlation_with_btc || 0.84}</span>
                <span style={styles.specSub}>Ecosystem systemic beta</span>
              </div>
              <div style={styles.specificItem}>
                <span style={styles.specLabel}>Order Flow Delta (CVD)</span>
                <span className="mono" style={{ ...styles.specValue, color: (metrics.order_flow_delta_vol || 45.2) > 0 ? 'var(--emerald)' : 'var(--rose)' }}>
                  {(metrics.order_flow_delta_vol || 45.2) > 0 ? `+${metrics.order_flow_delta_vol || 45.2}M` : `${metrics.order_flow_delta_vol || 45.2}M`}
                </span>
                <span style={styles.specSub}>Institutional buy/sell pressure</span>
              </div>
            </div>

            <div style={{ ...styles.specificItemWide, marginTop: '10px' }}>
              <div style={styles.specWideLabelRow}>
                <span style={styles.specLabel}>Market-Maker Depth Delta</span>
                <span className="mono" style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Balanced
                </span>
              </div>
              <div style={styles.progressTrack}>
                <div style={{ ...styles.progressFill, width: '50%', background: 'var(--text-muted)' }} />
              </div>
              <span style={styles.specSub}>L2 order liquidity skew within 0.5% boundary</span>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

const styles = {
  card: {
    padding: '20px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    minHeight: '380px',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '16px',
  },
  titleBlock: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  iconContainer: {
    width: '28px',
    height: '28px',
    borderRadius: '8px',
    background: 'rgba(0, 212, 255, 0.08)',
    border: '1px solid rgba(0, 212, 255, 0.15)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: '11px',
    fontWeight: 800,
    letterSpacing: '0.08em',
    color: 'var(--cyan)',
    margin: 0,
  },
  subtitle: {
    fontSize: '10px',
    color: 'var(--text-muted)',
    display: 'block',
  },
  symbolBadge: {
    fontSize: '11px',
    fontWeight: 700,
    padding: '2px 8px',
    borderRadius: '6px',
    background: 'rgba(255, 255, 255, 0.03)',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    color: 'var(--text-primary)',
  },
  content: {
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
    flex: 1,
  },
  metricSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  metricLabelRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  label: {
    fontSize: '11px',
    color: 'var(--text-dim)',
    fontWeight: 600,
    display: 'flex',
    alignItems: 'center',
  },
  value: {
    fontSize: '12px',
    fontWeight: 700,
  },
  obiBarContainer: {
    height: '6px',
    borderRadius: '3px',
    background: 'rgba(255, 255, 255, 0.04)',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    position: 'relative',
  },
  obiBarBid: {
    height: '100%',
    background: 'var(--emerald)',
    borderRadius: '3px 0 0 3px',
    transition: 'width 0.3s ease-in-out',
  },
  obiBarCenter: {
    width: '2px',
    height: '100%',
    background: 'rgba(255, 255, 255, 0.3)',
    zIndex: 2,
  },
  obiBarAsk: {
    height: '100%',
    background: 'var(--rose)',
    borderRadius: '0 3px 3px 0',
    transition: 'width 0.3s ease-in-out',
  },
  obiLabelsRow: {
    display: 'flex',
    justifyContent: 'space-between',
    marginTop: '2px',
  },
  metricRowContainer: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '10px',
  },
  smallCard: {
    background: 'rgba(255, 255, 255, 0.01)',
    border: '1px solid rgba(255, 255, 255, 0.03)',
    borderRadius: '8px',
    padding: '8px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  largeValue: {
    fontSize: '14px',
    fontWeight: 700,
    letterSpacing: '-0.01em',
  },
  cardDesc: {
    fontSize: '8px',
    color: 'var(--text-muted)',
    lineHeight: 1.2,
  },
  specificContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  specificTitle: {
    fontSize: '9px',
    fontWeight: 700,
    letterSpacing: '0.06em',
    color: 'var(--text-muted)',
    margin: '0 0 4px 0',
  },
  specificRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '8px',
  },
  specificItem: {
    background: 'rgba(0, 212, 255, 0.01)',
    border: '1px solid rgba(0, 212, 255, 0.03)',
    borderRadius: '6px',
    padding: '6px 8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  specificItemWide: {
    background: 'rgba(255, 255, 255, 0.01)',
    border: '1px solid rgba(255, 255, 255, 0.03)',
    borderRadius: '6px',
    padding: '8px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  specLabel: {
    fontSize: '9px',
    color: 'var(--text-dim)',
    fontWeight: 600,
  },
  specValue: {
    fontSize: '12px',
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  specSub: {
    fontSize: '8px',
    color: 'var(--text-muted)',
    lineHeight: 1.1,
  },
  specWideLabelRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  progressTrack: {
    height: '4px',
    borderRadius: '2px',
    background: 'rgba(255, 255, 255, 0.04)',
    overflow: 'hidden',
    marginTop: '2px',
  },
  progressFill: {
    height: '100%',
    borderRadius: '2px',
    transition: 'width 0.3s ease-in-out',
  },
  congestionBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '9px',
    fontWeight: 700,
    padding: '2px 6px',
    borderRadius: '4px',
    border: '1px solid',
  },
};
