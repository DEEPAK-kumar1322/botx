"""
Live Macro & Crypto News Sentiment Analyzer for BotX.

Fetches real-time headlines from verified industry news feeds (CoinTelegraph, CoinDesk),
scores market sentiment across macro themes (Fed rate hikes/cuts, CPI inflation, ETF flows, liquidations),
and produces actionable trading guidance for the Liquidity Sweep Strategy.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import requests
from loguru import logger
from pydantic import BaseModel, Field


class NewsHeadline(BaseModel):
    title: str
    source: str
    link: Optional[str] = None
    pub_date: Optional[str] = None
    sentiment: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    sentiment_score: float = 0.0  # -1.0 to +1.0
    impact_keywords: List[str] = Field(default_factory=list)


class MacroSentimentReport(BaseModel):
    macro_bias: str  # BULLISH, BEARISH, NEUTRAL
    sentiment_score: float  # -1.0 to +1.0
    high_impact_warning: bool
    key_theme: str
    top_headlines: List[NewsHeadline]
    trading_guidance: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NewsSentimentAnalyzer:
    """Parses live feeds and extracts macro sentiment to guide Liquidity Sweep execution."""

    RSS_FEEDS = [
        ("CoinTelegraph", "https://cointelegraph.com/rss"),
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ]

    BEARISH_KEYWORDS = {
        "inflation": 2.5,
        "cpi": 2.5,
        "rate hike": 3.0,
        "hike": 2.0,
        "hawkish": 2.0,
        "crash": 2.0,
        "dump": 2.0,
        "plunge": 2.0,
        "slump": 1.5,
        "dip": 1.0,
        "fall": 1.0,
        "liquidat": 2.0,
        "sec": 1.5,
        "lawsuit": 2.0,
        "ban": 2.5,
        "outflow": 2.0,
        "war": 2.0,
        "conflict": 1.5,
        "tighter": 1.5,
        "yield surge": 2.0,
        "bear": 1.0,
    }

    BULLISH_KEYWORDS = {
        "rate cut": 3.0,
        "cut": 1.5,
        "dovish": 2.0,
        "etf inflow": 3.0,
        "inflow": 2.0,
        "approval": 2.5,
        "approve": 2.0,
        "rally": 2.0,
        "surge": 2.0,
        "pump": 1.5,
        "breakout": 2.0,
        "adoption": 1.5,
        "bull": 1.0,
        "record high": 2.5,
        "all-time high": 3.0,
        "accumulat": 1.5,
        "partner": 1.0,
        "reserve": 1.0,
    }

    def __init__(self, timeout: int = 6):
        self.timeout = timeout
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BotX-News/1.0"}

    def fetch_headlines(self, limit: int = 15) -> List[NewsHeadline]:
        """Fetch headlines from public RSS feeds and score sentiment."""
        headlines: List[NewsHeadline] = []

        for source_name, feed_url in self.RSS_FEEDS:
            try:
                resp = requests.get(feed_url, headers=self.headers, timeout=self.timeout)
                if resp.status_code != 200:
                    continue

                root = ET.fromstring(resp.content)
                items = root.findall(".//item")
                for item in items[:10]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    date_elem = item.find("pubDate")

                    title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                    link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                    pub_date = date_elem.text.strip() if date_elem is not None and date_elem.text else ""

                    if not title:
                        continue

                    # Score headline
                    title_lower = title.lower()
                    bear_score = 0.0
                    bull_score = 0.0
                    matched_kw = []

                    for kw, weight in self.BEARISH_KEYWORDS.items():
                        if kw in title_lower:
                            bear_score += weight
                            matched_kw.append(f"-{kw}")

                    for kw, weight in self.BULLISH_KEYWORDS.items():
                        if kw in title_lower:
                            bull_score += weight
                            matched_kw.append(f"+{kw}")

                    net_score = bull_score - bear_score
                    if net_score > 0.5:
                        sent = "BULLISH"
                        norm_score = min(1.0, net_score / 4.0)
                    elif net_score < -0.5:
                        sent = "BEARISH"
                        norm_score = max(-1.0, net_score / 4.0)
                    else:
                        sent = "NEUTRAL"
                        norm_score = 0.0

                    headlines.append(NewsHeadline(
                        title=title,
                        source=source_name,
                        link=link,
                        pub_date=pub_date,
                        sentiment=sent,
                        sentiment_score=norm_score,
                        impact_keywords=matched_kw
                    ))

            except Exception as e:
                logger.warning(f"Failed to fetch news from {source_name}: {e}")

        return headlines[:limit]

    def analyze(self) -> MacroSentimentReport:
        """Analyze current news environment and produce actionable trading recommendations."""
        headlines = self.fetch_headlines(limit=20)

        if not headlines:
            return MacroSentimentReport(
                macro_bias="NEUTRAL",
                sentiment_score=0.0,
                high_impact_warning=False,
                key_theme="No active breaking headlines detected.",
                top_headlines=[],
                trading_guidance="Standard Liquidity Sweep rules apply. Await 1H HTF trend alignment."
            )

        total_score = sum(h.sentiment_score for h in headlines)
        avg_score = total_score / len(headlines) if headlines else 0.0

        # High impact flags
        high_impact = any(
            any(k in h.title.lower() for k in ["cpi", "inflation", "rate hike", "fed", "fomc", "sec", "liquidation"])
            for h in headlines
        )

        if avg_score <= -0.10:
            bias = "BEARISH"
            theme = "Macro Hawkish Fears & Liquidation Pressure (Sticky Inflation / Fed Tightening Risks)"
            guidance = (
                "FAVOR RESISTANCE SWEEPS (SHORTS): When macro headlines are bearish, breakout buyers get trapped easily. "
                "Look for Resistance (BSL) sweeps with Bearish Pin Bars or Pause Candle breakdowns. "
                "DO NOT dip-buy early; only take Longs if a massive Support (SSL) wash-out occurs with an extreme rejection wick."
            )
        elif avg_score >= 0.10:
            bias = "BULLISH"
            theme = "Risk-On Momentum & Institutional Inflows"
            guidance = (
                "FAVOR SUPPORT SWEEPS (LONGS): Dips into key Support (SSL) are being absorbed quickly by smart money. "
                "Look for Sell-Side liquidity stop-hunts followed by Bullish Pin Bars or Pause Candle High breaks. "
                "Avoid shorting high momentum breakout candles without a confirmed 15m closed rejection."
            )
        else:
            bias = "NEUTRAL"
            theme = "Choppy / Two-Sided Market (Consolidation Ahead of Next Catalyst)"
            guidance = (
                "TRADE BOTH SIDES AT RANGE EXTREMES: Market is balancing between Support and Resistance. "
                "Only trade strictly at the outer edges (Sweep of Swing Highs for Shorts, Sweep of Swing Lows for Longs). "
                "Avoid mid-range chop."
            )

        return MacroSentimentReport(
            macro_bias=bias,
            sentiment_score=round(avg_score, 2),
            high_impact_warning=high_impact,
            key_theme=theme,
            top_headlines=headlines[:8],
            trading_guidance=guidance,
        )
