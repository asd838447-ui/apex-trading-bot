"""
Skill 04 – NLP Sentiment Analysis (Advanced).

Uses a hybrid approach:
1. VADER for general English sentiment.
2. Custom Crypto Lexicon for slang (LFG, rekt, moon).
3. Telegram Web Scraper (t.me/s/...) for TON/HYPE insider data with Engagement Multiplier (Views).
4. CryptoPanic for BTC/ETH/SOL.
"""
from __future__ import annotations

import logging
import re
import random
from typing import List, Optional, Dict, Any

import aiohttp
from server.config import settings

logger = logging.getLogger(__name__)

# User-Agents to rotate to prevent simple bot blocking
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0"
]

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
    "moon": 1.5, "pump": 1.5, "bullish": 1.5, "ath": 1.0, "lfg": 1.0, "gem": 1.0, 
    "hodl": 0.5, "airdrop": 1.5, "partnership": 1.0, "listing": 1.5, "adopted": 1.0,
    "ton": 0.5, "hype": 0.5, "durov": 1.0, "tma": 1.0, "notcoin": 1.0, "dogs": 1.0, 
    "hyperliquid": 1.0, "tge": 1.5, "purr": 1.0, "hip-1": 1.0, "hip-2": 1.0, "ston.fi": 1.0,
    
    "dump": -1.5, "bearish": -1.5, "rekt": -1.5, "fud": -1.0, "scam": -2.0, "hack": -2.0, 
    "rug": -2.0, "delist": -2.0, "ban": -1.5, "sec": -1.0, "arrest": -2.0, "down": -1.0
}

def crypto_score_text(text: str) -> float:
    text_lower = text.lower()
    score = 0.0
    for word, val in CRYPTO_LEXICON.items():
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            score += val
    return score

def parse_views(views_str: str) -> float:
    """Parse '1.5K', '2M' into numbers for multiplier."""
    views_str = views_str.upper().strip()
    try:
        if 'K' in views_str:
            return float(views_str.replace('K', '')) * 1000
        elif 'M' in views_str:
            return float(views_str.replace('M', '')) * 1000000
        return float(views_str)
    except Exception:
        return 1.0

# ── Scoring ─────────────────────────────────────────────────────────────

def score_texts(items: List[Dict[str, Any]]) -> float:
    """Return average sentiment applying Engagement Multiplier."""
    if not items:
        return 0.0

    analyzer = _get_vader()
    compounds: list[float] = []
    
    import math
    for item in items:
        text = item.get("text", "")
        views = item.get("views", 1.0)
        
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
        
        # Engagement Multiplier (logarithmic scale of views)
        # 1 view -> log10(10) = 1x
        # 10k views -> log10(10000) = 4x multiplier
        multiplier = math.log10(max(10, views))
        
        score = score * multiplier
        
        # Clamp between -5 and 5 due to multiplier expansion
        score = max(-5.0, min(5.0, score)) 
        compounds.append(score)

    if not compounds:
        return 0.0
    
    avg_score = sum(compounds) / len(compounds)
    # Re-normalize back to [-1, 1] range for the engine
    return max(-1.0, min(1.0, avg_score / 5.0))

def nlp_signal(sentiment_score: float, news_weight: float = 1.0) -> int:
    weighted = sentiment_score * news_weight
    if weighted > 0.25:
        return 1
    if weighted < -0.25:
        return -1
    return 0

# ── News aggregation ────────────────────────────────────────────────────

async def scrape_telegram_channel(channel: str, proxy: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scrapes public Telegram channels and extracts text + views engagement."""
    url = f"https://t.me/s/{channel}"
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    results = []
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            async with session.get(url, timeout=10, proxy=proxy) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    
                    # Split into individual message blocks
                    blocks = html.split('<div class="tgme_widget_message ')
                    for block in blocks[1:]:
                        text_match = re.search(r'<div class="tgme_widget_message_text js-message_text".*?>(.*?)</div>', block, re.DOTALL)
                        views_match = re.search(r'<span class="tgme_widget_message_views">(.*?)</span>', block, re.DOTALL)
                        
                        if text_match:
                            clean_text = re.sub(r'<[^>]+>', ' ', text_match.group(1)).strip()
                            views = 1.0
                            if views_match:
                                views = parse_views(views_match.group(1))
                            
                            results.append({"text": clean_text, "views": views})
    except Exception as e:
        logger.debug(f"Failed to scrape Telegram {channel}: {e}")
        
    return results[-15:] # Return last 15 posts

async def fetch_crypto_news(symbol: str = "BTCUSDT") -> List[Dict[str, Any]]:
    """Aggregate headlines based on the specific asset."""
    headlines: List[Dict[str, Any]] = []
    proxy = settings.PROXY_URL if settings.PROXY_URL else None

    # Custom sources per asset
    if symbol == "TONUSDT":
        headlines.extend(await scrape_telegram_channel("durov", proxy))
        headlines.extend(await scrape_telegram_channel("toncoin", proxy))
        headlines.extend(await scrape_telegram_channel("toncoin_rus", proxy))
        return headlines
        
    elif symbol == "HYPEUSDT":
        headlines.extend(await scrape_telegram_channel("HyperliquidX", proxy))
        headlines.extend(await scrape_telegram_channel("DeFiRaccoons", proxy))
        return headlines

    # Default CryptoPanic for BTC, ETH, SOL
    base_asset = symbol.replace("USDT", "")
    url = f"https://cryptopanic.com/api/free/v1/posts/?currencies={base_asset}&kind=news"
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            try:
                async with session.get(url, timeout=10, proxy=proxy) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        results = data.get("results", [])
                        for item in results[:20]:
                            title = item.get("title")
                            if title:
                                # Cryptopanic doesn't easily expose views in free API, assume baseline 1000
                                headlines.append({"text": title, "views": 1000.0})
            except Exception as exc:
                logger.debug("News source error (%s): %s", url, exc)
    except Exception as exc:
        logger.warning("News fetch session error: %s", exc)

    if not headlines:
        logger.info(f"No live headlines available for {symbol}. Defaulting to neutral sentiment.")

    return headlines
