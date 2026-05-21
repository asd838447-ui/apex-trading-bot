import React, { useState, useEffect, useCallback, useMemo } from 'react';
import useWebSocket from './hooks/useWebSocket';
import Header from './components/Header';
import Dashboard from './components/Dashboard';

/* ============================================================
   Demo Data Generators
   ============================================================ */

const SKILLS = [
  { id: 1, name: 'Trend Follower', category: 'momentum' },
  { id: 2, name: 'Mean Reversion', category: 'reversion' },
  { id: 3, name: 'Breakout Hunter', category: 'momentum' },
  { id: 4, name: 'Volume Profiler', category: 'volume' },
  { id: 5, name: 'Order Flow', category: 'flow' },
  { id: 6, name: 'Regime Filter', category: 'regime' },
  { id: 7, name: 'Sentiment Gauge', category: 'sentiment' },
];

function generateEquityCurve(days = 90) {
  const data = [];
  let equity = 10000;
  const now = Date.now();
  const msPerDay = 86400000;

  for (let i = days; i >= 0; i--) {
    const dailyReturn = (Math.random() - 0.42) * 0.025;
    equity *= 1 + dailyReturn;
    equity = Math.max(equity, 5000);
    const date = new Date(now - i * msPerDay);
    data.push({
      date: date.toISOString().split('T')[0],
      timestamp: date.getTime(),
      equity: Math.round(equity * 100) / 100,
      drawdown: -(Math.random() * 5).toFixed(2),
    });
  }
  return data;
}

function generateTradeHistory(count = 20) {
  const trades = [];
  const sides = ['LONG', 'SHORT'];
  const statuses = ['CLOSED', 'CLOSED', 'CLOSED', 'CLOSED', 'OPEN', 'CANCELLED'];
  const now = Date.now();

  for (let i = 0; i < count; i++) {
    const side = sides[Math.floor(Math.random() * sides.length)];
    const entry = 67000 + Math.random() * 5000;
    const pnlPct = (Math.random() - 0.4) * 6;
    const exit = entry * (1 + pnlPct / 100);
    const status = i === 0 ? 'OPEN' : statuses[Math.floor(Math.random() * statuses.length)];
    const rr = Math.abs(pnlPct) / (1 + Math.random());

    trades.push({
      id: `T-${(10000 + count - i).toString()}`,
      time: new Date(now - i * 3600000 * (2 + Math.random() * 10)).toISOString(),
      symbol: 'BTC/USDT',
      side,
      entry: Math.round(entry * 100) / 100,
      exit: status === 'OPEN' ? null : Math.round(exit * 100) / 100,
      pnl: status === 'OPEN' ? null : Math.round(pnlPct * entry / 100 * 100) / 100,
      pnlPct: status === 'OPEN' ? null : Math.round(pnlPct * 100) / 100,
      rr: status === 'OPEN' ? null : Math.round(rr * 100) / 100,
      status,
    });
  }
  return trades;
}

function generateSignals() {
  const signals = SKILLS.map((skill) => {
    const signal = [-1, 0, 1][Math.floor(Math.random() * 3)];
    return {
      ...skill,
      signal,
      weight: Math.round((0.05 + Math.random() * 0.25) * 1000) / 10,
      confidence: Math.round((0.4 + Math.random() * 0.55) * 100),
      accuracy: Math.round((55 + Math.random() * 30) * 10) / 10,
    };
  });

  // Normalise weights
  const totalWeight = signals.reduce((s, sk) => s + sk.weight, 0);
  signals.forEach((s) => {
    s.weight = Math.round((s.weight / totalWeight) * 1000) / 10;
  });

  const compositeScore = signals.reduce((sum, s) => sum + s.signal * (s.weight / 100), 0);
  const compositeNorm = Math.round(compositeScore * 1000) / 10;
  const action = compositeNorm > 0.15 ? 'LONG' : compositeNorm < -0.15 ? 'SHORT' : 'WAIT';
  const compositeConfidence = Math.round(signals.reduce((s, sk) => s + sk.confidence * sk.weight / 100, 0));

  return { skills: signals, compositeScore: compositeNorm, action, confidence: compositeConfidence };
}

function generateRisk() {
  return {
    positionSize: Math.round(Math.random() * 0.5 * 1000) / 1000,
    leverage: Math.floor(1 + Math.random() * 10),
    stopLoss: Math.round((67000 + Math.random() * 5000) * 0.97 * 100) / 100,
    takeProfit: Math.round((67000 + Math.random() * 5000) * 1.04 * 100) / 100,
    dailyPnl: Math.round((Math.random() - 0.4) * 800 * 100) / 100,
    maxDrawdown: Math.round((3 + Math.random() * 8) * 100) / 100,
    riskPerTrade: Math.round((0.5 + Math.random() * 1.5) * 100) / 100,
    tiltGuard: { active: Math.random() > 0.7, cooldownSec: Math.floor(Math.random() * 600) },
    lossStreak: Math.floor(Math.random() * 5),
  };
}

function generateRegime() {
  const regimes = ['TREND', 'FLAT', 'VOLATILE'];
  const current = regimes[Math.floor(Math.random() * regimes.length)];
  const history = [];
  const now = Date.now();
  for (let i = 24; i >= 0; i--) {
    history.push({
      time: new Date(now - i * 3600000).toISOString(),
      regime: regimes[Math.floor(Math.random() * regimes.length)],
    });
  }
  return {
    current,
    confidence: Math.round((60 + Math.random() * 35) * 10) / 10,
    history,
  };
}

/* ============================================================
   App Component
   ============================================================ */

export default function App() {
  // Core state
  const [btcPrice, setBtcPrice] = useState(69427.50);
  const [equityCurve, setEquityCurve] = useState(() => generateEquityCurve(90));
  const [tradeHistory, setTradeHistory] = useState(() => generateTradeHistory(20));
  const [signals, setSignals] = useState(() => generateSignals());
  const [risk, setRisk] = useState(() => generateRisk());
  const [regime, setRegime] = useState(() => generateRegime());
  const [botMode, setBotMode] = useState('paper'); // paper | live
  const [systemStatus, setSystemStatus] = useState('running'); // running | paused | error

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
        setEquityCurve((prev) => [...prev.slice(-89), data]);
        break;
      case 'trade_update':
        setTradeHistory((prev) => [data, ...prev.slice(0, 19)]);
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

  // Simulated live updates when backend unavailable
  useEffect(() => {
    if (isConnected) return;

    const priceTimer = setInterval(() => {
      setBtcPrice((p) => {
        const delta = (Math.random() - 0.5) * 80;
        return Math.round((p + delta) * 100) / 100;
      });
    }, 2000);

    const dataTimer = setInterval(() => {
      setSignals(generateSignals());
      setRisk(generateRisk());
    }, 8000);

    const regimeTimer = setInterval(() => {
      setRegime(generateRegime());
    }, 15000);

    const equityTimer = setInterval(() => {
      setEquityCurve((prev) => {
        const last = prev[prev.length - 1];
        const dailyReturn = (Math.random() - 0.42) * 0.015;
        const newEquity = Math.round(last.equity * (1 + dailyReturn) * 100) / 100;
        const now = new Date();
        return [
          ...prev.slice(1),
          {
            date: now.toISOString().split('T')[0],
            timestamp: now.getTime(),
            equity: newEquity,
            drawdown: -(Math.random() * 5).toFixed(2),
          },
        ];
      });
    }, 10000);

    return () => {
      clearInterval(priceTimer);
      clearInterval(dataTimer);
      clearInterval(regimeTimer);
      clearInterval(equityTimer);
    };
  }, [isConnected]);

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
        // Backend not available, demo mode
      }
    };
    fetchData();
  }, []);

  const toggleBotMode = useCallback(() => {
    const newMode = botMode === 'paper' ? 'live' : 'paper';
    setBotMode(newMode);
    sendMessage({ type: 'set_mode', mode: newMode });
  }, [botMode, sendMessage]);

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
