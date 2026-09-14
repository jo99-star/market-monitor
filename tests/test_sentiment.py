import pytest
from backend.analysis.sentiment import SentimentAnalyzer


def make_option_snap(contract_type, oi, volume):
    return {
        "details": {"contract_type": contract_type},
        "open_interest": oi,
        "day": {"volume": volume},
    }


def test_oi_pcr_bearish_signal():
    analyzer = SentimentAnalyzer()
    options = [
        make_option_snap("put", 15000, 500),
        make_option_snap("call", 10000, 800),
    ]
    result = analyzer.compute_pcr(options)
    assert result["oi_pcr"] == pytest.approx(1.5, rel=0.01)
    assert result["oi_pcr_signal"] == "bearish"


def test_volume_pcr_bullish_signal():
    analyzer = SentimentAnalyzer()
    options = [
        make_option_snap("put", 10000, 400),
        make_option_snap("call", 8000, 600),
    ]
    result = analyzer.compute_pcr(options)
    assert result["vol_pcr"] == pytest.approx(400 / 600, rel=0.01)
    assert result["vol_pcr_signal"] == "bullish"


def test_vader_scores_positive_text():
    analyzer = SentimentAnalyzer()
    score = analyzer._vader_score("Amazing gains today! Market is fantastic and wonderful!")
    assert score > 0


def test_vader_scores_negative_text():
    analyzer = SentimentAnalyzer()
    score = analyzer._vader_score("Terrible crash, awful losses, horrible market disaster")
    assert score < 0


def test_score_reddit_posts_empty():
    analyzer = SentimentAnalyzer()
    assert analyzer.score_reddit_posts([]) == 0.5


def test_score_headlines():
    analyzer = SentimentAnalyzer()
    articles = [{"title": "Market surges to record high"}, {"title": "Stocks crash amid panic"}]
    score = analyzer.score_headlines(articles)
    assert 0.0 <= score <= 1.0
