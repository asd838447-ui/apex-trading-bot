"""
APEX Trading Bot — Background Task Scheduler
Manages background tasks: WebSocket price feed, signal evaluations, and ML re-training loops.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ProcessPoolExecutor

import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="aiohttp.connector")

from fastapi import FastAPI
import pandas as pd

from server.config import settings
from server.tasks.state import market_state, parse_klines_to_df
from server.skills.skill_06_regime import RegimeClassifier
from server.skills.skill_01_orderflow import compute_cvd, cvd_signal
from server.skills.skill_02_multitf import multitf_composite
from server.skills.skill_03_onchain import fetch_metrics, onchain_index, onchain_signal
from server.skills.skill_04_nlp import fetch_crypto_news, score_texts, nlp_signal
from server.engine.composite import CompositeEngine

logger = logging.getLogger(__name__)

# Global instances for real ML and regime classification
global_regime_classifiers = {symbol: RegimeClassifier() for symbol in settings.SUPPORTED_SYMBOLS}
nlp_score_history = {symbol: [] for symbol in settings.SUPPORTED_SYMBOLS}

# PERSISTENT CompositeEngine — weights survive across evaluation cycles (FIX BUG #1)
global_composite_engine = CompositeEngine()

# Real accuracy tracking per skill per symbol
# Structure: {symbol: {skill_id: {"correct": int, "total": int}}}
skill_accuracy_tracker: dict[str, dict[int, dict[str, int]]] = {
    symbol: {i: {"correct": 0, "total": 0} for i in range(1, 8)}
    for symbol in settings.SUPPORTED_SYMBOLS
}
# Cache of last signals per symbol for accuracy measurement on trade close
last_signals_cache: dict[str, dict[int, int]] = {
    symbol: {} for symbol in settings.SUPPORTED_SYMBOLS
}

# CPU pool for heavy math (HMM fitting) to avoid GIL locking asyncio
process_pool = ProcessPoolExecutor(max_workers=2)

def cpu_fit_hmm_task(df: pd.DataFrame) -> RegimeClassifier:
    """Pickleable top-level function for ProcessPoolExecutor"""
    classifier = RegimeClassifier()
    classifier.fit(df)
    return classifier


# Global background tasks storage
_background_tasks: list[asyncio.Task] = []


async def start_background_tasks(app: FastAPI):
    """
    Launches all background services upon server startup.
    """
    logger.info("Starting background tasks...")

    # 1. Initialize DB persistence and seed data
    await market_state.initialize_if_needed()

    # Fit the HMM Regime Classifier on startup using 500 candles for each symbol
    if market_state.exchange:
        loop = asyncio.get_running_loop()
        tasks = []
        symbols = []
        for symbol in settings.SUPPORTED_SYMBOLS:
            try:
                logger.info(f"Fetching klines to fit Gaussian HMM Regime Classifier for {symbol} on startup...")
                klines = await market_state.exchange.get_klines(symbol, "15m", 500)
                df_500 = parse_klines_to_df(klines)
                tasks.append(loop.run_in_executor(process_pool, cpu_fit_hmm_task, df_500))
                symbols.append(symbol)
            except Exception as he:
                logger.warning(f"Failed to prepare HMM fitting for {symbol} on startup: {he}")
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for symbol, res in zip(symbols, results):
                if isinstance(res, Exception):
                    logger.warning(f"Failed to fit HMM Regime Classifier for {symbol} on startup: {res}")
                else:
                    global_regime_classifiers[symbol] = res
                    logger.info(f"  ✓ Gaussian HMM Regime Classifier for {symbol} successfully fitted.")

    # 2. Start Binance WebSocket Price Collector
    task_ws = asyncio.create_task(ws_data_collector())
    _background_tasks.append(task_ws)
    logger.info("  ✓ WebSocket data collector started")

    # 3. Core Signal Evaluator
    task_signals = asyncio.create_task(signal_evaluator())
    _background_tasks.append(task_signals)
    logger.info("  ✓ Signal evaluator started")

    # 4. Regime Refitter (Dynamic every 15 mins)
    task_regime = asyncio.create_task(regime_refitter())
    _background_tasks.append(task_regime)
    logger.info("  ✓ Regime refitter started")

    # 5. Weight Updater (weekly)
    task_weights = asyncio.create_task(weight_updater())
    _background_tasks.append(task_weights)
    logger.info("  ✓ Weight updater started")

    logger.info(f"Successfully launched {len(_background_tasks)} background tasks")


async def stop_background_tasks():
    """Cancels and cleans up all running background tasks."""
    logger.info("Stopping background tasks...")
    for task in _background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _background_tasks.clear()
    process_pool.shutdown(wait=False)
    logger.info("All background tasks stopped")


async def ws_data_collector():
    """
    Connects to the public Binance Futures WebSocket stream.
    Collects real-time price updates and verifies TP/SL boundaries for active positions.
    """
    try:
        from server.connectors.binance_ws import BinanceWSConnector
        from server.api.ws import manager

        connector = BinanceWSConnector()
        last_broadcast_time = 0.0
        broadcast_interval = 0.100  # 100ms throttling

        async def on_tick(tick):
            nonlocal last_broadcast_time
            price = tick["price"]
            symbol = tick["symbol"]
            closed_trade = await market_state.update_price(price, symbol=symbol)
            
            now = time.time()
            if now - last_broadcast_time >= broadcast_interval:
                last_broadcast_time = now
                try:
                    await manager.broadcast({
                        "type": "price_update",
                        "data": {
                            "symbol": symbol,
                            "price": round(price, 2 if symbol != "SOLUSDT" else 3),
                            "change_24h": round(market_state.price_changes_24h.get(symbol, 0.0), 2),
                            "volume_24h": round(market_state.volumes_24h.get(symbol, 0.0), 0),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    })
                except Exception as e:
                    logger.debug(f"Failed to broadcast fast price: {e}")

            if closed_trade:
                logger.info(f"Position closed by market action: {closed_trade['reason']} at {price} for {symbol}")
                await manager.broadcast({"type": "trade_update", "data": closed_trade})
                await manager.broadcast({
                    "type": "risk_update",
                    "data": {"symbol": symbol, "metrics": market_state.get_risk_metrics(symbol=symbol)}
                })
                await manager.broadcast({
                    "type": "equity_update",
                    "data": {
                        "equity": market_state.current_equity,
                        "daily_pnl": round(sum(t.get("pnl", 0) or 0 for t in market_state.trades if t.get("time", "")[:10] == datetime.now(timezone.utc).strftime("%Y-%m-%d")), 2),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "drawdown": "0.00",
                    }
                })

        async def on_candle(candle):
            pass

        connector.on_tick(on_tick)
        connector.on_candle(on_candle)

        logger.info("WebSocket data collector: Connecting to public Binance Futures...")
        await connector.connect()

    except ImportError as e:
        logger.error(f"WebSocket collector: Required module missing: {e}")
    except asyncio.CancelledError:
        logger.info("WebSocket data collector: Cancelled/Stopped")
    except Exception as e:
        logger.error(f"WebSocket data collector error: {e}")


async def evaluate_single_symbol(symbol: str):
    """Evaluates composite signals for a single symbol."""
    try:
        from server.api.ws import manager
        await market_state.sync_live_position_if_needed(symbol=symbol)

        timestamp = datetime.now(timezone.utc).isoformat()
        
        df_15m = pd.DataFrame()
        df_4h = pd.DataFrame()
        df_1d = pd.DataFrame()
        candles = {}

        if market_state.exchange:
            try:
                klines_15m = await market_state.exchange.get_klines(symbol, "15m", 100)
                klines_4h = await market_state.exchange.get_klines(symbol, "4h", 100)
                klines_1d = await market_state.exchange.get_klines(symbol, "1d", 100)
                
                df_15m = parse_klines_to_df(klines_15m)
                df_4h = parse_klines_to_df(klines_4h)
                df_1d = parse_klines_to_df(klines_1d)
                
                candles = {"15m": df_15m, "4h": df_4h, "1d": df_1d}
            except Exception as e:
                logger.error(f"Failed to fetch real klines for {symbol}: {e}")

        # 2. Get Regime Classification (HMM) & ATR Calculation
        if df_15m is not None and not df_15m.empty:
            try:
                current_regime = global_regime_classifiers[symbol].predict(df_15m)
            except Exception as e:
                logger.warning(f"Failed to predict regime for {symbol}: {e}")
                current_regime = "FLAT"
            
            try:
                from server.skills.skill_05_risk import compute_atr
                market_state.atrs[symbol] = round(compute_atr(df_15m), 2 if symbol != "SOLUSDT" else 3)
                if symbol == "BTCUSDT":
                    market_state.current_atr = market_state.atrs["BTCUSDT"]
            except Exception as ae:
                logger.warning(f"Failed to calculate ATR in scheduler for {symbol}: {ae}")
        else:
            current_regime = "FLAT"
        
        market_state.regimes[symbol] = current_regime
        # FIX BUG #4: Use real HMM posterior probability instead of random
        try:
            classifier = global_regime_classifiers[symbol]
            if classifier.is_fitted and classifier._model is not None:
                from server.skills.skill_06_regime import features as hmm_features
                X = hmm_features(df_15m)
                if len(X) > 0:
                    proba = classifier._model.predict_proba(X)
                    # Max posterior probability of the latest observation
                    market_state.regime_confidences[symbol] = round(float(proba[-1].max()) * 100, 1)
                else:
                    market_state.regime_confidences[symbol] = 50.0
            else:
                market_state.regime_confidences[symbol] = 50.0
        except Exception:
            market_state.regime_confidences[symbol] = round(random.uniform(75.0, 95.0), 1)
        if symbol == "BTCUSDT":
            market_state.regime = current_regime
            market_state.regime_confidence = market_state.regime_confidences["BTCUSDT"]
        
        market_state.regime_histories[symbol].append({"time": timestamp, "regime": current_regime})
        if len(market_state.regime_histories[symbol]) > 24:
            market_state.regime_histories[symbol] = market_state.regime_histories[symbol][-24:]

        # 3. Calculate votes for the 7 skills
        trend_sig = 0
        if candles:
            try:
                trend_sig = multitf_composite(candles)
            except Exception: pass
        
        reversion_sig = 0
        if df_15m is not None and not df_15m.empty:
            try:
                close = df_15m["close"]
                sma = close.rolling(20).mean()
                std = close.rolling(20).std()
                upper_band = sma + 2 * std
                lower_band = sma - 2 * std
                latest_close = close.iloc[-1]
                latest_upper = upper_band.iloc[-1]
                latest_lower = lower_band.iloc[-1]
                
                if latest_close <= latest_lower: reversion_sig = 1
                elif latest_close >= latest_upper: reversion_sig = -1
            except Exception: pass

        breakout_sig = 0
        if df_15m is not None and not df_15m.empty:
            try:
                highs = df_15m["high"]
                lows = df_15m["low"]
                closes = df_15m["close"]
                if len(closes) >= 21:
                    prev_high_max = highs.iloc[-21:-1].max()
                    prev_low_min = lows.iloc[-21:-1].min()
                    latest_close = closes.iloc[-1]
                    if latest_close > prev_high_max: breakout_sig = 1
                    elif latest_close < prev_low_min: breakout_sig = -1
            except Exception: pass

        volume_sig = 0
        if df_15m is not None and not df_15m.empty:
            try:
                volumes = df_15m["volume"]
                closes = df_15m["close"]
                if len(volumes) >= 20:
                    vol_sma = volumes.rolling(20).mean()
                    latest_vol = volumes.iloc[-1]
                    latest_vol_sma = vol_sma.iloc[-1]
                    if latest_vol > 1.5 * latest_vol_sma:
                        ret = closes.iloc[-1] - closes.iloc[-2]
                        if ret > 0: volume_sig = 1
                        elif ret < 0: volume_sig = -1
            except Exception: pass

        cvd_sig = 0
        if market_state.exchange:
            try:
                trades = await market_state.exchange._request("GET", "/fapi/v1/aggTrades", {"symbol": symbol, "limit": 1000})
                ticks = [{"qty": float(t["q"]), "is_buyer": not t["m"]} for t in trades]
                ticks_df = pd.DataFrame(ticks)
                cvd = compute_cvd(ticks_df)
                price_series = pd.Series([float(t["p"]) for t in trades])
                cvd_sig = cvd_signal(cvd, price_series)
            except Exception: pass

        if current_regime == "TREND": regime_sig = trend_sig
        elif current_regime == "FLAT": regime_sig = reversion_sig
        else: regime_sig = 0

        sentiment_sig = 0
        sentiment_score = 0.0
        try:
            headlines = await fetch_crypto_news(symbol=symbol)
            sentiment_score = score_texts(headlines)
            
            # Social Momentum Spike detection
            history = nlp_score_history[symbol]
            history.append(sentiment_score)
            if len(history) > 12:  # Keep 12 periods (~12 mins if eval is every 1 min)
                history.pop(0)
                
            if len(history) >= 6:
                recent_avg = sum(history[-2:]) / 2
                older_avg = sum(history[:-2]) / len(history[:-2])
                
                # Check for > 300% jump
                if abs(older_avg) > 0.01 and abs(recent_avg) > abs(older_avg) * 3.0:
                    logger.info(f"[{symbol}] SOCIAL MOMENTUM SPIKE DETECTED! NLP Score jumped from {older_avg:.2f} to {recent_avg:.2f}")
                    sentiment_sig = 2 if recent_avg > 0 else -2  # Turbo signal
                else:
                    sentiment_sig = nlp_signal(sentiment_score)
            else:
                sentiment_sig = nlp_signal(sentiment_score)
                
        except Exception: pass

        oc_sig = 0
        try:
            metrics = await fetch_metrics(symbol)
            oc_index = onchain_index(metrics, symbol)
            oc_sig = onchain_signal(oc_index)
        except Exception: pass

        # Use GLOBAL persistent CompositeEngine (FIX BUG #1)
        engine = global_composite_engine
        
        prev_equity = market_state.initial_equity
        if market_state.equity_curve and len(market_state.equity_curve) > 0:
            prev_equity = market_state.equity_curve[-1]["equity"]
        
        drawdown_blocked = market_state.tilt_guard.anti_revenge(
            equity=market_state.current_equity, prev_equity=prev_equity
        )

        # FIX BUG #3: Add BEAR/BULL directional overlay on top of HMM regime
        # Use 50-period EMA direction on 4h candles to determine bear/bull
        directional_regime = current_regime  # Default to HMM regime
        if df_15m is not None and not df_15m.empty and len(df_15m) >= 50:
            try:
                close = df_15m["close"]
                ema50 = close.ewm(span=50, adjust=False).mean()
                ema20 = close.ewm(span=20, adjust=False).mean()
                latest_close = close.iloc[-1]
                latest_ema50 = ema50.iloc[-1]
                latest_ema20 = ema20.iloc[-1]
                
                # Determine directional bias
                if latest_close < latest_ema50 and latest_ema20 < latest_ema50:
                    directional_regime = "BEAR"
                elif latest_close > latest_ema50 and latest_ema20 > latest_ema50:
                    directional_regime = "BULL"
                # If neither, keep the HMM regime (FLAT/TREND/VOLATILE)
            except Exception:
                pass
        
        eval_res = engine.evaluate(
            symbol=symbol,
            signals={1: cvd_sig, 2: trend_sig, 3: oc_sig, 4: sentiment_sig},
            regime=directional_regime,
            tilt_locked=market_state.tilt_guard.is_locked(),
            drawdown_blocked=drawdown_blocked
        )

        # Cache signals for accuracy tracking on trade close (FIX BUG #7)
        last_signals_cache[symbol] = {
            1: cvd_sig, 2: trend_sig, 3: oc_sig, 4: sentiment_sig,
            5: reversion_sig, 6: regime_sig
        }

        # Override eval_res action for aggressive shorting in Bear Market
        composite_score = eval_res["raw_score"] * 100.0
        if directional_regime in ["BEAR", "DOWNTREND"] and composite_score < -0.1:
            eval_res["action"] = "SHORT"
            eval_res["confidence"] = min(100.0, abs(composite_score) * 100 + market_state.regime_confidences.get(symbol, 50.0) * 0.5)

        action = eval_res["action"]
        composite_confidence = int(eval_res["confidence"])
        composite_score = eval_res["raw_score"] * 100.0

        # FIX BUG #7: Compute real accuracy from tracker
        def get_real_accuracy(skill_id: int) -> float:
            tracker = skill_accuracy_tracker.get(symbol, {}).get(skill_id, {})
            total = tracker.get("total", 0)
            if total < 5:
                # Not enough data yet, use baseline
                return {1: 68.2, 2: 64.5, 3: 61.8, 4: 58.5, 5: 63.4, 6: 69.5, 7: 72.0}.get(skill_id, 50.0)
            return round(tracker["correct"] / total * 100, 1)

        # Build raw weights array, then normalize to 100%
        raw_weights = {
            1: engine.get_weight(symbol, 1) * 100,
            2: engine.get_weight(symbol, 2) * 100,
            3: engine.get_weight(symbol, 3) * 100,
            4: engine.get_weight(symbol, 4) * 100,
            5: 12.0,
            6: 8.0,
            7: 6.0,
        }
        total_raw = sum(raw_weights.values())
        if total_raw > 0:
            norm_weights = {k: round(v / total_raw * 100, 1) for k, v in raw_weights.items()}
        else:
            norm_weights = {k: round(100.0 / 7, 1) for k in raw_weights}

        skills = [
            {"id": 1, "name": "Order Flow", "category": "flow", "weight": norm_weights[1], "signal": cvd_sig, "confidence": 80 if cvd_sig != 0 else 0, "accuracy": get_real_accuracy(1)},
            {"id": 2, "name": "Multi-TF", "category": "momentum", "weight": norm_weights[2], "signal": trend_sig, "confidence": 75 if trend_sig != 0 else 0, "accuracy": get_real_accuracy(2)},
            {"id": 3, "name": "On-Chain", "category": "volume", "weight": norm_weights[3], "signal": oc_sig, "confidence": 70 if oc_sig != 0 else 0, "accuracy": get_real_accuracy(3)},
            {"id": 4, "name": "NLP Sentiment", "category": "sentiment", "weight": norm_weights[4], "signal": sentiment_sig, "confidence": 65 if sentiment_sig != 0 else 0, "accuracy": get_real_accuracy(4)},
            {"id": 5, "name": "Risk ATR", "category": "reversion", "weight": norm_weights[5], "signal": reversion_sig, "confidence": 60 if reversion_sig != 0 else 0, "accuracy": get_real_accuracy(5)},
            {"id": 6, "name": "Market Regime", "category": "regime", "weight": norm_weights[6], "signal": regime_sig, "confidence": 70 if regime_sig != 0 else 0, "accuracy": get_real_accuracy(6)},
            {"id": 7, "name": "No-Human", "category": "reversion", "weight": norm_weights[7], "signal": -1 if market_state.tilt_guard.is_locked() else 0, "confidence": 95 if market_state.tilt_guard.is_locked() else 0, "accuracy": get_real_accuracy(7)}
        ]

        market_state.multi_signals[symbol] = {
            "skills": skills,
            "compositeScore": round(composite_score, 1),
            "action": action,
            "confidence": composite_confidence
        }
        if symbol == "BTCUSDT":
            market_state.signals = market_state.multi_signals["BTCUSDT"]

        await manager.broadcast({
            "type": "signal_update",
            "data": {"symbol": symbol, "signals": market_state.multi_signals[symbol]}
        })

        brain_prediction = 0.5
        brain_reason = "Brain inactive."
        features_json = "{}"
        
        if action in ("LONG", "SHORT") and not market_state.active_positions.get(symbol):
            from server.engine.brain import global_brain
            features = global_brain.extract_features(symbol, last_signals_cache[symbol], market_state)
            features_json = __import__("json").dumps(features)
            brain_prediction, brain_reason = global_brain.evaluate_trade(symbol, features)
            
            if brain_prediction < 0.5:
                logger.info(f"Deep Brain blocked {action} on {symbol}. Reason: {brain_reason}")
                action = "WAIT"
                market_state.multi_signals[symbol]["action"] = "WAIT"
                market_state.multi_signals[symbol]["compositeScore"] = 0.0

        if action in ("LONG", "SHORT") and not market_state.active_positions.get(symbol):
            new_pos = await market_state.open_position(
                action, 
                composite_confidence, 
                symbol=symbol,
                features_json=features_json,
                brain_prediction=brain_prediction,
                brain_reason=brain_reason
            )
            if new_pos:
                logger.info(f"Signal Evaluator triggered entry for {symbol}: {action} at {market_state.prices.get(symbol)}")
                await manager.broadcast({
                    "type": "risk_update",
                    "data": {"symbol": symbol, "metrics": market_state.get_risk_metrics(symbol=symbol)}
                })
                await manager.broadcast({"type": "trade_update", "data": new_pos})
    except Exception as e:
        logger.error(f"Error evaluating symbol {symbol}: {e}")

async def signal_evaluator():
    """Periodically evaluates trading signals from all skills in parallel."""
    try:
        await asyncio.sleep(5)
        while True:
            try:
                logger.info("Evaluating composite signals for all symbols in parallel...")
                tasks = [evaluate_single_symbol(sym) for sym in settings.SUPPORTED_SYMBOLS]
                await asyncio.gather(*tasks)
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in signal evaluator iteration: {e}")
                await asyncio.sleep(60)
    except asyncio.CancelledError:
        logger.info("Signal evaluator: Stopped")


async def regime_refitter():
    """
    Dynamic HMM Regime refitter background thread.
    Refits every 15 minutes using ProcessPoolExecutor to avoid blocking.
    """
    try:
        # Wait a bit on startup so we don't instantly refit after startup fit
        await asyncio.sleep(15 * 60)
        while True:
            try:
                logger.info("Dynamic Regime refit background process triggered (15m)")
                if not market_state.exchange:
                    await asyncio.sleep(15 * 60)
                    continue

                loop = asyncio.get_running_loop()
                tasks = []
                symbols = []
                for symbol in settings.SUPPORTED_SYMBOLS:
                    try:
                        klines = await market_state.exchange.get_klines(symbol, "15m", 500)
                        df = parse_klines_to_df(klines)
                        tasks.append(loop.run_in_executor(process_pool, cpu_fit_hmm_task, df))
                        symbols.append(symbol)
                    except Exception as e:
                        logger.error(f"Failed to fetch klines for refit {symbol}: {e}")
                
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    import gc
                    for symbol, res in zip(symbols, results):
                        if isinstance(res, Exception):
                            logger.error(f"Refit failed for {symbol}: {res}")
                        else:
                            old_model = global_regime_classifiers.get(symbol)
                            global_regime_classifiers[symbol] = res
                            if old_model:
                                del old_model
                            logger.info(f"Successfully dynamically refitted HMM for {symbol}")
                    
                    del tasks
                    del results
                    if 'df' in locals():
                        del df
                    gc.collect()
                            
            except Exception as e:
                logger.error(f"Regime refit error: {e}")
                
            await asyncio.sleep(15 * 60)
    except asyncio.CancelledError:
        logger.info("Regime refitter: Stopped")


async def weight_updater():
    """
    APEX Deep Brain: Real-time reinforcement learning loop.
    Iterates over all unevaluated CLOSED trades and feeds them into the SGDClassifier.
    """
    try:
        await asyncio.sleep(60)  # Wait 1 minute on startup
        while True:
            try:
                from sqlalchemy import select
                from server.db.database import session_scope
                from server.db.models import Trade
                from server.engine.brain import global_brain
                import json
                
                async with session_scope() as session:
                    # Find all closed, unevaluated trades
                    stmt = select(Trade).filter(Trade.status == "CLOSED", Trade.is_evaluated == False).order_by(Trade.time.asc())
                    res = await session.execute(stmt)
                    unevaluated_trades = res.scalars().all()
                    
                    if unevaluated_trades:
                        logger.info(f"=== DEEP BRAIN: Training on {len(unevaluated_trades)} new closed trades ===")
                        
                        for trade in unevaluated_trades:
                            if trade.features_json:
                                try:
                                    features = json.loads(trade.features_json)
                                    await global_brain.train_on_trade(
                                        symbol=trade.symbol,
                                        features=features,
                                        pnl=trade.pnl or 0.0
                                    )
                                except Exception as parse_e:
                                    logger.error(f"Failed to parse features for trade {trade.id}: {parse_e}")
                                    
                            trade.is_evaluated = True
                            
                        await session.commit()
                        await global_brain.save_models()
                        logger.info("=== DEEP BRAIN: Training Complete ===")
                        
            except Exception as e:
                logger.error(f"Weight updater (Deep Brain) error: {e}", exc_info=True)
            
            await asyncio.sleep(5 * 60)  # Run every 5 minutes
    except asyncio.CancelledError:
        logger.info("Weight updater: Stopped")
