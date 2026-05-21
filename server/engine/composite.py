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
    Веса адаптируются еженедельно на основе точности каждого навыка.
    """

    def __init__(self):
        # Начальные веса сигнальных навыков (адаптируются еженедельно)
        self.weights: dict[int, float] = {
            1: 0.22,  # Order Flow
            2: 0.20,  # Multi-TF
            3: 0.18,  # On-Chain
            4: 0.14,  # NLP Sentiment
        }
        # Навыки 5-7 — фильтры, не участвуют в голосовании
        self.signal_skills = {1, 2, 3, 4}

    def evaluate(
        self,
        signals: dict[int, int],
        regime: str,
        tilt_locked: bool = False,
        drawdown_blocked: bool = False,
    ) -> dict:
        """
        Вычисляет композитный сигнал на основе голосов навыков.

        Args:
            signals: {skill_id: score} где score ∈ {-1, 0, +1}
            regime: Текущий режим рынка ('FLAT', 'TREND', 'VOLATILE')
            tilt_locked: True если TiltGuard активирован
            drawdown_blocked: True если превышена просадка (anti-revenge)

        Returns:
            dict с ключами: action, confidence, reason, regime, signals_used
        """
        # Проверка блокировок (Skill 07 — No-Human Protocol)
        if tilt_locked:
            logger.warning("TILT LOCK активен — торговля заблокирована")
            return {
                "action": "WAIT",
                "confidence": 0.0,
                "reason": "TILT_LOCK",
                "regime": regime,
                "signals_used": {},
            }

        if drawdown_blocked:
            logger.warning("ANTI-REVENGE активен — просадка превышает порог")
            return {
                "action": "WAIT",
                "confidence": 0.0,
                "reason": "ANTI_REVENGE",
                "regime": regime,
                "signals_used": {},
            }

        # Определяем активные навыки на основе режима рынка (Skill 06)
        active = set(self.signal_skills)
        if regime == "FLAT":
            active.discard(2)  # Multi-TF менее полезен во флэте
        if regime == "VOLATILE":
            active.discard(4)  # NLP лагает в волатильности

        # Фильтруем сигналы только по активным навыкам
        active_signals = {k: signals.get(k, 0) for k in active}

        # Вычисляем взвешенную сумму
        total_weight = sum(self.weights[k] for k in active)
        if total_weight == 0:
            return {
                "action": "WAIT",
                "confidence": 50.0,
                "reason": "NO_ACTIVE_SKILLS",
                "regime": regime,
                "signals_used": active_signals,
            }

        raw_score = sum(self.weights[k] * active_signals[k] for k in active)

        # Нормализация в диапазон 0-100
        # raw_score ∈ [-total_weight, +total_weight]
        confidence = (raw_score / total_weight + 1) / 2 * 100

        # Определение действия
        if confidence >= CONFIDENCE_THRESHOLD:
            action = "LONG"
        elif confidence <= (100 - CONFIDENCE_THRESHOLD):
            action = "SHORT"
        else:
            action = "WAIT"

        result = {
            "action": action,
            "confidence": round(confidence, 1),
            "reason": f"COMPOSITE_SCORE_{confidence:.0f}",
            "regime": regime,
            "signals_used": active_signals,
            "weights_used": {k: self.weights[k] for k in active},
            "raw_score": round(raw_score, 4),
        }

        logger.info(
            f"Composite: action={action}, confidence={confidence:.1f}%, "
            f"regime={regime}, active_skills={sorted(active)}"
        )

        return result

    def update_weights(self, performance: dict[int, float]) -> dict[int, float]:
        """
        Обновляет веса навыков на основе их точности за последние 30 дней.

        Args:
            performance: {skill_id: accuracy} где accuracy ∈ [0.0, 1.0]

        Returns:
            Обновлённые веса
        """
        valid_skills = {k: v for k, v in performance.items() if k in self.signal_skills}
        if not valid_skills:
            logger.warning("Нет данных для обновления весов")
            return dict(self.weights)

        total_accuracy = sum(valid_skills.values())
        if total_accuracy <= 0:
            logger.warning("Суммарная точность = 0, веса не обновлены")
            return dict(self.weights)

        old_weights = dict(self.weights)

        for skill_id in self.signal_skills:
            if skill_id in valid_skills:
                self.weights[skill_id] = valid_skills[skill_id] / total_accuracy
            # Если навыка нет в performance — оставляем текущий вес

        # Нормализация (на случай если не все навыки в performance)
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

        logger.info(
            f"Веса обновлены: {old_weights} -> {self.weights}"
        )

        return dict(self.weights)

    def get_state(self) -> dict:
        """Возвращает текущее состояние движка для API/Dashboard."""
        return {
            "weights": dict(self.weights),
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "signal_skills": sorted(self.signal_skills),
        }
