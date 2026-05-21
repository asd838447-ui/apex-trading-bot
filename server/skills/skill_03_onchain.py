"""
Skill 03 – On-Chain Analytics.

Fetches key Bitcoin metrics from Glassnode and converts them into a
composite on-chain index (0-100) and a directional signal.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import aiohttp

from server.config import get_settings

logger = logging.getLogger(__name__)

# ── Glassnode metric endpoints (free tier) ──────────────────────────────
_METRICS: Dict[str, str] = {
    "sopr": "/v1/metrics/indicators/sopr",
    "nupl": "/v1/metrics/indicators/net_unrealized_profit_loss",
    "mvrv": "/v1/metrics/market/mvrv",
    "active_addresses": "/v1/metrics/addresses/active_count",
}
_BASE_URL = "https://api.glassnode.com"


async def fetch_metrics() -> Dict[str, Optional[float]]:
    """Fetch latest on-chain metrics from Glassnode.

    Returns dict ``{ metric_name: latest_value }`` or ``None`` for each
    metric that could not be fetched.
    """
    settings = get_settings()
    results: Dict[str, Optional[float]] = {}

    if not settings.has_glassnode:
        logger.info("Glassnode API key not configured – returning demo data.")
        return _demo_metrics()

    api_key = settings.GLASSNODE_API_KEY
    params_base = {"a": "BTC", "api_key": api_key, "i": "24h", "s": "0"}

    try:
        async with aiohttp.ClientSession() as session:
            for name, path in _METRICS.items():
                try:
                    url = f"{_BASE_URL}{path}"
                    async with session.get(url, params=params_base, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status != 200:
                            logger.warning(
                                "Glassnode %s returned HTTP %d", name, resp.status
                            )
                            results[name] = None
                            continue
                        data = await resp.json()
                        if data and isinstance(data, list):
                            results[name] = float(data[-1].get("v", 0))
                        else:
                            results[name] = None
                except Exception as exc:
                    logger.warning("Error fetching Glassnode %s: %s", name, exc)
                    results[name] = None
    except Exception as exc:
        logger.error("Glassnode session error: %s", exc)
        return _demo_metrics()

    return results


def _demo_metrics() -> Dict[str, Optional[float]]:
    """Return plausible dynamic demo values when no API key is set."""
    import random
    import time
    
    # Use time-based seed to make changes progressive but somewhat consistent
    seed = int(time.time() / 3600)  # changes every hour
    random.seed(seed)
    
    base_sopr = 1.02 + random.uniform(-0.05, 0.05)
    base_nupl = 0.55 + random.uniform(-0.1, 0.1)
    base_mvrv = 2.3 + random.uniform(-0.3, 0.3)
    base_aa = 950_000 + random.randint(-50000, 50000)
    
    return {
        "sopr": base_sopr,
        "nupl": base_nupl,
        "mvrv": base_mvrv,
        "active_addresses": base_aa,
    }


# ── Index ───────────────────────────────────────────────────────────────

def onchain_index(metrics: Dict[str, Optional[float]]) -> float:
    """Convert raw metrics into a 0-100 composite index.

    Higher → more bullish on-chain picture.
    """
    scores: list[float] = []

    # SOPR > 1 is bullish (profit taking is healthy); < 1 is bearish
    sopr = metrics.get("sopr")
    if sopr is not None:
        scores.append(_clamp((sopr - 0.9) / 0.2 * 100))  # 0.9 → 0, 1.1 → 100

    # NUPL: 0 → 50, >0.75 → 100 (euphoria), <-0.25 → 0 (capitulation)
    nupl = metrics.get("nupl")
    if nupl is not None:
        scores.append(_clamp((nupl + 0.25) / 1.0 * 100))

    # MVRV: 1 → 25, 3.5 → 100, <1 → 0 (undervalued)
    mvrv = metrics.get("mvrv")
    if mvrv is not None:
        scores.append(_clamp((mvrv - 0.5) / 3.0 * 100))

    # Active addresses: normalised to arbitrary baseline
    aa = metrics.get("active_addresses")
    if aa is not None:
        scores.append(_clamp(aa / 1_200_000 * 100))

    if not scores:
        return 50.0  # neutral fallback
    return round(sum(scores) / len(scores), 2)


def onchain_signal(index: float) -> int:
    """Convert index to directional signal.

    Returns:
        +1  bullish  (index > 65)
        -1  bearish  (index < 35)
         0  neutral
    """
    if index > 65:
        return 1
    if index < 35:
        return -1
    return 0


# ── Helpers ─────────────────────────────────────────────────────────────

def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))
