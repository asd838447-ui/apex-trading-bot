"""
Skill 04 – NLP Sentiment Analysis (Lightweight).

Uses a hybrid approach:
1. VADER for general English sentiment.
2. Custom Crypto Lexicon for slang (LFG, rekt, moon).
3. Telegram Web Scraper (t.me/s/...) for TON/HYPE insider data.
4. CryptoPanic for BTC/ETH/SOL.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

import aiohttp
from server.config import settings

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
            logger.warning("vaderSentiment not installed. Fallback to basic.")
    return _vader

# ── Crypto Lexicon ──────────────────────────────────────────────────────

CRYPTO_LEXICON = {
    "moon": 1.5,
    "pump": 1.5,
    "bullish": 1.5,
    "ath": 1.0,
    "lfg": 1.0,
    "gem": 1.0,
    "hodl": 0.5,
    "airdrop": 1.5,
    "partnership": 1.0,
    "listing": 1.5,
    "adopted": 1.0,
    "ton": 0.5,
    "hype": 0.5,
    
    "dump": -1.5,
    "bearish": -1.5,
    "rekt": -1.5,
    "fud": -1.0,
    "scam": -2.0,
    "hack": -2.0,
    "rug": -2.0,
    "delist": -2.0,
    "ban": -1.5,
}

def crypto_score_text(text: str) -> float:
    text_lower = text.lower()
    score = 0.0
    for word, val in CRYPTO_LEXICON.items():
        # Match whole words to avoid partial matches
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            score += val
    return score

# ── Scoring ─────────────────────────────────────────────────────────────

def score_texts(texts: List[str]) -> float:
    """Return average sentiment combining VADER and Crypto Lexicon."""
    if not texts:
        return 0.0

    analyzer = _get_vader()
    compounds: list[float] = []
    
    for text in texts:
        score = 0.0
        # VADER Score
        if analyzer:
            try:
                v_score = analyzer.polarity_scores(text)
                score += v_score["compound"]
            except Exception:
                pass
        
        # Add Custom Crypto Lexicon Score
        score += crypto_score_text(text)
        
        # Clamp between -1 and 1
        score = max(-1.0, min(1.0, score))
        compounds.append(score)

    if not compounds:
        return 0.0
    return sum(compounds) / len(compounds)

def nlp_signal(sentiment_score: float, news_weight: float = 1.0) -> int:
    weighted = sentiment_score * news_weight
    if weighted > 0.25:
        return 1
    if weighted < -0.25:
        return -1
    return 0

# ── News aggregation ────────────────────────────────────────────────────

async def scrape_telegram_channel(channel: str, proxy: Optional[str] = None) -> List[str]:
    """Scrapes public Telegram channels without API keys."""
    url = f"https://t.me/s/{channel}"
    texts = []
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, timeout=10, proxy=proxy) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    matches = re.findall(r'<div class="tgme_widget_message_text js-message_text".*?>(.*?)</div>', html, re.DOTALL)
                    for match in matches:
                        clean_text = re.sub(r'<[^>]+>', ' ', match)
                        texts.append(clean_text.strip())
    except Exception as e:
        logger.debug(f"Failed to scrape Telegram {channel}: {e}")
    return texts[-15:] # Return last 15 posts

async def fetch_crypto_news(symbol: str = "BTCUSDT") -> List[str]:
    """Aggregate headlines based on the specific asset."""
    headlines: List[str] = []
    proxy = settings.PROXY_URL if settings.PROXY_URL else None

    # Custom sources per asset
    if symbol == "TONUSDT":
        headlines.extend(await scrape_telegram_channel("durov", proxy))
        headlines.extend(await scrape_telegram_channel("toncoin", proxy))
        headlines.extend(await scrape_telegram_channel("toncoin_rus", proxy))
        return headlines
        
    elif symbol == "HYPEUSDT":
        headlines.extend(await scrape_telegram_channel("HyperliquidX", proxy))
        # HYPE might not have a huge TG presence, but we can search for generic hype
        headlines.extend(await scrape_telegram_channel("DeFiRaccoons", proxy))
        return headlines

    # Default CryptoPanic for BTC, ETH, SOL
    base_asset = symbol.replace("USDT", "")
    url = f"https://cryptopanic.com/api/free/v1/posts/?currencies={base_asset}&kind=news"
    
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.get(url, timeout=10, proxy=proxy) as resp:
                    if resp.status == 200:
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
        logger.info(f"No live headlines available for {symbol}. Defaulting to neutral sentiment.")

    return headlines
