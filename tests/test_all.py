"""
Test suite for Finance Discord Bot.

Run with:
    pytest tests/ -v

Requirements:
    pip install pytest pytest-asyncio
"""
from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ─── Force in-memory DB for all tests ────────────────────────────────────────
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("DISCORD_TOKEN", "test-token")


# ══════════════════════════════════════════════════════════════════════════════
# TTLCache
# ══════════════════════════════════════════════════════════════════════════════


class TestTTLCache:
    def _make(self, ttl=60):
        from src.utils.cache import TTLCache
        return TTLCache(default_ttl=ttl)

    def test_set_and_get(self):
        c = self._make()
        c.set("k", "v")
        assert c.get("k") == "v"

    def test_miss_returns_none(self):
        c = self._make()
        assert c.get("missing") is None

    def test_expiry(self):
        c = self._make(ttl=1)
        c.set("x", 42)
        assert c.get("x") == 42
        time.sleep(1.1)
        assert c.get("x") is None

    def test_delete(self):
        c = self._make()
        c.set("k", "v")
        c.delete("k")
        assert c.get("k") is None

    def test_contains(self):
        c = self._make()
        c.set("k", "v")
        assert "k" in c
        assert "missing" not in c

    def test_keys_excludes_expired(self):
        c = self._make(ttl=1)
        c.set("alive", 1, ttl=60)
        c.set("dead", 2, ttl=1)
        time.sleep(1.1)
        assert "alive" in c.keys()
        assert "dead" not in c.keys()

    def test_evict_expired(self):
        c = self._make(ttl=1)
        c.set("a", 1)
        c.set("b", 2, ttl=60)
        time.sleep(1.1)
        removed = c.evict_expired()
        assert removed == 1
        assert len(c) == 1

    def test_override_with_custom_ttl(self):
        c = self._make(ttl=60)
        c.set("k", "v", ttl=1)
        time.sleep(1.1)
        assert c.get("k") is None


# ══════════════════════════════════════════════════════════════════════════════
# Formatter helpers
# ══════════════════════════════════════════════════════════════════════════════


class TestFormatter:
    def test_fmt_usd(self):
        from src.utils.formatter import fmt_usd
        assert fmt_usd(1234.5) == "$1,234.50"
        assert fmt_usd(0) == "$0.00"

    def test_fmt_pct_positive(self):
        from src.utils.formatter import fmt_pct
        assert fmt_pct(3.14) == "+3.14%"

    def test_fmt_pct_negative(self):
        from src.utils.formatter import fmt_pct
        assert fmt_pct(-1.5) == "-1.50%"

    def test_build_alert_list_embed_empty(self):
        import discord
        from src.utils.formatter import build_alert_list_embed
        embed = build_alert_list_embed([])
        assert isinstance(embed, discord.Embed)
        assert "No active alerts" in embed.description

    def test_build_alert_list_embed_price(self):
        import discord
        from src.utils.formatter import build_alert_list_embed
        alerts = [
            {
                "id": 1,
                "symbol": "AAPL",
                "alert_type": "price",
                "target_price": 200.0,
                "direction": "upper",
            }
        ]
        embed = build_alert_list_embed(alerts)
        assert isinstance(embed, discord.Embed)
        assert len(embed.fields) == 1
        assert "AAPL" in embed.fields[0].name

    def test_build_alert_list_embed_percent(self):
        import discord
        from src.utils.formatter import build_alert_list_embed
        alerts = [
            {
                "id": 2,
                "symbol": "TSLA",
                "alert_type": "percent",
                "pct_change": 5.0,
                "base_price": 150.0,
            }
        ]
        embed = build_alert_list_embed(alerts)
        assert "TSLA" in embed.fields[0].name

    def test_build_portfolio_embed_zero_holdings(self):
        import discord
        from src.utils.formatter import build_portfolio_embed
        embed = build_portfolio_embed([], {})
        assert isinstance(embed, discord.Embed)

    def test_build_portfolio_embed_with_data(self):
        import discord
        from src.utils.formatter import build_portfolio_embed

        holdings = [{"symbol": "AAPL", "quantity": 10, "avg_cost": 150.0}]
        prices = {"AAPL": {"price": 175.0, "change_pct": 2.5}}
        embed = build_portfolio_embed(holdings, prices)
        assert isinstance(embed, discord.Embed)
        fields_text = " ".join(f.value for f in embed.fields)
        assert "AAPL" in " ".join(f.name for f in embed.fields)
        assert "$1,750.00" in fields_text or "1,750" in fields_text

    def test_build_help_embed(self):
        import discord
        from src.utils.formatter import build_help_embed
        embed = build_help_embed()
        assert isinstance(embed, discord.Embed)
        assert len(embed.fields) >= 3  # Alerts, Portfolio, News


# ══════════════════════════════════════════════════════════════════════════════
# DB — models + queries (uses :memory: via env var)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestDatabase:
    """
    All DB tests share the same in-memory database initialised once per class.
    Because aiosqlite opens a new connection each time and :memory: DBs are
    per-connection, we patch DB_PATH to a temp file for isolation.
    """

    @pytest_asyncio.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        with patch.dict(os.environ, {"DB_PATH": db_file}):
            # Re-import so the module picks up the new DB_PATH
            import importlib
            import src.db.models as models_mod
            import src.db.queries as queries_mod
            importlib.reload(models_mod)
            importlib.reload(queries_mod)
            await models_mod.init_db()
            self.queries = queries_mod
            yield

    async def test_upsert_user_creates_and_returns_id(self):
        uid = await self.queries.upsert_user("111", "Alice")
        assert isinstance(uid, int)
        assert uid > 0

    async def test_upsert_user_idempotent(self):
        id1 = await self.queries.upsert_user("222", "Bob")
        id2 = await self.queries.upsert_user("222", "Bob Updated")
        assert id1 == id2

    async def test_create_price_alert(self):
        uid = await self.queries.upsert_user("333", "Carol")
        aid = await self.queries.create_price_alert(uid, "AAPL", 200.0, "upper")
        assert isinstance(aid, int)
        alerts = await self.queries.get_user_alerts(uid)
        assert len(alerts) == 1
        assert alerts[0]["symbol"] == "AAPL"
        assert alerts[0]["target_price"] == 200.0

    async def test_create_percent_alert(self):
        uid = await self.queries.upsert_user("444", "Dave")
        aid = await self.queries.create_percent_alert(uid, "TSLA", 5.0, 150.0)
        alerts = await self.queries.get_user_alerts(uid)
        assert alerts[0]["alert_type"] == "percent"
        assert alerts[0]["pct_change"] == 5.0

    async def test_deactivate_alert(self):
        uid = await self.queries.upsert_user("555", "Eve")
        aid = await self.queries.create_price_alert(uid, "GOOG", 100.0, "lower")
        result = await self.queries.deactivate_alert(aid, uid)
        assert result is True
        alerts = await self.queries.get_user_alerts(uid)
        assert len(alerts) == 0

    async def test_deactivate_alert_wrong_user(self):
        uid = await self.queries.upsert_user("666", "Frank")
        uid2 = await self.queries.upsert_user("777", "Grace")
        aid = await self.queries.create_price_alert(uid, "MSFT", 300.0, "upper")
        result = await self.queries.deactivate_alert(aid, uid2)
        assert result is False

    async def test_upsert_holding_new(self):
        uid = await self.queries.upsert_user("888", "Heidi")
        await self.queries.upsert_holding(uid, "NVDA", 5, 400.0)
        holdings = await self.queries.get_holdings(uid)
        assert len(holdings) == 1
        assert holdings[0]["symbol"] == "NVDA"
        assert holdings[0]["quantity"] == 5

    async def test_upsert_holding_weighted_avg(self):
        uid = await self.queries.upsert_user("999", "Ivan")
        await self.queries.upsert_holding(uid, "AAPL", 10, 100.0)
        await self.queries.upsert_holding(uid, "AAPL", 10, 200.0)
        holdings = await self.queries.get_holdings(uid)
        assert holdings[0]["quantity"] == 20
        assert holdings[0]["avg_cost"] == pytest.approx(150.0)

    async def test_remove_holding(self):
        uid = await self.queries.upsert_user("1010", "Judy")
        await self.queries.upsert_holding(uid, "META", 3, 300.0)
        removed = await self.queries.remove_holding(uid, "META")
        assert removed is True
        holdings = await self.queries.get_holdings(uid)
        assert len(holdings) == 0

    async def test_remove_holding_not_found(self):
        uid = await self.queries.upsert_user("1111", "Karl")
        removed = await self.queries.remove_holding(uid, "FAKE")
        assert removed is False

    async def test_openai_usage_zero_initially(self):
        uid = await self.queries.upsert_user("1212", "Liam")
        count = await self.queries.get_openai_usage(uid)
        assert count == 0

    async def test_openai_usage_increments(self):
        uid = await self.queries.upsert_user("1313", "Mia")
        await self.queries.increment_openai_usage(uid)
        await self.queries.increment_openai_usage(uid)
        count = await self.queries.get_openai_usage(uid)
        assert count == 2

    async def test_get_all_active_alerts_returns_discord_id(self):
        uid = await self.queries.upsert_user("1414", "Nina")
        await self.queries.create_price_alert(uid, "SPY", 500.0, "upper")
        all_alerts = await self.queries.get_all_active_alerts()
        assert any(a["discord_id"] == "1414" for a in all_alerts)

    async def test_get_all_holding_symbols(self):
        uid = await self.queries.upsert_user("1515", "Oscar")
        await self.queries.upsert_holding(uid, "BTC-USD", 1, 60000.0)
        await self.queries.upsert_holding(uid, "ETH-USD", 5, 3000.0)
        symbols = await self.queries.get_all_holding_symbols()
        assert "BTC-USD" in symbols
        assert "ETH-USD" in symbols


# ══════════════════════════════════════════════════════════════════════════════
# Price Service
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestPriceService:
    @pytest_asyncio.fixture(autouse=True)
    def clear_cache(self):
        from src.utils.cache import price_cache
        price_cache.clear()
        yield
        price_cache.clear()

    async def test_fetch_price_returns_cached(self):
        from src.utils.cache import price_cache
        from src.services.price import fetch_price

        price_cache.set("AAPL", {"symbol": "AAPL", "price": 170.0, "change_pct": 1.0})
        result = await fetch_price("AAPL")
        assert result["price"] == 170.0

    async def test_fetch_prices_batch_cache_hit(self):
        from src.utils.cache import price_cache
        from src.services.price import fetch_prices_batch

        price_cache.set("MSFT", {"symbol": "MSFT", "price": 400.0, "change_pct": 0.5})
        price_cache.set("GOOG", {"symbol": "GOOG", "price": 180.0, "change_pct": -0.3})
        results = await fetch_prices_batch(["MSFT", "GOOG"])
        assert "MSFT" in results
        assert "GOOG" in results

    async def test_fetch_prices_batch_empty(self):
        from src.services.price import fetch_prices_batch
        result = await fetch_prices_batch([])
        assert result == {}

    async def test_fetch_from_yfinance_retries_on_failure(self):
        from src.services.price import _fetch_from_yfinance

        call_count = 0

        def boom(symbols):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("simulated failure")

        with patch("src.services.price._sync_fetch", side_effect=boom):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await _fetch_from_yfinance(["FAKE"])

        assert result == {}
        assert call_count == 3  # MAX_RETRIES

    async def test_sync_fetch_populates_cache_fields(self):
        from src.services.price import _sync_fetch

        mock_ticker = MagicMock()
        mock_ticker.fast_info.last_price = 150.0
        mock_ticker.fast_info.previous_close = 148.0
        mock_tickers = MagicMock()
        mock_tickers.tickers = {"AAPL": mock_ticker}

        with patch("yfinance.Tickers", return_value=mock_tickers):
            result = _sync_fetch(["AAPL"])

        assert "AAPL" in result
        assert result["AAPL"]["price"] == 150.0
        assert result["AAPL"]["change"] == pytest.approx(2.0)
        assert result["AAPL"]["change_pct"] == pytest.approx(2.0 / 148.0 * 100, rel=1e-3)

    async def test_sync_fetch_skips_none_price(self):
        from src.services.price import _sync_fetch

        mock_ticker = MagicMock()
        mock_ticker.fast_info.last_price = None
        mock_ticker.fast_info.previous_close = 100.0
        mock_tickers = MagicMock()
        mock_tickers.tickers = {"BAD": mock_ticker}

        with patch("yfinance.Tickers", return_value=mock_tickers):
            result = _sync_fetch(["BAD"])

        assert "BAD" not in result


# ══════════════════════════════════════════════════════════════════════════════
# Sentiment Service
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSentimentService:
    async def test_analyze_sentiment_empty_headlines(self):
        from src.services.sentiment import analyze_sentiment
        result = await analyze_sentiment([])
        assert result is None

    async def test_analyze_sentiment_success(self):
        from src.services.sentiment import analyze_sentiment

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Bullish. Markets look strong."

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("src.services.sentiment._get_client", return_value=mock_client):
            result = await analyze_sentiment(["AAPL hits all-time high"])

        assert result == "Bullish. Markets look strong."

    async def test_analyze_sentiment_retries_and_returns_none(self):
        from src.services.sentiment import analyze_sentiment

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API down"))

        with patch("src.services.sentiment._get_client", return_value=mock_client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await analyze_sentiment(["headline"])

        assert result is None

    async def test_headlines_capped_at_max(self):
        """Verify we never send more than MAX_HEADLINES headlines to OpenAI."""
        from src.services import sentiment as svc

        captured = {}
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"

        async def mock_create(**kwargs):
            captured["messages"] = kwargs["messages"]
            return mock_response

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

        with patch("src.services.sentiment._get_client", return_value=mock_client):
            await svc.analyze_sentiment(["h"] * 50)

        user_msg = captured["messages"][1]["content"]
        bullet_count = user_msg.count("•")
        assert bullet_count <= svc.MAX_HEADLINES


# ══════════════════════════════════════════════════════════════════════════════
# News Service
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestNewsService:
    @pytest_asyncio.fixture(autouse=True)
    def clear_news_cache(self):
        from src.utils.cache import news_cache
        news_cache.clear()
        yield
        news_cache.clear()

    async def test_fetch_headlines_returns_cached(self):
        from src.utils.cache import news_cache
        from src.services.news import fetch_headlines

        news_cache.set("news:AAPL", ["Cached headline"])
        result = await fetch_headlines("AAPL")
        assert result == ["Cached headline"]

    async def test_fetch_headlines_falls_back_to_rss(self):
        from src.services.news import fetch_headlines

        mock_feed = MagicMock()
        mock_entry = MagicMock()
        mock_entry.title = "AAPL sets record"
        mock_feed.entries = [mock_entry]

        with patch.dict(os.environ, {"NEWSAPI_KEY": ""}):
            with patch("feedparser.parse", return_value=mock_feed):
                result = await fetch_headlines("AAPL")

        assert "AAPL sets record" in result

    async def test_fetch_headlines_multi_concurrent(self):
        from src.services.news import fetch_headlines_multi
        from src.utils.cache import news_cache

        news_cache.set("news:A", ["Headline A"])
        news_cache.set("news:B", ["Headline B"])
        result = await fetch_headlines_multi(["A", "B"])
        assert "Headline A" in result
        assert "Headline B" in result


# ══════════════════════════════════════════════════════════════════════════════
# Scheduler — alert polling logic
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSchedulerAlertLogic:
    async def test_price_alert_upper_triggers(self):
        """Alert fires when current_price >= target_price (upper)."""
        from src.services.scheduler import _poll_alerts

        alerts = [
            {
                "id": 1,
                "symbol": "AAPL",
                "alert_type": "price",
                "direction": "upper",
                "target_price": 200.0,
                "pct_change": None,
                "base_price": None,
                "user_id": 1,
                "discord_id": "123",
            }
        ]
        prices = {"AAPL": {"price": 201.0, "change_pct": 1.0}}
        bot = MagicMock()

        with patch("src.services.scheduler.queries.get_all_active_alerts", new_callable=AsyncMock, return_value=alerts):
            with patch("src.services.scheduler.fetch_prices_batch", new_callable=AsyncMock, return_value=prices):
                with patch("src.services.scheduler._dm_user", new_callable=AsyncMock) as mock_dm:
                    with patch("src.services.scheduler.queries.deactivate_alert_by_id", new_callable=AsyncMock) as mock_deact:
                        await _poll_alerts(bot)

        mock_dm.assert_awaited_once()
        mock_deact.assert_awaited_once_with(1)

    async def test_price_alert_upper_does_not_trigger_below(self):
        from src.services.scheduler import _poll_alerts

        alerts = [
            {
                "id": 2,
                "symbol": "AAPL",
                "alert_type": "price",
                "direction": "upper",
                "target_price": 200.0,
                "pct_change": None,
                "base_price": None,
                "user_id": 1,
                "discord_id": "123",
            }
        ]
        prices = {"AAPL": {"price": 199.0, "change_pct": -0.5}}
        bot = MagicMock()

        with patch("src.services.scheduler.queries.get_all_active_alerts", new_callable=AsyncMock, return_value=alerts):
            with patch("src.services.scheduler.fetch_prices_batch", new_callable=AsyncMock, return_value=prices):
                with patch("src.services.scheduler._dm_user", new_callable=AsyncMock) as mock_dm:
                    with patch("src.services.scheduler.queries.deactivate_alert_by_id", new_callable=AsyncMock):
                        await _poll_alerts(bot)

        mock_dm.assert_not_awaited()

    async def test_price_alert_lower_triggers(self):
        from src.services.scheduler import _poll_alerts

        alerts = [
            {
                "id": 3,
                "symbol": "TSLA",
                "alert_type": "price",
                "direction": "lower",
                "target_price": 100.0,
                "pct_change": None,
                "base_price": None,
                "user_id": 1,
                "discord_id": "456",
            }
        ]
        prices = {"TSLA": {"price": 99.0, "change_pct": -2.0}}
        bot = MagicMock()

        with patch("src.services.scheduler.queries.get_all_active_alerts", new_callable=AsyncMock, return_value=alerts):
            with patch("src.services.scheduler.fetch_prices_batch", new_callable=AsyncMock, return_value=prices):
                with patch("src.services.scheduler._dm_user", new_callable=AsyncMock) as mock_dm:
                    with patch("src.services.scheduler.queries.deactivate_alert_by_id", new_callable=AsyncMock):
                        await _poll_alerts(bot)

        mock_dm.assert_awaited_once()

    async def test_percent_alert_triggers(self):
        from src.services.scheduler import _poll_alerts

        alerts = [
            {
                "id": 4,
                "symbol": "NVDA",
                "alert_type": "percent",
                "direction": None,
                "target_price": None,
                "pct_change": 5.0,
                "base_price": 100.0,
                "user_id": 1,
                "discord_id": "789",
            }
        ]
        # 106 = +6% from 100 → should trigger (>= 5%)
        prices = {"NVDA": {"price": 106.0, "change_pct": 6.0}}
        bot = MagicMock()

        with patch("src.services.scheduler.queries.get_all_active_alerts", new_callable=AsyncMock, return_value=alerts):
            with patch("src.services.scheduler.fetch_prices_batch", new_callable=AsyncMock, return_value=prices):
                with patch("src.services.scheduler._dm_user", new_callable=AsyncMock) as mock_dm:
                    with patch("src.services.scheduler.queries.deactivate_alert_by_id", new_callable=AsyncMock):
                        await _poll_alerts(bot)

        mock_dm.assert_awaited_once()

    async def test_percent_alert_does_not_trigger_below_threshold(self):
        from src.services.scheduler import _poll_alerts

        alerts = [
            {
                "id": 5,
                "symbol": "NVDA",
                "alert_type": "percent",
                "direction": None,
                "target_price": None,
                "pct_change": 10.0,
                "base_price": 100.0,
                "user_id": 1,
                "discord_id": "789",
            }
        ]
        prices = {"NVDA": {"price": 103.0, "change_pct": 3.0}}  # only +3%
        bot = MagicMock()

        with patch("src.services.scheduler.queries.get_all_active_alerts", new_callable=AsyncMock, return_value=alerts):
            with patch("src.services.scheduler.fetch_prices_batch", new_callable=AsyncMock, return_value=prices):
                with patch("src.services.scheduler._dm_user", new_callable=AsyncMock) as mock_dm:
                    with patch("src.services.scheduler.queries.deactivate_alert_by_id", new_callable=AsyncMock):
                        await _poll_alerts(bot)

        mock_dm.assert_not_awaited()

    async def test_no_alerts_skips_price_fetch(self):
        from src.services.scheduler import _poll_alerts

        bot = MagicMock()
        with patch("src.services.scheduler.queries.get_all_active_alerts", new_callable=AsyncMock, return_value=[]):
            with patch("src.services.scheduler.fetch_prices_batch", new_callable=AsyncMock) as mock_fetch:
                await _poll_alerts(bot)

        mock_fetch.assert_not_awaited()
