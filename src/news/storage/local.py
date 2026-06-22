from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.news.config import resolve_path
from src.news.utils.io import merge_by_key, read_jsonl, write_jsonl


class LocalStorage:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def latest_path(self, area: str) -> Path:
        return resolve_path(self.config, area) / "latest.jsonl"

    def read(self, area: str) -> list[dict[str, Any]]:
        return read_jsonl(self.latest_path(area))

    def save_run(self, area: str, run_id: str, rows: list[dict[str, Any]]) -> Path:
        path = resolve_path(self.config, area) / f"{run_id}.jsonl"
        write_jsonl(path, rows)
        return path

    def merge_latest(self, area: str, rows: list[dict[str, Any]], key: str) -> Path:
        path = self.latest_path(area)
        merged = merge_by_key(read_jsonl(path), rows, key)
        write_jsonl(path, merged)
        return path

    def save_features(self, rows: list[dict[str, Any]]) -> Path:
        directory = resolve_path(self.config, "features")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "daily_news_features.csv"
        if not rows:
            return path
        frame = pd.DataFrame(rows)
        # Es un snapshot derivado de todo `processed + enriched`, no un flujo
        # incremental. Sobrescribir elimina fechas obsoletas tras corregir metadatos.
        frame = frame.drop_duplicates("feature_date", keep="last").sort_values("feature_date")
        frame.to_csv(path, index=False)
        write_jsonl(directory / "latest.jsonl", frame.to_dict(orient="records"))
        return path
