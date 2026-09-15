import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    # SPY options chain is structurally put-heavy (hedging demand); calibrated to historical mean ~1.4-1.6
    OI_BULL = 1.2
    OI_BEAR = 1.8
    VOL_BULL = 0.9
    VOL_BEAR = 1.1

    def __init__(self):
        self._vader = SentimentIntensityAnalyzer()

    def _vader_score(self, text: str) -> float:
        return self._vader.polarity_scores(text)["compound"]

    def compute_pcr(self, options: list[dict]) -> dict:
        put_oi = call_oi = put_vol = call_vol = 0
        for opt in options:
            ct = opt["details"]["contract_type"]
            oi = opt.get("open_interest", 0) or 0
            vol = (opt.get("day") or {}).get("volume", 0) or 0
            if ct == "put":
                put_oi += oi
                put_vol += vol
            else:
                call_oi += oi
                call_vol += vol

        oi_pcr = round(put_oi / call_oi, 3) if call_oi else 0
        vol_pcr = round(put_vol / call_vol, 3) if call_vol else 0

        oi_signal = "bullish" if oi_pcr < self.OI_BULL else "bearish" if oi_pcr > self.OI_BEAR else "neutral"
        vol_signal = "bullish" if vol_pcr < self.VOL_BULL else "bearish" if vol_pcr > self.VOL_BEAR else "neutral"

        return {
            "oi_pcr": oi_pcr,
            "oi_pcr_signal": oi_signal,
            "vol_pcr": vol_pcr,
            "vol_pcr_signal": vol_signal,
        }

    def score_reddit_posts(self, posts: list[dict]) -> float:
        if not posts:
            return 0.5
        scores = [self._vader_score(p.get("title", "") + " " + p.get("selftext", "")) for p in posts]
        positive = sum(1 for s in scores if s > 0.05)
        return round(positive / len(scores), 3)

    def score_headlines(self, articles: list[dict]) -> float:
        if not articles:
            return 0.5
        scores = [self._vader_score(a.get("title", "")) for a in articles]
        positive = sum(1 for s in scores if s > 0.05)
        return round(positive / len(scores), 3)

    async def fetch_reddit(self, reddit_client, subreddits: list[str] = None, limit: int = 25) -> list[dict]:
        subreddits = subreddits or ["wallstreetbets", "stocks"]
        posts = []
        try:
            for sub in subreddits:
                subreddit = await reddit_client.subreddit(sub)
                async for post in subreddit.hot(limit=limit):
                    posts.append({"title": post.title, "selftext": post.selftext[:500]})
        except Exception as e:
            logger.warning(f"Reddit fetch failed: {e}")
        return posts
