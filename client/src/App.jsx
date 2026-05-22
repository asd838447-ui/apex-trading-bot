import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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

  const lastDirectTickTimeRef = useRef(0);

  // Direct real-time high-frequency Multi-Source WebSocket price feed (Zero lag with automatic fallbacks)
  useEffect(() => {
    let ws = null;
    let reconnectTimer = null;
    let watchdogTimer = null;
    let currentSourceIdx = 0;

    const sources = [
      {
        name: 'Binance Futures WS',
        url: 'wss://fstream.binance.com/ws/btcusdt@aggTrade',
        parse: (data) => data && data.p ? parseFloat(data.p) : null
      },
      {
        name: 'Binance Spot WS',
        url: 'wss://stream.binance.com:9443/ws/btcusdt@aggTrade',
        parse: (data) => data && data.p ? parseFloat(data.p) : null
      },
      {
        name: 'Bybit Spot WS',
        url: 'wss://stream.bybit.com/v5/public/spot',
        subscribe: { op: 'subscribe', args: ['publicTrade.BTCUSDT'] },
        parse: (data) => {
          if (data && data.topic === 'publicTrade.BTCUSDT' && data.data && data.data[0]) {
            return parseFloat(data.data[0].p);
          }
          return null;
        }
      }
    ];

    const connectPriceWS = () => {
      const source = sources[currentSourceIdx];

      try {
        ws = new WebSocket(source.url);

        const resetWatchdog = () => {
          if (watchdogTimer) clearTimeout(watchdogTimer);
          watchdogTimer = setTimeout(() => {
            moveToNextSource();
          }, 6000);
        };

        ws.onopen = () => {
          resetWatchdog();
          if (source.subscribe) {
            ws.send(JSON.stringify(source.subscribe));
          }
        };

        ws.onmessage = (event) => {
          try {
            const rawData = JSON.parse(event.data);
            const price = source.parse(rawData);
            if (price && !isNaN(price)) {
              setBtcPrice(price);
              lastDirectTickTimeRef.current = Date.now();
              resetWatchdog();
            }
          } catch (err) {
            // Silence parser errors
          }
        };

        ws.onclose = () => {
          cleanupTimers();
          reconnectTimer = setTimeout(() => {
            moveToNextSource();
          }, 2000);
        };

        ws.onerror = () => {
          if (ws) ws.close();
        };

      } catch (err) {
        cleanupTimers();
        reconnectTimer = setTimeout(() => {
          moveToNextSource();
        }, 2000);
      }
    };

    const moveToNextSource = () => {
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
      cleanupTimers();
      currentSourceIdx = (currentSourceIdx + 1) % sources.length;
      connectPriceWS();
    };

    const cleanupTimers = () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (watchdogTimer) clearTimeout(watchdogTimer);
    };

    connectPriceWS();

    return () => {
      cleanupTimers();
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, []);

  // Handle incoming WS messages
  useEffect(() => {
    if (!lastMessage) return;
    const { type, data } = lastMessage;
    switch (type) {
      case 'price_update':
        // Use backend price update as a fallback if direct stream is lagging or inactive
        setBtcPrice((prev) => {
          if (Date.now() - lastDirectTickTimeRef.current > 3000 || prev === 0.0) {
            return data.price;
          }
          return prev;
        });
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
