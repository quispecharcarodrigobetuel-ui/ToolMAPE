from __future__ import annotations

from collections import defaultdict
from typing import Any


IMPACT_SCORE = {"nulo": 0, "bajo": 1, "medio": 2, "alto": 3, "muy_alto": 4}


def _contains(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def build_daily_features(news_rows: list[dict[str, Any]], enriched_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    news_by_id = {row["news_id"]: row for row in news_rows}
    grouped: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for enriched in enriched_rows:
        if enriched.get("enrichment_status") != "completed" or not enriched.get("classification"):
            continue
        news = news_by_id.get(enriched["news_id"])
        if not news:
            continue
        timestamp = news.get("published_at") or news.get("scraped_at")
        grouped[timestamp[:10]].append((news, enriched["classification"]))

    output: list[dict[str, Any]] = []
    for feature_date, records in sorted(grouped.items()):
        row: dict[str, Any] = {
            "feature_date": feature_date,
            "news_count_total": len(records),
            "news_count_gold": 0,
            "news_count_dollar": 0,
            "news_count_fed": 0,
            "news_count_geopolitics": 0,
            "news_count_mining_peru": 0,
            "gold_bullish_score": 0.0,
            "gold_bearish_score": 0.0,
            "dollar_bullish_score": 0.0,
            "dollar_bearish_score": 0.0,
            "fed_hawkish_score": 0.0,
            "fed_dovish_score": 0.0,
            "geopolitical_risk_score": 0.0,
            "avg_impact_expected": 0.0,
            "max_impact_expected": 0.0,
            "avg_confidence_gpt": 0.0,
            "news_conflict_score": 0.0,
        }
        impact_values: list[float] = []
        confidence_values: list[float] = []
        gold_signs: list[int] = []
        for news, cls in records:
            text = " ".join(
                [
                    news.get("title", ""),
                    news.get("summary") or "",
                    cls.get("tipo_activo", ""),
                    cls.get("subtipo_evento", ""),
                    " ".join(cls.get("variables_afectadas", [])),
                ]
            ).lower()
            weight = float(news.get("reliability_weight", 1)) * float(cls["confianza_gpt"])
            impact = float(IMPACT_SCORE.get(cls["impacto_esperado"], 0))
            if _contains(text, ("oro", "gold", "bullion")):
                row["news_count_gold"] += 1
            if _contains(text, ("dólar", "dolar", "dollar", "usd")):
                row["news_count_dollar"] += 1
            if _contains(text, ("fed", "reserva federal", "fomc")):
                row["news_count_fed"] += 1
            if _contains(text, ("geopol", "guerra", "conflicto", "sancion", "tensión")):
                row["news_count_geopolitics"] += 1
                row["geopolitical_risk_score"] += weight * impact
            if _contains(text, ("minería", "mineria", "mining")) and _contains(text, ("perú", "peru")):
                row["news_count_mining_peru"] += 1
            if cls["sentido_oro"] == "alcista":
                row["gold_bullish_score"] += weight * impact
                gold_signs.append(1)
            elif cls["sentido_oro"] == "bajista":
                row["gold_bearish_score"] += weight * impact
                gold_signs.append(-1)
            if cls["sentido_dolar"] == "alcista":
                row["dollar_bullish_score"] += weight * impact
            elif cls["sentido_dolar"] == "bajista":
                row["dollar_bearish_score"] += weight * impact
            if _contains(text, ("hawkish", "tasas altas", "subida de tasas")):
                row["fed_hawkish_score"] += weight * impact
            if _contains(text, ("dovish", "recorte de tasas", "bajada de tasas")):
                row["fed_dovish_score"] += weight * impact
            impact_values.append(impact)
            confidence_values.append(float(cls["confianza_gpt"]))
        row["avg_impact_expected"] = sum(impact_values) / len(impact_values)
        row["max_impact_expected"] = max(impact_values)
        row["avg_confidence_gpt"] = sum(confidence_values) / len(confidence_values)
        if gold_signs:
            bullish = gold_signs.count(1)
            bearish = gold_signs.count(-1)
            row["news_conflict_score"] = 2 * min(bullish, bearish) / len(gold_signs)
        output.append(row)
    return output
