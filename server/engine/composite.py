"""
APEX Trading Bot — Composite Signal Engine
Взвешенная агрегация сигналов 7 навыков с адаптивными весами.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Порог уверенности для входа в позицию (0-100)
CONFIDENCE_THRESHOLD = 65.0


class CompositeEngine:
    """
    Агрегирует сигналы от навыков 1-4 (сигнальные), фильтрует по навыкам 5-7 (фильтры).
    Веса теперь задаются индивидуально для каждого символа (Asset-Specific Weights).
    """

    def __init__(self):
        default_weights = {
            1: 0.22,  # Order Flow
            2: 0.20,  # Multi-TF
            3: 0.18,  # On-Chain
            4: 0.14,  # NLP Sentiment
        }
        
        # Индивидуальные векторы весов (нормализация происходит динамически)
        self.weights_by_symbol = {
            "BTCUSDT": dict(default_weights),
            "ETHUSDT": dict(default_weights),
            "SOLUSDT": dict(default_weights),
            "HYPEUSDT": {
                1: 0.35,  # Order Flow (HYPE очень чувствителен к микроструктуре)
                2: 0.25,  # Multi-TF
                3: 0.10,  # On-Chain (Hyperliquid L1 TVL)
                4: 0.04,  # NLP Sentiment (слабо влияет)
            },
            "TONUSDT": {
                1: 0.10,  # Order Flow
                2: 0.10,  # Multi-TF
                3: 0.14,  # On-Chain (DeDust, STON.fi)
                4: 0.40,  # NLP Sentiment (TON критически зависит от инсайдов Telegram/Павла Дурова)
            }
        }
        self.signal_skills = {1, 2, 3, 4}

    def get_weight(self, symbol: str, skill_id: int) -> float:
        """Возвращает текущий вес конкретного навыка для заданного символа."""
        weights = self.weights_by_symbol.get(symbol, self.weights_by_symbol["BTCUSDT"])
        return weights.get(skill_id, 0.0)

    def evaluate(
        self,
        symbol: str,
        signals: dict[int, int],
        regime: str,
        tilt_locked: bool = False,
        drawdown_blocked: bool = False,
    ) -> dict:
        """
        Вычисляет композитный сигнал на основе голосов навыков для конкретного символа.
        """
        if tilt_locked:
            logger.warning("TILT LOCK активен — торговля заблокирована")
            return {"action": "WAIT", "confidence": 0.0, "reason": "TILT_LOCK", "regime": regime, "signals_used": {}}

        if drawdown_blocked:
            logger.warning("ANTI-REVENGE активен — просадка превышает порог")
            return {"action": "WAIT", "confidence": 0.0, "reason": "ANTI_REVENGE", "regime": regime, "signals_used": {}}

        active = set(self.signal_skills)
        if regime == "FLAT":
            active.discard(2)  # Multi-TF менее полезен во флэте
        if regime == "VOLATILE":
            active.discard(4)  # NLP может лагать при высокой волатильности, кроме TON
            if symbol == "TONUSDT":
                active.add(4) # Для TON мы всегда слушаем новости

        active_signals = {k: signals.get(k, 0) for k in active}
        weights = self.weights_by_symbol.get(symbol, self.weights_by_symbol["BTCUSDT"])

        total_weight = sum(weights[k] for k in active)
        if total_weight == 0:
            return {"action": "WAIT", "confidence": 50.0, "reason": "NO_ACTIVE_SKILLS", "regime": regime, "signals_used": active_signals}

        raw_score = sum(weights[k] * active_signals[k] for k in active)
        confidence = (raw_score / total_weight + 1) / 2 * 100

        if confidence >= CONFIDENCE_THRESHOLD:
            action = "LONG"
        elif confidence <= (100 - CONFIDENCE_THRESHOLD):
            action = "SHORT"
        else:
            action = "WAIT"

        result = {
            "action": action,
            "confidence": round(confidence, 1),
            "reason": f"COMPOSITE_{symbol}_{confidence:.0f}",
            "regime": regime,
            "signals_used": active_signals,
            "weights_used": {k: weights[k] for k in active},
            "raw_score": round(raw_score, 4),
        }

        logger.info(f"Composite [{symbol}]: action={action}, conf={confidence:.1f}%, regime={regime}")
        return result

    def update_weights(self, symbol: str, performance: dict[int, float]) -> dict[int, float]:
        """Обновляет веса навыков для конкретного символа на основе точности."""
        weights = self.weights_by_symbol.get(symbol)
        if not weights:
            return {}

        valid_skills = {k: v for k, v in performance.items() if k in self.signal_skills}
        if not valid_skills:
            return dict(weights)

        total_accuracy = sum(valid_skills.values())
        if total_accuracy <= 0:
            return dict(weights)

        for skill_id in self.signal_skills:
            if skill_id in valid_skills:
                weights[skill_id] = valid_skills[skill_id] / total_accuracy

        total = sum(weights.values())
        if total > 0:
            self.weights_by_symbol[symbol] = {k: v / total for k, v in weights.items()}

        return dict(self.weights_by_symbol[symbol])

    def get_state(self) -> dict:
        return {
            "weights": self.weights_by_symbol,
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "signal_skills": sorted(self.signal_skills),
        }
