import React, { useState, useEffect, useCallback, useMemo } from 'react';
import useWebSocket from './hooks/useWebSocket';
import Header from './components/Header';
import Dashboard from './components/Dashboard';

const SKILLS = [
  { id: 1, name: 'Order Flow', category: 'flow' },
  { id: 2, name: 'Multi-TF', category: 'momentum' },
  { id: 3, name: 'On-Chain', category: 'volume' },
  { id: 4, name: 'NLP Sentiment', category: 'sentiment' },
  { id: 5, name: 'Risk ATR', category: 'reversion' },
  { id: 6, name: 'Market Regime', category: 'regime' },
  { id: 7, name: 'No-Human', category: 'reversion' },
];

/* ============================================================
   App Component
   ============================================================ */

export default function App() {
  // Core state initialized to neutral/empty values for strictly live data
  const [btcPrice, setBtcPrice] = useState(0.0);
  const [equityCurve, setEquityCurve] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [signals, setSignals] = useState({
    skills: [],
    compositeScore: 0.0,
    action: 'WAIT',
    confidence: 0,
  });
  const [risk, setRisk] = useState({
    positionSize: 0.0,
    leverage: 5,
    stopLoss: 0.0,
    takeProfit: 0.0,
    dailyPnl: 0.0,
    maxDrawdown: 3.0,
    riskPerTrade: 1.0,
    tiltGuard: { active: false, cooldownSec: 0, consecutiveLosses: 0, dailyStops: 0 },
    lossStreak: 0,
  });
  const [regime, setRegime] = useState({
    current: 'FLAT',
    confidence: 100.0,
    history: [],
  });
  const [botMode, setBotMode] = useState('live');
  const [systemStatus, setSystemStatus] = useState('running');

  // WebSocket
  const wsUrl = useMemo(() => {
    if (typeof window !== 'undefined') {
      const isProd = window.location.protocol === 'https:';
      return isProd
        ? `wss://${window.location.host}/ws`
        : 'ws://localhost:8000/ws';
    }
    return 'ws://localhost:8000/ws';
  }, []);

  const { isConnected, lastMessage, sendMessage } = useWebSocket(wsUrl);

  // Handle incoming WS messages
  useEffect(() => {
    if (!lastMessage) return;
    const { type, data } = lastMessage;
    switch (type) {
      case 'price_update':
        setBtcPrice(data.price);
        break;
      case 'equity_update':
        setEquityCurve((prev) => {
          const newPoint = {
            date: data.date || new Date().toISOString().split('T')[0],
            equity: typeof data.equity === 'number' ? data.equity : (prev.length ? prev[prev.length - 1].equity : 10000),
            daily_pnl: data.daily_pnl || 0,
          };
          const filtered = prev.filter((p) => p.date !== newPoint.date);
          return [...filtered.slice(-89), newPoint];
        });
        break;
      case 'trade_update':
        setTradeHistory((prev) => {
          const filtered = prev.filter((t) => t.id !== data.id);
          return [data, ...filtered.slice(0, 19)];
        });
        break;
      case 'signal_update':
        setSignals(data);
        break;
      case 'risk_update':
        setRisk(data);
        break;
      case 'regime_update':
        setRegime(data);
        break;
      case 'status_update':
        setSystemStatus(data.status);
        break;
      default:
        break;
    }
  }, [lastMessage]);

  // Try fetching initial data from API
  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/status');
        if (res.ok) {
          const data = await res.json();
          if (data.equity_curve) setEquityCurve(data.equity_curve);
          if (data.trade_history) setTradeHistory(data.trade_history);
          if (data.signals) setSignals(data.signals);
          if (data.risk) setRisk(data.risk);
          if (data.regime) setRegime(data.regime);
          if (data.btc_price) setBtcPrice(data.btc_price);
          if (data.bot_mode) setBotMode(data.bot_mode);
          if (data.status) setSystemStatus(data.status);
        }
      } catch {
        // Backend connection failed
      }
    };
    fetchData();
  }, []);

  const toggleBotMode = useCallback(() => {
    // Hardlocked to Live Combat Mode
  }, []);

  return (
    <div className="app-container">
      <Header
        btcPrice={btcPrice}
        isConnected={isConnected}
        systemStatus={systemStatus}
        botMode={botMode}
        onToggleMode={toggleBotMode}
      />
      <Dashboard
        equityCurve={equityCurve}
        tradeHistory={tradeHistory}
        signals={signals}
        risk={risk}
        regime={regime}
        btcPrice={btcPrice}
      />
    </div>
  );
}
