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

  // Parallel Multi-Source feed statuses
  const [feedStatuses, setFeedStatuses] = useState({
    binanceFutures: 'disconnected',
    binanceSpot: 'disconnected',
    bybitFutures: 'disconnected',
    bybitSpot: 'disconnected',
    okxSpot: 'disconnected',
  });
  const [lastActiveSource, setLastActiveSource] = useState('Local Server');
  const [ticksPerSecond, setTicksPerSecond] = useState(0);

  // Ref to hold tick counter for frequency measurement
  const tickCounterRef = useRef(0);

  const latestPriceRef = useRef(0.0);
  const latestSourceRef = useRef('Local Server');

  // Throttled UI updater for high-frequency price data (100ms interval / 10Hz) to prevent browser main-thread choking
  useEffect(() => {
    const timer = setInterval(() => {
      if (latestPriceRef.current !== 0.0) {
        setBtcPrice(latestPriceRef.current);
      }
      if (latestSourceRef.current !== '') {
        setLastActiveSource(latestSourceRef.current);
      }
    }, 100);
    return () => clearInterval(timer);
  }, []);

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

  // Direct real-time high-frequency Multi-Source Parallel WebSocket price feed (Zero lag, instant aggregation)
  useEffect(() => {
    const sources = [
      {
        id: 'binanceFutures',
        name: 'Binance Fut',
        url: 'wss://fstream.binance.com/ws/btcusdt@aggTrade',
        parse: (data) => data && data.p ? parseFloat(data.p) : null
      },
      {
        id: 'binanceSpot',
        name: 'Binance Spot',
        url: 'wss://stream.binance.com:9443/ws/btcusdt@aggTrade',
        parse: (data) => data && data.p ? parseFloat(data.p) : null
      },
      {
        id: 'bybitFutures',
        name: 'Bybit Fut',
        url: 'wss://stream.bybit.com/v5/public/linear',
        subscribe: { op: 'subscribe', args: ['publicTrade.BTCUSDT'] },
        parse: (data) => {
          if (data && data.topic === 'publicTrade.BTCUSDT' && data.data && data.data[0]) {
            return parseFloat(data.data[0].p);
          }
          return null;
        }
      },
      {
        id: 'bybitSpot',
        name: 'Bybit Spot',
        url: 'wss://stream.bybit.com/v5/public/spot',
        subscribe: { op: 'subscribe', args: ['publicTrade.BTCUSDT'] },
        parse: (data) => {
          if (data && data.topic === 'publicTrade.BTCUSDT' && data.data && data.data[0]) {
            return parseFloat(data.data[0].p);
          }
          return null;
        }
      },
      {
        id: 'okxSpot',
        name: 'OKX Spot',
        url: 'wss://ws.okx.com:8443/ws/v5/public',
        subscribe: { op: 'subscribe', args: [{ channel: 'trades', instId: 'BTC-USDT' }] },
        parse: (data) => {
          if (data && data.arg && data.arg.channel === 'trades' && data.data && data.data[0]) {
            return parseFloat(data.data[0].px);
          }
          return null;
        }
      }
    ];

    const activeConnections = {};
    const reconnectTimers = {};

    const connectSource = (source, reconnectDelay = 1000) => {
      try {
        const ws = new WebSocket(source.url);
        activeConnections[source.id] = ws;

        setFeedStatuses((prev) => ({ ...prev, [source.id]: 'connecting' }));

        ws.onopen = () => {
          setFeedStatuses((prev) => ({ ...prev, [source.id]: 'connected' }));
          if (source.subscribe) {
            ws.send(JSON.stringify(source.subscribe));
          }
        };

        ws.onmessage = (event) => {
          try {
            const rawData = JSON.parse(event.data);
            const price = source.parse(rawData);
            if (price && !isNaN(price)) {
              latestPriceRef.current = price;
              latestSourceRef.current = source.name;
              tickCounterRef.current += 1;
              lastDirectTickTimeRef.current = Date.now();
            }
          } catch (err) {
            // Ignore parser errors
          }
        };

        ws.onclose = () => {
          setFeedStatuses((prev) => ({ ...prev, [source.id]: 'disconnected' }));
          scheduleReconnect(source, reconnectDelay);
        };

        ws.onerror = () => {
          ws.close();
        };

      } catch (err) {
        setFeedStatuses((prev) => ({ ...prev, [source.id]: 'disconnected' }));
        scheduleReconnect(source, reconnectDelay);
      }
    };

    const scheduleReconnect = (source, delay) => {
      if (reconnectTimers[source.id]) clearTimeout(reconnectTimers[source.id]);
      
      const nextDelay = Math.min(delay * 2, 30000);
      const jitter = Math.random() * 1000;
      
      reconnectTimers[source.id] = setTimeout(() => {
        connectSource(source, nextDelay);
      }, delay + jitter);
    };

    // Connect to all 5 sources in parallel on startup
    sources.forEach((src) => connectSource(src));

    // Dynamic feed frequency calculator
    const tpsTimer = setInterval(() => {
      setTicksPerSecond(tickCounterRef.current);
      tickCounterRef.current = 0;
    }, 1000);

    return () => {
      clearInterval(tpsTimer);
      Object.keys(activeConnections).forEach((id) => {
        const ws = activeConnections[id];
        if (ws) {
          ws.onclose = null;
          ws.close();
        }
      });
      Object.keys(reconnectTimers).forEach((id) => {
        clearTimeout(reconnectTimers[id]);
      });
    };
  }, []);

  // Handle incoming WS messages
  useEffect(() => {
    if (!lastMessage) return;
    const { type, data } = lastMessage;
    switch (type) {
      case 'price_update':
        // Use backend price update as a fallback if direct streams are lagging or inactive
        if (Date.now() - lastDirectTickTimeRef.current > 3000 || latestPriceRef.current === 0.0) {
          latestPriceRef.current = data.price;
          latestSourceRef.current = 'Local Server';
        }
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
          if (data.btc_price) {
            setBtcPrice(data.btc_price);
            latestPriceRef.current = data.btc_price;
          }
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
        feedStatuses={feedStatuses}
        lastActiveSource={lastActiveSource}
        ticksPerSecond={ticksPerSecond}
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
