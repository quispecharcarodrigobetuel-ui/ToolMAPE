from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.macro.fred_config import macro_path


def _read_dated(path: Path, aliases: tuple[str, ...]) -> pd.DataFrame | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    frame = pd.read_csv(path)
    date_column = next((column for column in aliases if column in frame.columns), None)
    if date_column is None:
        raise ValueError(f"{path} no contiene una columna de fecha reconocida")
    frame = frame.rename(columns={date_column: "date"})
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    return frame.dropna(subset=["date"]).drop_duplicates("date", keep="last")


def build_final_feature_dataset(config: dict[str, Any]) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    market = _read_dated(
        macro_path(config, "market_features"), ("date", "Date", "fecha", "feature_date")
    )
    macro = _read_dated(
        macro_path(config, "processed") / "daily_macro_features.csv",
        ("feature_date", "date"),
    )
    news = _read_dated(
        macro_path(config, "news_features"), ("feature_date", "date")
    )
    if macro is None:
        raise FileNotFoundError("No existe daily_macro_features.csv")

    base = market if market is not None else macro[["date"]].copy()
    if market is None:
        warnings.append("No se encontró el dataset de mercado; el resultado usa el calendario macro.")
    if macro is not base:
        base = base.merge(macro, on="date", how="left")
    if news is not None:
        base = base.merge(news, on="date", how="left")
        news_columns = [column for column in news.columns if column != "date"]
        base[news_columns] = base[news_columns].fillna(0)
    else:
        warnings.append("No se encontró daily_news_features.csv.")
    base = base.sort_values("date")
    output = macro_path(config, "final_features")
    output.parent.mkdir(parents=True, exist_ok=True)
    base.to_csv(output, index=False)
    return base, warnings
