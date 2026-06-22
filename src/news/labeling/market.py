from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.news.models import MarketLabel


def load_market_prices(config: dict[str, Any]) -> pd.DataFrame:
    pipeline = config["pipeline"]
    path = Path(config["root"]) / pipeline["market_prices_path"]
    if path.exists():
        frame = pd.read_csv(path)
    elif pipeline.get("download_market_if_missing"):
        frame = _download_market(pipeline.get("market_start_date", "2020-01-01"))
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    else:
        raise FileNotFoundError(
            f"No existe {path}. Proporciona date + precio_oro_soles_gramo, o activa download_market_if_missing."
        )
    return prepare_market_frame(frame)


def _download_market(start: str) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Instala yfinance para descargar precios") from exc
    data = yf.download(["GC=F", "PEN=X"], start=start, auto_adjust=False, progress=False)
    close = data["Close"]
    result = pd.DataFrame(
        {
            "date": close.index,
            "precio_oro_usd_oz": close["GC=F"],
            "tipo_cambio_usd_pen": close["PEN=X"],
        }
    ).dropna()
    result["precio_oro_soles_gramo"] = (
        result["precio_oro_usd_oz"] / 31.1035 * result["tipo_cambio_usd_pen"]
    )
    return result.reset_index(drop=True)


def prepare_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    aliases = {"Date": "date", "fecha": "date", "target": "precio_oro_soles_gramo"}
    frame = frame.rename(columns=aliases).copy()
    if "precio_oro_soles_gramo" not in frame:
        required = {"precio_oro_usd_oz", "tipo_cambio_usd_pen"}
        if not required.issubset(frame.columns):
            raise ValueError("El CSV necesita precio_oro_soles_gramo o precio_oro_usd_oz + tipo_cambio_usd_pen")
        frame["precio_oro_soles_gramo"] = (
            frame["precio_oro_usd_oz"] / 31.1035 * frame["tipo_cambio_usd_pen"]
        )
    frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.normalize()
    return frame.sort_values("date").dropna(subset=["precio_oro_soles_gramo"]).reset_index(drop=True)


def _classes(value: float, config: dict[str, Any]) -> tuple[str, str]:
    pct = value * 100
    direction_threshold = float(config["labeling"]["direction_threshold_pct"])
    direction = "alcista" if pct > direction_threshold else "bajista" if pct < -direction_threshold else "neutral"
    magnitude = abs(pct)
    limits = config["labeling"]["impact_thresholds_pct"]
    if magnitude < float(limits["low"]):
        impact = "nulo"
    elif magnitude < float(limits["medium"]):
        impact = "bajo"
    elif magnitude < float(limits["high"]):
        impact = "medio"
    elif magnitude < float(limits["very_high"]):
        impact = "alto"
    else:
        impact = "muy_alto"
    return direction, impact


def label_news(news_rows: list[dict[str, Any]], market: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []
    dates = market["date"]
    for row in news_rows:
        published = row.get("published_at")
        if not published:
            continue
        event_date = pd.Timestamp(published)
        event_date = event_date.tz_convert("UTC").normalize() if event_date.tzinfo else event_date.tz_localize("UTC").normalize()
        candidates = market.index[dates >= event_date]
        if candidates.empty:
            continue
        index = int(candidates[0])
        reference = float(market.loc[index, "precio_oro_soles_gramo"])
        payload: dict[str, Any] = {
            "news_id": row["news_id"],
            "reference_date": market.loc[index, "date"].date().isoformat(),
            "reference_price": reference,
            "labeled_at": datetime.now(timezone.utc),
        }
        for horizon in (1, 3):
            target_index = index + horizon
            if target_index >= len(market):
                continue
            price = float(market.loc[target_index, "precio_oro_soles_gramo"])
            market_return = price / reference - 1
            direction, impact = _classes(market_return, config)
            payload.update(
                {
                    f"price_{horizon}d": price,
                    f"return_{horizon}d": market_return,
                    f"direction_{horizon}d": direction,
                    f"impact_class_{horizon}d": impact,
                }
            )
        labels.append(MarketLabel.model_validate(payload).model_dump(mode="json"))
    return labels
