from datetime import datetime, timezone

import pandas as pd
import pytest

from src.news.features.daily import build_daily_features
from src.news.labeling.market import label_news
from src.news.processing.dedup import deduplicate
from src.news.processing.normalizer import normalize_item
from src.news.processing.normalizer import parse_date


def config():
    return {
        "labeling": {
            "direction_threshold_pct": 0.3,
            "impact_thresholds_pct": {"low": 0.3, "medium": 0.7, "high": 1.5, "very_high": 2.5},
        }
    }


def news_item(url="https://example.com/a"):
    return normalize_item(
        {
            "url": url,
            "title": "La Fed evalúa recortar tasas y el oro avanza",
            "summary": "El dólar pierde fuerza.",
            "published_at": "2026-06-15T10:00:00Z",
        },
        {
            "id": "test",
            "name": "Test",
            "url": "https://example.com",
            "expected_language": "es",
            "reliability_weight": 0.9,
        },
        datetime.now(timezone.utc),
        "requests",
    )


def test_deduplicate_by_url_and_content_hash():
    item = news_item()
    fresh, duplicates = deduplicate([item, news_item()], [])
    assert len(fresh) == 1
    assert duplicates == 1


def test_label_uses_next_sessions():
    item = news_item().model_dump(mode="json")
    market = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18"], utc=True),
            "precio_oro_soles_gramo": [400.0, 404.0, 402.0, 412.0],
        }
    )
    labels = label_news([item], market, config())
    assert labels[0]["return_1d"] == pytest.approx(0.01)
    assert labels[0]["direction_1d"] == "alcista"
    assert labels[0]["return_3d"] == pytest.approx(0.03)
    assert labels[0]["impact_class_3d"] == "muy_alto"


def test_daily_features():
    item = news_item().model_dump(mode="json")
    enriched = [
        {
            "news_id": item["news_id"],
            "enrichment_status": "completed",
            "classification": {
                "tipo_activo": "oro",
                "subtipo_evento": "Fed recorte de tasas",
                "variables_afectadas": ["oro", "USD"],
                "impacto_esperado": "alto",
                "confianza_gpt": 0.8,
                "sentido_oro": "alcista",
                "sentido_dolar": "bajista",
            },
        }
    ]
    rows = build_daily_features([item], enriched)
    assert rows[0]["news_count_gold"] == 1
    assert rows[0]["gold_bullish_score"] > 0


def test_spanish_date_is_not_misread_as_future_month():
    parsed = parse_date("Eva Cruz - 12 junio, 2026")
    assert parsed.date().isoformat() == "2026-06-12"


def test_iso_date_keeps_year_month_day_order():
    parsed = parse_date("2026-06-12T09:14:12-05:00")
    assert parsed.date().isoformat() == "2026-06-12"
