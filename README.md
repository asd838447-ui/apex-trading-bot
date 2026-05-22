# 🤖 APEX Trading Bot

**Algorithmic Trading System · 7 Skills Engine · Production-Ready Architecture**

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis)
![License](https://img.shields.io/badge/License-Private-red)

---

## 📋 Overview

APEX Trading Bot — алгоритмическая торговая система для криптовалютных рынков, реализующая 7 специализированных навыков:

| # | Навык | Описание |
|---|-------|----------|
| 01 | **Order Flow** | CVD delta, обнаружение спуфинга, DOM-кластеры |
| 02 | **Multi-TF** | EMA/ADX анализ на 1D, 4H, 15M таймфреймах |
| 03 | **On-Chain** | Netflow бирж, потоки майнеров, активные адреса |
| 04 | **NLP Sentiment** | Анализ тональности новостей (VADER/FinBERT) |
| 05 | **Risk Management** | Динамический ATR-стоп, критерий Келли |
| 06 | **Market Regime** | HMM-классификатор: trend/flat/volatile |
| 07 | **No-Human Protocol** | Tilt-lock, защита от revenge trading |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  FRONTEND LAYER                      │
│       React Dashboard • WebSocket • Charts           │
├─────────────────────────────────────────────────────┤
│                   API GATEWAY                        │
│     FastAPI • JWT Auth • Rate Limiting • WS Hub      │
├─────────────────────────────────────────────────────┤
│                  SIGNAL ENGINE                       │
│   Skill 1-7 • Composite Score • Risk • Executor      │
├─────────────────────────────────────────────────────┤
│                   DATA LAYER                         │
│         PostgreSQL • Redis Cache • Analytics         │
├─────────────────────────────────────────────────────┤
│               EXCHANGE CONNECTORS                    │
│      Binance WS • REST API • On-chain • NLP          │
└─────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+

### Local Development

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/apex-trading-bot.git
cd apex-trading-bot

# 2. Set up Python environment
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 3. Set up environment variables
copy .env.example .env
# Edit .env with your API keys

# 4. Install frontend dependencies
cd client
npm install
cd ..

# 5. Start the backend
uvicorn server.main:app --reload --port 8000

# 6. Start the frontend (in another terminal)
cd client
npm run dev
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `JWT_SECRET_KEY` | JWT signing key | Yes |
| `DEMO_MODE` | Run with simulated data | No (default: true) |
| `BINANCE_API_KEY` | Binance API key | No* |
| `BINANCE_API_SECRET` | Binance API secret | No* |
| `GLASSNODE_API_KEY` | Glassnode API key | No* |
| `TELEGRAM_BOT_TOKEN` | Telegram alerts bot | No |
| `TELEGRAM_CHAT_ID` | Telegram chat for alerts | No |

\* Required for live trading. Demo mode works without them.

## ☁️ Deploy to Render

This project includes a `render.yaml` blueprint for one-click deployment:

1. **Push to GitHub** — ensure your repo is on GitHub
2. **Connect Render** — go to [render.com](https://render.com), click "New" → "Blueprint"
3. **Select repo** — choose `apex-trading-bot`
4. **Deploy** — Render auto-provisions PostgreSQL, Redis, and the web service

The blueprint configures:
- 🖥️ **Web Service** — FastAPI + React static files
- 🗄️ **PostgreSQL** — Persistent data storage
- ⚡ **Redis** — Cache, queues, tilt guard state

## 📊 Dashboard

The premium React dashboard provides:
- 📈 **Equity Curve** — Real-time portfolio tracking
- 🎯 **Signal Panel** — Live signals from all 7 skills
- 📋 **Trade History** — Detailed trade log
- ⚖️ **Risk Monitor** — Position sizing, drawdown, tilt guard
- 🌊 **Regime Indicator** — Current market regime (HMM)
- 🎨 **Skill Weights** — Adaptive weight visualization

## 🔒 Security

- API keys encrypted with Fernet (never stored in plaintext)
- JWT authentication for dashboard access
- IP whitelist for exchange API keys
- Separate read-only keys for monitoring
- No withdrawal permissions on exchange keys

## ⚠️ Disclaimer

This software is for educational purposes. Cryptocurrency trading carries significant risk. Never trade with funds you cannot afford to lose. The authors are not responsible for any financial losses incurred through use of this software.

---

*Built with APEX BOT Architecture v1.0*


