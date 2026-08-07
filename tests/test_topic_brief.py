from __future__ import annotations

from tests.test_offline_signals import load_script


def test_find_news_prefers_prod_when_dev_empty(monkeypatch):
    module = load_script("topic-brief.py")
    calls: list[tuple[str, dict, str]] = []

    def fake_fetch(tool, args, tier="dev", api_key=None, endpoint="/mcp"):
        calls.append((tool, args, tier))
        if tool == "find" and args.get("type") == "news":
            if tier == "dev":
                return {"hits": [], "query": args["query"]}
            return {
                "hits": [
                    {
                        "id": "87c4973c-a3da-4416-9f20-666c256bd66a",
                        "name": "Washington football confident in added depth",
                        "source": "usa-today",
                        "published_date": "2026-08-07T12:00:35Z",
                        "type": "news",
                        "url": "https://example.com/article",
                    }
                ]
            }
        raise AssertionError(f"unexpected fetch {tool} {args} {tier}")

    monkeypatch.setattr(module, "fetch", fake_fetch)
    rows, warnings = module.find_news("washington football", "dev", None, 5)
    assert len(rows) == 1
    assert rows[0]["id"] == "87c4973c-a3da-4416-9f20-666c256bd66a"
    assert any("prod" in w for w in warnings)
    assert ("find", {"query": "washington football", "type": "news"}, "prod") in calls


def test_candidate_market_limit_is_3x_with_floor():
    module = load_script("topic-brief.py")
    assert module.candidate_market_limit(5) == 15
    assert module.candidate_market_limit(8) == 24
    assert module.candidate_market_limit(1) == 15


def test_rank_markets_prefers_chartable_then_liquid():
    module = load_script("topic-brief.py")
    ranked = module.rank_markets(
        [
            {
                "id": "thin",
                "name": "Thin",
                "ok": True,
                "chartable": False,
                "quote_source": "find_probability",
                "liquidity": 0,
                "mid": 0.5,
            },
            {
                "id": "liquid",
                "name": "Liquid",
                "ok": True,
                "chartable": False,
                "quote_source": "find_probability",
                "liquidity": 1000,
                "mid": 0.4,
            },
            {
                "id": "series",
                "name": "Series",
                "ok": True,
                "chartable": True,
                "quote_source": "price",
                "liquidity": 10,
                "mid": 0.6,
                "point_count": 48,
            },
        ]
    )
    assert [row["id"] for row in ranked] == ["series", "liquid", "thin"]


def test_run_brief_overfetches_ranks_and_charts_only_chartable(monkeypatch, tmp_path):
    module = load_script("topic-brief.py")
    price_ids: list[str] = []

    def fake_fetch(tool, args, tier="dev", api_key=None, endpoint="/mcp"):
        if tool == "find" and args.get("type") == "news":
            return {
                "hits": [
                    {
                        "id": "n1",
                        "name": "Headline one",
                        "source": "wire",
                        "published_date": "2026-08-07T12:00:00Z",
                    }
                ]
            }
        if tool == "find" and args.get("type") == "market":
            return {
                "hits": [
                    {
                        "id": "kalshi:THIN",
                        "name": "Thin market",
                        "probability": 50.0,
                        "type": "market",
                    },
                    {
                        "id": "kalshi:LIQUID",
                        "name": "Liquid market",
                        "probability": 40.0,
                        "volume_24h": 500,
                        "type": "market",
                    },
                    {
                        "id": "kalshi:SERIES",
                        "name": "Series market",
                        "probability": 60.0,
                        "volume_24h": 50,
                        "type": "market",
                    },
                ]
            }
        if tool == "price":
            price_ids.append(args["id"])
            if args["id"] == "kalshi:SERIES" and args.get("raw"):
                return {
                    "points": [
                        {"timestamp": "2026-08-06T12:00:00Z", "price": 0.55},
                        {"timestamp": "2026-08-06T13:00:00Z", "price": 0.56},
                    ]
                }
            return {"count": 0, "points": [], "note": "no price points"}
        raise AssertionError(f"unexpected {tool} {args}")

    def fake_build_charts(market_ids, timeframe, tier, api_key, output_dir, png):
        return [{"id": mid, "ok": True, "csv": str(output_dir / f"{mid}.csv"), "points": 2} for mid in market_ids]

    monkeypatch.setattr(module, "fetch", fake_fetch)
    monkeypatch.setattr(module, "build_charts", fake_build_charts)

    result = module.run_brief(
        "trump",
        tier="dev",
        api_key=None,
        news_limit=5,
        market_limit=2,
        timeframe="7d",
        chart=True,
        png=True,
        output_dir=tmp_path,
    )

    assert result["ok"] is True
    assert [m["id"] for m in result["markets"]] == ["kalshi:SERIES", "kalshi:LIQUID"]
    assert result["markets"][0]["chartable"] is True
    assert result["markets"][1]["chartable"] is False
    assert result["charts"] == [
        {"id": "kalshi:SERIES", "ok": True, "csv": str(tmp_path / "kalshi:SERIES.csv"), "points": 2}
    ]
    assert "kalshi:THIN" not in [m["id"] for m in result["markets"]]


def test_price_falls_back_to_find_probability_when_candles_empty(monkeypatch):
    module = load_script("topic-brief.py")

    def fake_fetch(tool, args, tier="dev", api_key=None, endpoint="/mcp"):
        if tool == "price":
            return {
                "count": 0,
                "id": args["id"],
                "note": "no price points in the requested window",
                "points": [],
            }
        raise AssertionError(f"unexpected {tool}")

    monkeypatch.setattr(module, "fetch", fake_fetch)
    quote = module.price_market("kalshi:UW-8", "7d", "dev", None, probability=56.5)
    assert quote["ok"] is True
    assert quote["mid"] == 0.565
    assert quote["quote_source"] == "find_probability"
    assert quote["chartable"] is False


def test_mid_from_price_reads_points_shape():
    module = load_script("topic-brief.py")
    quote = module._mid_from_price(
        {
            "points": [
                {"timestamp": "2026-08-06T12:00:00Z", "price": 0.40},
                {"timestamp": "2026-08-06T13:00:00Z", "price": 0.42},
            ]
        }
    )
    assert quote["mid"] == 0.42
    assert quote["as_of"] == "2026-08-06T13:00:00Z"
    assert quote["point_count"] == 2


def test_topic_brief_argv_builder():
    import sys
    from pathlib import Path

    hermes_root = Path(__file__).resolve().parents[1] / ".hermes" / "plugins"
    sys.path.insert(0, str(hermes_root))
    import adjacent.tools as tools  # type: ignore

    argv = tools._topic_brief_argv(
        {
            "topic": "washington football",
            "news_limit": 3,
            "chart": True,
            "png": True,
        }
    )
    assert argv[0].endswith("topic-brief.py")
    assert argv[1] == "washington football"
    assert "--news-limit" in argv
    assert "3" in argv
    assert "--chart" in argv
    assert "--png" in argv


def test_skill_requires_branded_chart_png():
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[1]
        / "plugins/adjacent/skills/adjacent-topic-brief/SKILL.md"
    ).read_text(encoding="utf-8")
    lowered = text.lower()
    assert "Mandatory chart rule" in text
    assert "at least one branded chart png" in lowered
    assert "charts: (none)" in lowered
    assert "never deliver" in lowered or "never ship" in lowered