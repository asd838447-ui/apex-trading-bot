"""
APEX Deep Brain Module
Handles the global context (World Model) and trade introspection (Self Model) using scikit-learn.
"""
import json
import base64
import pickle
import logging
import numpy as np
from typing import Dict, Any, Tuple
from sqlalchemy import select
from sklearn.linear_model import SGDClassifier
from datetime import datetime, timezone
import aiohttp

from server.db.database import get_session_factory
from server.db.models import BrainState
from server.config import settings

logger = logging.getLogger(__name__)

class ApexBrain:
    def __init__(self):
        # Models per symbol
        self.models: Dict[str, SGDClassifier] = {}
        # We need a fixed feature structure to ensure numpy arrays align correctly
        self.feature_names = [
            "signal_1", "signal_2", "signal_3", "signal_4",
            "fear_greed", "rsi_15m", "funding_rate", "obi", "regime_idx"
        ]
        
        # Macro data cache
        self.fear_greed_idx = 50.0  # Default neutral
        self.last_macro_update = 0

    async def initialize(self):
        """Loads serialized models from the database."""
        logger.info("Initializing APEX Deep Brain...")
        factory = get_session_factory()
        async with factory() as session:
            for symbol in settings.SUPPORTED_SYMBOLS:
                stmt = select(BrainState).filter(BrainState.symbol == symbol)
                res = await session.execute(stmt)
                record = res.scalars().first()
                if record and record.model_data:
                    try:
                        model_bytes = base64.b64decode(record.model_data)
                        self.models[symbol] = pickle.loads(model_bytes)
                        logger.info(f"Loaded Deep Brain model for {symbol}")
                    except Exception as e:
                        logger.error(f"Failed to load model for {symbol}: {e}")
                        self._create_fresh_model(symbol)
                else:
                    self._create_fresh_model(symbol)
                    
        # Fetch initial macro data
        await self.update_macro_data()

    def _create_fresh_model(self, symbol: str):
        # SGDClassifier with log_loss provides predict_proba
        model = SGDClassifier(loss='log_loss', max_iter=1000, random_state=42)
        # We must initialize it with classes [0, 1] (0 = Loss, 1 = Win)
        # We pass a dummy batch to initialize the weights
        dummy_X = np.zeros((2, len(self.feature_names)))
        dummy_y = np.array([0, 1])
        model.partial_fit(dummy_X, dummy_y, classes=np.array([0, 1]))
        self.models[symbol] = model
        logger.info(f"Created fresh Deep Brain model for {symbol}")

    async def save_models(self):
        """Serializes and saves current models to the DB."""
        factory = get_session_factory()
        async with factory() as session:
            for symbol, model in self.models.items():
                model_bytes = pickle.dumps(model)
                model_b64 = base64.b64encode(model_bytes).decode('utf-8')
                
                stmt = select(BrainState).filter(BrainState.symbol == symbol)
                res = await session.execute(stmt)
                record = res.scalars().first()
                
                if record:
                    record.model_data = model_b64
                else:
                    new_record = BrainState(symbol=symbol, model_data=model_b64)
                    session.add(new_record)
            await session.commit()
            logger.info("Saved Deep Brain models to DB.")

    async def update_macro_data(self):
        """Fetches Fear & Greed index (World Model context)."""
        now = datetime.now(timezone.utc).timestamp()
        if now - self.last_macro_update < 3600:
            return  # Update once per hour
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.alternative.me/fng/?limit=1") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        val = data.get("data", [{}])[0].get("value")
                        if val:
                            self.fear_greed_idx = float(val)
                            self.last_macro_update = now
                            logger.info(f"Deep Brain: Updated Fear & Greed Index to {self.fear_greed_idx}")
        except Exception as e:
            logger.warning(f"Failed to fetch Fear & Greed: {e}")

    def extract_features(self, symbol: str, active_signals: dict, market_state) -> dict:
        """Takes current market context and formats it for the brain."""
        # Convert regime to numeric
        regimes = {"BULL": 1, "FLAT": 0, "BEAR": -1, "VOLATILE": -2}
        regime = market_state.regimes.get(symbol, "FLAT")
        regime_idx = regimes.get(regime, 0)
        
        # Get quant alphas
        from server.skills.skill_03_onchain import get_quant_alphas
        alphas = get_quant_alphas(symbol)
        
        # Get RSI
        rsi = 50.0
        # In a real setup we'd extract this from market_state.candles, simplified here:
        if symbol in market_state.prices:
            # Placeholder, actual RSI requires technical analysis array
            pass
            
        return {
            "signal_1": active_signals.get(1, 0),
            "signal_2": active_signals.get(2, 0),
            "signal_3": active_signals.get(3, 0),
            "signal_4": active_signals.get(4, 0),
            "fear_greed": self.fear_greed_idx,
            "rsi_15m": rsi,
            "funding_rate": alphas.get("funding_rate", 0.0),
            "obi": alphas.get("obi", 0.0),
            "regime_idx": regime_idx
        }

    def _dict_to_array(self, features: dict) -> np.ndarray:
        arr = []
        for name in self.feature_names:
            arr.append(features.get(name, 0.0))
        return np.array(arr).reshape(1, -1)

    def evaluate_trade(self, symbol: str, features: dict) -> Tuple[float, str]:
        """Returns (Probability of Success, Reason)."""
        model = self.models.get(symbol)
        if not model:
            return 0.5, "No model loaded."
            
        X = self._dict_to_array(features)
        
        try:
            # predict_proba returns [[prob_loss, prob_win]]
            probs = model.predict_proba(X)[0]
            win_prob = probs[1]
        except Exception:
            return 0.5, "Prediction error (model untrained)."
            
        # Formulate reason based on extreme features
        reason = f"Win Probability: {win_prob:.1%}. "
        if win_prob < 0.5:
            reason += "Trade blocked by Brain due to low historical win rate under these specific conditions (e.g. bad Fear/Greed or Funding divergence)."
        else:
            reason += "Trade approved by Brain."
            
        if self.fear_greed_idx > 75:
            reason += " Caution: Extreme Greed in macro market."
        elif self.fear_greed_idx < 25:
            reason += " Caution: Extreme Fear in macro market."
            
        return win_prob, reason

    async def train_on_trade(self, symbol: str, features: dict, pnl: float):
        """Online learning step. If PnL > 0, label is 1 (Win), else 0 (Loss)."""
        model = self.models.get(symbol)
        if not model:
            return
            
        X = self._dict_to_array(features)
        # Binary classification: 1 for profit, 0 for loss
        y = np.array([1 if pnl > 0 else 0])
        
        try:
            # Learning rate is managed internally by SGDClassifier (invscaling/optimal)
            model.partial_fit(X, y)
            logger.info(f"Deep Brain [{symbol}]: Trained on trade (PnL: {pnl:.2f}, Label: {y[0]})")
        except Exception as e:
            logger.error(f"Failed to train brain for {symbol}: {e}")

global_brain = ApexBrain()
