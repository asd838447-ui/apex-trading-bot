"""
APEX Batch ML Training
Trains XGBoost models offline using historical trade data from the database.
"""
import os
import json
import logging
import asyncio
import numpy as np
import xgboost as xgb
import joblib
from sqlalchemy import select

from server.db.database import session_scope
from server.db.models import Trade

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODELS_DIR, exist_ok=True)

async def train_batch_models():
    """Trains an XGBoost model for each symbol using historical trades."""
    logger.info("Starting Batch ML XGBoost training...")
    
    async with session_scope() as session:
        stmt = select(Trade).filter(Trade.status == "CLOSED", Trade.features_json != None)
        res = await session.execute(stmt)
        trades = res.scalars().all()
        
    if not trades:
        logger.warning("No closed trades with features found for Batch ML.")
        return
        
    # Group trades by symbol
    trades_by_symbol = {}
    for t in trades:
        if t.symbol not in trades_by_symbol:
            trades_by_symbol[t.symbol] = []
        trades_by_symbol[t.symbol].append(t)
        
    for symbol, symbol_trades in trades_by_symbol.items():
        if len(symbol_trades) < 10:
            logger.info(f"Not enough data to train XGBoost for {symbol} ({len(symbol_trades)} trades). Minimum 10.")
            continue
            
        X = []
        y = []
        
        # Consistent feature order
        feature_names = [
            "signal_1", "signal_2", "signal_3", "signal_4",
            "fear_greed", "rsi_15m", "funding_rate", "obi", "regime_idx"
        ]
        
        for t in symbol_trades:
            try:
                features = json.loads(t.features_json)
                arr = [features.get(n, 0.0) for n in feature_names]
                X.append(arr)
                # 1 if profit, 0 if loss
                y.append(1 if (t.pnl and t.pnl > 0) else 0)
            except Exception as e:
                logger.warning(f"Error parsing features for trade {t.id}: {e}")
                
        if not X:
            continue
            
        X_np = np.array(X)
        y_np = np.array(y)
        
        # Train XGBoost
        model = xgb.XGBClassifier(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=4,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42
        )
        
        logger.info(f"Training XGBoost for {symbol} on {len(X_np)} samples...")
        model.fit(X_np, y_np)
        
        # Save with joblib
        model_path = os.path.join(MODELS_DIR, f"xgb_{symbol}.joblib")
        joblib.dump(model, model_path)
        logger.info(f"Saved {symbol} XGBoost model to {model_path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(train_batch_models())
