"""
Skill 04 – NLP Sentiment Analysis (Lightweight).

Uses VADER (no GPU required) instead of FinBERT to stay
deployable on free-tier hosts like Render.
Aggregates crypto news from free RSS/API sources.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded VADER to avoid startup cost if skill not used
# ---------------------------------------------------------------------------
_vader: Optional[object] = None


def _get_vader():
    global _vader
    if _vader is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            _vader = SentimentIntensityAnalyzer()
        except ImportError:
            logger.warning(
                "vaderSentiment not installed – sentiment will default to neutral. "
                "pip install vaderSentiment"
            )
    return _vader


# ── Scoring ─────────────────────────────────────────────────────────────

def score_texts(texts: List[str]) -> float:
    """Return average compound sentiment in [-1, 1].

    Falls back to 0.0 (neutral) if VADER is unavailable or *texts* is empty.
    """
    if not texts:
        return 0.0

    analyzer = _get_vader()
    if analyzer is None:
        return 0.0

    compounds: list[float] = []
    for text in texts:
        try:
            score = analyzer.polarity_scores(text)  # type: ignore[union-attr]
            compounds.append(score["compound"])
        except Exception as exc:
            logger.debug("VADER error on text: %s", exc)

    if not compounds:
        return 0.0
    return sum(compounds) / len(compounds)


def nlp_signal(sentiment_score: float, news_weight: float = 1.0) -> int:
    """Convert weighted sentiment into directional signal.

    Args:
        sentiment_score: Average compound score in ``[-1, 1]``.
        news_weight: Multiplier for recency/relevance (default 1.0).

    Returns:
        +1  bullish  (weighted score > 0.25)
        -1  bearish  (weighted score < -0.25)
         0  neutral
    """
    weighted = sentiment_score * news_weight
    if weighted > 0.25:
        return 1
    if weighted < -0.25:
        return -1
    return 0


# ── News aggregation ────────────────────────────────────────────────────

_NEWS_SOURCES = [
    # CryptoPanic free API (no key needed for public feed)
    "https://cryptopanic.com/api/free/v1/posts/?currencies=BTC&kind=news",
]


async def fetch_crypto_news() -> List[str]:
    """Aggregate headlines from free crypto-news APIs.

    Returns a list of headline strings. On failure returns empty list.
    """
    headlines: List[str] = []

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        proxy = settings.PROXY_URL if settings.PROXY_URL else None
        async with aiohttp.ClientSession(connector=connector) as session:
            for url in _NEWS_SOURCES:
                try:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=10), proxy=proxy
                    ) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json(content_type=None)
                        results = data.get("results", [])
                        for item in results[:20]:
                            title = item.get("title")
                            if title:
                                headlines.append(title)
                except Exception as exc:
                    logger.debug("News source error (%s): %s", url, exc)
    except Exception as exc:
        logger.warning("News fetch session error: %s", exc)

    if not headlines:
        logger.info("No live headlines available. Defaulting to neutral sentiment.")

    return headlines
