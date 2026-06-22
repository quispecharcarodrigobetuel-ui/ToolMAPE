from __future__ import annotations

import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


class FredClient:
    """Cliente pequeño para la API oficial FRED `series/observations`."""

    def __init__(self, config: dict[str, Any], session: requests.Session | None = None):
        self.config = config
        self.api_key = os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise RuntimeError("FRED_API_KEY no está configurada")
        self.session = session or requests.Session()

    def download_series(
        self,
        series_id: str,
        observation_start: str,
        observation_end: str | None = None,
    ) -> pd.DataFrame:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": observation_start,
        }
        if observation_end:
            params["observation_end"] = observation_end
        last_error: Exception | None = None
        retries = int(self.config.get("request_retries", 3))
        for attempt in range(retries):
            try:
                response = self.session.get(
                    FRED_OBSERVATIONS_URL,
                    params=params,
                    timeout=int(self.config.get("request_timeout_seconds", 30)),
                )
                response.raise_for_status()
                return self._to_frame(series_id, response.json().get("observations", []))
            except (requests.RequestException, ValueError, KeyError) as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(2**attempt)
        raise RuntimeError(f"FRED {series_id}: {last_error}")

    @staticmethod
    def _to_frame(series_id: str, observations: list[dict[str, Any]]) -> pd.DataFrame:
        columns = ["series_id", "observation_date", "value", "realtime_start", "realtime_end"]
        rows = [
            {
                "series_id": series_id,
                "observation_date": item.get("date"),
                "value": item.get("value"),
                "realtime_start": item.get("realtime_start"),
                "realtime_end": item.get("realtime_end"),
            }
            for item in observations
        ]
        frame = pd.DataFrame(rows, columns=columns)
        if frame.empty:
            return frame
        frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce").dt.date
        frame["realtime_start"] = pd.to_datetime(frame["realtime_start"], errors="coerce").dt.date
        frame["realtime_end"] = pd.to_datetime(frame["realtime_end"], errors="coerce").dt.date
        frame["value"] = pd.to_numeric(frame["value"].replace(".", pd.NA), errors="coerce")
        return frame.dropna(subset=["observation_date"]).sort_values("observation_date")

    def incremental_start(self, raw_path: Path) -> str:
        configured = pd.Timestamp(self.config["start_date"]).date()
        if not raw_path.exists() or raw_path.stat().st_size == 0:
            return configured.isoformat()
        existing = pd.read_csv(raw_path, usecols=["observation_date"])
        latest = pd.to_datetime(existing["observation_date"], errors="coerce").max()
        if pd.isna(latest):
            return configured.isoformat()
        overlap = timedelta(days=int(self.config.get("incremental_overlap_days", 400)))
        return max(configured, latest.date() - overlap).isoformat()

    def configured_end(self) -> str | None:
        value = self.config.get("end_date")
        return str(value) if value else date.today().isoformat()
