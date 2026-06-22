from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.macro.fred_config import macro_path


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)


class FredLocalStorage:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def raw_path(self, series_id: str) -> Path:
        return macro_path(self.config, "raw") / f"{series_id}.csv"

    def merge_raw(self, series_id: str, incoming: pd.DataFrame) -> pd.DataFrame:
        path = self.raw_path(series_id)
        frames = [incoming]
        if path.exists() and path.stat().st_size:
            frames.insert(0, pd.read_csv(path))
        combined = pd.concat(frames, ignore_index=True)
        combined["observation_date"] = pd.to_datetime(
            combined["observation_date"], errors="coerce"
        ).dt.date
        combined = (
            combined.dropna(subset=["observation_date"])
            .drop_duplicates(["series_id", "observation_date"], keep="last")
            .sort_values("observation_date")
        )
        combined.to_csv(path, index=False)
        return combined

    def read_raw(self, series_id: str) -> pd.DataFrame:
        path = self.raw_path(series_id)
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    def save_processed(self, filename: str, frame: pd.DataFrame) -> Path:
        path = macro_path(self.config, "processed") / filename
        frame.to_csv(path, index=False)
        return path

    def append_log(self, payload: dict[str, Any]) -> None:
        path = macro_path(self.config, "logs") / "fred_pipeline_runs.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=_json_default) + "\n")


class FredSupabaseStorage:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        from supabase import create_client

        self.client = create_client(url, key)

    def upsert_metadata(self, rows: list[dict[str, Any]]) -> int:
        return self._upsert_chunks("fred_series_metadata", rows, "series_id")

    def upsert_observations(self, rows: list[dict[str, Any]]) -> int:
        clean = [_clean_record(row) for row in rows]
        return self._upsert_chunks(
            "fred_observations", clean, "series_id,observation_date"
        )

    def upsert_features(self, rows: list[dict[str, Any]]) -> int:
        clean = [_clean_record(row) for row in rows]
        return self._upsert_chunks("daily_macro_features", clean, "feature_date")

    def _upsert_chunks(
        self, table: str, rows: list[dict[str, Any]], on_conflict: str, size: int = 1000
    ) -> int:
        for start in range(0, len(rows), size):
            self.client.table(table).upsert(
                rows[start : start + size], on_conflict=on_conflict
            ).execute()
        return len(rows)


def _clean_record(row: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in row.items():
        if pd.isna(value):
            clean[key] = None
        elif isinstance(value, (pd.Timestamp, date, datetime)):
            clean[key] = value.isoformat()
        elif hasattr(value, "item"):
            clean[key] = value.item()
        else:
            clean[key] = value
    return clean
